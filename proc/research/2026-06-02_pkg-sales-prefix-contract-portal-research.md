# PKG Sales-prefix 계약번호의 포털 Contract 생성 여부 조사

작성: 2026-06-02 KST

## 질문

SharePoint `매출현황_2026.xlsx`의 패키지 관련 시트에서 `Contract` 열 값이 `Sales17371`처럼 `Sales`로 시작하는 항목들이 있다. 이 항목들을 이전 포털 적재 작업에서 포털 `Contract`로 생성한 적이 있는지, 또는 그렇게 하자는 논의가 있었는지 확인한다.

## 결론

- 현재 확인한 범위에서는 `Sales17371`, `Sales15814`, `Sales17415`, `Sales19685` 같은 Sales-prefix 값이 포털 `Contract.contractNo`로 생성된 증거는 없다.
- 포털 DB에서는 Sales-prefix 값이 `Contract`가 아니라 `Order.orderNo`로 존재한다.
- 최신 SharePoint 파일에서 추출한 Sales-prefix 패키지 키 118개는 로컬 DB와 개발 DB 모두에서 `Order`로 118/118 매칭되고, `Contract`로는 0/118 매칭된다.
- 이전 논의/문서에는 Sales-prefix PKG 행을 "패키지 계약 버킷" 또는 "PKG 외부 정답지의 contractNumber"로 다룬 흔적은 있지만, 이를 포털 `Contract` 엔티티로 새로 만들자는 합의나 실행 기록은 확인되지 않았다.

## 확인한 입력

- SharePoint 파일: `매출현황_2026.xlsx`
  - URL: `https://doflab.sharepoint.com/sites/msteams_c2df28/Shared Documents/재무/매출/매출현황_2026.xlsx`
  - Graph search 기준 last modified: `2026-06-02 17:09:46+09:00`
  - 로컬 다운로드본: `/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04/output/sharepoint/매출현황_2026.xlsx`
- 관련 저장소:
  - `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dofing-order-portal-data-3-az`
  - `/Users/gq/works/projs/dofing-order-app/order-invoicing/portal-ledger-invoice-gen-and-send`

## SharePoint PKG 시트 파싱 결과

최신 다운로드본에서 `Contract` 헤더가 있는 시트를 훑어 `^Sales[0-9]+$` 값을 추출했다.

| 구분 | 값 |
|---|---:|
| Sales-prefix `Contract` 행 수 | 120 |
| 고유 Sales-prefix 값 | 118 |
| `Promotion PKG_출고내역` 행 | 119 |
| `가계약` 행 | 1 |
| 중복 값 | `Sales14581`, `Sales19685` |

기존 `portal-ledger-invoice-gen-and-send/data/pkg-derived/pkg-summary.json`도 같은 구조를 가진다.

| 기존 파싱 요약 | 값 |
|---|---:|
| 전체 contractCount | 249 |
| CO prefix | 130 |
| Sales prefix | 118 |
| other | 1 |

중요: `portal-ledger-invoice-gen-and-send/src/pkg/parsePkgSheet.js`는 이 시트를 원장용 패키지 버킷으로 파싱한다. 주석상 `Contract` 열이 채워진 행을 "새 PKG 계약" header로 분류하고, 빈 `Contract` 행은 직전 contract를 forward-fill한다. 여기서의 `contractNumber`는 원장/패키지 차감 계산 단위이지, 포털 DB `Contract` 테이블 적재 규칙이라는 뜻은 아니다.

## 포털 로더 설계 확인

`dofing-order-portal-data-3-az`의 SF 로더 설계는 Sales 번호와 Contract 번호를 분리한다.

- `Order`: SF `Opportunity_ID__c`를 `Order.orderNo`로 직접 사용한다. 예: `Sales00001`
- `Contract`: SF `Contract_No__c`를 `Contract.contractNo`로 직접 사용한다. 예: `C00457`
- `Contract.Sales_Number__c`는 `opportunityUk`로 역참조되어 Order와 연결될 뿐, `contractNo`가 되지 않는다.

근거 파일:

- `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dofing-order-portal-data-3-az/src/loaders/sf-crm/loaders.ts`
  - `loadSfOrders()`: `Opportunity_ID__c -> orderNo`
  - `loadSfContracts()`: `Contract_No__c -> contractNo`, `Sales_Number__c -> opportunityUk`
- `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dofing-order-portal-data-3-az/plans/sf/loading/00-overview.md`
  - `Order | orderNo:{Opportunity_ID__c} | orderNo:Sales00001`
  - `Contract | contractNo:{Contract_No__c} | contractNo:C00457`
- `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dofing-order-portal-data-3-az/plans/sf/loading/03-field-mapping.md`
  - `Opportunity_ID__c -> orderNo`
  - `Contract_No__c -> contractNo`
  - `Sales_Number__c -> opportunityUk`

## 현재 DB 대조

대상 DB:

- 로컬: `.env`의 `DATABASE_URL`
- 개발: `.env`의 `DATABASE_URL_REMOTE`

두 DB 모두 같은 결과였다.

### 전체 Sales-prefix 존재 위치

| DB | `Contract.contractNo ~ '^Sales[0-9]+$'` | `Order.orderNo ~ '^Sales[0-9]+$'` |
|---|---:|---:|
| local | 0 | 19,733 |
| dev remote | 0 | 19,733 |

### 예시 4건

| Sales 번호 | Contract 매칭 | Order 매칭 |
|---|---:|---|
| `Sales15814` | 0 | `다온치과기공소(대구) - Tool PKG 300(1)` |
| `Sales17371` | 0 | `새이로치과기공소(동대문) - 1,000 Warranty PKG(1)` |
| `Sales17415` | 0 | `다온치과기공소(대구) - 2,000 PKG(1)` |
| `Sales19685` | 0 | `씨에이치엠(포항미르치과) - 600 Warranty PKG(1)` |

### SharePoint에서 추출한 118개 Sales-prefix PKG 키 전수 대조

| DB | 시트 Sales-prefix 고유값 | `Order` 매칭 | `Contract` 매칭 | `Order.contractUk` 있음 |
|---|---:|---:|---:|---:|
| local | 118 | 118 | 0 | 1 |
| dev remote | 118 | 118 | 0 | 1 |

`Order.contractUk`가 있는 1건은 `Sales12811`이다. 이것도 `Sales12811`이 계약으로 생성된 것이 아니라, `Order.orderNo = Sales12811`이 별도 SF 계약 `C00552`에 연결된 상태다.

| orderNo | linked contractNo | linked contractName |
|---|---|---|
| `Sales12811` | `C00552` | `C00552 모아치과기공소(수원)` |

## 이전 논의/문서 흔적

확인된 관련 흔적은 다음 두 갈래다.

1. SF 데이터 적재 작업
   - 2026-05-20/2026-05-25/2026-05-26의 SF dev/prod 적재 기록에서 `Order=19,747`, `Contract=644` 같은 적재 결과가 남아 있다.
   - 이때의 설계와 실행은 `Opportunity -> Order`, `SF Contract -> Contract`였다.
   - Sales-prefix를 `Contract.contractNo`로 만들었다는 기록은 없다.

2. PKG 시트 검증/거래원장 작업
   - `plans/sf/loading/10-tax-double-count-bug.md`는 `portal-ledger-invoice-gen-and-send/data/pkg-derived/pkg.json`을 외부 정답지로 사용하면서 "Sales-prefix 118건, 모두 portal에 존재"라고 기록했다.
   - 같은 문서는 비교 대상을 `Portal Order 헤더 totalAmount`와 `OrderProduct` 라인합으로 잡았다. `Contract` 테이블 생성이나 `Contract.contractNo` 매칭을 주장하지 않는다.
   - 거래원장 audit 규칙에도 ERP 적요의 `OD...`/`Sales...` 번호를 포털 주문/수금스케줄/paymentNote와 대조하라는 내용이 있다. 이것도 Sales 번호를 주문 근거로 다루는 흐름이다.

따라서 "Contract 열에 Sales 번호가 있으니 포털 Contract로 생성해야 한다"는 논의는 확인되지 않았다. 실제로는 회계 PKG 시트의 `Contract` 열 명칭과 포털 데이터 모델의 `Contract` 엔티티명이 겹쳐 혼동이 생긴 것으로 보는 편이 맞다.

## 해석

- PKG 시트의 Sales-prefix `Contract` 값은 패키지 선수금/차감 원장에서 계약처럼 관리되는 bucket key다.
- SF/포털 데이터 모델에서는 같은 Sales 번호가 SF Opportunity 번호이며, 포털 `Order.orderNo`가 된다.
- 실제 포털 `Contract.contractNo`는 `C...` 계열의 SF `Contract_No__c` 또는 FG `CO...` 계열 계약번호가 담당한다.
- 그러므로 `Sales17371` 같은 값은 포털에 존재한다면 "계약으로 생성됨"이 아니라 "주문으로 적재됨"이라고 표현해야 한다.

## 후속 검토: Sales-prefix PKG 계약을 포털 Contract로 추가하는 방법

사용자 설명에 따르면 SF에는 포털식 `Contract` 개념이 없었고, 예전 화면에서는 SF 주문/Sales 번호를 계약처럼 사용했다. 이 방식은 참고 프론트 데이터에서도 확인된다.

- `/Users/gq/works/projs/dofing-order-app/order-web/order-web-ref/order-web-front-hong/public/data/contracts.json`
  - 전체 177개 contract-like row 중 Sales-prefix `contractNumber`가 118개다.
  - 예: `Sales17371.contractAmount = 9,999,900`, `Sales17529.contractAmount = 1,500,000`, `Sales18987.contractAmount = 2,000,000`.
- 같은 reference app의 `sales.json`도 `contractNumber: Sales...`를 보조장표 연결키로 사용한다.

따라서 "포털에 Sales-prefix 계약을 추가한다"는 것은 SF `Contract` 적재를 바꾸는 일이 아니라, SF 주문을 근거로 한 **합성 PKG 선수금 계약**을 만드는 별도 백필/로더 작업으로 보는 편이 맞다.

### 계약금액 산정 원칙

계약금액은 `Order.totalAmount`가 아니라 해당 Sales 주문 안의 PKG 제품 라인 합이어야 한다.

예: `Sales17529`는 포털 `OrderProduct`에 다음 두 PKG 라인이 있고, 합계가 1,500,000원이다.

| productCode | productName | totalAmount |
|---|---|---:|
| `CO-ET-002` | `Promotion package 100 (For Korea)` | 1,000,000 |
| `CO-ET-003` | `Promotion package 50 (For Korea)` | 500,000 |

이 원칙이 필요한 이유는 `Sales18987` 같은 반례 때문이다. 이 주문의 전체 `Order.totalAmount`는 5,000,000원이지만, PKG 계약금액으로 잡아야 할 라인은 `CO-ET-002` 2,000,000원뿐이다. `SU-WP-006 DOF Milling Machin Warranty 300` 3,000,000원은 현재 PKG 계약금액에 포함하면 안 된다.

현재 2026-06-02 17:09:46 KST SharePoint 원본과 개발 DB를 대조하면 다음과 같다.

| 항목 | 결과 |
|---|---:|
| `Promotion PKG_출고내역`의 Sales-prefix header row | 119 |
| 고유 Sales-prefix 값 | 118 |
| PKG 라인 합이 시트/old-front의 유효 계약금액과 일치 | 116 / 118 |
| `Order.totalAmount`와 PKG 라인 합이 다른 반례 | `Sales18987`, `Sales12811` |

현재 데이터에서 PKG 계약금액 후보로 쓸 수 있는 제품코드 allowlist는 다음처럼 좁게 잡는 것이 안전하다.

```text
CO-ET-002   Promotion package 100 (For Korea)
CO-ET-003   Promotion package 50 (For Korea)
CO-ET-006   Promotion package 10
CO-ET-002-1 재계약 - Promotion package 100
CO-PR-002   Promotion package T 300
CO-PR-003   Promotion package T 500
CO-PR-004   Promotion package J2 150
SU-WP-007   1,000 Warranty PKG
SU-WP-008   600 Tool Warranty PKG
SU-WP-009   600 All Warranty PKG
```

주의: `productName`에 `package`나 `Warranty`가 들어간다고 모두 포함하면 안 된다. 실제 대상 Sales 주문 안에도 `DM-CR-001 CRAFT 5X(Complete package w/o CAM)`, `SU-WP-006 DOF Milling Machin Warranty 300` 같은 비-PKG 계약금액 품목이 섞여 있다.

### 자동 생성 제외/검토 대상

다음은 자동 생성 전에 수동 검토가 필요하다.

| Sales 번호 | 이유 |
|---|---|
| `Sales18301` | SharePoint/old-front 유효 계약금액은 2,000,000원이지만 현재 dev DB의 PKG `OrderProduct.totalAmount` 합은 1,000,000원이다. 제품 라인 중 하나가 0원으로 적재되어 있다. |
| `Sales12811` | SharePoint/old-front 계약금액은 220,000원이지만 현재 dev DB의 PKG 라인 합은 0원이고 주문 전체금액은 53,660,000원이다. 또한 현재 `Order.contractUk`가 기존 SF 계약 `C00552`에 이미 연결되어 있다. |

`Sales14581`은 원본 시트에 header row가 2개라 단순 합산하면 7,000,000원이 되지만, old-front의 `contractAmount`와 포털 PKG 주문 라인 합은 5,000,000원이다. 이 건은 "중복 header row를 단순 합산하지 않는다"는 검증 규칙을 두면 자동 생성 가능 쪽으로 분류할 수 있다.

### 구현 경로

1. `dofing-order-portal-data-3-az`에 SF Contract 로더와 분리된 별도 로더를 둔다.
   - 예: `src/loaders/pkg-sales-contracts/...` 또는 별도 `scripts/backfill-pkg-sales-contracts.ts`.
   - 기존 `loadSfContracts()`를 바꾸지 않는다. 그 로더는 `Contract_No__c -> Contract.contractNo`, `Sales_Number__c -> opportunityUk`라는 SF 계약용 매핑을 유지해야 한다.

2. 입력은 두 가지를 함께 사용한다.
   - SharePoint `매출현황_2026.xlsx`의 `Promotion PKG_출고내역`.
   - 이미 적재된 포털 `Order`/`OrderProduct`.
   - 시트는 "어떤 Sales 번호가 PKG 계약 bucket인지"를 판별하고, 금액은 포털 `OrderProduct`의 PKG 라인 합으로 검증/산정한다.

3. `Contract`는 직접 upsert한다.
   - 일반 포털 계약 생성 API는 `contractNo`를 받지 않고 `generateContractNumber()`로 `CO...`를 자동 채번한다.
   - 프론트도 `contractNo`를 자동생성/수정불가 필드로 다룬다.
   - 따라서 `contractNo = Salesxxxxx`를 만들려면 UI/API create 경로가 아니라 데이터 로더에서 DB upsert를 해야 한다.

4. 합성 `Contract` 필드 제안:

| 필드 | 제안 |
|---|---|
| `uk` | `generateContractUk(contractNo)` 방식과 동일하게 deterministic 생성 |
| `contractNo` | `Salesxxxxx` |
| `contractName` | 원 주문명 또는 `[고객사] - [PKG 제품 요약]` |
| `contractType` | `PREPAID` (`Promotion PKG`) |
| `status` | 초기에는 `REGISTERED` 또는 시트 잔액/완료여부 기반 상태. 잔액 로직 확정 전에는 보수적으로 `REGISTERED` 권장 |
| `companyUk`, `customerUk`, `managerUk`, `managerName` | matching `Order`에서 복사 |
| `opportunityUk` | source `Order.uk` 저장. "이 Sales 주문이 계약 역할을 했다"는 추적 포인트 |
| `contractDate` | source `Order.orderDate` 또는 시트 `Shipping Date`. 운영 의미상 패키지 시작일이 중요하면 `Shipping Date` 우선 |
| `currency`, `taxType`, `priceType`, `paymentTerms` | source `Order`에서 복사 |
| `totalAmount` | allowlist PKG `OrderProduct.totalAmount` 합 |
| `balance` | 1차 백필에서는 `totalAmount` 또는 시트 원장의 최종 잔액. 기존 재계산 함수에 맡기면 안 됨 |
| `importSource` | `pkg-sheet-sales-contract`처럼 실제 SF 계약과 구분되는 값 |
| `note` | SharePoint source row, source orderNo/orderUk, 산정 PKG 라인, 예외 여부 기록 |

5. `ContractProduct`는 source `OrderProduct`의 PKG 라인을 복제한다.
   - `productCode`, `productName`, `factory`, `unitPrice`, `quantity`, `supplyAmount`, `taxAmount`, `totalAmount`를 그대로 사용한다.
   - 이 방식이면 `PKG 50 + PKG 100 = 1,500,000원` 같은 복합 주문도 자연스럽게 처리된다.

### 잔액/차감 연결 주의점

합성 계약을 만들었다고 해서 source Sales 주문의 `Order.contractUk`를 곧바로 자기 합성 계약에 연결하면 안 된다.

현재 포털 서버의 `ContractsService.recalculateBalance()`는 다음 방식이다.

```text
balance = Contract.totalAmount
        - SUM(Order.totalAmount WHERE Order.contractUk = Contract.uk AND status >= 승인요청)
```

이 로직은 일반 계약에는 맞지만 PKG 합성 계약에는 위험하다.

- source Sales 주문은 "패키지를 산 주문"이지 "패키지를 차감한 주문"이 아니다.
- `Order.totalAmount`는 PKG 라인 합이 아니라 주문 전체금액이다.
- `Sales18987`처럼 주문 전체금액 5,000,000원 중 PKG 계약금액은 2,000,000원인 케이스가 있다.
- `Sales12811`처럼 기존 `C...` 계약에 이미 연결된 주문도 있다.

따라서 권장 단계는 다음이다.

1. 1차: `Contract` + `ContractProduct`만 생성한다.
   - 계약 목록/계약상품 목록에서 Sales-prefix PKG 계약을 볼 수 있게 한다.
   - source Sales 주문에는 `opportunityUk`로만 연결한다.
   - `Order.contractUk`는 건드리지 않는다.

2. 2차: PKG 차감 원장을 별도 구조로 만든다.
   - 권장: `PackageContractUsage` 또는 `ContractUsage` 테이블 추가.
   - 필드 예: `contractUk`, `orderUk`, `salesNumber`, `usageAmount`, `sourceSheet`, `sourceRow`, `usageDate`, `kind`.
   - 잔액은 `Contract.totalAmount - SUM(usageAmount)` 또는 시트의 이관/잔액 행까지 반영한 별도 함수로 계산한다.

3. 2차를 스키마 변경 없이 처리해야 한다면 최소한 `PREPAID` 계약에 대해 `Order.totalAmount`가 아니라 PKG 사용금액을 차감하도록 `recalculateBalance()`를 분기해야 한다.
   - 그러나 이 경우에도 사용금액의 source가 필요하므로 결국 시트 원장 row 또는 별도 generated ledger가 필요하다.

### 권장 작업 순서

1. dry-run 리포트부터 만든다.
   - 총 118건 중 자동 생성 가능/수동검토/스킵을 분리한다.
   - `Contract.contractNo = Sales...` 충돌 여부를 확인한다. 현재 dev DB 기준 충돌은 0건이다.

2. 자동 생성 가능 건만 `Contract`/`ContractProduct` upsert한다.
   - 현재 기준 116건은 PKG 라인 합과 유효 계약금액이 일치한다.
   - `Sales18301`, `Sales12811`은 별도 보정 없이 자동 생성하지 않는다.

3. 생성 후 검증한다.
   - `Contract.contractNo ~ '^Sales[0-9]+$'` 건수.
   - 각 `Contract.totalAmount = SUM(ContractProduct.totalAmount)`.
   - 각 `Contract.totalAmount = source Order의 allowlist PKG line sum`.
   - `Order.contractUk`를 실수로 변경하지 않았는지 확인.

4. 잔액/사용 원장은 별도 단계로 처리한다.
   - 기존 계약 잔액 재계산 함수에 바로 연결하지 않는다.
   - SharePoint PKG 원장의 사용/이관 row까지 모델링한 뒤 연결한다.

## 남은 리스크

- 이 문서는 현재 로컬/개발 DB와 관련 메모리/문서 검색 기준이다. 운영자가 SharePoint 원본을 수기로 바꿀 수 있으므로 PKG 시트 행 수는 이후 변경될 수 있다.
- 전체 과거 대화 원문을 사람이 직접 전수 독해한 것은 아니지만, 관련 메모리, 롤아웃 요약, 로더 설계, 현재 DB 상태에서는 Sales-prefix를 포털 Contract로 생성했다는 근거가 없다.
- 후속 방안의 자동 생성 가능 건수는 최신 SharePoint 파일과 dev DB를 기준으로 한 dry-run 결과다. 운영 DB 반영 전에는 반드시 운영 DB 대상 dry-run과 백업이 필요하다.
