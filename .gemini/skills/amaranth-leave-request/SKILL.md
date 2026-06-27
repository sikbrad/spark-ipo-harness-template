---
name: amaranth-leave-request
description: 아마란스 ERP(erp.doflab.com) 연차휴가신청서 작성·상신 자동화 — 결재작성 → HPD0110 폼 → 결재상신 popup → 상신까지 4단계 워크플로우. playwright-cli 기반. "휴가 신청해줘", "5/14에 연차 신청", "오전반차 신청해줘", "연차휴가신청서 상신", "휴가 자동으로 올려줘" 등 휴가 상신 요청 시 사용. 휴가함 조회는 `/amaranth-approval`.
---

# 아마란스 ERP 연차휴가신청서 상신

`@playwright/cli` 기반. `proc/lib/pwc_amaranth.py`의 `submit_leave()` helper로 연차휴가신청서를 자동 작성·상신한다.

## 도구 스택

- `@playwright/cli` (전역 `playwright-cli` 명령) — 사이트별 격리 세션, 영속 프로필
- `proc/lib/pwc.py` — 세션 wrapper (`S('amaranth')`)
- `proc/lib/pwc_amaranth.py` — `submit_leave()`, `_click_obt_button()` helpers

## 전제

1. `playwright-cli` 설치 — 한 번만: `npm install -g @playwright/cli@latest`.
2. **Amaranth 세션 부트스트랩** (첫 1회):
   ```bash
   playwright-cli -s=amaranth open https://erp.doflab.com/ --persistent --headed
   ```
   회사코드 `doflab` → ID(`.env ERP_PERSONAL_ID`) → PW(`.env ERP_PERSONAL_PW`) → 출퇴근 체크 popup **취소**.
3. 동시성: 다른 `-s=` 세션과 별개 브라우저라 충돌 없음.

## 워크플로우 (4단계)

| Step | 페이지 / 탭 | 동작 |
|---|---|---|
| 1 | `UBA6000` (결재작성) | "연차휴가신청서" 카드 클릭 → `HPD0110` 이동 |
| 2 | `HPD0110` step 1 | sub-type 클릭(시간계산 활성화) → 시작·종료일 입력 → 사유 입력 → **신청완료** |
| 3 | `HPD0110` step 2 | **제목** 입력 → **결재상신** 클릭 → **새 탭** (popup) 오픈 |
| 4 | `/#/popup` (popup 탭) | 휴가신청서 전자결재 view → 우상단 **상신** 클릭 → 결재라인 발송 |

## 표준 호출

### 1) 단순 — 평일 1일 연차

```bash
python3 -c "
import sys, json; sys.path.insert(0, 'proc/lib')
from pwc import S
from pwc_amaranth import submit_leave
s = S('amaranth')
result = submit_leave(s,
    leave_date='2026-05-11',
    reason='개인 일정',
    title='5/11 연차')
print(json.dumps(result, ensure_ascii=False, indent=2))
"
```

성공 시:
```json
{
  "결재일시": "2026-05-08 16:09:31",
  "양식": "연차휴가신청서",
  "제목": "5/11 연차",
  "문서번호": "DOF-2605-0143",
  "상태": "진행",
  ...
}
```

### 2) 반차

```python
submit_leave(s, leave_date='2026-05-12', sub_type='오전반차',
             reason='병원', title='5/12 오전반차')
```

`sub_type` 후보: `연차` / `오전반차` / `오후반차` / `반반차` / `대체휴가(반반차)`.

### 3) 다일 연차

```python
submit_leave(s, leave_date='2026-05-18', end_date='2026-05-22',
             reason='가족여행', title='5/18~22 휴가')
```

## API 한계 — 직접 fetch는 차단

요청 헤더가 SPA 번들 내부 `wehago-sign` HMAC 서명으로 보호되며, 외부 fetch 호출 시 `601 허용된 쿠키 인증 URL이 아닙니다`로 거절. 따라서 **모든 단계가 SPA UI 다이얼로그를 통한 클릭/타이핑**으로 진행되어야 함. 이건 본 스킬뿐 아니라 ERP 모든 쓰기 작업의 공통 제약.

## 주요 trick (구현 detail)

### OBT 버튼 (`OBTButton_root`) 클릭
`.click()` / `dispatchEvent('click')` 안 통함 — wrapper가 가로챔. inner `<button>` 좌표에 `mousedown` + `mouseup` + `click` 셋을 합성 디스패치. helper: `_click_obt_button(s, '신청완료')`.

### OBT DatePicker (`OBTDatePickerRebuild_inputYMD`) 입력
React-controlled — `Object.getOwnPropertyDescriptor(...).value.set` 트릭이 안 통함. **focus + select + `s.type("YYYY-MM-DD")` + `s.press("Tab")`**. range picker라 시작일 입력 시 종료일도 동기화됨.

### sub-type 버튼 클릭이 시간계산 트리거
폼이 열리면 `연차` sub-type이 디폴트처럼 보이지만 **명시적 클릭 전까지는 시간 계산 비활성**. 안 누르고 신청완료 → 토스트 "잔여시간 정보가 없습니다" + 시간계 "-" + 차단.

### 결재상신은 새 브라우저 탭
modal이 아니라 별개 탭. `tab-list` → `popup` URL 식별 → `tab-select`. 탭 URL 패턴: `/#/popup?...&callComp=UBAP001&popupUUID=...`.

### popup 탭의 상신 버튼은 `<div>`
`<button>`이 아니라 `<div role=cursor-pointer>`. `<div>/<span>/<button>` 모두 검색해서 텍스트 "상신" 매칭 + y < 60 (상단바) 필터.

## 함정

1. **주말·공휴일 거부** — `잔여시간 정보가 없습니다` 토스트. 평일만 가능.
2. **잔여 연차 부족 시 거부** — eap105A04 캡처에 별도 토스트. 미사용 일수 초과 안 되게.
3. **결재선은 자동 세팅** — 부장 → 대표이사 (회사 정책상 자동). 수정하려면 popup 탭의 "양식필수정보" 패널에서 별도 조작 필요 (본 스킬 미커버).
4. **첨부파일 / 합의자 미지원** — 본 스킬은 단순 사유 텍스트만. 첨부 파일이 필요한 경조휴가 등은 별도 처리 필요.
5. **검증 단계** — `submit_leave()` 마지막에 `approval_docs(s)` 로 자동 확인. 반환값이 None이면 상신 실패 또는 indexing 지연 (수 초 후 재시도).
6. **5/9 같은 비근무일을 강행하면 step 2(신청완료) 클릭 후 토스트만 뜨고 진행 안 함** — `submit_leave()`는 이때 `잔여시간 정보가 없습니다` 토스트를 직접 감지하지는 않으므로, 시간계 input ("08시간 00분" 등)이 비어 있으면 호출자가 별도 검증 권장.

## 양식 다른 휴가는?

같은 `HPD0110` 좌측 리스트에 다음 양식들이 있음 (현재 미지원):

| 양식명 | 설명 |
|---|---|
| 연차휴가신청서 | **본 스킬** |
| 연장근무신청서 | 야근 |
| 경조휴가신청서 | 결혼·상 |
| 기타휴가신청서 | 일반 |
| 출산및육아휴직신청서 | 장기 |
| 휴직신청서 | 장기 |
| 외출신청서 | 단시간 |

다른 양식 자동화가 필요하면 `submit_leave()`의 step 1 카드 텍스트 ("연차휴가신청서") 만 변경하고 step 2의 sub-type 버튼 라벨을 양식별로 매핑하면 동일 패턴으로 확장 가능.

## 검증 (eap105A04)

```bash
python3 -c "
import sys, json; sys.path.insert(0, 'proc/lib')
from pwc import S
from pwc_amaranth import approval_url, approval_docs
s = S('amaranth')
s.goto(approval_url('기결문서'))
import time; time.sleep(3)
docs = approval_docs(s)
for d in docs[:5]:
    if '연차' in (d.get('양식') or ''):
        print(f\"{d['결재일시']} | {d['제목']:<30} | {d['상태']} | {d['문서번호']}\")
"
```
