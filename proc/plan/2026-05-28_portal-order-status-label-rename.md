# 포탈웹 실주 라벨 주문취소 변경

## 목표

포탈웹에서 사용자에게 보이는 `실주` 문구를 `주문취소`로 일관 변경한다.
이번 변경은 표시 라벨 변경으로 한정하고, 기존 DB/API 상태값인 `CLOSED_LOST` 및 관련 enum 이름은 유지한다.

완료 기준:
- 활성 포탈웹 화면, 공통 라벨, 테스트 기대값, 사용자 문서에서 `실주`가 `주문취소`로 정리된다.
- 단순 문자열 치환이 아니라 주문/견적 상태 문맥의 `실주`만 변경한다.
- 빌드와 관련 테스트가 통과하고, 로컬 화면에서 `CLOSED_LOST` 상태가 `주문취소`로 표시됨을 확인한다.

## 대상 저장소

- `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az`

## 현재 확인된 변경 후보

- `packages/api-contract/src/schemas/common.ts`
  - `ORDER_STATUS_LABELS.CLOSED_LOST: '실주'`
  - `QUOTATION_STATUS_LABELS.REJECTED: '실주'`
- `apps/front/src/pages/UserManualPage.tsx`
  - 견적 상태 흐름의 `수주/실주`
- `apps/front/src/utils/fieldEditabilityRules.ts`
  - 주문/견적 상태 설명 주석의 `실주`
- `tests/sf-data-integrity.spec.ts`
  - `실주` 라벨 기대값
- `tests/sf-data-display.spec.ts`
  - `실주` 라벨 기대값 및 테스트 설명
- `tests/with-cli/references/middle_quotation_list_properties.md`
  - 상태 필터 기대 설명의 `실주`
- `apps/server/prisma/schema.prisma`, `apps/server/prisma/migrations/007_order_status_closed_lost.sql`
  - DB schema/comment 문구. enum 값은 유지하되 주석 문구는 `주문취소` 기준으로 정리할지 확인한다.
- `proc/10_spec`, `proc/30_research`, `proc/50_plan` 하위 문서
  - 활성 명세는 최신 라벨로 갱신하고, 과거 조사/계획 기록은 이력 보존 관점에서 필요한 경우만 별도 메모를 남긴다.

## 작업 항목

- [x] 대상 저장소의 `AGENTS.md`와 현재 git 상태를 확인한다.
- [x] `실주` 전체 사용처를 다시 검색하고, `과실주`처럼 무관한 단어는 제외 목록으로 분리한다.
- [x] 상태 코드/DB 값 유지 원칙을 확인한다.
  - `OrderStatus.CLOSED_LOST`는 유지
  - `QuotationStatus.REJECTED`는 유지
  - DB migration 또는 enum rename은 이번 범위 밖
- [x] 공통 API contract 라벨을 `주문취소`로 변경한다.
- [x] 프론트 사용자 매뉴얼, 상태 표시, 주석 등 활성 코드의 사용자-facing 문구를 변경한다.
- [x] 테스트명, 테스트 기대값, reference 문서를 새 라벨 기준으로 변경한다.
- [x] 활성 명세 문서 중 현재 제품 동작을 설명하는 곳만 `주문취소` 기준으로 갱신한다.
- [x] `rg -n "실주"`로 잔여 사용처를 재검토하고 의도적으로 남기는 곳은 이유를 기록한다.
- [x] 검증을 실행한다.
  - `bun run build:backend`
  - `bun run build:front`
  - 라벨 관련 Playwright 테스트 또는 대상 spec 실행
- [x] 로컬 포탈 화면에서 `CLOSED_LOST` 주문/견적 상태가 `주문취소`로 보이는지 확인한다.
- [x] 변경 파일과 검증 결과를 계획 문서에 실행 기록으로 업데이트한다.

## 주의 사항

- 이 작업은 “실패/상실” 의미의 코드명을 “취소” 의미로 바꾸는 업무 용어 변경이다. 데이터 상태 전환 규칙까지 바꾸면 영향 범위가 커지므로, 구현 중에는 표시 라벨 변경과 상태 전이/DB 변경을 분리한다.
- 견적 `REJECTED`의 기존 라벨도 `실주`라서 사용자-facing 일괄 변경 대상 후보에 포함한다. 다만 “견적 거절”과 “주문취소”의 업무 의미가 다르면 별도 용어 확인 후 범위를 조정한다.
- `proc/archive/`는 명시 요청 없이는 열람하지 않는다.

## 실행 기록

변경:
- `packages/api-contract/src/schemas/common.ts`
  - `ORDER_STATUS_LABELS.CLOSED_LOST: '주문취소'`
  - `QUOTATION_STATUS_LABELS.REJECTED: '주문취소'`
- `apps/front/src/pages/UserManualPage.tsx`
  - 견적 상태 흐름 표시를 `수주/주문취소`로 변경
- `apps/front/src/utils/fieldEditabilityRules.ts`
  - 상태 설명 주석을 새 라벨로 정리
- `apps/server/prisma/schema.prisma`
  - `QuotationStatus.REJECTED` 주석을 `주문취소`로 변경
- `apps/server/prisma/migrations/007_order_status_closed_lost.sql`
  - migration 설명 주석을 `주문취소`로 정리
- `proc/10_spec/fsd/spec-quotation-create.md`
  - 견적 상태 옵션/라벨을 `주문취소` 기준으로 갱신
- `tests/sf-data-display.spec.ts`, `tests/sf-data-integrity.spec.ts`, `tests/with-cli/references/middle_quotation_list_properties.md`
  - 테스트명/기대값/reference 문구를 `주문취소` 기준으로 변경

잔여 `실주`:
- `scripts/erp/product.html`: `과실주`로 무관
- `proc/30_research/**`, `proc/50_plan/**`: 과거 연구/계획 기록이므로 이력 보존을 위해 유지

검증:
- `bun run build:backend` 통과
- `bun run build:front` 통과
- 로컬 브라우저 `Sales20409` 주문 상세:
  - `order-status-badge-CLOSED_LOST`: `주문취소`
  - `order-status-label-CLOSED_LOST`: `주문취소`
  - 화면 내 `실주` 텍스트 0건, `주문취소` 텍스트 2건
- `bunx playwright test tests/sf-data-display.spec.ts -g "CLOSED_LOST"`:
  - 라벨 관련 2건 통과
  - 데이터 건수 회귀 테스트 1건 실패: 현재 DB `CLOSED_LOST total=992`, 테스트 기대값 `977`
- `bunx playwright test tests/sf-data-display.spec.ts -g "주문취소"` 통과
- `bunx playwright test tests/sf-data-integrity.spec.ts -g "주문취소"` 통과
