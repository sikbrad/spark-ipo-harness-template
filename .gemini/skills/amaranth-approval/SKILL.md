---
name: amaranth-approval
description: 아마란스 ERP(erp.doflab.com) 전자결재 문서함 조회 — 미결/기결 문서 목록과 본인이 결재 처리한 이력. playwright-cli 기반. "내가 결재할 문서", "미결문서", "결재해야 할 거", "내가 결재한 문서", "기결문서", "지난달 결재한 거", "결재 진행 이력" 등 결재함 관련 요청 시 사용.
---

# 아마란스 ERP 전자결재 문서함 조회

`@playwright/cli` 기반. `proc/lib/pwc_amaranth.py`의 `approval_*` helper로 ERP 전자결재함(미결/기결) 문서 목록을 가져온다.

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
3. 전자결재 모듈 진입은 `approval_url(box)` 가 만들어 주는 URL로 `s.goto()`.
4. 동시성: 다른 `-s=` 세션(Teams, Salesforce)과 별개 브라우저라 충돌 없음.

## API 한계 — 직접 fetch는 차단

요청 헤더가 SPA 번들 내부 cookie/HMAC 서명으로 보호되며, 외부 fetch 호출 시 `601 허용된 쿠키 인증 URL이 아닙니다`로 거절. 따라서:
- **읽기**: SPA가 fire하는 `/eap/eap105A04` 응답을 `s.requests()` + `s.response_body()` 로 캡처해 파싱.
- **쓰기(결재 승인/반려)**: 본 스킬 미커버 — 다이얼로그 UI 통과 필요.

## 결재함(box) ↔ pageCode

`APPROVAL_PAGES`:

| box 키 | pageCode | 설명 |
|---|---|---|
| `결재HOME` | UBA7000 | 결재 홈(대시보드) |
| `미결문서` | UBA2020 | 내가 결재해야 할 대기 문서 |
| `기결문서` | UBA2030 | 내가 처리한 결재 (진행+종결) |
| `기결문서_진행` | UBA2040 | 결재 라인이 아직 진행 중인 것만 |
| `기결문서_종결` | UBA2050 | 종결된 것만 |

URL 생성: `approval_url('기결문서')` →
`https://erp.doflab.com/#/UB/UB/UBA0000?specialLnb=Y&moduleCode=UB&menuCode=UBA&pageCode=UBA2030`

## 핵심 endpoint

`POST /eap/eap105A04` — 결재함 list. 디폴트 기간은 최근 3개월(`sfrDt~stoDt`), 정렬은 `ACTION_TIME DESC`. SPA가 페이지 진입/기간 변경/페이지네이션 시 자동 호출.

응답 형태:
```json
{ "resultCode": "...", "resultData": { "map": { "list": [...], "totalCount": 18 } } }
```

list 항목의 주요 필드: `ACTION_TIME`(내가 결재한 시각), `REP_DT`(상신일), `ARRIVED_DT`(나에게 도착한 시각), `FORM_NM`(양식명), `DOC_TITLE`, `DOC_NO`, `USER_NM`(기안자), `GRADE_NM`/`DUTY_NM`/`DEPT_NM`, `DOC_STSNM`(진행/종결), `OUT_PROC_NM`.

## 핵심 helper (`proc/lib/pwc_amaranth.py`)

| 이름 | 용도 |
|---|---|
| `APPROVAL_PAGES` | box 키 → pageCode dict |
| `approval_url(box)` | SPA hash URL 생성 |
| `approval_docs(s, min_action_dt=None, max_action_dt=None)` | 마지막 eap105A04 캡처를 파싱해서 dict 리스트로. ACTION_TIME 문자열로 기간 필터(`'YYYY-MM-DD'`). |
| `approval_total_count(s)` | 응답의 `totalCount` |

`approval_docs()`가 반환하는 dict 키: `결재일시` / `REP_DT` / `도착일` / `양식` / `제목` / `문서번호` / `기안자` / `직급` / `부서` / `상태` / `BIZ` / `OUT_PROC`. `결재일시` 내림차순 정렬.

## 표준 호출

### 1) 미결문서 (내가 처리해야 할 결재)

```bash
python3 -c "
import sys, time, json; sys.path.insert(0, 'proc/lib')
from pwc import S
from pwc_amaranth import approval_url, approval_docs, approval_total_count
s = S('amaranth')
s.goto(approval_url('미결문서'))
time.sleep(3)
docs = approval_docs(s)
print(f'미결 {approval_total_count(s)}건')
print(json.dumps(docs, ensure_ascii=False, indent=2))
"
```

### 2) 기결문서 — 내가 결재한 문서

```bash
python3 -c "
import sys, time, json; sys.path.insert(0, 'proc/lib')
from pwc import S
from pwc_amaranth import approval_url, approval_docs, approval_total_count
s = S('amaranth')
s.goto(approval_url('기결문서'))
time.sleep(3)
docs = approval_docs(s)
print(f'기결 {approval_total_count(s)}건')
print(json.dumps(docs[:5], ensure_ascii=False, indent=2))
"
```

### 3) 4-5월 본인 결재 이력 (기간 필터)

```bash
python3 -c "
import sys, time, json; sys.path.insert(0, 'proc/lib')
from pwc import S
from pwc_amaranth import approval_url, approval_docs
s = S('amaranth')
s.goto(approval_url('기결문서'))
time.sleep(3)
docs = approval_docs(s, min_action_dt='2026-04-01', max_action_dt='2026-05-31')
print(f'4-5월 결재: {len(docs)}건')
for d in docs:
    print(f\"{d['결재일시'][:16]} | {d['양식']:<20} | {d['제목']:<40} | 기안:{d['기안자']} | {d['상태']}\")
"
```

## 기간(sfrDt/stoDt) 변경

페이지 디폴트는 **최근 3개월**. 더 넓게 보려면 UI 조작:
1. 페이지 우상단 기간 picker(`결재일 YYYY-MM-DD ~ YYYY-MM-DD`)에서 시작일 input 클릭 → 캘린더에서 원하는 일자 선택 → 검색 버튼.
2. 기간 picker의 좌측 드롭다운(`결재일`/`도착일` 등)을 바꾸면 SPA가 새로 eap105A04 fire.

## 페이지네이션

응답 body에 `page:"1", pageSize:"30"`. `totalCount > 30`이면 페이지 단위 조회. 다음 페이지 버튼 클릭 시 SPA가 동일 endpoint 재호출 → 마지막 capture가 갱신되므로 `approval_docs()`는 항상 **마지막 페이지**만 반환. 누적 수집이 필요하면 페이지마다 호출 후 결과를 모아두는 패턴 권장.

## 주의 / 함정

- **eap105A04 응답이 없으면 빈 리스트** — 페이지 진입 후 1~3초 sleep 필요.
- **`결재일시 = ACTION_TIME`** — 본인이 마지막 결재 처리한 시각이지, 상신일은 `REP_DT` 별도 필드.
- **본인이 기안자인 문서도 기결문서함에 포함** — 기안자 필터(`USER_NM != '본인이름'`)로 후처리 가능.
- **미결문서가 0건이어도 결재 HOME 우상단 위젯은 본인 상신 문서를 카운트해 표시** — 해석 주의.
- **상태(DOC_STSNM)는 `진행`/`종결` 외 `반려`/`회수` 등도 가능** — `DOC_STS` 코드로 필터.
- **로그인 풀린 상태** → `playwright-cli -s=amaranth open https://erp.doflab.com/ --persistent --headed` 로 재로그인.
