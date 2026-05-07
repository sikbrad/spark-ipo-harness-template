---
name: amaranth-calendar
description: 아마란스 ERP(erp.doflab.com) 일정/캘린더 데이터 받기. "아마란스 일정", "ERP 캘린더", "5월 일정 받아줘", "개발부 일정", "출장 일정", "근태/연차 조회" 등 캘린더 관련 요청 시 사용.
---

# 아마란스 ERP 캘린더 데이터 추출

`browser-harness` + `agent_helpers.py`의 `amaranth_*` helper로 ERP 일정을 가져온다.

## 사전 조건

1. browser-harness가 사용자의 Chrome에 attach 가능한 상태.
2. https://erp.doflab.com 에 로그인되어 있어야 한다. 없으면 `browser-harness` skill의 로그인 절차를 따른다 — 회사코드 doflab → ID `ins` (.env `ERP_PERSONAL_ID`) → PW `.env ERP_PERSONAL_PW` → 출퇴근 체크 popup 취소.
3. 일정 모듈 진입: 좌측 사이드바 `span.module-link.CL` 클릭 (또는 직접 URL `#/UE/UEA/UEA0000?specialLnb=Y&moduleCode=UE&menuCode=UEA&pageCode=UEA0000`).
4. **`목록` (list) 뷰로 전환** — `amaranth_calendar_list_rows()`는 list 뷰의 큰 table을 파싱한다. 월간/주간 뷰에서는 0행 반환됨.

## 핵심 helper

| 함수 | 용도 |
|---|---|
| `amaranth_calendar_list_rows()` | 목록 뷰 table을 raw 2D list로 — 첫 행은 header (`['일자','시간','캘린더','제목','등록자','참여자','연락처']`) |
| `amaranth_calendar_events()` | 위를 dict 리스트로 파싱 + 같은 일자 다중 행의 date carry 처리 |
| `amaranth_dev_events()` | events × 연구소+선행기술 멤버 매칭. 매 항목에 `dev_matched: [이름,...]` 추가, 일자순 정렬 |

## 표준 호출

```bash
# 일정 목록 뷰 진입 후
browser-harness -c "
events = amaranth_calendar_events()
print(f'total: {len(events)}')
"

# 개발부(연구소+선행기술) 매칭 일정만
browser-harness -c "
import json
events = amaranth_dev_events()
print(f'dev events: {len(events)}')
print(json.dumps(events[:10], ensure_ascii=False, indent=2))
"
```

## 출력 가공 패턴

긴 결과는 stdout에 다 찍지 말고 `/tmp/`에 dump 후 Python으로 후처리한다:

```bash
browser-harness -c "
import json
with open('/tmp/dev_events.json','w') as f:
    json.dump(amaranth_dev_events(), f, ensure_ascii=False, indent=2)
print('saved')
"
```

## 일자 형식 주의

`일자` 필드 예: `26.05.31(일)`. 같은 날 여러 행은 첫 행에만 일자 표시되고 이후 행은 6칸. `amaranth_calendar_events()`가 carry 처리하지만 raw rows로 작업할 때는 직접 처리해야 함.

## 캘린더 종류 (`캘린더` 컬럼 값)

- `근태관리` — 연차/대체휴가/오후반차/휴일근무/경조휴가
- `외근 및 출장` — 외근, 출장, 건강검진
- `전시회 및 행사` — 전시회, 컨퍼런스
- `개인캘린더 백인식` — 본인 일정 (구독 중인 캘린더에 따라 다름)
- `전사일정` / `근태관리` 등 공유 캘린더는 전 사원 대상

## 참여자 필드 동작

`등록자`와 `참여자`는 한글 이름(공백 구분 다인 가능). 매칭은 substring 기반이므로 동명이인 가능성을 의식해야 한다 — 회사 규모(86명)면 보통 안전.

## 다른 월/날짜로 전환

`이전달`/`다음달`/`이전년`/`다음년` 버튼을 클릭하면 `gw114A14`(holidays) + `sc111A03`(events) 호출이 fire된다. 자동화는 다음 helper로 (필요하면 `agent_helpers.py`에 추가):

```python
def amaranth_calendar_navigate(direction):
    """direction: 'prev_month' | 'next_month' | 'prev_year' | 'next_year' | 'today'."""
    label = {'prev_month':'이전달','next_month':'다음달','prev_year':'이전년','next_year':'다음년','today':'오늘'}[direction]
    return click_element_by_text(label, tag='button')
```

## 주의

- 보이는 일정 = 좌측 패널에서 체크된 캘린더만. 미구독 캘린더(타인 개인캘린더 등)는 누락된다.
- 회의/스프린트 같은 협업 일정은 보통 개인캘린더에 등록되어 있어 공유 뷰엔 안 나옴.
