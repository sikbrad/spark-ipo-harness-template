# 포탈 주문취소 데이터 변경 규칙 리서치

작성일: 2026-05-28 10:50 KST

## 질문

새로 생긴 `실주(주문취소)` 상태에서 데이터 변경 규칙을 어떻게 잡을지, 누가 수정권한을 가져야 할지에 대한 초안.

## 결론 요약

`주문취소`는 일반 수정권한으로 처리하면 안 된다. 취소는 주문 금액, 물류 발주, 출하, 수금, ERP 연동, 자산 생성까지 되돌릴 수 있는 업무 이벤트이므로 다음 원칙을 권장한다.

1. 주문취소 후 원 주문 데이터는 기본 잠금.
2. 취소 사유, 고객 요청 근거, 취소 영향, 증빙 파일은 필수.
3. 취소 요청자와 승인자는 분리.
4. 출고/수금/ERP 영향이 생긴 이후에는 물류 또는 회계 확인을 추가.
5. 주문완료 후에는 `CLOSED_LOST`로 직접 바꾸지 말고, 주문완료취소/ERP 삭제/매출취소/반품 같은 별도 회계 플로우로 처리.

## 포탈 현재 상태

확인 저장소: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az`

- `apps/server/prisma/schema.prisma`
  - `OrderStatus.CLOSED_LOST`가 존재하며 주석은 `영업종결-실패 (SF Closed Lost)`.
  - `QuotationStatus.REJECTED`도 `실주` 라벨을 사용한다.
- `packages/api-contract/src/schemas/common.ts`
  - `ORDER_STATUS_LABELS.CLOSED_LOST`는 현재 `실주`.
- `apps/server/src/orders/order-transition-policy.helper.ts`
  - `CLOSED_LOST: []`로 종결 상태. 현재 상태에서 가능한 다음 전이가 없다.
- `apps/front/src/utils/orderStatusTransition.ts`
  - 프론트 상태 전이도 `CLOSED_LOST: []`.
- `apps/server/src/permissions/permissions.service.ts`
  - `canEditOrder()`는 `REGISTERED`~`COMPLETED`까지만 명시 허용하고 default는 false라 `CLOSED_LOST` 수정은 서버에서 막힌다.
- `apps/front/src/utils/fieldEditabilityRules.ts`
  - `CLOSED_LOST`를 `COMPLETED`와 유사한 종결 상태로 다루려는 주석과 잠금 목록이 있다. 다만 서버처럼 전면 차단이 아니라 일부 필드가 UI상 열릴 가능성이 있어 UX/서버 정책 정렬이 필요하다.

관련 기존 계획:
- `proc/plan/2026-05-26_portal-order-status-real-order.md`
  - 15개 주문을 prod/test/local에서 `CLOSED_LOST`로 직접 변경한 기록이 있다. 변경 범위는 `Order.status`, `updatedAt`뿐이라 사유/승인/감사로그가 남는 정식 취소 플로우는 아니었다.
- `proc/plan/2026-05-28_portal-order-status-label-rename.md`
  - 사용자 표시명 `실주`를 `주문취소`로 바꾸는 계획이 있다. DB/API enum은 `CLOSED_LOST` 유지.

## 내부 업무 자료 근거

`dof-order-web-3-az/proc/30_research/references/fg-infos/rule-analysis/from-interviews/08-예외처리-업무규칙.md`에는 이미 주문취소 규칙 부재가 문제로 기록되어 있다.

핵심 내용:
- 주문취소에 대한 명확한 규칙/프로세스가 없다.
- 큰 주문이 갑자기 취소되면 이미 발주된 비용과 인력 손실이 발생한다.
- 필요한 규칙 후보로 사유 필수, 유예 기간, 당일 취소 제한, 대형 주문 선입금, 발주 이후 취소 수수료/위약금이 제시되어 있다.

## 외부 기준

- OWASP Authorization Cheat Sheet: 새 기능은 기본 차단 원칙으로 설계하고, 권한은 모든 요청에서 서버 쪽에서 검증해야 한다. 클라이언트 UI 잠금만 믿으면 안 된다.
  - https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html
- NIST RBAC FAQ: RBAC는 사용자-역할, 권한-역할 배정을 핵심으로 하고, 정적/동적 직무분리 관계를 모델에 포함한다.
  - https://csrc.nist.gov/Projects/role-based-access-control/faqs
- NIST SP 800-53 Rev.5: 감사 기록은 사후 조사와 조직 기록 보존 요구를 지원해야 하며, 시스템은 정의된 이벤트에 대한 감사 기록 생성 능력을 가져야 한다.
  - https://doi.org/10.6028/NIST.SP.800-53r5
- Salesforce Developer Docs: 주문 취소 전에 fulfillment의 PONR(point of no return)를 확인하고, 취소는 별도 supplemental/change order를 통해 처리하는 패턴을 제시한다. 이는 취소가 단순 상태값 변경이 아니라 이행 상태와 보상 작업을 포함하는 워크플로우라는 근거로 볼 수 있다.
  - https://developer.salesforce.com/docs/industries/cme/guide/comms-freeze-order.html
  - https://developer.salesforce.com/docs/industries/cme/guide/comms-cancel-order.html

## 권한 설계안

### 추천 capability

| 권한 | 부여 대상 | 용도 |
|---|---|---|
| `cancel.order.request` | 담당 영업, 영업팀장 | 주문취소 요청 생성 |
| `cancel.order.approve` | 영업팀장, 운영관리/SalesOps | 주문취소 승인 |
| `cancel.order.logistics` | 물류 책임자 | 출고승인 이후 취소 확인 |
| `cancel.order.accounting` | 회계/수금 담당 | 수금/계산서/ERP 영향 확인 |
| `cancel.order.force` | ADMIN + 지정 운영관리자 | 오입력 복구, 예외적 재개방 |

### 역할별 초안

- 영업 담당자: 취소 요청만 가능. 본인 요청을 본인이 승인하지 못한다.
- 영업팀장: 초기 단계 취소 승인 가능. 금액/고객/계약 영향이 큰 건은 임원 또는 운영관리 확인으로 올린다.
- 물류: 출고승인 이후 취소에 필수 확인자. 이미 발주, 외주 작업, 출하, 운송 예약이 있으면 손실/수수료 메모를 요구한다.
- 회계/수금: 수금 완료, 계산서 발행, ERP 연동, 회계마감이 있는 경우 필수 확인자.
- ADMIN: 권한 부여/복구자이지 일반 취소 승인자가 되면 안 된다. 긴급 복구는 가능하되 감사로그와 사유를 강제한다.

### 화면 조작 매트릭스

| 권한/역할 | 가능 | 불가능 |
|---|---|---|
| 담당 영업 | 주문취소 요청 버튼, 취소 사유 코드/상세 사유 입력, 고객 요청일 입력, 증빙 첨부, 승인 전 요청 철회 | 본인 요청 승인, 취소 확정, 제품/수량/단가/고객사/수금/출고 정보 수정 |
| 영업팀장/운영관리 | 승인, 반려, 보완요청, 사유 코드 확정, 취소 영향 메모 입력 | 본인이 요청한 건 승인, 물류/회계 확인 대상 건 단독 확정 |
| 물류 | 물류 영향 확인, 발주/외주/출하/운송예약 손실 메모 입력, 물류 확인 완료 처리 | 최종 승인 단독 처리, 영업 사유 변경, 수금/계산서/ERP 정보 수정 |
| 회계/수금 | 회계 영향 확인, 매출취소 필요 여부 표시, 회계 확인 메모 입력, 권한 범위 내 수금행 정리 | 영업 사유 변경, 제품/단가/고객사/출고 정보 수정 |
| 관리자/예외처리자 | 예외 재개방, 오입력 복구, 강제 상태 보정, 권한 부여 | 일반 운영 승인자로 상시 사용 |

## 상태별 규칙 초안

| 현재 상태 | 취소 요청 | 승인/확인 | 데이터 처리 |
|---|---:|---|---|
| `REGISTERED` | 영업 가능 | 영업팀장 또는 운영관리 | `CLOSED_LOST` 전환, 사유 필수, 원 데이터 잠금 |
| `APPROVAL_REQUESTED` | 영업 가능 | 영업팀장. 요청자 본인 승인 금지 | 계약잔액/수금예정 복원 확인 |
| `TEAM_LEAD_APPROVED` | 가능 | 임원/영업팀장 중 업무상 상위자 | 승인 이후 변경 필드 영향 점검 |
| `EXECUTIVE_APPROVED` | 가능 | 출고승인권자 또는 임원 확인 | 고객/결제/제품 변경 잠금 유지 |
| `RELEASE_APPROVED` | 제한 가능 | 물류 필수, 필요 시 회계 | 발주/출고예약/외주작업 손실 기록 |
| `RELEASE_HOLD` | 가능 | 물류 또는 회계, 보류 사유와 함께 판단 | 보류 사유 해결 없이 취소만 남기지 않도록 사유 연결 |
| `SHIPPED` | 매우 제한 | 물류 + 회계 필수 | 출하/자산/운송 이력 때문에 반품/매출취소 플로우 후보 |
| `COMPLETED` | 직접 금지 권장 | ADMIN + `approve.done` + 회계/ERP 확인 | 기존 주문완료취소 또는 별도 ERP/매출취소 플로우 |
| `CLOSED_LOST` | 재취소 없음 | 재개방은 `cancel.order.force`만 | 원 주문 데이터 수정 불가. 댓글/증빙 append-only |

## 취소 후 허용 필드

원칙: 원 주문의 상업적 사실을 바꾸는 필드는 모두 잠근다.

허용 후보:
- 취소 사유 코드
- 취소 상세 사유
- 고객 요청일
- 고객 요청 근거 첨부
- 내부 영향 메모
- 취소 수수료/손실 추정
- 댓글/히스토리/해시태그

불허 후보:
- 고객사, 고객, 주문구분, 제품, 수량, 단가, 통화, 과세, 결제조건
- 출고요청일, 출고일, 운송장, 시리얼번호
- 입금 완료 수금행 직접 수정

수금/회계 정보는 `write.collection` 또는 회계 전용 권한으로 별도 처리한다. 주문취소 권한자가 회계 데이터를 같이 고칠 수 있으면 직무분리가 깨진다.

## 구현 아이디어

1. 즉시 적용 가능한 최소안
   - `CLOSED_LOST`에서는 원 주문 데이터 조작을 서버/프론트 모두 차단.
   - 상태 전환은 ADMIN + `approve.done`만 임시 허용.
   - 전환 시 `note` 필수, 댓글과 AuditLog 기록.

2. 추천안
   - `OrderCancellationRequest` 또는 기존 Comment/AuditLog 확장으로 취소 요청 레코드 생성.
   - 요청, 승인, 물류 확인, 회계 확인, 최종 전환을 분리.
   - 상태 전환 API는 `targetStatus=CLOSED_LOST`일 때 사유/근거/승인 조건을 강제.
   - 취소 후에는 취소 메타데이터만 수정 가능하고 원 주문 필드는 잠근다.

3. 장기안
   - 주문취소를 `CLOSED_LOST` 단일 상태로 끝내지 않고, 회계/물류 영향 단계에 따라 `CANCEL_REQUESTED`, `CANCEL_APPROVED`, `CANCELLED`, `CANCEL_REJECTED` 같은 별도 취소 워크플로우를 둔다.
   - 완료/출하 이후는 반품, 매출취소, ERP 삭제/수정과 연결된 별도 모듈로 분리한다.

## 업무 확정 질문

아래는 사용자에게 바로 물어보기보다, 회의/업무정의 때 결정받아야 할 항목이다.

- `주문취소`는 SF `Closed Lost`와 같은 의미인가, 아니면 고객의 실제 주문 취소인가?
- 취소 요청 사유 코드는 어떤 값으로 둘 것인가?
- 금액 기준을 둘 것인가? 예: USD 10,000 이상, 이미 외주 발주 있음, 미수/연체 있음.
- 취소 유예 기간을 둘 것인가? 예: 요청 후 24시간 내 물류 확인 전까지 보류.
- 요청자 본인 승인 금지를 시스템 규칙으로 강제할 것인가?
- 완료 주문은 포탈에서 취소할 수 없게 할 것인가, 아니면 ERP/회계 플로우까지 포함해 허용할 것인가?
- 과거 DB 직접 변경된 `CLOSED_LOST` 주문에 사유/승인 이력을 소급 입력할 것인가?

## 추천 답변안

업무 담당자에게는 이렇게 제안하면 된다.

> 주문취소는 일반 수정권한으로 열지 말고, 담당 영업은 취소 요청만 가능하게 두는 것이 좋겠습니다. 승인권한은 영업팀장/운영관리 쪽에 두고, 출고승인 이후 건은 물류 확인, 수금/계산서/ERP 영향이 있으면 회계 확인을 추가하는 방식이 안전합니다. 주문취소 후 원 주문 데이터는 잠그고, 취소 사유/증빙/댓글만 남기게 하는 것을 기본 규칙으로 제안드립니다. 주문완료 이후 건은 단순 주문취소가 아니라 ERP/매출취소/반품 쪽 절차로 분리하는 게 맞습니다.
