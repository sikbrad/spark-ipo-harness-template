# Amaranth ERP 회계 스킬 확장 (2026-05-08~09)

## 목표

기존 `/amaranth-acc-ledger` (ACC3030 거래처계정내역) + `/amaranth-acc-balance` (ACC3020 거래처계정잔액) 위에 두 개 신규 스킬 추가:
1. **`/amaranth-acc-period`** — 거래처계정내역(ACC3030) 임의 기간 derive (이월잔액 코드 계산)
2. **`/amaranth-acc-customer-ledger`** — 거래처원장(ACC3010) transaction-level 원장

## 1. `/amaranth-acc-period` (ACC3030 derive)

### 동기

`/amaranth-acc-ledger`는 단일 기간을 ERP에 직접 query — 매번 호출 = 재 fetch. 시계열 분석/임의 기간 derive를 위해 **전체 history를 한 번 fetch + 메모리에서 임의 기간 derive** 필요.

### 핵심 구현 ([proc/lib/pwc_amaranth.py](../lib/pwc_amaranth.py))

| 함수 | 동작 |
|---|---|
| `acc3030_history(s, codes, end_year)` | vGisu 13(2024) ~ end_year 모든 FY를 한 번에 fetch. 반환: `{transactions, fy_carries, fetched_years}` |
| `acc3030_period_view(history, start, end)` | history → 임의 기간 row 리스트. ERP carry + 사전 transactions 가산 |

### 이월잔액(전월이월) 공식

```
period_carry_dr = vGisu_carry(FY of period_start).dr + sum(raw_dr in [FY_start, period_start - 1])
period_carry_cr = vGisu_carry(FY of period_start).cr + sum(raw_cr in [FY_start, period_start - 1])
```

### 핵심 발견 — vGisu 매핑

`vGisu = year - 2011` (DOF 회사 설립 2012):
- 13 → 2024 (가장 빠른 접근)
- 14 → 2025
- 15 → 2026
- ≤12 → endpoint 거절 (`resultData: 0` 반환)

### 검증

- 00136/1080000 carry: derived `dr=110,414,660 cr=76,025,972 bal=34,388,688` = manual 정확 일치
- 4월/Q1/12개월치 derive 모두 정상

## 2. `/amaranth-acc-customer-ledger` (ACC3010 거래처원장)

### 동기

거래처원장 ACC3010는 거래처별 **transaction-level** 원장 + 월계/누계 marker (SPA UI 형식). ACC3030 거래처계정내역(요약)과 별개의 view.

### Endpoint

`POST /financial/acc3010/getGridDetailTab2`

### 핵심 발견 1 — body-locked HMAC

ACC3030는 body 변경 후 replay 가능. 그러나 **ACC3010는 body 한 글자라도 바꿔서 replay 시 `resultCode:-1 FAIL`**. wehago-sign이 body 내용에 잠긴 HMAC.

→ 해결: 매 fetch마다 SPA UI driving (date 입력 + 조회 클릭)으로 fresh signed request 받기.

### 핵심 발견 2 — SPA 자동 월별 chunking

원장 탭 1년 조회 시 SPA가 자동으로 **12개 monthly request fire**. 1년 한 번에 못 받음. helper가 settle window 기다린 후 모든 월별 응답 merge.

```python
def _acc3010_drive_query(s, fdate_from, fdate_to, settle_seconds=10):
    """월별 chunked 응답 모두 capture + return idx list"""
```

### 핵심 발견 3 — 세목별 모드 (`vPrtFg=2`) 필수

이게 가장 중요한 발견.

**기본(계정별, vPrtFg=1) 모드의 문제**: 1080000(외상매출금) query 시 서버가 **모든 외상매출금 하위 세목**(1080001 패키지 / 1080002 렌탈료 / 1080003 워런티) entries까지 1080000 라벨로 함께 반환 → manual export 대비 ~1.5x rows.

**예시**: 01363 거래처 2025-09:
- 계정별 모드 query → 20 transactions (Sales19684 = 1080001 entries 포함)
- 세목별 모드 query → 1 transaction (`OD202508200022`만, 정확)

**세목별 모드 전환 자동화** ([acc3010_bootstrap](../lib/pwc_amaranth.py)):
```
1. 원장 탭 클릭
2. 계정선택 dropdown(text="계정별") → chevron button 클릭
3. 펼침 옵션 중 "세목별" 클릭
4. 1080000 입력 → Enter → 조회 클릭
```

DOM:
- dropdown wrapper: `[class*="OBTDropDownList_default"]` text=계정별
- chevron: `<button>` inside wrapper
- option list: `<li>` text=세목별

### 검증

| | Manual_일반 (1080000) | Auto v1 (계정별) | Auto v2 (세목별) |
|---|---|---|---|
| 행수 | 42,707 | 60,209 | **44,732** |
| 거래처 | 1,103 | 1,320 | **1,117** |
| 차이 vs manual | — | +17,502 | **+2,025** |

차이 +2,025은 manual 추출 ~ auto 실행 사이 ERP 신규 입력 + 거래처 14개 추가.

### 시도하고 실패한 옵션들

| 옵션 | 결과 |
|---|---|
| body 변경 replay | ❌ wehago-sign body-locked → FAIL |
| nocodeOpt=3 (코드누락 제외) | ❌ 무관 |
| 1080001 직접 type | ❌ codepicker 자동 매칭 |
| rmkDck 후처리 분류 | ❌ 빈 rmkDck가 가장 큰 그룹 |
| **세목별 dropdown** | ✅ 정답 |

## 3. ACC3010 Excel formatter ([proc/lib/pwc_amaranth_excel.py](../lib/pwc_amaranth_excel.py))

`build_acc3010_xlsx(rows, path)` — 31열 manual UI export 형식:
```
0:날짜  1:적요  2:차변  3:대변  4:잔액
5:거래처코드  6:거래처명  7:거래처분류코드  8:거래처분류명
9:적요구분 (0=carry / 1=tx / 2=월계 / 3=누계)
10:계좌번호  ...  30:관리사원명
```

월계/누계 marker는 자동 삽입.

## 4. 등록 위치

| 스킬 | 경로 |
|---|---|
| `/amaranth-acc-period` | [.claude/skills/amaranth-acc-period/SKILL.md](../../.claude/skills/amaranth-acc-period/SKILL.md) |
| `/amaranth-acc-customer-ledger` | [.claude/skills/amaranth-acc-customer-ledger/SKILL.md](../../.claude/skills/amaranth-acc-customer-ledger/SKILL.md) |

`.gemini/skills/` 양쪽 미러링 + [CLAUDE.md](../../CLAUDE.md) 표 갱신 완료.

## 5. 알려진 한계

### `/amaranth-acc-period`
- ACC3030 endpoint 한계: vGisu별 fetch 필요 (한 호출에 다년치 못 받음)
- vGisu carry는 raw txs로 노출 안 되는 결산 분개를 포함 → 별도 fetch 필수

### `/amaranth-acc-customer-ledger`
- body-locked HMAC → 매 연도 12 monthly request → 1년치 ≈10s, 3년치 ≈30s
- multi-code 시드 미커버 — 1080001/02/03 동시 fetch는 codepicker UI 추가 조작 필요 (현재 단일 code)
- 거래처 carry 정확도: vGisu별 carry는 ERP가 직접 반환, 첫 월 응답의 carry만 채택

## 6. 후속 과제

- [ ] ACC3010 multi-code 시드 — codepicker dialog 자동화
- [ ] ACC3030 `acc3030_history` 결과의 tuple-key dict → JSON 직렬화 변환 helper
- [ ] 시계열 잔액 변화 분석 helper (월별 carry 추이)
- [ ] 외화환산 entry 별도 분류·요약 helper

## 참조

- 마이그레이션 배경: [playwright-cli-migration.md](playwright-cli-migration.md)
- 부트스트랩: [playwright-cli-bootstrap.md](playwright-cli-bootstrap.md)
