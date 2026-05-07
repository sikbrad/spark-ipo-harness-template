---
name: amaranth-calendar
description: 아마란스 ERP(erp.doflab.com) 일정/캘린더 데이터 받기. playwright-cli 기반. "아마란스 일정", "ERP 캘린더", "5월 일정 받아줘", "개발부 일정", "출장 일정", "근태/연차 조회" 등 캘린더 관련 요청 시 사용.
---

# 아마란스 ERP 캘린더 데이터 추출

`@playwright/cli` 기반. `proc/lib/pwc_amaranth.py`의 calendar helper로 ERP 일정을 가져온다.

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
   브라우저 창이 뜨면 회사코드 `doflab` → ID(`.env ERP_PERSONAL_ID`) → PW(`.env ERP_PERSONAL_PW`) 로그인 → 출퇴근 체크 popup **취소**. 이후 `--persistent` 디스크 프로필이 로그인 유지.
3. 동시성: 다른 `-s=` 세션(Teams, Salesforce)과 별개 브라우저라 충돌 없음.

## 사전 조건

1. 일정 모듈 진입: 좌측 사이드바 `span.module-link.CL` 클릭 또는 직접 URL
   `https://erp.doflab.com/#/UE/UEA/UEA0000?specialLnb=Y&moduleCode=UE&menuCode=UEA&pageCode=UEA0000`
2. **`목록` (list) 뷰로 전환** — `calendar_list_rows()`는 list 뷰의 큰 table을 파싱한다. 월간/주간 뷰에서는 0행 반환됨.

## 핵심 helper (`proc/lib/pwc_amaranth.py`)

| 함수 | 용도 |
|---|---|
| `calendar_list_rows(s)` | 목록 뷰 table을 raw 2D list로 — 첫 행은 header (`['일자','시간','캘린더','제목','등록자','참여자','연락처']`) |
| `calendar_events(s)` | 위를 dict 리스트로 파싱 + 같은 일자 다중 행의 date carry 처리 |
| `dev_events(s)` | events × 연구소+선행기술 멤버 매칭. 매 항목에 `dev_matched: [이름,...]` 추가, 일자순 정렬 |

## 표준 호출

### 1) 일정 목록 (일정 목록 뷰 진입 후)

```bash
python3 -c "
import sys; sys.path.insert(0, 'proc/lib')
from pwc import S
from pwc_amaranth import calendar_events
s = S('amaranth')
events = calendar_events(s)
print(f'total: {len(events)}')
for ev in events[:5]:
    print(ev['date'], ev['time'], ev['title'], ev['registrar'])
"
```

### 2) 개발부(연구소+선행기술) 매칭 일정만

```bash
python3 -c "
import sys, json; sys.path.insert(0, 'proc/lib')
from pwc import S
from pwc_amaranth import dev_events
s = S('amaranth')
events = dev_events(s)
print(f'dev events: {len(events)}')
print(json.dumps(events[:10], ensure_ascii=False, indent=2))
"
```

### 3) 결과를 파일로 저장

```bash
python3 -c "
import sys, json; sys.path.insert(0, 'proc/lib')
from pwc import S
from pwc_amaranth import dev_events
s = S('amaranth')
with open('/tmp/dev_events.json', 'w') as f:
    json.dump(dev_events(s), f, ensure_ascii=False, indent=2)
print('saved')
"
```

## 다른 월/날짜로 전환

`이전달`/`다음달`/`이전년`/`다음년` 버튼을 클릭하면 `gw114A14`(holidays) + `sc111A03`(events) 호출이 fire된다:

```python
from pwc_amaranth import _click_by_text
_click_by_text(s, '다음달', tag='button')
```

## 일자 형식 주의

`일자` 필드 예: `26.05.31(일)`. 같은 날 여러 행은 첫 행에만 일자 표시되고 이후 행은 6칸. `calendar_events()`가 carry 처리하지만 raw rows로 작업할 때는 직접 처리해야 함.

## 캘린더 종류 (`캘린더` 컬럼 값)

- `근태관리` — 연차/대체휴가/오후반차/휴일근무/경조휴가
- `외근 및 출장` — 외근, 출장, 건강검진
- `전시회 및 행사` — 전시회, 컨퍼런스
- `개인캘린더 백인식` — 본인 일정 (구독 중인 캘린더에 따라 다름)
- `전사일정` / `근태관리` 등 공유 캘린더는 전 사원 대상

## 참여자 필드 동작

`등록자`와 `참여자`는 한글 이름(공백 구분 다인 가능). 매칭은 substring 기반이므로 동명이인 가능성을 의식해야 한다 — 회사 규모(86명)면 보통 안전.

## 주의

- 보이는 일정 = 좌측 패널에서 체크된 캘린더만. 미구독 캘린더(타인 개인캘린더 등)는 누락된다.
- 회의/스프린트 같은 협업 일정은 보통 개인캘린더에 등록되어 있어 공유 뷰엔 안 나옴.
- **로그인 풀린 상태** → `playwright-cli -s=amaranth open https://erp.doflab.com/ --persistent --headed` 로 재로그인.
