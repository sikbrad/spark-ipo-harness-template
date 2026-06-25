# Salesforce 한글 무상 조건 vs 포탈 유상 분류 조사

- 작성일: 2026-06-23
- 보정 기준: `FOC` 단독은 제외. Salesforce 거래조건/결제조건에 한글 `무상`이 있거나, 주문명에 `무상`/`무료`가 있는 건만 추출.
- 범위: 포탈 로컬 DB `dof_portal` 의 `importSource='sf'` 주문과 Salesforce 스크랩/로더 원천 데이터 대조
- 원칙: read-only 조사. 포탈 DB 수정 없음.

> 후속 판정 메모: 이 문서는 한글 `무상`/`무료` 키워드 기준의 1차 보정 추출이다. `grand total=0`, `PKG`, `Warranty 무상 연장`, 렌탈/대여, AS/보증/교체 등 업무 맥락을 직접 판정해 줄인 최종 후보는 `proc/research/2026-06-23_sf_musang_judged_free_cases_research.md`를 기준으로 본다.

## 결론

기준을 `FOC` 포함에서 한글 무상/무료 근거 중심으로 바꾸면, 포탈에서 `유상(PAID)` 으로 남아 있는 후보는 3,020건이다.

세부적으로는 Salesforce 거래조건/결제조건 필드에 `무상`이 들어간 건이 3,002건, 주문명에 `무상` 또는 `무료`가 들어간 건이 49건이다. 두 조건이 동시에 걸린 31건이 있어 전체 unique 후보는 3,020건이다.

포탈 DB의 Salesforce 이관 주문 19,747건은 여전히 전부 `orderType=PAID` 로 저장되어 있고, 새 기준 후보 3,020건의 주문제품 `freeReason` 도 전부 비어 있다.

## 변경된 판정 기준

포함:

- 포탈: `Order.importSource='sf'`
- 포탈: `Order.orderType='PAID'`
- 거래조건/결제조건: `Opportunity_Payment_Condition__c`, 브라우저 스크랩 `sales_payment_condition`, 또는 포탈 `paymentNote` 에 `무상` 포함
- 주문명: SF `Name`, 브라우저 스크랩 `sales_name`, 또는 포탈 `orderName` 에 `무상` 또는 `무료` 포함

제외:

- `FOC`, `F.O.C`, `Free of charge` 만 있는 경우
- 제품 라인 설명, 비고, ERP 메모, 주소 필드만의 무상 문구
- 배송비 무료/운임 선지급처럼 `FOC`가 인코텀/배송비 의미일 가능성이 있는 건

## 집계

| 항목 | 건수 |
|---|---:|
| 포탈 SF 이관 주문 전체 | 19,747 |
| 포탈 `PAID` | 19,747 |
| 포탈 `FREE` | 0 |
| 거래조건/결제조건에 `무상` | 3,002 |
| 주문명에 `무상`/`무료` | 49 |
| 둘 다 해당 | 31 |
| 전체 unique 후보 | 3,020 |

분류별 unique 후보:

| 분류 | 건수 |
|---|---:|
| 거래조건/결제조건 `무상`만 | 2,971 |
| 주문명 `무상`/`무료`만 | 18 |
| 둘 다 해당 | 31 |

상태 분포:

| 상태 | 건수 |
|---|---:|
| COMPLETED | 2,969 |
| CLOSED_LOST | 41 |
| REGISTERED | 10 |

금액 분포:

| 금액 상태 | 건수 |
|---|---:|
| `totalAmount=0` | 2,407 |
| `totalAmount<>0` | 613 |

통화 분포:

| 통화 | 건수 |
|---|---:|
| KRW | 2,903 |
| JPY | 46 |
| USD | 40 |
| EUR | 30 |
| CNY | 1 |

포탈 결제조건 분포:

| paymentTerms | 건수 |
|---|---:|
| `007` | 1,602 |
| null | 852 |
| `001` | 409 |
| `002` | 74 |
| `006` | 68 |
| `003` | 8 |
| `005` | 5 |
| `010` | 2 |

## 대표 사례

| 분류 | 주문번호 | 포탈 주문명 | 상태 | 통화 | 총액 | 포탈 결제조건 | 거래조건/결제 메모 |
|---|---|---|---|---:|---:|---|---|
| 거래조건 `무상` | Sales0051 | USB 2.5M CABLE SET ASS'Y(1) | COMPLETED | KRW | 0 | `001` | `무상` |
| 거래조건 `무상` | Sales0080 | USB 2.5M CABLE SET ASS'Y(1) | COMPLETED | KRW | 0 | `001` | `(보증기간내) 무상공급` |
| 거래조건 `무상` | Sales0119 | USB 2.5M Cable set ass'y (1) | COMPLETED | KRW | 0 | `007` | `무상(워런티 내 고객 지원)` |
| 주문명 `무상` | Sales14081 | PI DENTAL - Calibration Jig(1) [무상지급 / 2024.04] | COMPLETED | EUR | 0 | `002` | `T/T 100% IN ADVANCE` |
| 주문명 `무상` | Sales15067 | IAD - Fi(1) [무상대여 / 2024.07] | COMPLETED | USD | 400 | `002` | `T/T 100% IN ADVANCE` |
| 주문명 `무상` | Sales15182 | Yamamoto - 24vSMPS(1), Power cable(1) [2024.07-무상건이지만 인보이스 1,045유로로 진행] | COMPLETED | EUR | 1045 | `002` | `100% T/T in advance` |

## 원인

원인은 기존 조사와 동일하다. SF 주문 로더가 주문구분을 전부 `PAID` 로 하드코딩한다.

- `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dofing-order-portal-data-3-az/src/loaders/sf-crm/orders.ts:151`
  - `"PAID", // orderType`
- 같은 로더에서 `Opportunity_Payment_Condition__c` 는 `paymentNote` 로만 저장된다.
  - `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dofing-order-portal-data-3-az/src/loaders/sf-crm/orders.ts:185`
- `paymentTerms` 는 주문 단 조건이 아니라 `Account_Payment_Condition__c` 를 매핑한다.
  - `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dofing-order-portal-data-3-az/src/loaders/sf-crm/orders.ts:179-182`

따라서 Salesforce 거래조건에 `무상`이 있어도 포탈 `orderType` 은 `PAID` 로 유지되고, 무상 근거는 결제 메모 또는 주문명에만 남는다.

## 산출물

| 파일 | 내용 |
|---|---|
| `/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04/output/research/sf-free-paid-mismatch-korean-criteria-20260623/sf_free_paid_mismatch_korean_criteria_summary.json` | 새 기준 집계 JSON |
| `/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04/output/research/sf-free-paid-mismatch-korean-criteria-20260623/sf_free_paid_mismatch_korean_criteria_all.csv` | 전체 unique 후보 3,020건 |
| `/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04/output/research/sf-free-paid-mismatch-korean-criteria-20260623/sf_free_paid_mismatch_korean_criteria_payment_condition_musang.csv` | 거래조건/결제조건 `무상` 후보 3,002건 |
| `/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04/output/research/sf-free-paid-mismatch-korean-criteria-20260623/sf_free_paid_mismatch_korean_criteria_order_name_free.csv` | 주문명 `무상`/`무료` 후보 49건 |

## 후속 판단

1차 보정 대상으로는 `REGISTERED` 10건을 먼저 보는 편이 안전하다. 아직 운영 중일 가능성이 있어 포탈 사용자에게 바로 영향을 줄 수 있다.

`COMPLETED` 2,969건은 과거 이력/회계/출고와 연결되어 있으므로, 단순히 `orderType` 만 바꾸기보다 수금/ERP/전표 영향까지 확인해야 한다.

`totalAmount<>0` 613건은 특히 주의해야 한다. 주문명이나 거래조건에는 무상 근거가 있지만 금액이 남아 있으므로, 실제로는 일부 제품만 무상인지, 운임/문서 value/수리비가 포함된 건인지 분리 검토가 필요하다.
