# Salesforce 무상 조건 vs 포탈 유상 분류 조사

- 작성일: 2026-06-23
- 범위: 포탈 로컬 DB `dof_portal` 의 `importSource='sf'` 주문과 Salesforce 스크랩/로더 원천 데이터 대조
- 원칙: read-only 조사. 포탈 DB 수정은 하지 않았다.

> 보정 메모: 이 문서는 `FOC/Free of charge` 까지 포함한 1차 조사본이다. `FOC` 가 배송비/운임 무료 조건일 수 있다는 기준 정정 후, 한글 `무상`/`무료` 근거만 남긴 보정본은 `proc/research/2026-06-23_sf_free_paid_mismatch_korean_criteria_research.md` 를 기준으로 사용한다.

## 결론

포탈 DB의 Salesforce 이관 주문 19,747건은 현재 전부 `orderType=PAID` 로 저장되어 있다.

그중 Salesforce 주문 단 결제조건/거래조건(`Opportunity_Payment_Condition__c`, 브라우저 스크랩의 `sales_payment_condition`)에 `무상`, `FOC`, `Free of charge` 계열 문구가 있는 직접 불일치가 4,181건이다. 이 4,181건은 Salesforce 조건상 무상 계열인데 포탈에서는 모두 `유상(PAID)` 으로 남아 있는 건이다.

추가로 결제조건 자체는 아니지만 Salesforce 주문명/비고/ERP 메모/제품 라인 설명에서 무상 힌트가 잡히는 검토 후보가 826건 있다. 이들은 결제조건 직접 근거가 아니므로 자동 보정 대상이라기보다 사람이 확인해야 할 보조 목록으로 분리했다.

## 사용한 데이터

| 구분 | 경로/대상 | 건수 |
|---|---:|---:|
| 포탈 DB | `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/.env` 의 로컬 `DATABASE_URL` | SF 주문 19,747 |
| SF 로더 원천 | `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dofing-order-portal-data-3-az/resources/sf-crm/opportunities.jsonl` | 19,747 |
| SF 브라우저 스크랩 | `/Users/gq/works/projs/crm-migration/dataset/fetched/sf_sales_infos_org1.jsonl` | 19,745 |

포탈 DB 기준 최신 `Order.importDatetime` 는 `2026-06-23 04:58:35.932` 이다.

## 판정 기준

직접 불일치로 잡은 조건:

- 포탈: `Order.importSource='sf'`
- 포탈: `Order.orderType='PAID'`
- Salesforce 주문 단 결제조건/거래조건: `Opportunity_Payment_Condition__c` 또는 `sales_payment_condition` 에 `무상`, `FOC`, `F.O.C`, `Free of charge` 계열 문구 포함

검토 후보로만 잡은 조건:

- 직접 결제조건에는 무상 문구가 없지만, Salesforce `Name`, `Remarks__c`, `ERP__c`, `Request__c`, `PO_number__c`, 또는 브라우저 스크랩 `products` 에 무상/FOC 문구가 있음

주소 필드의 무상 문구는 고객사 기본주소에 반복 포함된 문장일 수 있어 후보 기준에서 제외했다.

## 집계

| 항목 | 건수 |
|---|---:|
| 포탈 SF 이관 주문 전체 | 19,747 |
| 포탈 `PAID` | 19,747 |
| 포탈 `FREE` | 0 |
| 직접 불일치: SF 결제조건/거래조건상 무상인데 포탈 `PAID` | 4,181 |
| 검토 후보: 이름/비고/제품 라인 등의 무상 힌트만 있음 | 826 |
| 전체 후보 | 5,007 |

직접 불일치 4,181건의 상태 분포:

| 상태 | 건수 |
|---|---:|
| COMPLETED | 4,071 |
| CLOSED_LOST | 80 |
| REGISTERED | 30 |

직접 불일치 4,181건의 금액 분포:

| 금액 상태 | 건수 |
|---|---:|
| `totalAmount=0` | 3,511 |
| `totalAmount<>0` | 670 |

금액이 0이 아닌 무상 조건 주문이 670건 있으므로, `totalAmount=0` 만으로 무상 여부를 판정하면 누락이 생긴다.

직접 불일치 4,181건의 포탈 결제조건 분포:

| paymentTerms | 건수 |
|---|---:|
| `007` | 1,653 |
| null | 1,060 |
| `002` | 690 |
| `001` | 410 |
| `006` | 169 |
| `005` | 91 |
| `010` | 55 |
| `003` | 39 |
| `004` | 12 |
| `008` | 2 |

`FOC` 로 들어간 건은 없다. 직접 불일치 4,181건의 주문제품 `freeReason` 도 전부 비어 있다.

## 대표 사례

| 주문번호 | 포탈 주문명 | 포탈 상태 | 통화 | 총액 | 포탈 결제조건 | SF/포탈 결제 메모 |
|---|---|---|---:|---:|---|---|
| Opp00000035 | DOF China-Tools (14) | COMPLETED | USD | 0 | `002` | `free of charge` |
| Sales0051 | USB 2.5M CABLE SET ASS'Y(1) | COMPLETED | KRW | 0 | `001` | `무상` |
| Sales0063 | IDCcable(1)Projector(1)USBhub(1)USBAtoBcable(1) | COMPLETED | USD | 607 | `002` | `FOC` |
| Sales0065 | Prime spare parts | COMPLETED | USD | 198 | `002` | `Free of charge` |
| Sales0080 | USB 2.5M CABLE SET ASS'Y(1) | COMPLETED | KRW | 0 | `001` | `(보증기간내) 무상공급` |
| Sales0113 | repalcement scan engine 2.0(1) | COMPLETED | EUR | 0 | `007` | `Free of Charge` |

상위 결제 메모 패턴:

| 결제 메모 | 건수 |
|---|---:|
| `FOC` | 187 |
| `무상` | 170 |
| `무상(계약 연장 건)` | 133 |
| `FOC (under warranty)` | 92 |
| `Free of charge` | 80 |
| `FOC (Warranty in)` | 56 |
| `무상(렌탈스캐너)` | 50 |

## 원인

SF 주문 로더가 주문구분을 전부 `PAID` 로 하드코딩한다.

- `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dofing-order-portal-data-3-az/src/loaders/sf-crm/orders.ts:151`
  - `"PAID", // orderType`
- 같은 로더에서 `Opportunity_Payment_Condition__c` 는 `paymentNote` 로만 저장된다.
  - `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dofing-order-portal-data-3-az/src/loaders/sf-crm/orders.ts:185`
- `paymentTerms` 는 주문 단 조건이 아니라 `Account_Payment_Condition__c` 를 매핑한다.
  - `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dofing-order-portal-data-3-az/src/loaders/sf-crm/orders.ts:179-182`

즉, Salesforce 주문 단 조건이 `FOC/무상` 이어도 포탈의 `orderType` 은 바뀌지 않고, 무상 근거는 `paymentNote` 에만 남는다.

관련 설계 문서에도 같은 전제가 남아 있다.

- `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dofing-order-portal-data-3-az/plans/sf/loading/00-overview.md:134`
  - SF `OrderType` 은 현재 전부 `PAID`
- `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dofing-order-portal-data-3-az/plans/sf/loading/05-facade-insights.md:140-152`
  - FOC/총액 0 기반 FREE 감지는 고려됐지만, 실제 적용은 보류됨

`mapSfPaymentTerms()` 자체는 `FOC` 를 인식할 수 있다. 다만 현재 적용 대상이 `Account_Payment_Condition__c` 라서 주문 단 무상 조건(`Opportunity_Payment_Condition__c`)을 `orderType=FREE` 로 승격하지 못한다.

## 산출물

| 파일 | 내용 |
|---|---|
| `/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04/output/research/sf-free-paid-mismatch-20260623/sf_free_paid_mismatch_summary.json` | 집계 JSON |
| `/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04/output/research/sf-free-paid-mismatch-20260623/sf_free_paid_mismatch_cases_direct_payment_condition.csv` | 직접 불일치 4,181건 |
| `/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04/output/research/sf-free-paid-mismatch-20260623/sf_free_paid_mismatch_cases_review_text_hint_only.csv` | 검토 후보 826건 |
| `/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04/output/research/sf-free-paid-mismatch-20260623/sf_free_paid_mismatch_cases_all.csv` | 전체 후보 5,007건 |

## 후속 판단

바로 보정한다면 1차 대상은 `direct_payment_condition` 4,181건이다. 다만 실제 변경 시에는 아래를 분리해야 한다.

- `REGISTERED` 30건: 현재 운영 영향이 남아 있을 수 있어 우선 검토 대상
- `COMPLETED` 4,071건: 과거 회계/출고 이력 영향이 있어 단순 `orderType` 변경 전에 수금/ERP/전표 영향 확인 필요
- `CLOSED_LOST` 80건: 영업종결 실패 주문이라 운영 보정 대상에서 제외하거나 별도 정책 필요
- `totalAmount<>0` 670건: 무상 조건인데 금액이 남아 있으므로 제품 단가/수금/회계 처리까지 같이 봐야 함

코드 보정 방향은 `Opportunity_Payment_Condition__c` 의 FOC/무상 판정으로 `orderType=FREE` 후보를 만들고, warranty/repair/replacement 계열은 `AS` 와 `FREE` 중 어느 쪽으로 갈지 운영 정책을 먼저 정하는 것이다.
