# PKG 잔액보정 정정주문 생성 리포트

작성시각: 2026-06-11 KST

## 전제

이 문서는 실제 주문을 생성하지 않고, **잔액보정 정정주문을 생성한다면 어떤 주문을 얼마로 만들어야 하는지**를 계산한 리포트다.

포탈 계약 잔액 산식은 코드 기준으로 다음과 같다.

```text
Contract.balance = Contract.totalAmount - SUM(Order.totalAmount)
```

단, `Order.status`가 아래 상태일 때만 잔액 차감에 포함된다.

```text
APPROVAL_REQUESTED, TEAM_LEAD_APPROVED, EXECUTIVE_APPROVED,
RELEASE_APPROVED, SHIPPED, COMPLETED, RELEASE_HOLD
```

따라서 보정 주문을 생성만 하고 `REGISTERED`에 두면 계약 잔액은 바뀌지 않는다. 실제 잔액 반영 목적이면 최소 `APPROVAL_REQUESTED`까지 상태를 올려야 한다.

## 보정 제품

DB 제품 마스터에서 보정용으로 사용할 수 있는 제품은 아래가 확인됐다.

| 필드 | 값 |
|---|---|
| productCode | `DOF-PKG-Balance` |
| productName | `Promotion PKG 잔액 이관` |
| parentProductCode | `PG001102` |
| factory | `DOF` |
| discontinuedYn | `false` |

기존 운영 데이터에서도 이 제품은 양수/음수 잔액 이관 주문에 사용 중이다. 최근 사용 패턴은 `orderType=PAID`, `currency=KRW`, `taxType=TAXABLE`, `priceType=INCLUDING_VAT`이며, 결제조건은 `009`(`Promotion PKG (선수금)`)가 주로 쓰인다.

## 계산식

```text
보정 주문 총액 = 현재 포탈 계산잔액 - 목표 다우 잔액
```

- 보정 주문 총액이 양수면: 잔액을 그만큼 더 차감하는 주문.
- 보정 주문 총액이 음수면: 잔액을 그만큼 복원하는 마이너스 주문.
- 보정 주문 총액이 0이면: 주문 생성 불필요.

목표 다우 잔액은 `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dofing-order-portal-data-3-az/resources/daou-office/package-contracts/20260610T_contract_amount_all_status/all-package-contracts.jsonl` 기준이며, `접수`와 `출고완료` 전체 상태 및 `SalesNNNNN-1`, `SalesNNNNN-2` 같은 파생 번호를 합산했다.

## 요약

| Sales | 고객사 | 현재 포탈 계산잔액 | 목표 다우 잔액 | 보정 주문 총액 | 방향 | 생성 판단 |
|---|---|---:|---:|---:|---|---|
| Sales15705 | 라보테크 | 21,000,000 | 1,000,000 | 20,000,000 | 양수 차감 | 생성 필요 |
| Sales13813 | 아해바덴탈(대전) | 1,745,000 | 1,270,000 | 475,000 | 양수 차감 | 생성 필요 |
| Sales14356 | 지.비.에스(G.B.S)치과기공소 | 2,500,000 | 983,000 | 1,517,000 | 양수 차감 | 생성 필요 |
| Sales14454 | 인사랑치과 | 2,670,000 | 355,750 | 2,314,250 | 양수 차감 | 생성 필요 |
| Sales14966 | 경성치과기공소(부산) | 2,000,000 | 2,000,000 | 0 | 없음 | 불필요 |
| Sales16128 | 에이블치과기공소(영등포) | -985,000 | 15,000 | -1,000,000 | 음수 복원 | 생성 필요 |
| Sales11804 | 바른손치과기공소(아산) [구]천안 | 250,000 | 150,000 | 100,000 | 양수 차감 | 생성 필요 |
| Sales19534 | (주)메디클러스(청주) | 1,825,000 | 1,805,000 | 20,000 | 양수 차감 | 생성 필요 |

## 주문 생성 공통값

| 필드 | 권장값 |
|---|---|
| orderType | `PAID` |
| currency | `KRW` |
| taxType | `TAXABLE` |
| priceType | `INCLUDING_VAT` |
| paymentTerms | `009` (`Promotion PKG (선수금)`) |
| requestDate | `2026-06-11` |
| importSource | `manual` 또는 `portal-correction` |
| collections | 원칙적으로 0원 또는 미생성. 기존 양수 이관 주문은 0원 수금 row가 있는 사례가 있고, 음수 이관 주문은 수금 row가 없는 사례가 많다. |
| status | 생성 직후 `REGISTERED`; 잔액 반영 필요 시 `APPROVAL_REQUESTED` 이상으로 전이 |
| productCode | `DOF-PKG-Balance` |
| productName | `Promotion PKG 잔액 이관` |
| product quantity | `1` |
| product note | `PKG 잔액보정(<Sales>): 현재 포탈 계산잔액 <A> -> 목표 다우잔액 <B>` |

금액은 VAT 포함가 기준으로 입력한다. API/DB로 직접 넣을 때는 기존 운영 데이터 패턴처럼 `unitPrice = totalAmount`, `quantity = 1`, `supplyAmount = round(totalAmount / 1.1)`, `taxAmount = totalAmount - supplyAmount`를 사용하면 된다. 음수 복원 주문도 같은 방식으로 음수 값을 넣는다.

## 주문별 생성 정보

### Sales15705

| 필드 | 값 |
|---|---|
| 고객사 | 라보테크 |
| companyUk | `c0435f64-1f05-55c8-afdf-8c695fe8197a` |
| 고객 | 이석구 |
| customerUk | `c7159834-ba8a-5b14-8b11-df5daf17b74a` |
| 담당자 | 김수련 Chloe |
| contractNo | `Sales15705` |
| contractUk | `contract_sf_pkg_v2_de81a389ab79e47ab09898f1` |
| contractName | `라보테크(힘찬치과기공소)_Sales15705_PKG` |
| 현재 포탈 계산잔액 | 21,000,000 |
| 목표 다우 잔액 | 1,000,000 |
| 보정 주문 총액 | 20,000,000 |
| 권장 orderName | `라보테크_Promotion PKG 잔액 보정(Sales15705)` |
| 권장 externalOrderNo | `PKG-BAL-CORR-Sales15705` |
| 제품 unitPrice/totalAmount | 20,000,000 |
| 제품 supplyAmount | 18,181,818 |
| 제품 taxAmount | 1,818,182 |
| 비고 | 포탈 계약원금 21,000,000원 자체가 과대 산정된 케이스다. 주문 보정으로 맞추면 큰 양수 차감 주문이 생기므로 계약금 직접 정정 방식과 비교 검토가 필요하다. |

### Sales13813

| 필드 | 값 |
|---|---|
| 고객사 | 아해바덴탈(대전) |
| companyUk | `930fe921-88d6-5d05-8708-6ce99bccc74e` |
| 고객 | 안대훈 |
| customerUk | `2c2f2e38-3793-5709-a502-53c048241569` |
| 담당자 | Tech |
| contractNo | `Sales13813` |
| contractUk | `contract_sf_pkg_v2_4af3fd1f42f9ea32c52d0f98` |
| contractName | `아해바 덴탈(대전)_Sales13813_PKG` |
| 현재 포탈 계산잔액 | 1,745,000 |
| 목표 다우 잔액 | 1,270,000 |
| 보정 주문 총액 | 475,000 |
| 권장 orderName | `아해바덴탈(대전)_Promotion PKG 잔액 보정(Sales13813)` |
| 권장 externalOrderNo | `PKG-BAL-CORR-Sales13813` |
| 제품 unitPrice/totalAmount | 475,000 |
| 제품 supplyAmount | 431,818 |
| 제품 taxAmount | 43,182 |
| 비고 | 다우 차감 합계 1,230,000원 중 포탈 반영 주문은 `Sales14091` 755,000원뿐이다. 누락/미반영분 475,000원을 보정한다. |

### Sales14356

| 필드 | 값 |
|---|---|
| 고객사 | 지.비.에스(G.B.S)치과기공소 |
| companyUk | `991ab8d4-20d8-5eeb-b4f9-1a26d61212a1` |
| 고객 | 배현민 |
| customerUk | `6d81424f-7549-52e7-bdfc-e40f493696a0` |
| 담당자 | 이미연 |
| contractNo | `Sales14356` |
| contractUk | `contract_sf_pkg_v2_cd19446ddff5fc4d62b67999` |
| contractName | `지.비.에스(G.B.S)치과기공소(창원)_Sales14356_PKG` |
| 현재 포탈 계산잔액 | 2,500,000 |
| 목표 다우 잔액 | 983,000 |
| 보정 주문 총액 | 1,517,000 |
| 권장 orderName | `지.비.에스(G.B.S)치과기공소_Promotion PKG 잔액 보정(Sales14356)` |
| 권장 externalOrderNo | `PKG-BAL-CORR-Sales14356` |
| 제품 unitPrice/totalAmount | 1,517,000 |
| 제품 supplyAmount | 1,379,091 |
| 제품 taxAmount | 137,909 |
| 비고 | 다우 `Sales14356-1` 출고완료 행의 차감 1,517,000원이 포탈 계약 주문에는 반영되지 않았다. |

### Sales14454

| 필드 | 값 |
|---|---|
| 고객사 | 인사랑치과 |
| companyUk | `77b658cc-51cc-59f0-aae5-7dc5b3c109ad` |
| 고객 | 윤효진 |
| customerUk | `6943a470-3c89-576f-9fea-e9c10ad6fe72` |
| 담당자 | 김수련 Chloe |
| contractNo | `Sales14454` |
| contractUk | `contract_sf_pkg_v2_f54223d289e65f05cb40b913` |
| contractName | `인사랑치과(수원)_Sales14454_PKG` |
| 현재 포탈 계산잔액 | 2,670,000 |
| 목표 다우 잔액 | 355,750 |
| 보정 주문 총액 | 2,314,250 |
| 권장 orderName | `인사랑치과_Promotion PKG 잔액 보정(Sales14454)` |
| 권장 externalOrderNo | `PKG-BAL-CORR-Sales14454` |
| 제품 unitPrice/totalAmount | 2,314,250 |
| 제품 supplyAmount | 2,103,864 |
| 제품 taxAmount | 210,386 |
| 비고 | 현재 포탈에는 `Sales19481` 330,000원만 계약 차감 반영되어 있다. 다우 목표 차감 합계 2,644,250원 대비 부족분 2,314,250원을 보정한다. |

### Sales14966

| 필드 | 값 |
|---|---|
| 고객사 | 경성치과기공소(부산) |
| companyUk | `c915963f-8f88-55fa-a9fe-2622f6cc14ba` |
| 고객 | 박동위 |
| customerUk | `ac26ae7f-17fd-5a5e-838d-9d5eab86b0ce` |
| 담당자 | 김수련 Chloe |
| contractNo | `Sales14966` |
| contractUk | `contract_sf_pkg_v2_a8851a11cd8270791f9c6153` |
| 현재 포탈 계산잔액 | 2,000,000 |
| 목표 다우 잔액 | 2,000,000 |
| 보정 주문 총액 | 0 |
| 생성 판단 | 주문 생성 불필요 |
| 비고 | 다우 `Sales14966` + `Sales14966-1` 합산 기준으로 이미 포탈 계산잔액과 일치한다. |

### Sales16128

| 필드 | 값 |
|---|---|
| 고객사 | 에이블치과기공소(영등포) |
| companyUk | `fd0e0b6f-0e97-5e3d-b74d-18bdb8e4190e` |
| 고객 | 심규현 |
| customerUk | `c6d3297e-4fa6-5336-852e-1425d3d7c9a9` |
| 담당자 | 이미연 |
| contractNo | `Sales16128` |
| contractUk | `contract_sf_pkg_v2_e94339560b25d4f1563c0bf6` |
| contractName | `에이블덴탈랩(영등포)_Sales16128_PKG` |
| 현재 포탈 계산잔액 | -985,000 |
| 목표 다우 잔액 | 15,000 |
| 보정 주문 총액 | -1,000,000 |
| 권장 orderName | `에이블치과기공소(영등포)_Promotion PKG 잔액 보정(Sales16128)` |
| 권장 externalOrderNo | `PKG-BAL-CORR-Sales16128` |
| 제품 unitPrice/totalAmount | -1,000,000 |
| 제품 supplyAmount | -909,091 |
| 제품 taxAmount | -90,909 |
| 비고 | 포탈 계약원금이 1,000,000원 작게 잡혀 현재 잔액이 -985,000원이다. 마이너스 보정 주문으로 잔액을 1,000,000원 복원해야 다우 잔액 15,000원과 맞는다. |

### Sales11804

| 필드 | 값 |
|---|---|
| 고객사 | 바른손치과기공소(아산) [구]천안 |
| companyUk | `10a743d1-dd4f-5083-9184-6fe2f1387c4a` |
| 고객 | 이성근 |
| customerUk | `38e9aec2-b4fd-5a1d-8913-db13637162a9` |
| 담당자 | 김오중, 이미연 |
| contractNo | `Sales11804` |
| contractUk | `contract_sf_pkg_v2_89eafd3296bcdaee3445c04e` |
| contractName | `바른손치과기공소(천안)_Sales11804_PKG` |
| 현재 포탈 계산잔액 | 250,000 |
| 목표 다우 잔액 | 150,000 |
| 보정 주문 총액 | 100,000 |
| 권장 orderName | `바른손치과기공소(아산)_Promotion PKG 잔액 보정(Sales11804)` |
| 권장 externalOrderNo | `PKG-BAL-CORR-Sales11804` |
| 제품 unitPrice/totalAmount | 100,000 |
| 제품 supplyAmount | 90,909 |
| 제품 taxAmount | 9,091 |
| 비고 | 포탈 계약원금 500,000원과 다우 원금 400,000원의 차이 100,000원을 주문 차감으로 보정하는 방식이다. |

### Sales19534

| 필드 | 값 |
|---|---|
| 고객사 | (주)메디클러스(청주) |
| companyUk | `076e8f6d-23b5-508f-bcdf-a86cfcc89973` |
| 고객 | 최돈주 |
| customerUk | `acc0541e-77da-55fc-8679-e09f717ad0fe` |
| 담당자 | 최성혁 Hardy |
| contractNo | `Sales19534` |
| contractUk | `contract_sf_pkg_v2_e3a6f42b1aa91ffebb30f99d` |
| contractName | `(주)메디클러스(청주)_Sales19534_PKG` |
| 현재 포탈 계산잔액 | 1,825,000 |
| 목표 다우 잔액 | 1,805,000 |
| 보정 주문 총액 | 20,000 |
| 권장 orderName | `(주)메디클러스(청주)_Promotion PKG 잔액 보정(Sales19534)` |
| 권장 externalOrderNo | `PKG-BAL-CORR-Sales19534` |
| 제품 unitPrice/totalAmount | 20,000 |
| 제품 supplyAmount | 18,182 |
| 제품 taxAmount | 1,818 |
| 비고 | 포탈 계약원금 3,000,000원과 다우 원금 2,980,000원의 차이 20,000원을 주문 차감으로 보정하는 방식이다. |

## 검토 포인트

1. `Sales15705`의 20,000,000원 보정 주문은 금액이 크다. 주문으로 맞출 수는 있지만, 실제 원인은 계약원금 과대 산정이므로 계약금 직접 정정 방식과 비교해야 한다.
2. `Sales16128`은 마이너스 주문이 필요하다. 기존 `DOF-PKG-Balance` 운영 데이터에 음수 주문 사례는 있지만, UI/승인 정책에서 음수 제품 입력이 막히는지 별도 확인이 필요하다.
3. 보정 주문이 ERP/매출/수금에 어떤 영향을 주는지 확인해야 한다. 잔액만 맞추려는 목적이라면 수금은 0원 또는 미생성으로 두는 것이 기존 이관 주문 패턴과 가깝다.
4. 이 방식은 계약 잔액을 다우 PKG 잔액에 맞추는 운영 가정이다. 기존 정책 문서에는 계약 계산값과 다우 PKG 원장을 분리해야 한다는 판단도 있으므로, 실제 반영 전 정책 결정이 필요하다.
