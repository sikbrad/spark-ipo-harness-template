# SF Grand Total 0 + `무상` 키워드 정정 리서치

작성일: 2026-06-23

## 결론

사용자 지적이 맞다. 거래원장/계약잔액 오류를 볼 때는 포탈 `Order.totalAmount`가 아니라 Salesforce 화면 스크랩의 `Grand Total`을 기준으로 봐야 한다.

이 기준으로 다시 자른 결과는 다음과 같다.

| 범위 | 건수 | 해석 |
|---|---:|---|
| 기존 `무상/무료` 원천 후보 중 SF `Grand Total = 0` | 3,443 | 너무 넓은 원천 풀 |
| 위 후보 중 포탈 금액이 남아 있는 건 | 788 | 실제 거래원장 오류 후보가 될 수 있는 풀 |
| 포탈 금액 불일치 중 literal `무상/무료`가 보이는 건 | 609 | 사용자가 말한 `무상` 키워드 중심 후보 |
| `무상/무료` 후보에서 PKG/AS/워런티/렌탈/내부 테스트 등을 제거하고 프로모션 무상은 유지한 건 | 453 | `Sales14091` 포함. 장부 0원 처리 검토 대상 |
| literal `무상`은 없지만 `프로모션 차감` 또는 `동기화x/계산서x`인 예외 후보 | 265 | `Sales19737` 포함. 별도 장부 0원 처리 검토 대상 |
| 엄격한 일반 무상 참고 목록 | 99 | 포탈 금액도 이미 0이라 이번 오류 해소 대상은 아님 |

따라서 “100건 내외”는 엄격한 일반 무상 참고 목록 숫자와는 맞지만, 사용자가 지적한 `Sales14091`까지 포함하려면 프로모션 무상/차감 케이스를 별도 버킷으로 둬야 한다. 그 경우 오류 후보는 100건이 아니라 수백 건 단위다.

## 사용자 지정 사례 확인

| Sales | SF Grand Total | 포탈 금액 | literal `무상` 후보 | 장부 0원 후보 | 메모 |
|---|---:|---:|---|---|---|
| `Sales14091` | KRW 0 | 755,000 | 포함 | 포함 | `무상(Sales13813 프로모션)`. 기존 로직의 프로모션 일괄 제외가 과했다. |
| `Sales19737` | KRW 0 | 310,000 | 미포함 | 예외 후보 포함 | `프로모션 차감(Sales14074)`, `동기화x`, `계산서x`. literal `무상`은 없음. |

## 기준

주 기준:

- Salesforce 스크랩: `/Users/gq/works/projs/crm-migration/dataset/fetched/sf_sales_infos_org1.jsonl`
- 필드: `grand_total`
- 포탈 대조: Salesforce import 주문의 포탈 금액/주문명/결재조건/비고

이번 문서의 핵심 조건:

1. SF `Grand Total = 0`
2. 포탈에는 금액이 남아 있음
3. `무상/무료` 또는 사용자가 지적한 `프로모션 차감`, `동기화x`, `계산서x` 신호를 검토
4. 주문명 `PKG`/`package`, 워런티 연장, AS/교체/수리, 렌탈/대여, 내부 테스트/샘플/전시 등은 별도 제외

주의: 프로모션은 두 갈래로 나눴다.

- `Sales14091`처럼 결재조건 자체가 `무상(...프로모션)`이고 SF Grand Total이 0이면 장부 0원 처리 후보로 유지
- 주문명에 `PKG`, `package`, 패키지성 프로모션이 있으면 사용자의 기존 지시에 따라 일반 무상에서 제외

## 산출물

출력 폴더:

`/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04/output/research/sf-grand-total-zero-musang-corrected-20260623`

주요 파일:

- `summary.json`: 전체 집계와 `Sales14091`, `Sales19737` 검증 결과
- `01_focused_prior_musang_keyword_sf_grand_total_zero_all.csv`: 기존 `무상/무료` 후보 중 SF Grand Total 0 전체 3,443건
- `02_focused_prior_musang_keyword_sf_grand_total_zero_portal_amount_mismatch_788.csv`: 위 후보 중 포탈 금액 불일치 788건
- `04_literal_musang_or_muryo_sf_gt_zero_portal_amount_mismatch_all_609.csv`: literal `무상/무료`가 보이는 포탈 금액 불일치 609건
- `05_literal_musang_ledger_zero_candidates_include_promotion_exclude_pkg_as_internal_453.csv`: `Sales14091` 포함, 장부 0원 처리 검토 대상 453건
- `06_literal_musang_excluded_by_user_rules_156.csv`: PKG/AS/워런티/렌탈/내부 테스트 등 제외 156건
- `08_promo_chagam_or_no_sync_ledger_zero_candidates_exclude_pkg_as_internal_265.csv`: `Sales19737` 포함, literal `무상` 없는 프로모션 차감/동기화x 예외 후보 265건

## 원인

포탈 적재 쪽은 SF 화면의 Opportunity `Grand Total`이 아니라 제품 라인 단가 합계를 주문 총액으로 사용한다.

- `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dofing-order-portal-data-3-az/src/loaders/sf-crm/orders.ts:121`
  - `const agg = oppAggregates.get(o.Id);`
- `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dofing-order-portal-data-3-az/src/loaders/sf-crm/orders.ts:122`
  - `const totalAmount = agg?.totalAmount ?? 0;`
- `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dofing-order-portal-data-3-az/src/loaders/sf-crm/order-products.ts:58`
  - `agg.totalAmount += unitPrice * qty;`

이 구조 때문에 SF 화면 Grand Total은 0인데 라인 단가가 남아 있는 무상/프로모션/차감 주문이 포탈에서는 금액 있는 `PAID` 주문으로 들어간다.

## 해소 방향

단순히 “SF Grand Total 0이면 전부 `FREE`”로 바꾸면 안 된다. PKG, 워런티, AS, 렌탈, 내부 테스트까지 섞여 있기 때문이다.

권장 버킷:

1. `FREE_GENERAL`: 일반 무상 제공. 엄격 참고 목록 99건 계열.
2. `PROMOTION_ZERO_DEDUCTION`: `Sales14091`, `Sales19737`처럼 SF Grand Total 0이므로 거래원장/계약잔액 차감액은 0으로 봐야 하는 프로모션/차감 계열.
3. `EXCLUDE_NON_FREE`: 주문명 PKG/package, 워런티 연장, AS/수리/교체, 렌탈/대여, 내부 테스트/샘플/전시.

거래원장 오류는 2번을 별도 처리하면 상당 부분 해소될 가능성이 높다. 다만 포탈 주문 타입을 전부 `FREE`로 바꾸는 방식이 아니라, 장부/계약잔액 계산에서 SF Grand Total 0을 반영하는 방식이어야 한다.

## 검증

- `summary.json` 기준 `Sales14091`: literal `무상` 장부 0원 후보 포함, SF `Grand Total=KRW 0`, 포탈 금액 `755000.000`
- `summary.json` 기준 `Sales19737`: literal `무상` 후보는 아니지만 프로모션 차감/동기화x 예외 후보 포함, SF `Grand Total=KRW 0`, 포탈 금액 `310000.000`
- CSV 파서 기준 집계:
  - 3,443 + 0원 교집합
  - 788 포탈 금액 불일치
  - 609 literal `무상/무료` 불일치
  - 453 `무상/무료` 장부 0원 후보
  - 265 프로모션 차감/동기화x 예외 후보
