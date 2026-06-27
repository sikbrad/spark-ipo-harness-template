---
name: amaranth-acc-ledger
description: 아마란스 ERP(erp.doflab.com) 거래처계정내역(ACC3030) 다운로드 — 기간·계정과목 조건으로 거래처별 차변/대변/잔액 원장을 받아 JSON+Excel로 저장. playwright-cli 기반. "거래처계정내역", "ACC3030", "거래처원장", "외상매출금 내역", "월별 거래처 원장 받아줘" 등 거래처계정내역 관련 요청 시 사용.
---

# 아마란스 ERP 거래처계정내역(ACC3030) 추출

회계 → 자동전표처리 → 전표/장부관리 → 거래처별장부 → **거래처계정내역**.
`@playwright/cli` + `proc/lib/pwc_amaranth.py`의 `acc303x_bootstrap` / `acc3030_query` 두 helper로 다중 계정과목 × 기간 데이터를 한 번에 받아 저장한다.

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
3. 직접 URL: `https://erp.doflab.com/#/A/ACC3030/ACC3030`
4. 동시성: 다른 `-s=` 세션과 별개 브라우저라 충돌 없음.

## 페이지 동작 — UI 우클릭 → "엑셀변환하기" 대신 API 직결

ERP 표 영역 우클릭 시 `엑셀변환하기` 팝업이 떠 .xlsx를 내려받을 수 있지만:
- **계정과목코드도움 팝업의 그리드는 canvas 렌더** — 다중선택을 DOM으로 못 건드림.
- OBT 날짜 picker는 입력 마스크가 강해 프로그램으로 값 변경이 안 됨.

따라서 SPA가 검색 시 호출하는 `POST /financial/ACC3030/00a00001` 를 직접 활용한다. 인증 헤더(`Authorization: Bearer ...`, `wehago-sign`, `timestamp`, `transaction-id`)는 SPA의 HTTP 클라이언트가 붙이는데, **서버는 body를 다시 서명 검증하지 않으므로** 한 번 캡처한 헤더로 다른 코드/날짜로 재호출 가능.

## 핵심 helper (`proc/lib/pwc_amaranth.py`)

| 함수 | 용도 |
|---|---|
| `acc303x_bootstrap(s, 'ACC3030', code='1080000')` | 페이지 진입 → seed 코드 입력 → 조회 클릭. 캡처 큐에 인증 헤더 적재 |
| `acc3030_query(s, codes, fdate, fill_dt, sub_ty='2', tr_codes=None)` | 캡처된 헤더를 재사용해 `vAcctCdStr=1080000\|1080001\|...\|` + 임의 기간으로 재요청. 응답 반환 |

`sub_ty`: `'1'`=계정별, `'2'`=세목별. 세목별이 사용자 요청의 디폴트.
`tr_codes`: 거래처코드 필터(공란이면 전체).

## 응답 row 컬럼

```
trCd       거래처코드           attrNm    거래처명
divCd      회계단위코드         divNm     회계단위명
acctCd     계정과목코드         acctNm    계정과목명
fillDt     승인일               fillNb    승인번호
rmkDc      적요(예: '[ 전 월 이 월 ]')
drAm       차변                 crAm      대변         janAm  잔액
deptCd/deptNm  부서             pjtCd/pjtNm  프로젝트
ctNb       전표번호             docuInfo  문서정보
baNb/depositor/bankNm  계좌
empCd/korNm  사원
```

## 표준 호출

```bash
python3 -c "
import sys, json; sys.path.insert(0, 'proc/lib')
from pathlib import Path
from pwc import S
from pwc_amaranth import acc303x_bootstrap, acc3030_query

s = S('amaranth')
acc303x_bootstrap(s, 'ACC3030')
data = acc3030_query(
    s,
    ['1080000','1080001','1080002','1080003','2590000','2590002'],
    fdate='20260501', fill_dt='20260531', sub_ty='2'
)
rows = (data or {}).get('resultData') or []
print(f'rows: {len(rows)}')
out = Path('output/ACC3030_거래처계정내역_2026-05.json')
out.write_text(json.dumps(data, ensure_ascii=False, indent=2))
print('saved:', out)
"
```

## Excel 변환 (system Python)

```bash
python3 - <<'EOF'
import json
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

OUT = Path('output')
src = OUT / 'ACC3030_거래처계정내역_2026-05.json'
data = json.loads(src.read_text())
rows = data.get('resultData') or []

HEADERS = [
    ('trCd','거래처코드'),('attrNm','거래처명'),
    ('divCd','회계단위코드'),('divNm','회계단위명'),
    ('acctCd','계정과목코드'),('acctNm','계정과목명'),
    ('fillDt','승인일'),('fillNb','승인번호'),('rmkDc','적요'),
    ('drAm','차변'),('crAm','대변'),('janAm','잔액'),
    ('deptCd','부서코드'),('deptNm','부서명'),
    ('pjtCd','프로젝트코드'),('pjtNm','프로젝트명'),
    ('ctNb','전표번호'),('docuInfo','문서정보'),
    ('baNb','계좌번호'),('depositor','예금주'),('bankNm','은행'),
    ('empCd','사원코드'),('korNm','사원명'),
]

wb = Workbook(); ws = wb.active; ws.title = '거래처계정내역'
ws.append([h[1] for h in HEADERS])
for c in ws[1]:
    c.font = Font(bold=True, color='FFFFFF')
    c.fill = PatternFill('solid', fgColor='305496')
    c.alignment = Alignment(horizontal='center', vertical='center')
for row in rows:
    ws.append([row.get(k) for k,_ in HEADERS])
for col in ws.columns:
    w = max((len(str(c.value or '')) for c in col), default=10)
    ws.column_dimensions[col[0].column_letter].width = min(max(w+2, 10), 40)
ws.freeze_panes = 'A2'
out = src.with_suffix('.xlsx')
wb.save(out); print('saved:', out)
EOF
```

## 자주 쓰는 계정과목코드

- `1080000` 외상매출금
- `1080001` 외상매출금_패키지
- `1080002` 외상매출금_(원/달러 파생 등)
- `1080003` 외상매출금_(특수)
- `2590000` 선수금
- `2590002` 선수금_패키지

월별 거래원장/패키지·선수금 대조용 ERP 이력을 받을 때는 외상매출금 계열만 받지 말고,
`1080000`, `1080001`, `1080002`, `1080003`, `2590000`, `2590002`를 함께 받아야 한다.
특히 `2590000`/`2590002`가 빠지면 선수금·패키지 차감과 입금 반제 데이터가 누락되어
원장 audit에서 수금/패키지 오류가 과다하게 발생할 수 있다.

## 함정 / 주의

- **bootstrap 후 headers 만료**: 같은 세션 내라면 수십 분은 재사용 가능. `_amaranth_latest_auth`가 None을 반환하면 재bootstrap.
- **bootstrap 후 `s.requests()` 초기화 금지**: 캡처를 비우는 방법은 없지만 세션 재시작 시 다시 bootstrap.
- **이번달 = 5/1~5/31**: `fill_dt`를 today로 두고 싶으면 명시적으로 인자 전달.
- **응답 첫 행은 종종 `[ 전 월 이 월 ]`** 캐리오버 — 합계 계산 시 `rmkDc` 필터링 필요.
- **로그인 풀린 상태** → `playwright-cli -s=amaranth open https://erp.doflab.com/ --persistent --headed` 로 재로그인.
- **`_amaranth_post`는 page 내 window.fetch 사용** — 세션이 올바른 ERP 탭에 있어야 함. `acc303x_bootstrap`이 자동으로 탭 전환.
