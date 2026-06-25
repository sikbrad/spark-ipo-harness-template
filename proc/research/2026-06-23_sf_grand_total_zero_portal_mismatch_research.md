# Salesforce Grand Total 0 vs 포탈 금액 불일치 리서치

작성일: 2026-06-23

> 범위 주의: 이 문서는 SF `Grand Total = 0` 전체를 넓게 진단한 문서다. 사용자가 지적한 `무상` 키워드 중심의 focused 목록은 `proc/research/2026-06-23_sf_grand_total_zero_musang_corrected_research.md`를 기준으로 본다.

## 결론

이전 `무상` 판정에서 `grand total`을 포탈 `Order.totalAmount`로 해석한 것은 거래원장/계약잔액 문제에는 맞지 않았다. Salesforce 화면 스크랩 데이터의 `grand_total` 필드를 기준으로 다시 대조한 결과, Salesforce `Grand Total = 0`인데 포탈은 `PAID`이고 포탈 총액이 0이 아닌 주문이 1,637건 있다.

사용자가 지적한 `Sales14091`, `Sales19737`은 둘 다 이 목록에 포함된다.

| Sales | SF Grand Total | 포탈 totalAmount | 분류 | 메모 |
|---|---:|---:|---|---|
| `Sales14091` | 0 | 755,000 | PKG/프로모션 차감 | `무상(Sales13813 프로모션)` |
| `Sales19737` | 0 | 310,000 | PKG/프로모션 차감 | `프로모션 차감(Sales14074)`, `동기화x`, `계산서x` |

## 기준 변경

이번 대조의 기준:

- 주 기준: `/Users/gq/works/projs/crm-migration/dataset/fetched/sf_sales_infos_org1.jsonl` 의 `grand_total`
- 비교 대상: 포탈 로컬 DB `Order.importSource='sf'`
- 핵심 불일치: `sf.grand_total = 0` 이고 포탈 `orderType='PAID'`, 포탈 `totalAmount != 0`

중요한 차이:

- 로더용 SF Opportunity JSON에는 Opportunity 화면의 `Grand Total` 필드가 없다.
- 포탈 적재 코드는 Opportunity Line Item 단가 합산(`oppAggregates.totalAmount`)을 주문 `totalAmount`로 사용한다.
- 따라서 SF 화면 Grand Total은 0인데 제품 라인 단가는 남아 있는 프로모션/무상/차감 주문이 포탈에서는 금액 있는 `PAID`로 들어간다.

관련 코드:

- `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dofing-order-portal-data-3-az/src/loaders/sf-crm/orders.ts:121`
  - `const agg = oppAggregates.get(o.Id);`
- `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dofing-order-portal-data-3-az/src/loaders/sf-crm/orders.ts:122`
  - `const totalAmount = agg?.totalAmount ?? 0;`
- `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dofing-order-portal-data-3-az/src/loaders/sf-crm/order-products.ts:58`
  - `agg.totalAmount += unitPrice * qty;`

## 집계

Salesforce 스크랩 19,745건 중 `Grand Total = 0`은 5,677건이다.

| 포탈 대조 상태 | 건수 |
|---|---:|
| 포탈 `PAID` + 포탈 금액 있음 | 1,637 |
| 포탈 `PAID` + 포탈 금액 0 | 4,034 |
| 포탈 주문 미존재 | 6 |

포탈 금액 있음 1,637건의 맥락 분류:

| 맥락 | 건수 |
|---|---:|
| PKG/프로모션/차감 | 1,028 |
| SF Grand Total 0 외 근거 약함, UI 재확인 필요 | 355 |
| AS/보증/교체/운영 이슈 | 210 |
| 일반 무상/샘플 근거 | 42 |
| 렌탈/대여 | 2 |

우선순위:

| 우선순위 | 건수 | 의미 |
|---|---:|---|
| `P0_LEDGER_PKG_PROMOTION_ZERO_DEDUCTION` | 1,028 | 거래원장/계약잔액에서 0원 차감 또는 보정 대상으로 봐야 할 가능성이 큼 |
| `P0_PORTAL_FREE_RECLASSIFY_REVIEW` | 42 | 일반 무상/샘플로 포탈 FREE 재분류 검토 |
| `P1_AS_WARRANTY_ZERO_REVIEW` | 210 | AS/보증/교체 0원 처리 검토 |
| `P1_RENTAL_ZERO_REVIEW` | 2 | 렌탈/대여 0원 처리 검토 |
| `P2_SF_GRAND_TOTAL_ZERO_UI_VERIFY` | 355 | SF Grand Total 0은 맞지만 무상/프로모션 근거가 약해 화면 재확인 필요 |
| `P3_ORDER_TYPE_PAID_ZERO_AMOUNT_REVIEW` | 4,034 | 포탈 금액은 이미 0이나 `PAID` 상태 |
| `P2_PORTAL_MISSING_REVIEW` | 6 | 포탈 주문 미존재 |

## 거래원장/계약잔액 영향

`Sales14091`, `Sales19737` 같은 케이스는 일반 무상 주문 목록에서는 제외했지만, 거래원장/계약잔액 관점에서는 별도로 처리해야 한다. SF Grand Total이 0이므로 해당 주문을 계약잔액 차감액으로 쓰면 다우/포탈 잔액이 틀어질 수 있다.

따라서 거래원장 쪽에서는 다음 기준이 필요하다.

1. SF `grand_total=0`이면 포탈 제품 라인 단가 합산액을 그대로 차감액으로 쓰지 않는다.
2. PKG/프로모션/차감 맥락이면 계약잔액에서는 0원 사용행 또는 보정행으로 처리한다.
3. 일반 무상/샘플이면 포탈 주문 타입 `FREE` 재분류와 제품 무상사유 보강을 검토한다.
4. AS/보증/교체는 일반 무상이 아니라 AS/보증 0원 처리로 분리한다.
5. 맥락 근거가 약한 355건은 SF 화면 또는 원천 필드를 재확인한 뒤 적용한다.

## 산출물

출력 폴더:

`/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04/output/research/sf-grand-total-zero-mismatch-20260623`

파일:

- `sf_grand_total_zero_mismatch_cases.xlsx`: summary, mismatch, actionable, PKG/pro모션, unknown review 시트 포함
- `sf_grand_total_zero_portal_amount_mismatch.csv`: 포탈 금액 있음 1,637건
- `sf_grand_total_zero_actionable_context_mismatch.csv`: 맥락 근거 있는 불일치 1,282건
- `sf_grand_total_zero_pkg_promotion_mismatch.csv`: PKG/프로모션 차감 1,028건
- `sf_grand_total_zero_unknown_context_review.csv`: SF 화면 재확인 필요 355건
- `sf_grand_total_zero_portal_paid_zero_amount.csv`: 포탈 금액 0이나 `PAID`인 4,034건
- `sf_grand_total_zero_all.csv`: SF Grand Total 0 전체 5,677건
- `sf_grand_total_zero_summary.json`: 집계 요약

## 검증

- `Sales14091`: `sfGrandTotalRaw=KRW 0`, 포탈 `totalAmount=755000.000`, `P0_LEDGER_PKG_PROMOTION_ZERO_DEDUCTION`
- `Sales19737`: `sfGrandTotalRaw=KRW 0`, 포탈 `totalAmount=310000.000`, `P0_LEDGER_PKG_PROMOTION_ZERO_DEDUCTION`
- CSV 행 수:
  - 전체 SF Grand Total 0: 5,677
  - 포탈 금액 불일치: 1,637
  - 맥락 근거 있는 불일치: 1,282
  - PKG/프로모션 차감: 1,028
  - 화면 재확인 필요: 355
