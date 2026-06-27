---
name: amaranth-resource
description: 아마란스 ERP(erp.doflab.com) 자원(회의실/차량) 예약 상태 조회 및 신규 예약 등록. playwright-cli 기반. "회의실 예약", "306호 잡아줘", "5/12 자원 비어있어?", "ax회의 예약", "회의실 가용 시간 확인" 등 자원 관련 요청 시 사용.
---

# 아마란스 ERP 자원 예약 (회의실 / 차량)

`@playwright/cli` 기반. `proc/lib/pwc_amaranth.py`의 자원 helper로 ERP 자원(회의실·차량) 상태 조회와 신규 예약을 수행한다.

## 도구 스택

- `@playwright/cli` (전역 `playwright-cli` 명령) — 사이트별 격리 세션, 영속 프로필
- `proc/lib/pwc.py` — 세션 wrapper (`S('amaranth')`)
- `proc/lib/pwc_amaranth.py` — Amaranth ERP helper

## 전제

1. `playwright-cli` 설치 — 한 번만: `npm install -g @playwright/cli@latest`.
2. **Amaranth 세션 부트스트랩** (첫 1회):
   ```bash
   playwright-cli -s=amaranth open https://erp.doflab.com/ --persistent --headed
   ```
   브라우저 창이 뜨면 회사코드 `doflab` → ID(`.env ERP_PERSONAL_ID`) → PW(`.env ERP_PERSONAL_PW`) 로그인 → 출퇴근 체크 popup **취소**.
3. 자원 모듈 URL: `https://erp.doflab.com/#/UK/UKA/UKA0000?specialLnb=Y&moduleCode=UK&menuCode=UKA&pageCode=UKA0000`
4. 일간(`일간`) 뷰가 디폴트. 주간/월간/목록도 가능하나 본 스킬은 일간 기준.
5. 동시성: 다른 `-s=` 세션(Teams, Salesforce)과 별개 브라우저라 충돌 없음.

## API 한계 — 직접 fetch는 차단

요청 헤더가 SPA 번들 내부 `wehago-sign` HMAC 서명으로 보호되며, 외부 fetch 호출 시 `601 허용된 쿠키 인증 URL이 아닙니다`로 거절됨.

따라서:
- **읽기**: SPA가 발사한 XHR을 `s.requests()` + `s.response_body()` 로 캡처
- **쓰기**: SPA의 `자원 예약` 다이얼로그 UI를 통해 수행

## 자원(resSeq) 매핑 (`RES_SEQ` dict)

| 자원 | resSeq |
|---|---|
| 대표실 | 44 |
| **302호** | **45** |
| **306호** | **63** |
| 601호(DDA) | 47 |
| 602호 | 48 |
| 197하1718 (스포티지 검정) | 50 |
| 225하1481 (스포티지 흰색) | 60 |
| 224허9910 (GV70) | 64 |

## API 엔드포인트 (POST, JSON)

| URL | 용도 |
|---|---|
| `/schres/rs121A05` | 일자×자원 예약 조회 |
| `/schres/rs121A06` | 예약 생성 |
| `/schres/rs121A45`, `/schres/rs121A46` | 일별 부가 요약 (보통 무시 가능) |

### rs121A05 request body 핵심

```json
{
  "companyInfo": {"compSeq":"1000","groupSeq":"gcmsAmaranth36229","deptSeq":"...","emailAddr":"...","emailDomain":"doflab.com"},
  "startDate":"20260512","endDate":"20260512",
  "statusType":["10","20"],
  "resList":[{"resSeq":"44"}, {"resSeq":"45"}, ...],
  "menuAuth":"USER","langCode":"kr"
}
```

응답 `resultData.resultList`의 항목 = 예약 한 건. `resStartDate/resEndDate`는 `YYYYMMDDhhmm` 12자리.

### rs121A06 request body 핵심 (생성)

```json
{
  "companyInfo":{...},
  "resSeq":"63",
  "reqText":"ax회의",
  "apprYn":"N", "alldayYn":"N",
  "startDate":"202605121200", "endDate":"202605121300",
  "descText":"",
  "resSubscriberList":[{"groupSeq":"...","compSeq":"1000","deptSeq":"...","empSeq":"..."}],
  "uidList":"", "repeatType":"10", "repeatEndDay":"", "langCode":"kr"
}
```

## 핵심 helper (`proc/lib/pwc_amaranth.py`)

| 이름 | 용도 |
|---|---|
| `RES_SEQ` | 한글이름 → resSeq 매핑 dict |
| `resource_bookings(s, start_yyyymmdd, end_yyyymmdd=None)` | 캡처된 rs121A05 응답에서 예약 목록 파싱 |

## 1. 상태 조회 (가용성 확인)

```bash
python3 -c "
import sys, time, json; sys.path.insert(0, 'proc/lib')
from pwc import S
from pwc_amaranth import resource_bookings, RES_SEQ, _click_by_text

s = S('amaranth')
s.goto('https://erp.doflab.com/#/UK/UKA/UKA0000?specialLnb=Y&moduleCode=UK&menuCode=UKA&pageCode=UKA0000')
time.sleep(2)

# 날짜 picker: js로 원하는 일자 셀 찾아 클릭
s.eval('''() => {
    const c = [...document.querySelectorAll(\"span, td\")].find(
        el => (el.textContent||\"\").trim() === \"12\" && el.getBoundingClientRect().width > 0
    );
    if (c) c.click();
}''')
time.sleep(2)

items = resource_bookings(s, '20260512') or []
print(f'5/12 예약 {len(items)}건')
for it in items:
    print(it['resName'], it['resStartDate'][8:12]+'~'+it['resEndDate'][8:12], it['reqText'], '/', it['empName'])
"
```

빈 자원 = 응답 resultList에 해당 resSeq가 없는 경우 (예약 0건 = free).

## 2. 신규 예약 등록

핵심 흐름: **`자원 예약` 버튼 클릭 → 다이얼로그 → 자원/일시/예약명 입력 → 확인.**

캘린더 빈 셀 드래그/클릭은 시간 스냅이 어긋나기 쉬우므로 다이얼로그 내 `일시` 행을 펼쳐 수동 설정 권장.

```bash
python3 -c "
import sys, time; sys.path.insert(0, 'proc/lib')
from pwc import S
from pwc_amaranth import _click_by_text

s = S('amaranth')
s.goto('https://erp.doflab.com/#/UK/UKA/UKA0000?specialLnb=Y&moduleCode=UK&menuCode=UKA&pageCode=UKA0000')
time.sleep(2)

# 1) '자원 예약' 버튼 클릭
_click_by_text(s, '자원 예약', tag='button')
time.sleep(2)

# 2) 시작/종료 시간은 다이얼로그 내 드롭다운에서 화살표키로 설정
#    예: 시작 ArrowUp 4회 → Enter, 종료 ArrowUp 6회 → Enter

# 3) 예약명 입력
s.eval('''() => {
    const inp = [...document.querySelectorAll(\"input\")].find(
        el => (el.placeholder||\"\").includes(\"예약명\")
    );
    if (inp) { inp.focus(); }
}''')
s.type('ax회의')

# 4) 확인 버튼 클릭
_click_by_text(s, '확인', tag='button')
time.sleep(3)
print('done')
"
```

### 시간 정확히 맞추기 — 화살표키

다이얼로그 내 시간 드롭다운은 **5분 단위 LI 리스트**. 클릭으로 옵션 선택 시 종종 빗나가므로 **화살표키 + Enter** 권장:

```python
# 시작 시간 드롭다운에서 12:20 → 12:00 (위로 4번)
s.eval("() => { const el = document.querySelector('.time-start input, .start-time input'); if(el) el.click(); }")
time.sleep(1)
for _ in range(4):
    s.press('ArrowUp')
    time.sleep(0.1)
s.press('Enter')
```

## 주의 / 함정

- **드래그로 시간 선택은 비추천** — 캘린더 셀 분할이 5분 단위인데 드래그가 정확히 시간에 맞지 않아 12:20~13:30 같은 어긋난 값이 잡힘.
- **다이얼로그 좌표는 viewport 변동에 민감** — 안전하게는 매 단계 `s.eval()`로 element를 찾아 클릭.
- **기존 예약 셀 클릭 시 `예약 조회`(읽기) 다이얼로그가 열림** — 빈 시간대를 클릭하거나 좌측 상단 `자원 예약` 버튼을 사용해야 등록 다이얼로그가 열림.
- **rs121A05 응답은 예약 0건인 자원은 누락** — resultList에 해당 resSeq가 안 보이면 그 자원은 비어 있음.
- **wehago-sign 직접 위조 불가** — 외부 fetch는 모두 401. 쓰기 작업은 반드시 SPA UI 통과.
- **로그인 풀린 상태** → `playwright-cli -s=amaranth open https://erp.doflab.com/ --persistent --headed` 로 재로그인.

## 참고

- 자원 분류: 회의실(상위) / 차량(상위) / 펜 태블릿 / TV / 마이크 / 화상장비 등 좌측 `자원필터` 사이드바에서 카테고리/속성 필터 가능.
- `사용자` 필드는 기본 본인. 타인 명의 예약은 본 스킬 범위 밖.
- 예약 수정/삭제는 본 스킬 미커버 — 예약 셀 클릭 시 열리는 `예약 조회` 다이얼로그에서 처리.
