---
name: amaranth-doc-recall
description: 아마란스 ERP(erp.doflab.com) 상신문서함의 진행중 결재 문서 회수 — `회수` 버튼 + 확인 다이얼로그 자동 처리. playwright-cli 기반. "상신 취소", "휴가 회수", "결재 회수해줘", "DOF-2605-XXXX 회수", "올린거 취소", "상신한 거 다시 가져와" 등 회수 요청 시 사용. 상신 자체는 `/amaranth-leave-request`, 결재함 조회는 `/amaranth-approval`.
---

# 아마란스 ERP 결재문서 회수

`@playwright/cli` 기반. `proc/lib/pwc_amaranth.py`의 `recall_doc()` helper로 본인이 상신한 진행중 문서를 회수해 결재 라인에서 제거한다.

## 도구 스택

- `@playwright/cli` (전역 `playwright-cli` 명령) — 사이트별 격리 세션, 영속 프로필
- `proc/lib/pwc.py` — 세션 wrapper (`S('amaranth')`)
- `proc/lib/pwc_amaranth.py` — `recall_doc()`, `_click_outbox_row_title()` helpers

## 전제

1. `playwright-cli` 설치 — 한 번만: `npm install -g @playwright/cli@latest`.
2. **Amaranth 세션 부트스트랩** (첫 1회):
   ```bash
   playwright-cli -s=amaranth open https://erp.doflab.com/ --persistent --headed
   ```
3. 회수 대상은 **본인이 상신했고 아직 완전히 결재 처리되지 않은 문서**. `상신문서함(UBA1010)` 에 보이는 것만 가능. 결재가 완료되면 회수 불가.

## 워크플로우 (3단계)

| Step | 페이지 / 탭 | 동작 |
|---|---|---|
| 1 | `UBA1010` (상신문서함) | doc_no 매칭 row 의 제목 클릭 → 문서 viewer popup tab |
| 2 | `/#/popup` (`callComp=UBAP002`) | 우상단 **회수** `<div>` 클릭 → 확인 다이얼로그 |
| 3 | 다이얼로그 | **확인** 버튼 클릭 → popup 자동 닫힘 |

## 표준 호출

### 1) 단일 문서 회수

```bash
python3 -c "
import sys; sys.path.insert(0, 'proc/lib')
from pwc import S
from pwc_amaranth import recall_doc
s = S('amaranth')
ok = recall_doc(s, 'DOF-2605-0146')
print(f'recalled: {ok}')
"
```

성공 시 출력: `recalled: True`. 회수된 문서는 `상신문서함` / `기결문서함` / `기결문서(진행)` 어디에도 안 보임.

### 2) 상신 직후 즉시 회수 (취소 시나리오)

```python
from pwc_amaranth import submit_leave, recall_doc
s = S('amaranth')
result = submit_leave(s, leave_date='2026-05-13', reason='실수', title='실수')
recall_doc(s, result['문서번호'])  # 바로 회수
```

### 3) 여러 건 일괄 회수

```python
docs_to_recall = ['DOF-2605-0143', 'DOF-2605-0144', 'DOF-2605-0145']
for doc_no in docs_to_recall:
    ok = recall_doc(s, doc_no)
    print(f'{doc_no}: {"recalled" if ok else "skipped/failed"}')
```

## API 한계 — 직접 fetch는 차단

ERP 의 일반 제약과 동일: SPA 의 `wehago-sign` HMAC 헤더 때문에 외부 fetch 호출 불가. 회수도 SPA UI 다이얼로그를 통해 수행.

## 주요 trick (구현 detail)

### 상신문서함 row 의 제목 ref 는 row 마다 구조가 다름
어떤 row 는 `generic [ref=eNNNN] [cursor=pointer]: <제목>` 으로 단순한 ref-텍스트 매핑이지만, 다른 row 는 제목이 nested `text:` 노드로 들어 있어 snapshot 기반 ref 추출이 깨짐. 그래서 **eval 기반 DOM 검색** 사용:
1. `(el.textContent || '').trim() === 'DOF-YYMM-####'` 으로 doc_no leaf 노드 찾기
2. parent 체인을 12 hop 까지 거슬러 가장 가까운 `<li>` 도달
3. 해당 li 내부에서 `[class*=title]` 또는 `<strong>` 셀렉터로 제목 클릭 타겟 식별
4. mousedown/mouseup/click 합성 디스패치

### 문서 viewer popup tab 구분
상신 시 popup 은 `callComp=UBAP001` (작성/상신용), **회수 시 popup 은 `callComp=UBAP002`** (조회/액션용). 동일 `/#/popup?...` URL 이지만 callComp 으로 구분.

### 회수 버튼은 `<div>` (popup 우상단)
`<button>` 이 아니라 `<div>` cursor=pointer. snapshot 의 `generic [ref=eNN]: 회수` 라인에서 ref 추출. 위치는 popup 좌표계 우상단 (대략 y < 60).

### 확인 다이얼로그는 OBT confirm (`<button>`)
회수 버튼 클릭 후 "회수 하시겠습니까?" OBT confirm 다이얼로그 — 여긴 `<button>` 으로 `취소` / `확인` 두 개. snapshot 의 `button "확인"` ref 사용.

## 함정

1. **결재 완료된 문서는 회수 불가** — 마지막 결재자가 승인하면 popup 우상단의 `회수` 버튼 자체가 안 뜸. 그 경우 helper 가 RuntimeError 발생.
2. **거꾸로, "결재취소"는 별도 버튼** — 회수 옆에 `결재취소` 도 있는데, 본 helper 는 **회수만** 처리. 결재취소는 결재 진행 도중 무를 때 (반대 의미). 의미 헷갈리지 않게 주의.
3. **회수 후 내역 추적** — `eap105A04` 응답에서 사라짐. ERP 가 별도 회수문서함을 두는지는 미확인 — 본 helper 는 `상신문서함` 에서 doc_no 미존재로만 검증.
4. **연속 회수 시 popup 재사용** — 같은 세션에서 여러 건 회수 시 popup 탭이 매번 새로 열림. helper 는 매번 검증 후 자동 close 시도. 그래도 잔존 popup 탭이 보이면 `tab-close` 수동 정리 권장.
5. **doc_no 형식 정확히** — `DOF-2605-0146` 처럼 `DOF-YYMM-####` (YY=마지막 2자리, MM=월, ####=4자리 채번). DOM textContent trim() 으로 정확 매칭하므로 prefix/suffix 공백 있어선 안 됨.

## 검증

회수 전후 `상신문서함` 비교:

```bash
python3 -c "
import sys, time; sys.path.insert(0, 'proc/lib')
from pwc import S
s = S('amaranth')
s.goto('https://erp.doflab.com/#/UB/UB/UBA0000?specialLnb=Y&moduleCode=UB&menuCode=UBA&pageCode=UBA1010')
time.sleep(4)
print('DOF-2605-0146 in 상신문서함:', 'DOF-2605-0146' in s.snapshot())
"
```
