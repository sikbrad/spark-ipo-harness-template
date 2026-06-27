---
name: salesforce-record
description: Salesforce Lightning(d7f000002bofzuay.lightning.force.com) 레코드 정보 가져오기 — Opportunity/Quote 헤더와 라인아이템(제품·수량·단가). "세일즈포스 주문", "Sales20413 정보", "Opportunity XXX 라인아이템", "견적 제품 목록", "SF에서 ~ 받아와" 등 SF 레코드 조회 요청 시 사용. playwright-cli 기반 네트워크 캡처 + Aura $Record 캐시 파싱 방식.
---

# Salesforce Lightning 레코드 추출

`@playwright/cli` 기반. Lightning이 fire하는 Aura RPC 응답을 `s.requests()` + `s.response_body()` 로 캡처해 Opportunity / Quote / OpportunityLineItem / Product2 등 모든 캐시된 레코드를 추출한다.

## 도구 스택
- `@playwright/cli` (전역 `playwright-cli` 명령) — 사이트별 격리 세션, 영속 프로필
- `proc/lib/pwc.py` — 세션 wrapper (`S('salesforce')`)
- `proc/lib/pwc_salesforce.py` — Salesforce Lightning helper

## 사전 조건

1. **Salesforce 세션 부트스트랩**(첫 1회):
   ```bash
   playwright-cli -s=salesforce open https://d7f000002bofzuay.lightning.force.com/ --persistent --headed
   ```
   브라우저 창이 뜨면 Salesforce 계정으로 로그인. **TOTP/MFA 화면이 뜨면 사용자가 직접 처리해야 함** — 자동화 불가. 이후 `--persistent` 디스크 프로필이 로그인 상태를 유지.
2. 로그인 폼이 보이면 `login(s)` 호출 — `.env`의 `SF_ACCOUNT_ID`, `SF_ACCOUNT_PW` 사용.
3. 진입 URL: 제품 정보가 풍부한 곳은 **Opportunity** (`/lightning/r/Opportunity/<id>/view`). Quote는 라인아이템에 `Product2` 풀세트가 들어있지 않을 수 있음.
4. 동시성: `-s=salesforce`는 `-s=teams` / `-s=amaranth`와 완전히 독립된 브라우저라 충돌 없음. 같은 `-s=salesforce` 세션은 직렬화 필요.

## 데이터 채집 메커니즘

Lightning Aura RPC 응답은 다음 위치에 모든 관련 레코드를 캐시한다:

```
context.globalValueProviders[type=$Record].values.records
  └─ <recordId>
       └─ <ObjectApiName>
            └─ record.fields.<fname> = {value, displayValue}
```

`fields.<ref>.value` 안에 nested record(예: OpportunityLineItem.fields.Product2.value)가 통째로 들어있어, **부모 레코드 한 번 fetch만으로 자식 Product2 ProductCode·Name까지 함께 받는다**.

핵심 호출은 `aura.RecordUi.getRecordUis` (헤더, ~400KB) + `RelatedListContainerDataProvider.getRecords` (라인아이템 + 제품, ~22KB) — 페이지 진입 시 자동 호출되며 직접 fetch는 cookie-bound auth로 차단.

**XSSI 접두 처리**: 모든 Aura 응답은 `while(1);` 로 시작하는 XSSI 가드가 있다. `pwc_salesforce` 내부에서 자동으로 strip 후 JSON 파싱.

## 핵심 helper (`proc/lib/pwc_salesforce.py`)

| 이름 | 용도 |
|---|---|
| `login(s, login_url, sf_id, sf_pw)` | 로그인 폼 자동 입력 + #Login 클릭. env 디폴트. MFA 미지원. |
| `search_url(instance, term)` | 글로벌 검색 결과 페이지 SPA URL 생성 (검색창 타이핑보다 안정적) |
| `aura_records(s, api_name=None)` | 모든 캡처된 /aura 응답에서 캐시된 레코드를 평탄화. `api_name='Product2'` 등으로 필터. nested 레코드도 별도 entry로 emit. |
| `get_record_uis(s, record_id=None)` | `getRecordUis` 응답에서 메인 레코드 dict 반환. 헤더(Opportunity, Quote, ...) 추출용. |
| `line_items(s, parent_id, parent_field='OpportunityId')` | OpportunityLineItem/QuoteLineItem + Product2를 합쳐 깔끔한 dict 리스트로 반환. `parent_field='QuoteId'`로 견적용. |

`line_items()` 반환 항목:
```python
{
  'id', 'apiName', 'name', 'quantity', 'unitPrice', 'description',
  'factory', 'currency', 'parentId',
  'product': {'id', 'name', 'code', 'currency'}  # None if Product2 not cached
}
```

## 캡처 타이밍 — 중요

`s.requests()`는 playwright-cli가 CDP를 통해 수집하는 네트워크 로그다. **`s.goto(url)`로 풀 리로드하면 이전 캡처가 초기화된다**. 안정적 패턴:

1. **풀 리로드는 한 번만**: `s.goto(opportunity_detail_url)` 로 직접 진입.
2. `_time.sleep(8~10)` — SPA가 Aura RPC를 완료할 때까지 대기.
3. SPA가 자체적으로 fire하는 `aura?...getRecordUis` / `...getRecords` 응답이 캡처됨.
4. 추가 데이터는 SPA-내 클릭(related list refresh, 다른 레코드로 이동)으로 트리거 — **이 클릭들은 pushState라 캡처를 죽이지 않음**.

미캡처 시 증상: `aura_records(s)` 가 빈 리스트 반환. 이때는 다른 Lightning 페이지(`/lightning/page/home`)로 `s.goto()` 후 다시 진입.

## 표준 호출 — Opportunity by Sales Number

```python
python3 -c "
import sys; sys.path.insert(0, 'proc/lib')
import time, re, json
from pwc import S
from pwc_salesforce import search_url, aura_records, get_record_uis, line_items, INSTANCE

s = S('salesforce')

# 1) 글로벌 검색 결과 페이지로 직접 진입 (검색창 타이핑보다 안정)
s.goto(search_url(INSTANCE, 'Sales20413'))
time.sleep(6)

# 2) 좌측 사이드바의 'Sales' 카테고리 클릭 (Opportunity로 좁힘)
s.eval('''() => {
  function walk(root, depth){
    if (depth>10) return null;
    const els = root.querySelectorAll ? Array.from(root.querySelectorAll('a,span')) : [];
    for (const el of els) {
      if ((el.innerText||'').trim() === 'Sales') {
        const r = el.getBoundingClientRect();
        if (r.width > 0 && r.x < 200) { el.click(); return true; }
      }
    }
    const all = root.querySelectorAll ? root.querySelectorAll('*') : [];
    for (const e of all) if (e.shadowRoot) walk(e.shadowRoot, depth+1);
    return null;
  }
  walk(document, 0);
}''')
time.sleep(4)

# 3) 결과 행의 Sales Name 링크 클릭 (SPA pushState — 캡처 유지)
s.eval('''() => {
  function walk(root, depth){
    if (depth>10) return null;
    const els = root.querySelectorAll ? Array.from(root.querySelectorAll('a')) : [];
    for (const el of els) {
      if ((el.href||'').includes('/lightning/r/') && el.getBoundingClientRect().width > 50) {
        el.click(); return true;
      }
    }
    const all = root.querySelectorAll ? root.querySelectorAll('*') : [];
    for (const e of all) if (e.shadowRoot) walk(e.shadowRoot, depth+1);
    return null;
  }
  walk(document, 0);
}''')
time.sleep(8)

# 4) 페이지 스크롤로 lazy-load 트리거 (related lists)
s.eval('() => window.scrollTo(0, 1500)'); time.sleep(2)
s.eval('() => window.scrollTo(0, 0)'); time.sleep(1)

# 5) URL에서 Opportunity ID 추출
tabs = s.tab_list()
url = next((t['url'] for t in tabs if t.get('current')), '')
opp_id = re.search(r'/r/Opportunity/(\w+)/', url).group(1)

ru = get_record_uis(s, opp_id)
header = ru[opp_id]['fields'] if ru else {}
items = line_items(s, opp_id)

print(json.dumps({
    'opportunity_id': opp_id,
    'name': header.get('Name', {}).get('value'),
    'salesNumber': header.get('Opportunity_ID__c', {}).get('value'),
    'amount': header.get('Amount', {}).get('value'),
    'stage': header.get('StageName', {}).get('value'),
    'lineItems': len(items),
}, ensure_ascii=False, indent=2))

for it in items:
    p = it['product'] or {}
    print(f\"  [{p.get('code','?'):<10}] qty={int(it['quantity'] or 0)} unit={int(it['unitPrice'] or 0):>8}  {p.get('name','?')}\")
"
```

## Quote 진입 (참고)

Quote 상세 페이지는 `aura.RecordUi.getRecordUis`로 헤더 + `RelatedListContainerDataProvider.getRecords`로 QuoteLineItem 받음. `line_items(s, quote_id, parent_field='QuoteId')` 사용.

단, Quote의 라인아이템은 `Product2` nested에 ProductCode가 누락될 수 있음 — 그럴 땐 syncedQuote의 Opportunity로 거슬러 올라가는 편이 안전.

## 헤더 필드 매핑 (이 org 실제 사용)

`Opportunity` 주요 커스텀 필드:

| API 필드 | UI 라벨 | 비고 |
|---|---|---|
| `Opportunity_ID__c` | Sales Number | 'Sales20413' 형식. **Sales_Number__c 아님** |
| `Name` | Sales Name | 자유 텍스트 (계정명 + 제품 요약 패턴) |
| `Account_tier__c` | Account tier | 'A - Shipping before payment...' |
| `Amount`, `Grand_Total__c` | 금액/총액 | 같은 값(KRW) |
| `Forwarder__c`, `ShippingFeeWho__c` | 배송사·부담 | '롯데택배', 'DOF 부담' |
| `Tracking_Information__c` | 송장번호 | |
| `Opportunity_Payment_Condition__c` | 결제조건 | '익월말 계좌이체' 등 |
| `Invoicing_email_address__c` | 세금계산서 메일 | |
| `Billing_Address__c`, `ShippingAddress__c` | 청구·배송지 | |
| `StageName` | 스테이지 | 'Release / Installation', 'Closed Won' 등 |

`OpportunityLineItem` 핵심: `Quantity`, `UnitPrice`, `Description`, `Factory__c`('DOF' 등), `Product2Id`, `Product2.Name`, `Product2.ProductCode`.

## 글로벌 검색의 함정

- 글로벌 검색 결과는 **Opportunity와 Quote 둘 다 매칭** — 'Sales20413'으로 검색하면 둘 다 나옴. 라인아이템이 풍부한 건 Opportunity 쪽이니, 좌측 사이드바에서 'Sales'(=Opportunity의 한글 라벨, 이 org 한정) 필터를 거는 것이 안전.
- 검색창에 직접 타이핑(`s.fill`)은 **이전 입력이 누적**되는 경우가 있음(Lightning input 동작) — `search_url()` 직접 진입 권장.
- 검색 결과 페이지의 결과 링크는 shadow DOM 안에 있음. 위 예제처럼 `walk(document, 0)` 재귀 + `el.shadowRoot` 탐색 필요.

## 참조

- Sales tab in this org's Lightning navbar = Opportunity (커스텀 라벨 한국어).
- Setup 페이지 (`https://d7f000002bofzuay.my.salesforce-setup.com/lightning/setup/SetupOneHome/home`) 에서 Object Manager로 필드 API 이름 확인 가능.
- 직접 REST/SOAP 호출은 cookie+CSRF 의존이라 추천하지 않음. SPA의 자체 호출 캡처가 가장 안정.
