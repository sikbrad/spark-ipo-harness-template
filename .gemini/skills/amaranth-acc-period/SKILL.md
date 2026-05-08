---
name: amaranth-acc-period
description: 아마란스 ERP(erp.doflab.com) 거래처계정내역(ACC3030) 임의 기간 derive — 전체 history(2024~) 한 번 fetch → 임의 [start_dt, end_dt] 구간의 거래처 원장(전월이월 + 거래)을 코드가 직접 계산하여 manual ERP UI Export와 동일한 형식으로 출력. "거래처원장 임의기간", "Q1 거래처원장 만들어줘", "5월부터 7월까지 거래처내역", "이월잔액 직접 계산", "전체 기간 토대로 특정시점 거래처내역", "full-history 기반 거래처원장 derive" 등의 요청 시 사용.
---

# 아마란스 ERP — 임의 기간 거래처계정내역 derive

전체 회계기수(vGisu)의 raw transactions + 각 FY의 ERP-supplied 전기이월을 한 번에 fetch한 뒤, **코드가 직접 이월잔액을 계산**해 임의의 `[start_dt, end_dt]` 구간 거래처 원장을 produce.

기존 `amaranth-acc-ledger`와의 차이:
- `amaranth-acc-ledger`: 단일 기간으로 ERP에 직접 query (`acc3030_query`). 한 번 호출 = 한 기간.
- `amaranth-acc-period` (이 스킬): full-history 한 번 fetch → 메모리에서 임의 N개 기간 derive. 여러 기간 비교/시계열 분석에 유리.

## 도구 스택
- `proc/lib/pwc.py` — 세션 wrapper `S('amaranth')`
- `proc/lib/pwc_amaranth.py` — `acc303x_bootstrap`, `acc3030_history`, `acc3030_period_view`
- `proc/lib/pwc_amaranth_excel.py` — `build_acc3030_xlsx` (ERP UI 동일 형식)

## 전제
1. `playwright-cli -s=amaranth open https://erp.doflab.com/ --persistent --headed` (첫 1회 로그인).
2. `acc303x_bootstrap(s, 'ACC3030')` 으로 signed headers 캡처.

## 회계기수(vGisu) 매핑

이 ERP는 vGisu = year - 2011:
- vGisu=13 → 2024 FY (가장 빠른 접근 가능)
- vGisu=14 → 2025 FY
- vGisu=15 → 2026 FY
- vGisu≤12 → endpoint 거절 (회사 설립 2012지만 ERP 데이터는 2024부터)

각 FY는 **자체 전기이월** 보유 — 외화환산·결산분개·이월정리가 반영된 값으로 raw transactions 합산만으로는 못 만듦. `acc3030_history()`가 이 carry를 vGisu별로 보존.

## 전월이월 계산 공식

특정 기간 `[period_start, period_end]`의 carry per (거래처, 계정과목):

```
period_carry_dr = vGisu_carry(FY of period_start).dr + sum(raw_dr in [FY_start, period_start - 1])
period_carry_cr = vGisu_carry(FY of period_start).cr + sum(raw_cr in [FY_start, period_start - 1])
```

`period_start < 2024` (EARLIEST_FY_YEAR) 이면 vGisu carry = 0 (사전 데이터 없음 → 자연스럽게 raw 합 = 0이라 carry=0).

## 핵심 helper (`proc/lib/pwc_amaranth.py`)

| 이름 | 용도 |
|---|---|
| `acc3030_history(s, codes, end_year=None)` | vGisu 13(2024) ~ end_year 까지 모든 FY의 transactions + ERP carry를 한 번에 fetch. 반환: `{transactions, fy_carries, fetched_years}` |
| `acc3030_period_view(history, period_start, period_end)` | history dict + 기간 → derive된 row 리스트 (carry + 기간 transactions). `build_acc3030_xlsx`에 바로 feed |
| `EARLIEST_GISU` (=13) / `EARLIEST_FY_YEAR` (=2024) | 매핑 상수 |

## 표준 호출

### 1) 전체 history 한 번 fetch + 임의 기간 derive

```bash
python3 -c "
import sys; sys.path.insert(0, 'proc/lib')
from pathlib import Path
from pwc import S
from pwc_amaranth import acc303x_bootstrap, acc3030_history, acc3030_period_view
from pwc_amaranth_excel import build_acc3030_xlsx

s = S('amaranth')
acc303x_bootstrap(s, 'ACC3030')
hist = acc3030_history(s, ['1080000','1080001','1080002','1080003'], end_year=2026)
print(f'fetched: years={hist[\"fetched_years\"]} txs={len(hist[\"transactions\"])}')

# Derive 4월
rows = acc3030_period_view(hist, '20260401', '20260430')
build_acc3030_xlsx(rows, 'output/period_2026-04.xlsx')
print(f'4월: {len(rows)} rows')

# Derive Q1
rows = acc3030_period_view(hist, '20260101', '20260331')
build_acc3030_xlsx(rows, 'output/period_2026-Q1.xlsx')
print(f'Q1: {len(rows)} rows')

# Derive 1년치
rows = acc3030_period_view(hist, '20250501', '20260430')
build_acc3030_xlsx(rows, 'output/period_yearly.xlsx')
print(f'12개월: {len(rows)} rows')
"
```

### 2) 시계열 분석 — 월별 잔액 변화

```bash
python3 -c "
import sys; sys.path.insert(0, 'proc/lib')
from pwc import S
from pwc_amaranth import acc303x_bootstrap, acc3030_history, acc3030_period_view

s = S('amaranth')
acc303x_bootstrap(s, 'ACC3030')
hist = acc3030_history(s, ['1080000','1080001','1080002','1080003'], end_year=2026)

# 매월 1일 carry로 시계열
for month in ['20260101','20260201','20260301','20260401','20260501']:
    end = month[:6] + '99'  # 적당히 큰 일
    rows = acc3030_period_view(hist, month, '20260430')
    carry_dr = sum((r.get('drAm') or 0) for r in rows if '이 월' in (r.get('rmkDc') or ''))
    carry_cr = sum((r.get('crAm') or 0) for r in rows if '이 월' in (r.get('rmkDc') or ''))
    print(f'{month} 시점 전월이월: dr={carry_dr:,.0f} cr={carry_cr:,.0f} net={carry_dr-carry_cr:,.0f}')
"
```

### 3) 검증 — manual since-Apr와 비교

```bash
python3 -c "
import sys; sys.path.insert(0, 'proc/lib')
from pwc import S
from pwc_amaranth import acc303x_bootstrap, acc3030_history, acc3030_period_view
from pwc_amaranth_excel import build_acc3030_xlsx

s = S('amaranth')
acc303x_bootstrap(s, 'ACC3030')
hist = acc3030_history(s, ['1080000','1080001','1080002','1080003'])
rows = acc3030_period_view(hist, '20260401', '20260430')
build_acc3030_xlsx(rows, 'output/test/derived-Apr.xlsx')

from openpyxl import load_workbook
wb = load_workbook('output/test/derived-Apr.xlsx', read_only=True)
cur = None
for r in wb.active.iter_rows(values_only=True, min_row=2):
    if r[0] and r[0] != '총계': cur = r[0]
    if cur == '00136' and r[4] == '1080000' and '이 월' in str(r[8] or ''):
        print(f'00136 carry: dr={r[9]} cr={r[10]} bal={r[12]}')
        # Expected: dr=110,414,660 cr=76,025,972 bal=34,388,688
        break
"
```

## 응답 정확도

- **차변/이월 100% 일치** (`amaranth-acc-ledger` 단일 query와 동일).
- **거래 수**: ERP 실시간 입력으로 manual export 추출 시점과 +α 차이 (시점 race).
- **00136/1080000 carry**: derived 110,414,660 / 76,025,972 / 34,388,688 = manual since-Apr 정확 일치.

## 함정 / 주의

- **vGisu 거절**: 12 이하 무응답. `EARLIEST_GISU`(13) 미만은 fetch 안 됨. 그 이전 데이터 필요하면 closing entry가 vGisu=13 carry에 자동 반영됨 (수동 합산 불가).
- **결산 분개 비공개**: ERP는 raw txs로 노출 안 되는 결산 분개를 vGisu carry에 녹여줌. 그래서 raw 합산만으로 carry 못 만들고 ERP carry 필수.
- **bootstrap 헤더 만료**: 같은 세션 내라면 수십 분 재사용 가능. 401이면 재bootstrap.
- **`acc3030_history()`는 N년치 = N번 POST**: 3년치(2024-2026) ≈ 3 round-trip. 회계연도 늘어나면 비례 증가.
- **거래처 첫 등장 순서로 정렬**: `acc3030_period_view()` 결과는 transactions 첫 등장 trCd 순. ERP UI(거래처코드 ASC)와 살짝 다를 수 있어 정렬 차이는 발생 가능.
- **`acc3030_history()` 결과의 `fy_carries`는 tuple-key dict** — JSON 직렬화 시 변환 필요. `{f'{tr}|{acct}': v}` 처럼 key 변환 후 저장.
- **외화환산 entries**: raw txs로 노출되지만 결산 시 net=0으로 정리됨. derived 결과에 그대로 포함됨 — manual export와 일치.
