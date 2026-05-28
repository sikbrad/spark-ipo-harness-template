# 포탈 제품코드 정확일치 강조 계획

## 목표
제품코드 검색에서 퍼지/부분 검색 결과는 유지하되, 검색어와 제품코드가 정확히 일치하는 결과를 눈에 띄게 표시한다.
사용자는 검색 결과가 여러 개 떠도 빨간 강조 셀이 없으면 "입력한 코드와 정확히 같은 품목은 없다"고 판단할 수 있어야 한다.

## 배경
- 피드백: `https://portal.doflab.com/admin/feedback?id=cmpossedh000g4bjbvw9k8bka`
- 요청자: 이미연
- 사용자 응답 방향:
  - "입력한 코드가 없으면 다른 내역을 안 뜨게" 하는 것은 어렵다.
  - 현재 검색은 확률/유사도 기반 결과를 포함하므로 다른 후보도 떠야 한다.
  - 대신 `정확하게 일치`하는 경우 셀을 빨간색으로 표시하거나 강조할 수 있다.

## 가능 여부
가능하다. 검색 결과를 줄이는 서버 로직을 바꾸지 않고, 프론트 렌더링 단계에서 `productCode`와 적용된 검색어가 정확히 같은지만 판정하면 된다.

권장 범위는 프론트 중심 변경이다. API 응답 구조, DB 검색 조건, `pg_trgm` 유사도 기준은 유지한다.

## 확인한 현 구현
- 포탈 코드 위치: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az`
- 제품 검색 조건: `apps/server/src/common/helpers/db-search.helper.ts`
  - `PRODUCT`: `productCode`, `productName`, `engProductName`, `productShortName`, `factory`, `stdType`, `packUnit`
  - `ORDER_PRODUCT`: `productCode`, `productName`, `serialNumbers`, `note`, 주문/고객 관련 relation
  - `CONTRACT_PRODUCT`: `productCode`, `productName`, `note`, 계약/고객 관련 relation
- 제품 목록 검색: `apps/server/src/products/products.service.ts`
  - `contains` 검색 후 필요 시 `findFuzzyMatchIds`/`attachSimilarityAndSort` 사용
- 목록 UI:
  - `apps/front/src/pages/ProductList.tsx`
  - `apps/front/src/pages/OrderProductList.tsx`
  - `apps/front/src/pages/ContractProductList.tsx`
  - 공통 테이블: `apps/front/src/components/ListPageLayout.tsx`
- 검색어 상태:
  - `useListPage.ts`가 입력 중 검색어와 실제 적용된 검색어를 분리한다.
  - 화면 강조는 입력 중 값이 아니라 실행된 검색어, 즉 URL `q`/`appliedSearch` 기준이어야 한다.

## 설계
- 정확일치 기준:
  - 기본: `productCode.trim().toLowerCase() === appliedSearch.trim().toLowerCase()`
  - 제품코드에서 하이픈/공백 표기 흔들림이 실제로 문제가 되면, `UnifiedProductTree.tsx`의 `normalizeSeparators` 방식과 맞춰 보조 비교를 추가한다.
- 표시 방식:
  - 정확일치 셀만 연한 빨강 배경 + 진한 빨강 텍스트/테두리로 강조한다.
  - 셀 안에 작은 `정확일치` 배지를 붙인다.
  - 행 전체 강조보다 셀 강조를 우선한다. 사용자가 비교해야 하는 값은 제품코드이기 때문이다.
- 검색 결과 정책:
  - 다른 후보는 숨기지 않는다.
  - 정확일치가 없는 경우 별도 차단/필터 없이 빨간 셀이 없는 상태로 둔다.
  - 필요하면 후속으로 검색창 근처에 `정확일치 없음` 보조 문구를 추가할 수 있지만, 1차 범위에서는 과한 UI 변경을 피한다.

## 작업 항목
- [x] 현재 제품코드 검색/렌더링 위치 확인
- [x] 서버 검색 로직 변경 없이 프론트 강조로 해결 가능 여부 판단
- [x] `useListPageWithServer` 또는 `ListPageLayout`에서 적용된 검색어(`appliedSearch`)를 셀 렌더러에 전달할 수 있는 최소 변경 지점 확정
- [x] `productCode` 정확일치 판정 유틸을 추가하거나 가까운 컴포넌트 내부 함수로 구현
- [x] `ProductList.tsx`, `OrderProductList.tsx`, `ContractProductList.tsx`의 제품코드 셀에 정확일치 강조 적용
- [x] 피드백의 실제 `pageUrl`이 통합검색(`/search`)이면 `SearchPage.tsx`의 제품/주문제품/계약제품 섹션에도 같은 강조 적용
- [x] 타입체크 실행
- [x] 로컬 포탈에서 제품코드 정확일치 있음/없음 두 케이스를 브라우저로 확인

## 검증 계획
- 정확일치 있음:
  - `/products?q=<실제 제품코드>`에서 해당 제품코드 셀만 빨간 강조와 `정확일치` 배지가 표시되는지 확인한다.
  - `/order-products?q=<실제 제품코드>`, `/contract-products?q=<실제 제품코드>`도 같은 기준으로 확인한다.
- 정확일치 없음:
  - 비슷하지만 존재하지 않는 코드로 검색했을 때 유사 결과는 유지되고 빨간 강조는 없는지 확인한다.
- 회귀 확인:
  - 검색어 입력만 하고 검색 실행 전에는 강조가 바뀌지 않아야 한다.
  - 기존 필터/뷰/정렬/다운로드 동작에는 영향이 없어야 한다.

## 리스크
- 공통 `ListPageLayout`의 `renderCell` 시그니처를 바꾸면 여러 목록 페이지에 영향이 갈 수 있다. 가능하면 optional context 인자를 추가하거나 제품 관련 페이지에서만 래핑하는 방향이 안전하다.
- 제품코드 표기에서 하이픈/공백 차이를 정확일치로 볼지 정책 결정이 필요하다. 1차는 대소문자만 무시하고, 구분자 무시는 후속 정책으로 둔다.
- 정확일치가 여러 주문제품/계약제품 행에 반복될 수 있다. 이 경우 같은 제품코드가 들어간 모든 행의 제품코드 셀이 강조되는 것이 자연스럽다.

## 실행 기록
- 구현:
  - `apps/front/src/utils/productCodeExactMatch.ts`에 대소문자 무시 정확일치 판정 추가
  - `apps/front/src/components/ProductCodeExactMatchCell.tsx` 추가
  - `ListPageLayout` 렌더 컨텍스트에 `appliedSearch` 전달
  - 제품/주문제품/계약제품 목록과 통합검색 제품코드 셀에 강조 적용
- 검증:
  - `bun run build:front` 통과
  - 로컬 브라우저 `http://localhost:54221/products?q=TEST_1`: `정확일치` 배지 1개 확인
  - 로컬 브라우저 `http://localhost:54221/products?q=TEST`: 유사 결과 유지, `정확일치` 배지 0개 확인
  - 로컬 브라우저 `http://localhost:54221/search?q=TEST_1`: 통합검색 제품 섹션 `정확일치` 배지 1개 확인
