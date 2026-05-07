---
name: amaranth-acc-ledger
description: 아마란스 ERP(erp.doflab.com) 거래처계정내역(ACC3030) 다운로드 — 기간·계정과목 조건으로 거래처별 차변/대변/잔액 원장을 받아 JSON+Excel로 저장. "거래처계정내역", "ACC3030", "거래처원장", "외상매출금 내역", "월별 거래처 원장 받아줘" 등 거래처계정내역 관련 요청 시 사용.
---

# 아마란스 ERP 거래처계정내역(ACC3030) 추출

회계 → 자동전표처리 → 전표/장부관리 → 거래처별장부 → **거래처계정내역**.
`browser-harness` + `agent_helpers.py`의 `amaranth_acc303x_bootstrap` / `amaranth_acc3030_query` 두 helper로 다중 계정과목 × 기간 데이터를 한 번에 받아 저장한다.

## 사전 조건

1. browser-harness가 사용자의 Chrome에 attach 가능한 상태.
2. https://erp.doflab.com 에 로그인되어 있어야 함. 미로그인 시 `browser-harness` skill의 로그인 절차 참고.
3. 직접 URL `#/A/ACC3030/ACC3030` 으로 진입.

## 페이지 동작 — UI 우클릭 → "엑셀변환하기" 대신 API 직결

ERP 표 영역 우클릭 시 `엑셀변환하기` 팝업이 떠 .xlsx를 내려받을 수 있지만,

- **계정과목코드도움 팝업의 그리드는 canvas 렌더** — 다중선택을 DOM으로 못 건드림.
- OBT 날짜 picker는 입력 마스크가 강해 프로그램으로 값 변경이 안 됨.
- 우클릭 컨텍스트 메뉴 자동화는 운영 환경마다 좌표/타이밍에 민감.

따라서 SPA가 검색 시 호출하는 `POST /financial/ACC3030/00a00001` 를 직접 활용한다. 인증 헤더(`Authorization: Bearer ...`, `wehago-sign`, `timestamp`, `transaction-id`)는 SPA의 HTTP 클라이언트가 붙이는데, **서버는 body를 다시 서명 검증하지 않으므로** 한 번 캡처한 헤더로 다른 코드/날짜로 재호출 가능. 이 점을 이용해 한 번의 UI 검색으로 인증을 얻은 뒤, 4개 계정 × 한 달 데이터를 한 방에 받아온다.

## 핵심 helper

| 함수 | 용도 |
|---|---|
| `amaranth_acc303x_bootstrap('ACC3030', code='1080000')` | 페이지 진입 → seed 코드 입력 → 조회 클릭. 캡처 큐에 인증 헤더 적재 |
| `amaranth_acc3030_query(codes, fdate, fill_dt, sub_ty='2', tr_codes=None)` | 캡처된 헤더를 재사용해 `vAcctCdStr=1080000\|1080001\|...\|` + 임의 기간으로 재요청. 응답 `resultData` 리스트 반환 |

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
browser-harness -c "
import sys, json
from pathlib import Path
sys.path.insert(0, '/Users/gq/Developer/browser-harness/agent-workspace')
from agent_helpers import amaranth_acc303x_bootstrap, amaranth_acc3030_query

amaranth_acc303x_bootstrap('ACC3030')
data = amaranth_acc3030_query(
    ['1080000','1080001','1080002','1080003'],
    fdate='20260501', fill_dt='20260531', sub_ty='2'
)
rows = (data or {}).get('resultData') or []
print(f'rows: {len(rows)}')
out = Path('/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04/output/ACC3030_거래처계정내역_2026-05.json')
out.write_text(json.dumps(data, ensure_ascii=False, indent=2))
print('saved:', out)
"
```

## Excel 변환 (system Python)

`browser-harness`에는 openpyxl이 없으므로 시스템 python3로 별도 변환:

```bash
python3 - <<'EOF'
import json
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

OUT = Path('/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04/output')
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

코드 도움 팝업에서 `108`로 검색하면 후보 리스트가 나오나 그리드가 canvas라 코드 확인 후 직접 입력해야 함.

## 함정 / 주의

- **xhr capture 헤더 누락**: ACC3020/ACC3030는 일부가 `fetch`로 호출됨. `install_xhr_capture()` 가 fetch headers도 캡처하는지 확인 (현행 helper는 OK).
- **다른 탭으로 포커스 이동**: browser-harness가 가끔 비-ERP 탭에 attach. `amaranth_acc303x_bootstrap`은 자동으로 ERP 탭으로 switch.
- **bootstrap 후 `clear_captured()` 금지**: 캡처를 비우면 헤더 재사용 불가. helper 안에서 이미 적절히 처리.
- **이번달 = 5/1~5/31**: 사용자가 "이번달"로 말하면 월말까지 포함이 일반적. `fill_dt`를 today로 두고 싶으면 명시적으로 인자 전달.
- **응답 첫 행은 종종 `[ 전 월 이 월 ]`** 카리오버 — 합계 계산 시 `rmkDc` 필터링 필요.
