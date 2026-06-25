# SF `무상` 케이스 판정 리서치

작성일: 2026-06-23

> 정정: 이 문서의 `grand total` 기준은 포탈 `Order.totalAmount` 기준으로 좁게 판정한 일반 무상 후보 목록이다. Salesforce 화면의 `Grand Total` 필드 기준으로는 포탈 금액이 남아 있지만 SF Grand Total이 0인 케이스가 추가로 존재한다. 거래원장/계약잔액 오류 분석에는 `proc/research/2026-06-23_sf_grand_total_zero_musang_corrected_research.md`를 우선 기준으로 본다.

## 결론

포탈 DB와 Salesforce 적재/스크랩 데이터를 대조해 `무상`/`무료`가 들어간 모든 의미 필드 후보를 다시 판정했다. 단순 키워드 후보는 3,698건이었고, 포탈 금액 기준을 보수적으로 적용한 결과 포탈에서 `PAID`로 남아 있지만 일반 `FREE` 후보로 볼 수 있는 확정 케이스는 99건이다.

이번 판정은 `FOC` 단독을 근거로 쓰지 않았다. `FOC`가 있더라도 같은 행의 주문명, 결재조건, 비고, ERP 메모, 제품 라인 설명 등에 한글 `무상`/`무료` 근거가 있는 경우만 원천 후보에 포함했다.

## 판정 기준

확정 무상으로 남긴 조건:

- 포탈 DB의 `orderType`이 `PAID`인 Salesforce import 주문
- Salesforce/포탈 의미 필드 중 `무상` 또는 `무료` 근거 존재
- `grand total`, 즉 포탈 `totalAmount`가 0
- 일반 주문에서 물품/제품이 무상 제공, 지급, 출고, 공급, 경품 처리된 맥락

제외한 조건:

- `totalAmount != 0`
- 주문명에 `PKG` 포함
- 주문명 또는 맥락상 `package`, `promotion package`, 프로모션 차감/패키지 차감
- `Warranty 무상 연장`, 계약 연장, 워런티팩, 워런티 가입/연장
- 렌탈/대여/회수 예정
- 유상/무상 혼합, 크레딧 차감, 운임/면장/소프트웨어 매출/청구 예정
- AS, 보증, 초기불량, 교체/교환, 대체품, 수리, 보상, 오류/파손/누락, 이전 `Sales####` 참조
- `DOF Inc.` 내부, 창고/테스트/데모/전시/문서번호/영업지원/지사재고/로보틱스 협의 맥락

## 집계

| 판정 | 건수 |
|---|---:|
| 확정 무상: 일반 무상 + total 0 | 99 |
| 제외/검토 합계 | 3,599 |
| 전체 `무상`/`무료` 후보 | 3,698 |

제외 사유별 건수:

| 제외 사유 | 건수 |
|---|---:|
| AS/보증/교체/운영 이슈/이전 Sales 참조 | 1,413 |
| grand total이 0이 아님 | 1,043 |
| 내부/창고/테스트/데모/전시/문서번호/영업지원 | 579 |
| 렌탈/대여 | 236 |
| 계약/워런티 연장 또는 워런티팩 | 232 |
| 프로모션 맥락 | 33 |
| 유무상 혼합/운임/면장/소프트웨어 매출 | 24 |
| 주문명 PKG | 19 |
| 주문명 package/promotion package | 12 |
| PKG/프로모션 차감 | 8 |

확정 무상 99건 상태 분포:

| 포탈 상태 | 건수 |
|---|---:|
| `COMPLETED` | 97 |
| `CLOSED_LOST` | 2 |

## 예시

확정 무상으로 남긴 예:

- `Sales0529` 미향치과기공소-HD(1) 무상: `totalAmount=0`, 주문명/결재조건 모두 무상 지원.
- `Sales0593` 예성치과기공소-가공툴(2) 무상: `totalAmount=0`, 주문명/결재조건 모두 무상.
- `Sales16420` 디라이트치과기공소 FI(1): DOF Day 경품으로 무상 지급, `totalAmount=0`.
- `Sales18447` Cowell Shanghai: 판매증진 목적으로 무상 제공, `totalAmount=0`.

제외한 예:

- `Sales10571` 등 `무상(계약 연장 건)`: grand total은 0이어도 계약/워런티 연장 맥락이라 제외.
- `Sales1409`, `Sales15347`: 주문명에 `pkg`/`PKG` 또는 프로모션 패키지 맥락이 있어 제외.
- `Sales14975` 등 `무상대여`: 대여/회수 예정 맥락이라 제외.
- `Sales0199` 등 워런티 내 고객 지원/무상 교체: 제품 금액은 0이어도 일반 무상 제공이 아니라 AS/보증 맥락이라 제외.
- `Sales10178` 등 total이 0이 아닌 주문: 키워드가 있어도 `grand total=0` 기준 미충족.

## 원인 메모

현재 SF 적재 코드가 주문 타입을 조건 없이 `PAID`로 넣고 있다.

- `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dofing-order-portal-data-3-az/src/loaders/sf-crm/orders.ts:151`
  - `"PAID", // orderType`
- 같은 매핑에서 주문 단 결재조건 원문은 `paymentNote`로만 보존된다.
  - `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dofing-order-portal-data-3-az/src/loaders/sf-crm/orders.ts:185`

따라서 이번 99건은 데이터상 `FREE`로 재분류될 수 있는 후보이며, 실제 수정 로직은 `orderType` 산정 시 `totalAmount=0`과 제외 키워드/맥락을 함께 반영해야 한다.

## 거래원장/계약잔액 영향

Confluence `260610 계약잔액 안맞는건 계산` 페이지(`873398289`)의 무상 관련 사례는 이번 99건 재분류만으로 전부 해소되지 않는다.

이유:

- 해당 페이지의 주요 사례는 일반 무상 주문보다 `Promotion`, `PKG`, 계약잔액 차감, 다우 원장 금액 보정 성격이 강하다.
- 예를 들어 `Sales10422`, `Sales11731`, `Sales14643`은 포탈 금액이 0이지만 프로모션/PKG 차감 맥락이라 이번 확정 무상 99건에서 제외했다.
- `Sales14091`, `Sales19737`은 이 문서의 포탈 `totalAmount=0` 기준으로는 제외되지만, Salesforce 화면 `Grand Total=0` 기준으로는 거래원장/계약잔액 0원 처리 후보에 들어간다. 자세한 정정 목록은 `proc/research/2026-06-23_sf_grand_total_zero_musang_corrected_research.md`를 기준으로 본다.
- `Sales10636`은 포탈상 42,000,000원 유상 장비 주문이며, 문서의 문제는 이 주문 자체보다 관련 프로모션/차감행을 0원 또는 무상으로 보정해야 하는 쪽이다.
- 포탈 PKG 차감 로직은 주문 스냅샷에서 제품 `totalAmount` 합계를 사용하므로, 단순히 `orderType`만 `FREE`로 바꾸는 것으로는 계약잔액 차감액이 자동으로 0이 되지 않을 수 있다.

따라서 해결 범위는 두 갈래다.

1. 이번 99건 같은 일반 무상 주문: `orderType=FREE`, total 0, 무상사유 보강으로 포탈 수금/무상 주문 검증 오류를 줄일 수 있다.
2. Confluence 260610의 PKG/거래원장 사례: 포탈 주문 금액/제품 금액/계약 차감행과 다우 원장 금액을 별도로 보정해야 한다. 특히 계약잔액 계산에서는 무상/0원/PKG 프로모션 차감행을 차감 대상에서 제외하거나 0원 사용행으로 처리하는 로직이 필요하다.

## 산출물

출력 폴더:

`/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04/output/research/sf-musang-judged-20260623`

파일:

- `sf_musang_judged_cases.xlsx`: summary, confirmed, excluded/review, all judged 시트 포함
- `sf_musang_confirmed_free_general_total_zero.csv`: 확정 무상 99건
- `sf_musang_excluded_or_review.csv`: 제외/검토 3,599건
- `sf_musang_judged_all.csv`: 전체 판정 3,698건
- `sf_musang_all_candidates_raw.csv`: 판정 전 원천 후보
- `sf_musang_judgement_summary.json`: 집계와 기준

## 검증

- `sf_musang_confirmed_free_general_total_zero.csv`: 99행
- `sf_musang_excluded_or_review.csv`: 3,599행
- `sf_musang_judged_all.csv`: 3,698행
- 99 + 3,599 = 3,698로 원천 후보 수와 일치
- 확정 무상 잔여 목록에서 `PKG`, `무상 연장`, `렌탈`, `무상대여`, `워런티`, `프로모션`, `totalAmount != 0` 패턴 재검사 완료
