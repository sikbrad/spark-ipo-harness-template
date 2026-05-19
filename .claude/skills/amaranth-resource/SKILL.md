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

| 자원 | resSeq | 좌석수 |
|---|---|---|
| 대표실 | 44 | - |
| 302호 | 45 | **12인** (대형) |
| **306호** | **63** | **4인** (소형) ← 3층 기본 |
| 601호(DDA) | 47 | - |
| 602호 | 48 | - |
| 197하1718 (스포티지 검정) | 50 | - |
| 225하1481 (스포티지 흰색) | 60 | - |
| 224허9910 (GV70) | 64 | - |

### 3층 회의실 기본값

사용자가 "3층 회의실" 또는 "3층 위주"로 요청 시 **306호(4인실)를 기본**으로 잡는다. 302호는 12인실 대형 회의실이라 인원이 명시되지 않은 일반 미팅에는 과대.

- 302호 → 12인 (큰 회의·다인원 미팅)
- 306호 → 4인 (소규모·일반 미팅) — **default**

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

### 권장 흐름 (실전 검증됨 2026-05-19)

**캘린더 셀 직접 클릭**으로 자원 + 시간을 동시 pre-fill → 시간만 5분 단위에서 정시로 조정 → 예약명 입력 → 확인.

`자원 예약` 버튼은 자원이 비어 있어서 OBTComplete 자동완성을 직접 채워야 하는데, 이 컴포넌트는 `input.value` + `dispatchEvent('input')`/`fill`/`type` 모두 chip 선택까지 가지 않는다. 반면 캘린더 셀 클릭은 한 번에 자원 + 시간이 같이 들어와서 훨씬 안정적.

```python
import sys, time, json
sys.path.insert(0, 'proc/lib')
from pwc import S
s = S('amaranth')

# 1) 캘린더 row × 시간 셀 클릭 = 자원 + 시간 동시 pre-fill
#    좌표 계산:
#    - 자원 row y: span.fc-cell-text 텍스트의 y (예: 306호 → y=477 mid)
#    - 시간 cell x: 같은 hour label 의 x 에서 hour 폭만큼 좌우. 1시간 ≈ 155~156px
#    - 12시 cell ≈ (label_x - 62) ~ (label_x + 93) (label 중심 기준)
s.eval('''() => {
    const time12 = [...document.querySelectorAll('*')].find(el =>
        /^12시$/.test((el.textContent||'').trim()) && el.children.length === 0
    );
    const span306 = [...document.querySelectorAll('span.fc-cell-text')].find(s =>
        s.textContent.trim() === '306호'
    );
    const x = time12.getBoundingClientRect().x + 15;
    const y = span306.getBoundingClientRect().y + 16;
    const el = document.elementFromPoint(x, y);
    el.dispatchEvent(new MouseEvent('mousedown', {bubbles:true, clientX:x, clientY:y}));
    el.dispatchEvent(new MouseEvent('mouseup', {bubbles:true, clientX:x, clientY:y}));
    el.dispatchEvent(new MouseEvent('click', {bubbles:true, clientX:x, clientY:y}));
}''')
time.sleep(2)
# 결과: 자원명=306호, 일시=12:20~12:30 (셀이 5분 단위라 어긋남)

# 2) 일시 펼치고 시작/종료 LI 클릭 → drop-down 에서 정시 클릭
s.eval('''() => {
    const dl = [...document.querySelectorAll('dl')].find(dl =>
        /일시/.test(dl.textContent) && dl.getBoundingClientRect().width > 0
    );
    const head = dl.querySelector('.headTxt');
    (head || dl.querySelector('dd')).click();
}''')
time.sleep(1)

# 2a) 시작 시간 12:00
s.eval('''() => {
    const li = [...document.querySelectorAll('li')].find(li =>
        /시작.*\\d{2}:\\d{2}/.test(li.textContent) && li.getBoundingClientRect().width > 0
        && li.getBoundingClientRect().y > 380 && li.getBoundingClientRect().y < 460
    );
    const span = [...li.querySelectorAll('*')].find(e =>
        /^\\d{2}:\\d{2}$/.test((e.textContent||'').trim()) && e.children.length === 0
    );
    span.click();
}''')
time.sleep(1)
s.eval('''() => {
    const opt = [...document.querySelectorAll('li')].find(li =>
        li.textContent.trim() === '12:00' && li.getBoundingClientRect().width > 0
    );
    opt.scrollIntoView({block:'center'}); opt.click();
}''')
time.sleep(1)

# 2b) 종료 시간 13:00 (위와 동일 패턴, '종료' + '13:00')
# ... (생략)

# 3) 예약명 입력
s.eval('''() => {
    const dl = [...document.querySelectorAll('dl')].find(dl =>
        /예약명/.test(dl.textContent) && dl.getBoundingClientRect().width > 0
    );
    const inp = dl.querySelector('input');
    inp.click(); inp.focus();
}''')
s.type('AX회의')

# 4) 확인
s.eval('''() => {
    const b = [...document.querySelectorAll('button')].find(b =>
        b.textContent.trim() === '확인' && b.getBoundingClientRect().width > 0
    );
    b.click();
}''')
time.sleep(3)
```

### 캘린더 셀 좌표 계산 메모

- 가로 24시간 timeline은 hour 1개당 ~155~156px (`fc-timeline-event` 폭으로 확인 가능)
- 시간 label `12시` 등은 hour 셀의 **중심**에 정렬되어 있어 보통 `text.x ≈ cell_start + 61`
- 따라서 셀 좌측에서 살짝 들어간 점 = `label_x + 15` 정도가 hh:00 직후에 안전하게 떨어짐
- 자원 row 의 y 는 `span.fc-cell-text` (예: `306호`) rect 의 mid

### 함정 — OBTComplete (자원명 자동완성)이 fill/type/JS dispatch 모두 안 먹음

`자원 예약` 버튼으로 다이얼로그를 열면 자원명이 비어 있는데, 이 자동완성은:
- `input.value = '306호'` + `dispatchEvent('input'/'change')` → 텍스트만 들어가고 chip(선택 확정) 안 생김
- `playwright-cli fill` → 동일하게 텍스트만, chip 미생성
- `playwright-cli type` 한 글자씩 → 마찬가지

검증된 우회 = **캘린더 셀을 먼저 클릭**해서 다이얼로그 열기. 셀 클릭 시 자원/시간이 chip 형태로 같이 들어옴.

### 시간 드롭다운 LI 클릭

5분 단위 LI 리스트. `scrollIntoView({block:'center'}) → click()` 으로 정확히 잡힌다 (예: '12:00', '13:00'). 화살표키 + Enter 도 가능하지만 LI 직접 click 이 더 명확.

## 주의 / 함정

- **빈 캘린더 셀 클릭 → 다이얼로그 자동 오픈 + 자원·시간 pre-fill** — 위 권장 흐름의 핵심. 단 시간이 5분 단위로 스냅되므로 정시는 드롭다운에서 별도 조정.
- **드래그로 시간 선택은 비추천** — 드래그 끝점이 5분 단위로 어긋나 12:20~13:30 같은 값이 잡힘. 셀-클릭 후 LI 드롭다운 조정이 더 안전.
- **자원명 자동완성(OBTComplete) 직접 채우기 불가** — `input.value` + `dispatchEvent`/`fill`/`type` 어떤 방법으로도 chip 선택 확정이 안 됨. 캘린더 셀 클릭 우회 필수.
- **다이얼로그 좌표는 viewport 변동에 민감** — 안전하게는 매 단계 `s.eval()`로 element를 찾아 클릭.
- **기존 예약 셀 클릭 시 `예약 조회`(읽기) 다이얼로그가 열림** — 빈 시간대만 클릭해야 등록 다이얼로그가 열림.
- **rs121A05 응답은 예약 0건인 자원은 누락** — resultList에 해당 resSeq가 안 보이면 그 자원은 비어 있음.
- **wehago-sign 직접 위조 불가** — 외부 fetch는 모두 401. 쓰기 작업은 반드시 SPA UI 통과.
- **로그인 풀린 상태** → `playwright-cli -s=amaranth open https://erp.doflab.com/ --persistent --headed` 로 재로그인. 로그인 폼은 ID/PW가 영속 프로필에 기억되어 있어 `다음` → `로그인` 두 번 클릭만 하면 됨.
- **로그인 직후 출퇴근 popup 새 탭** — `https://erp.doflab.com/#/popup?...` 형태. 기능에 영향 없으므로 무시하고 작업 진행.

## 참고

- 자원 분류: 회의실(상위) / 차량(상위) / 펜 태블릿 / TV / 마이크 / 화상장비 등 좌측 `자원필터` 사이드바에서 카테고리/속성 필터 가능.
- `사용자` 필드는 기본 본인. 타인 명의 예약은 본 스킬 범위 밖.
- 예약 수정/삭제는 본 스킬 미커버 — 예약 셀 클릭 시 열리는 `예약 조회` 다이얼로그에서 처리.
