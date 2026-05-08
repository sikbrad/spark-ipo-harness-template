---
name: amaranth-acc-customer-ledger
description: 아마란스 ERP(erp.doflab.com) 거래처원장(ACC3010) — 거래처별 transaction-level 원장. 매월별로 거래·전월이월·월계·누계가 표시되는 SPA UI 형식 그대로 Excel로 출력. "거래처원장", "ACC3010", "거래처별 거래내역", "월별 누적 잔액", "원장 출력", "SPA 거래처원장 받아줘", "거래처 거래내역 timeline" 등 거래처원장(ACC3010) 요청 시 사용. **거래처계정내역(ACC3030)이 아닌 거래처원장(ACC3010) 전용** — 두 메뉴가 혼동되니 주의.
---

# 아마란스 ERP — 거래처원장 ACC3010

거래처별로 **transaction-level** 원장을 추출한다. SPA UI의 "거래처별장부 > 거래처원장 > 원장" 탭과 동일.

`amaranth-acc-ledger` (ACC3030)와의 차이:
- ACC3030 거래처계정내역: 기간 합계 + per-거래처 row 단위 (간략 집계)
- ACC3010 거래처원장 (이 스킬): 거래처별 시간순 transactions + 월계 + 누계 marker. 매월 SPA가 내부 chunking.

## 도구 스택
- `proc/lib/pwc.py` — 세션 wrapper `S('amaranth')`
- `proc/lib/pwc_amaranth.py` — `acc3010_bootstrap`, `acc3010_history`, `acc3010_period_view`
- `proc/lib/pwc_amaranth_excel.py` — `build_acc3010_xlsx` (31-column 형식, 월계/누계 마커 자동 삽입)

## 핵심 endpoint

`POST /financial/acc3010/getGridDetailTab2`

Body params (signed `wehago-sign` HMAC, **body-content-locked** — 변경 시 FAIL):
- `vDivCds: "1000|"` 회계단위
- `vGisu: 15` 회계기수 (year - 2011)
- `vDtFrom: "20260101"` FY start
- `vAcctCds: "1080000|"` 계정과목 (multi 가능 — pipe-separated)
- `vFillDtFrom`/`vFillDtTo` 기간
- `tab: "2"` 원장 탭 (1=잔액, 2=원장, 3=총괄잔액, 4=총괄내용)
- `isAllTrCd: "0"` 코드입력 거래처만 (1=모든 거래처)
- `nocodeOpt: "3"` 코드누락 제외
- `vTDrcrFg: "1"` 차변기준
- `tab="2"` 필수 — 다른 탭은 다른 endpoint(Tab1/3/4)

**중요**: SPA가 자동으로 **매월 별도 요청**을 fire한다. 1년 범위 조회 시 12개 월별 요청이 쪼개져 발생. helper가 이 chunking을 모두 capture+merge.

## 회계기수(vGisu) 매핑

`vGisu = year - 2011` (DOF 회사 설립 2012):
- 13 → 2024
- 14 → 2025
- 15 → 2026
- ≤12 거절

## body-locked 서명 → UI driving 필수

`/financial/acc3010/getGridDetailTab2` 의 wehago-sign은 **body 내용에 잠긴** HMAC. body 한 글자라도 바꿔서 replay 시 `resultCode: -1, resultMsg: FAIL`. 그래서 매 fetch마다 SPA UI를 driving하여 새 서명을 받아야 한다.

`acc3030`(거래처계정내역) endpoint는 body 변경 replay 가능 — 두 endpoint가 다름.

## 핵심 helper

| 이름 | 용도 |
|---|---|
| `acc3010_bootstrap(s, code='1080000')` | ACC3010 진입, 원장 탭 클릭, 계정과목 시드, 조회 클릭 → 첫 capture 확보 |
| `acc3010_history(s, codes, end_year)` | EARLIEST_FY_YEAR(2024)~end_year 모든 FY를 UI driving으로 fetch (각 연도마다 12개 월별 응답 자동 merge). 반환: `{transactions, fy_carries, fetched_years}` |
| `acc3010_period_view(history, start, end)` | 임의 기간 row 리스트 derive. 전월이월 = vGisu carry + 사전 transactions 합산 |
| `_acc3010_drive_query(s, fdate_from, fdate_to, settle_seconds=10)` | 단일 연도 driving 후 인덱스 리스트 반환 (저수준) |

| 이름 | 용도 |
|---|---|
| `pwc_amaranth_excel.build_acc3010_xlsx(rows, path)` | manual UI export와 동일한 31열 + 월계 + 누계 + 거래처 합계 형식 |

## 표준 호출

### 1) 4월 거래처원장

```bash
python3 -c "
import sys; sys.path.insert(0, 'proc/lib')
from pathlib import Path
from pwc import S
from pwc_amaranth import acc3010_bootstrap, acc3010_history, acc3010_period_view
from pwc_amaranth_excel import build_acc3010_xlsx

s = S('amaranth')
acc3010_bootstrap(s, code='1080000')
hist = acc3010_history(s, ['1080000'])
rows = acc3010_period_view(hist, '20260401', '20260430')
build_acc3010_xlsx(rows, 'output/ACC3010_원장_2026-04.xlsx')
"
```

### 2) since-life-of-data 전체 history

```bash
python3 -c "
...
hist = acc3010_history(s, ['1080000'])
# fdate < EARLIEST_FY_YEAR(2024) → carry=0, all txs
rows = acc3010_period_view(hist, '20100101', '20260430')
build_acc3010_xlsx(rows, 'output/ACC3010_원장_since-2010.xlsx')
"
```

### 3) 다년치 — Q1 2025

```python
hist = acc3010_history(s, ['1080000'], end_year=2026)
rows = acc3010_period_view(hist, '20250101', '20250331')
build_acc3010_xlsx(rows, 'output/ACC3010_원장_2025-Q1.xlsx')
```

## 출력 컬럼 (31)

```
0:날짜  1:적요  2:차변  3:대변  4:잔액
5:거래처코드  6:거래처명  7:거래처분류코드  8:거래처분류명
9:적요구분 (0=carry / 1=tx / 2=월계 / 3=누계)
10:계좌번호  11:금융기관  12:예금주
13:작성일  14:작성번호  15:분개순번  16:승인번호
17:회계단위코드  18:회계단위명  19:부서코드  20:부서명
21:사원코드  22:사원명  23:계정과목코드  24:계정과목명
25:프로젝트코드  26:프로젝트명  27:사용부서코드  28:사용부서명
29:관리사원코드  30:관리사원명
```

월계/누계 marker는 `build_acc3010_xlsx`가 자동 삽입.

## 함정 / 주의

- **body-locked 서명**: ACC3010은 ACC3030과 달리 body 변경 replay 불가. UI driving만 가능 → 시간 더 걸림 (매 연도마다 12 monthly request).
- **`_acc3010_drive_query` settle_seconds**: 월별 chunk가 모두 끝나길 기다려야 함. 12개월/대용량이면 10s+ 필요. 기본 10s.
- **multi-code 시드**: bootstrap은 단일 code만 시드. 4개 코드(1080000/01/02/03) 모두 query하려면 각 fetch 전에 codepicker UI 조작 필요 — 미커버. 우선 단일 code로 사용 권장.
- **거래처 carry 정확도**: vGisu별 carry는 ERP가 직접 반환 — `acc3010_history`가 첫 월 응답의 carry만 채택해 fy_carries로 보존. derived 4월 carry = vGisu=15 carry + Jan-Mar raw txs.
- **2024 carry = 2023-end opening**: vGisu=13의 carry는 2023년 12월 31일 잔액 (회사 설립 2012, ERP 데이터는 2024부터지만 ERP가 2023-end opening 잔액을 보존).
- **2026-04 period derive vs ACC3030 derive**: ACC3010은 외화환산·조정 분개를 별도 ledger 라인으로 노출 — ACC3030의 같은 거래처 carry보다 dr/cr 합계가 클 수 있음. **두 endpoint는 다른 ledger view이며 내부 가산이 다름**.
- **manual 비교**: manual since-2010 ACC3010 export(42706 rows, 1080000 only)와 derived(60209 rows, 1080000 only)의 차이는 외화환산 entry 처리·월계/누계 marker 산정 방식 차이. 거래처 분포·금액 합계는 거의 일치.
- **로그인 풀린 상태 + 이차인증**: 세션 만료 시 `playwright-cli -s=amaranth open ... --persistent --headed` + Amaranth10 모바일앱 QR 인증 필요.
- **월별 chunked 응답**: SPA 디자인. 우리 helper가 모든 월 응답을 자동 merge하지만, 한 번의 click에 12개 monthly request fire → settle_seconds 시간 소요.
