---
name: amaranth-acc-balance
description: 아마란스 ERP(erp.doflab.com) 거래처계정잔액(ACC3020) 다운로드 — 기준일·계정과목 조건으로 거래처별 잔액(합계 + 코드별)을 받아 JSON+Excel로 저장. playwright-cli 기반. "거래처계정잔액", "ACC3020", "잔액조회", "외상매출금 잔액", "월말 잔액 받아줘", "거래처별 미수 잔액" 등 거래처계정잔액 관련 요청 시 사용.
---

# 아마란스 ERP 거래처계정잔액(ACC3020) 추출

회계 → 자동전표처리 → 전표/장부관리 → 거래처별장부 → **거래처계정잔액**.
`@playwright/cli` + `proc/lib/pwc_amaranth.py`의 `acc303x_bootstrap` / `acc3020_query` 두 helper로 다중 계정과목 × 기준일 잔액을 한 번에 받아 저장한다.

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
3. 직접 URL: `https://erp.doflab.com/#/A/ACC3020/ACC3020`
4. 동시성: 다른 `-s=` 세션과 별개 브라우저라 충돌 없음.

## 페이지 동작 — API 직결

ACC3030과 같은 이유(canvas 그리드, 마스크 입력, 우클릭 자동화 불안정)로 API 직결을 사용한다. SPA가 검색 시 호출하는 `POST /financial/ACC3020/00a00001` 의 인증 헤더는 한 번 캡처해두면 body 변경 후 재사용 가능.

## 핵심 helper (`proc/lib/pwc_amaranth.py`)

| 함수 | 용도 |
|---|---|
| `acc303x_bootstrap(s, 'ACC3020', code='1080000')` | 페이지 진입 → seed 코드 입력 → 조회 클릭. 캡처 큐에 인증 헤더 적재 |
| `acc3020_query(s, codes, fill_dt, fdate=None, sub_ty=1, tr_codes=None)` | 캡처 헤더 재사용해 임의 코드/기준일 잔액 재요청. 응답 반환 |

`fdate`: 누적 기간 시작(생략 시 해당 연도 1/1).
`fill_dt`: 잔액 기준일(YYYYMMDD).
`sub_ty`: 1=계정별(기본), 2=세목별.

## 응답 row 컬럼

```
trCd       거래처코드           attrNm     거래처명
trFg       구분                 regNb      사업자등록번호
acctAm0    합계 잔액
acctAm1    codes[0] 잔액 (예: 1080000)
acctAm2    codes[1] 잔액 (예: 1080001)
acctAm3    codes[2] 잔액 (예: 1080002)
acctAm4    codes[3] 잔액 (예: 1080003)
baNb/depositor/bankNm  계좌
```

`acctAm{i+1}` 매핑 순서는 `query` 호출 시 넘긴 codes 순서 그대로. Excel 헤더 만들 때 코드명을 그대로 표기하면 됨.

## 표준 호출

```bash
python3 -c "
import sys, json; sys.path.insert(0, 'proc/lib')
from pathlib import Path
from pwc import S
from pwc_amaranth import acc303x_bootstrap, acc3020_query

s = S('amaranth')
acc303x_bootstrap(s, 'ACC3020')
data = acc3020_query(
    s,
    ['1080000','1080001','1080002','1080003'],
    fill_dt='20260531', sub_ty=1
)
rows = (data or {}).get('resultData') or []
print(f'rows: {len(rows)}')
out = Path('output/ACC3020_거래처계정잔액_2026-05-31.json')
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
src = OUT / 'ACC3020_거래처계정잔액_2026-05-31.json'
data = json.loads(src.read_text())
rows = data.get('resultData') or []

CODES = ['1080000','1080001','1080002','1080003']
HEADERS = [
    ('trCd','거래처코드'),('attrNm','거래처명'),('regNb','사업자등록번호'),
    ('acctAm0','합계 잔액'),
] + [(f'acctAm{i+1}', f'{c} 잔액') for i,c in enumerate(CODES)] + [
    ('baNb','계좌번호'),('depositor','예금주'),('bankNm','은행'),
]

wb = Workbook(); ws = wb.active; ws.title = '거래처계정잔액'
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

## "이번달" 해석

- 잔액은 시점 데이터이므로 `fill_dt = 월말 (예: 20260531)` 권장.
- 월중 시점 잔액이 필요하면 today 사용. 사용자가 명시 안 했으면 월말로 가는 게 ERP 관행.
- `fdate`는 누적 시작점인데 응답 잔액은 `acctAm0=fdate~fill_dt 누적 차변-대변`. 1년 단위로 보고 싶으면 1/1 (default), 월간 변동만 보고 싶으면 1일.

## 함정 / 주의

- **잔액 0 거래처는 응답에 포함됨** — 970+건 중 800+이 non-zero, 나머지는 잔액 0 정리거래처. 필요시 `acctAm0 != 0` 필터링.
- **acctAm 컬럼 순서**: query 호출 시 codes 순서 그대로 매핑. 매핑 표를 출력에 함께 적어두면 사용자가 헷갈리지 않음.
- **bootstrap 헤더 만료**: 같은 세션 내라면 수십 분은 재사용 가능. 401이 뜨면 재bootstrap.
- **합계 검증**: `sum(acctAm0)` 가 ERP 화면 하단 `합계` 와 일치해야 함. 일치 안 하면 의도치 않은 필터가 걸렸는지 확인.
- **`_amaranth_post`는 page 내 window.fetch 사용** — 세션이 올바른 ERP 탭에 있어야 함. `acc303x_bootstrap`이 자동으로 탭 전환.
- **로그인 풀린 상태** → `playwright-cli -s=amaranth open https://erp.doflab.com/ --persistent --headed` 로 재로그인.
