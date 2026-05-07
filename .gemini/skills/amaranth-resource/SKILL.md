---
name: amaranth-resource
description: 아마란스 ERP(erp.doflab.com) 자원(회의실/차량) 예약 상태 조회 및 신규 예약 등록. "회의실 예약", "306호 잡아줘", "5/12 자원 비어있어?", "ax회의 예약", "회의실 가용 시간 확인" 등 자원 관련 요청 시 사용.
---

# 아마란스 ERP 자원 예약 (회의실 / 차량)

`browser-harness` + `agent_helpers.py`의 자원 helper로 ERP 자원(회의실·차량) 상태 조회와 신규 예약을 수행한다.

## 사전 조건

1. browser-harness가 사용자의 Chrome에 attach 가능한 상태.
2. https://erp.doflab.com 에 로그인되어 있어야 한다 — 미로그인 시 `browser-harness` skill의 로그인 절차 참고.
3. 자원 모듈 진입 — 직접 URL `#/UK/UKA/UKA0000?specialLnb=Y&moduleCode=UK&menuCode=UKA&pageCode=UKA0000`.
4. 일간(`일간`) 뷰가 디폴트. 주간/월간/목록도 가능하나 본 스킬은 일간 기준.

## API 한계 — 직접 fetch는 차단

요청 헤더가 SPA 번들 내부 `wehago-sign` HMAC 서명으로 보호되며, 외부 fetch 호출 시 `601 허용된 쿠키 인증 URL이 아닙니다`로 거절됨.

따라서:
- **읽기**: SPA가 발사한 XHR을 캡처(`install_xhr_capture` + `captured_requests`)
- **쓰기**: SPA의 `자원 예약` 다이얼로그 UI를 통해 수행 (다이얼로그가 SPA 서명 파이프라인을 그대로 탐)

## 자원(resSeq) 매핑

`agent_helpers.py`의 `AMARANTH_RES_SEQ`:

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
| `/schres/rs121A05` | 일자×자원 예약 조회 (조회 응답에서 자원 목록 + 예약 list) |
| `/schres/rs121A06` | **예약 생성** |
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

## 핵심 helper (`agent_helpers.py`)

| 이름 | 용도 |
|---|---|
| `AMARANTH_RES_SEQ` | 한글이름 → resSeq 매핑 dict |
| `amaranth_resource_bookings(start_yyyymmdd, end_yyyymmdd=None, res_seqs=None)` | 캡처된 rs121A05 응답에서 해당 일자 예약 목록 파싱 |

## 1. 상태 조회 (가용성 확인)

```bash
# 모듈 진입 → 캡처 설치 → 일자 이동(SPA가 자동으로 rs121A05 호출) → 결과 수집
browser-harness -c "
import time, json
goto_url('https://erp.doflab.com/#/UK/UKA/UKA0000?specialLnb=Y&moduleCode=UK&menuCode=UKA&pageCode=UKA0000')
wait_for_load(); time.sleep(2)
install_xhr_capture(); clear_captured()

# 날짜 picker 열기 → 원하는 일자 클릭
click_at_xy(325, 284)  # 날짜 라벨
time.sleep(1)
# (picker 안에서 원하는 일 셀 클릭, 좌표는 동적이라 매번 js로 찾는 게 안전)

time.sleep(2)
items = amaranth_resource_bookings('20260512')
for it in items:
    print(it['resName'], it['resStartDate'][8:12]+'~'+it['resEndDate'][8:12], it['reqText'], '/', it['empName'])
"
```

빈 자원 = 응답에 해당 resSeq가 없는 경우 (예약이 한 건도 없으면 누락됨, 결석 = free).

## 2. 신규 예약 등록

핵심 흐름: **`자원 예약` 버튼 클릭 → 다이얼로그 → 자원/일시/예약명 입력 → 확인.**

캘린더 빈 셀 드래그/클릭은 시간 스냅이 어긋나기 쉬우므로 다이얼로그 내 `일시` 행을 펼쳐 수동 설정 권장.

### 단계별 패턴

```bash
browser-harness -c "
import time

# 1) '자원 예약' 버튼 (좌측 상단)
js('''[...document.querySelectorAll(\"button, a, div\")].find(el => (el.textContent||\"\").trim() === \"자원 예약\")?.click();''')
time.sleep(2)

# 2) 자원 클릭이 비어있으면, 자원명 행을 펼쳐 원하는 자원 선택 — 또는 미리 캘린더에서
#    원하는 자원의 빈 시간대를 클릭해 다이얼로그를 열면 자원/날짜가 pre-fill됨.
#    예) 5/12 306호 빈 시간 셀 클릭 → 다이얼로그에 306호 + 5/12 자동 입력
"
```

### 시간 정확히 맞추기 — `일시` 펼침 + 화살표키

다이얼로그 내 시간 드롭다운은 **5분 단위 LI 리스트**. 클릭으로 옵션 선택 시 종종 빗나가므로 **화살표키 + Enter** 권장.

```python
# 시작/종료 시간 = "12:00" / "13:00"으로 맞추기 (예: pre-fill이 12:20 / 13:30인 경우)
# 1) 일시 행 클릭해 펼치기
click_at_xy(1200, 331)  # '일시' label 우측 (좌표는 dialog 위치 따라 다름)
time.sleep(1)

# 2) 시작 시간 드롭다운 열기 → 12:20 → 12:00 (위로 4번)
click_at_xy(1262, 405)  # 시작 시간 입력
time.sleep(1)
for _ in range(4): press_key('ArrowUp'); time.sleep(0.1)
press_key('Enter')

# 3) 종료 시간 드롭다운 → 13:30 → 13:00 (위로 6번)
click_at_xy(1262, 437)
time.sleep(1)
for _ in range(6): press_key('ArrowUp'); time.sleep(0.1)
press_key('Enter')
```

### 예약명 입력

```python
click_at_xy(1230, 235)  # 예약명 input (placeholder "예약명을 입력해주세요")
type_text('ax회의')
```

### 제출 + save API 캡처

```python
js('window.__captured = [];')  # XHR 캡처 리셋 (이전에 install_xhr_capture 필요)
click_at_xy(1216, 812)  # '확인' 버튼
time.sleep(3)
# rs121A06 요청 body로 검증
captured = js('return window.__captured;')
```

성공 시 좌측 사이드바 `나의예약현황` 카운트가 +1, 캘린더에 `[등록자] 예약명` 표시.

## 표준 호출 (조회 → 예약 → 검증)

```bash
browser-harness -c "
import time, json

# 1) 진입
goto_url('https://erp.doflab.com/#/UK/UKA/UKA0000?specialLnb=Y&moduleCode=UK&menuCode=UKA&pageCode=UKA0000')
wait_for_load(); time.sleep(2)
install_xhr_capture()

# 2) 날짜 picker → 5/12 클릭 (좌표는 매번 js로 찾기)
loc = js('''
const dateEl = [...document.querySelectorAll(\"div\")].find(el => /2026\\\\.05\\\\./.test(el.textContent || \"\") && el.textContent.length < 30);
const r = dateEl.getBoundingClientRect();
return {x: Math.round(r.x+r.width/2), y: Math.round(r.y+r.height/2)};
''')
click_at_xy(loc['x'], loc['y']); time.sleep(1)
day12 = js('''
const c = [...document.querySelectorAll(\"span, td\")].find(el => (el.textContent||\"\").trim() === \"12\" && el.getBoundingClientRect().width > 0);
const r = c.getBoundingClientRect(); return {x: Math.round(r.x+r.width/2), y: Math.round(r.y+r.height/2)};
''')
click_at_xy(day12['x'], day12['y']); time.sleep(2)

# 3) 5/12 예약 현황 확인
items = amaranth_resource_bookings('20260512') or []
print(f'5/12 예약 {len(items)}건')
for it in items:
    if it['resSeq'] == AMARANTH_RES_SEQ['306호']:
        print('306호 예약됨:', it['resStartDate'][8:12]+'~'+it['resEndDate'][8:12], it['reqText'])
"
```

## 주의 / 함정

- **드래그로 시간 선택은 비추천** — 캘린더 셀 분할이 5분 단위인데 드래그가 정확히 시간에 맞지 않아 12:20~13:30 같은 어긋난 값이 잡힘. `자원 예약` 다이얼로그에서 화살표키로 입력하는 게 안정적.
- **다이얼로그 좌표는 viewport 변동에 민감** — 다이얼로그 위치(1393×858 viewport 기준 우측 패널)를 가정한 좌표는 매번 검증 필요. 안전하게는 매 단계 `js()`로 element를 찾아 그 시점의 BBox로 클릭.
- **기존 예약 셀 클릭 시 `예약 조회`(읽기) 다이얼로그가 열림** — 신규 등록이 아니라 조회 모드. 빈 시간대를 클릭하거나 좌측 상단 `자원 예약` 버튼을 사용해야 등록 다이얼로그가 열림.
- **rs121A05 응답은 예약 0건인 자원은 누락** — `resultList`에 해당 resSeq가 안 보이면 그 자원은 비어 있음. 예약 유무 판단 시 누락=자유로 해석.
- **닫기(X) 버튼이 tooltip에 가려짐** — 패널 우상단 close 버튼은 아이콘+tooltip이 겹쳐 첫 클릭이 tooltip 활성화에만 쓰일 수 있음. 두 번 클릭하거나 element 직접 click 필요.
- **wehago-sign 직접 위조 불가** — 외부 fetch는 모두 401. 쓰기 작업은 반드시 SPA UI 통과.

## 참고

- 자원 분류: 회의실(상위) / 차량(상위) / 펜 태블릿 / TV / 마이크 / 화상장비 등 좌측 `자원필터` 사이드바에서 카테고리/속성 필터 가능.
- `사용자` 필드는 기본 본인. 타인 명의 예약은 본 스킬 범위 밖.
- 예약 수정/삭제는 본 스킬 미커버 — 예약 셀 클릭 시 열리는 `예약 조회` 다이얼로그에서 처리.
