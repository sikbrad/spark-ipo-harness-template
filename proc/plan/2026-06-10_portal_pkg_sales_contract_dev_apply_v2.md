# 포탈 PKG Sales 계약 dev 반영 v2

## 목표
본섭 포탈 DB를 타임스탬프 덤프해 로컬/테섭 DB에 반영하되 `ApiToken`은 각 환경 값을 보존한다. 이후 테섭 DB에서 SF 스크랩 데이터 기반 `Sales*` PKG 계약을 생성하고, 다우오피스 PKG 데이터는 계약-차감주문 관계 확인에만 사용한다. 기존 계약 잔액 알고리즘으로 재계산한 뒤 다우 잔액과 비교 리포트 및 v2 HTML을 작성한다.

## 작업 항목
- [x] 본섭 포탈 DB 덤프를 `output/` 아래 타임스탬프 디렉터리에 저장
- [x] 로컬 DB `ApiToken` 백업 후 본섭 덤프 restore 및 토큰 복구
- [x] dev DB `ApiToken` 백업 후 본섭 덤프 restore 및 토큰 복구
- [x] SF 스크랩 데이터와 기존 로직을 확인해 `Sales*` PKG 계약 후보/초기금액 계산 기준 확정
- [x] 다우오피스 PKG 데이터는 액수 반영 없이 계약-차감주문 관계 매핑용으로만 준비
- [x] dev DB에서 기존 `Sales%` 계약 제거 후 SF 기반 계약/계약상품 생성
- [x] dev DB에서 다우 관계 기반 하위 주문 `Order.contractUk` 연결
- [x] 기존 계약 잔액 알고리즘으로 dev DB 계약 잔액 재계산
- [x] 다우 PKG 잔액과 dev 계산 잔액 비교 리포트 작성, 종결 Sales 계약 0원 여부 포함
- [x] 활성 계약 기준 다우 vs 포탈 주문별 v2 HTML 작성
- [x] dev DB 현재 상태를 덤프해 local DB에 반영하고 local `ApiToken` 복구
- [x] 초기 계약금 계산식을 특정 PKG 원금 제품 라인만 사용하도록 v3로 수정
- [x] dev/local Sales PKG 계약금, 계약상품, 잔액을 v3 기준으로 재계산
- [x] v3 리포트와 활성 HTML 작성
- [x] v3 원금 제품 계산식을 로컬 재계산 스크립트로 반영
- [x] v3 HTML을 v2처럼 다우 vs 포탈 비교 카드가 먼저 보이도록 갱신
- [x] 임시 재계산 스크립트 대신 포탈 공식 PKG 백필 경로에 v3 원금 제품 계산식 반영
- [x] 업무규칙 스펙에 Sales PKG 원금 제품/잔액 계산 규칙 반영
- [x] 공식 경로 계산값으로 v4 HTML 생성 후 v3와 차이 비교
- [x] ACC3030 거래처계정내역을 참고해 v5 HTML에 참값 후보 추정과 실제확인 필요 경고 추가
- [x] prod DB 변경 전 덤프를 `output/` 아래 타임스탬프 디렉터리에 저장
- [x] prod/local `Sales%` 계약 상태를 비교해 prod 적용 전후 건수 확인
- [x] 공식 PKG 백필 경로로 prod DB에 `Sales%` 계약/계약상품/하위주문 관계 반영
- [x] prod 계산 결과로 v6 HTML 작성
- [x] v3 HTML과 v6 HTML을 비교해 차이가 정상 범위인지 확인

## 진행 메모
- v2-v5까지 prod DB는 덤프 소스로만 사용했다. v6 요청부터는 prod 변경 전 덤프를 확보한 뒤 prod DB에 Sales PKG 계약을 직접 반영한다.
- dev/local restore 시 `ApiToken`은 restore 전 JSON 백업 후 restore 뒤 truncate/insert 방식으로 복구한다.
- 이번 명령은 다우 금액을 dev DB에 반영하지 않는다. 다우 사용행의 `usageAmount`, `packageAmount`, `packageBalance`는 리포트 비교용 ground truth로만 사용한다.
- 덤프 산출물: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/output/db-dumps/pkg-sales-dev-apply-v2-20260610_013052/`
- prod custom dump: `prod_dof_portal_prod_20260610_013052.dump` 68MB, restore list 960 lines.
- local restore 완료: Contract 1014건, Order 26509건, ApiToken 5건 복구.
- dev restore 완료: extension owner 관련 경고는 있었으나 Contract 1014건, Order 26509건으로 prod/local과 일치. ApiToken은 dev 백업본 9건으로 복구.
- SF/포탈 계약 시작금액 산정 기준: source `Sales*` 주문의 계약성 제품 라인(`SU-WP*`, `CO-ET*`, `CO-PR*`, 제품명 PKG/Package/Promotion/Warranty)을 사용한다. 제품 라인 총액이 양수면 그 값을 쓰고, 0원 `Promotion package 100/50` 또는 `Warranty 600`류는 제품명 숫자에서 금액을 추론한다. 다우 `packageAmount/packageBalance/usageAmount`는 계약 생성 금액으로 사용하지 않는다.
- dev 적용 결과: 다우 Sales PKG 후보 513건 중 source 주문과 SF/포탈 제품 금액 산정이 가능한 492건 생성, source 주문 누락 21건 제외. 생성된 Contract 492건, ContractProduct 1182건, 다우 usage 주문 매칭 1367건, 계약 하위 주문 연결 1341건.
- 리포트 산출물: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/output/pkg-sales-dev-apply-v2-20260610_013052/reconcile-report-v2/report.md`
- v2 HTML 산출물: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/output/pkg-sales-dev-apply-v2-20260610_013052/reconcile-report-v2/active-daou-vs-portal-v2.html`
- dev 비교 결과: 다우 Sales PKG 후보 513건, dev Sales 계약 492건, source 주문 누락 21건. 전체 잔액 일치 32건/불일치 460건. 활성(접수) 다우 127건 중 dev 계약 생성 120건, 활성 잔액 일치 9건/불일치 111건, 활성 차이 절대값 합계 3,510,313,468원. 종결(출고완료) dev 계약 372건 중 계산 잔액 비0은 356건이며 강제 보정하지 않았다.
- v2 HTML 검증: 계약 섹션 127개, usage row 387개, 제품 상세 details 213개. 검색 및 전체/잔액 차이/dev 계약 없음/주문금액 차이/주문 미매칭 필터 포함.
- dev -> local 반영: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/output/db-dumps/dev-to-local-sales-pkg-v2-20260610_014916/`에 dev custom dump를 저장하고 local DB에 restore했다. local `ApiToken`은 restore 전 백업본 5건으로 복구했다. 검증 결과 local/dev 모두 Sales Contract 492건, Sales ContractProduct 1182건, Sales linked child Order 1341건, Sales PackageContractUsage order 매칭 1367건으로 일치한다. ApiToken은 local 5건, dev 9건으로 각 환경 값 유지.
- v3 수정 필요: `Sales10213`, `Sales10410` 확인 결과 v2 계산식이 `CRAFT 5X Complete package` 같은 장비 본체 라인과 `Milling Machine Warranty 150`까지 원금에 포함했다. 실제 초기 PKG 원금은 `CO-ET-002 Promotion package 100 (For Korea)`처럼 특정 PKG 원금 제품 라인에서 계산해야 한다.
- v3 원금 제품 기준: `CO-ET*`/`CO-PR*` 중 제품명이 `Promotion package`인 라인, 또는 `SU-WP*` 중 제품명에 `PKG`가 있는 라인만 초기 계약금/초기잔여금에 사용한다. 장비 본체 `Complete package`, 일반 warranty, 기타 부속 패키지 라인은 제외했다.
- v3 dev/local 재계산 결과: 기존 Sales 계약 492건 중 v3 원금 제품이 없는 7건은 계약 생성 대상에서 제외되어 485건이 남았다. ContractProduct는 특정 원금 제품 511건으로 재구성했고, 계약 총액 합계는 1,248,229,700원이다. 관계 매핑은 다우 `PackageContractUsage`에서 `OD*`, `CO*`, `Sales*` 순으로 주문번호를 파싱하도록 수정해 `Sales20390`처럼 사용행 텍스트에 다른 Sales 번호가 섞인 경우를 보정했다. dev/local 모두 `Sales10213=계약금 1,000,000원/잔액 220,000원`, `Sales10410=계약금 1,000,000원/잔액 1,000,000원`, `Sales20390=계약금 6,000,000원/잔액 3,317,048원`으로 일치한다.
- v3 리포트 산출물: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/output/pkg-sales-dev-apply-v3-20260610_015148/reconcile-report-v3/report.md`
- v3 HTML 산출물: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/output/pkg-sales-dev-apply-v3-20260610_015148/reconcile-report-v3/active-daou-vs-portal-v3.html`
- v3 비교 결과: 다우 Sales PKG 513건, 포탈 v3 Sales 계약 485건, 포탈 계약 없음 28건. 전체 잔액 일치/불일치 289건/196건. 활성(접수) 다우 127건 중 포탈 계약 120건, 활성 잔액 일치/불일치 90건/30건, 활성 차이 절대값 합계 34,334,080원. 종결 계약 중 계산 잔액 비0은 317건/365건이며 강제 보정하지 않았다.
- v3 HTML 검증: 활성 계약 섹션 127개, 다우 사용행 387개, 포탈 주문 제품 상세 381개. 검색 및 전체/잔액 차이/포탈 계약 없음/주문금액 차이/주문 미매칭 필터 포함.
- 로컬 계산식 1차 반영: 처음에는 임시 `scripts/recalculate-sales-pkg-contracts-v3.mjs`와 `db:recalc:sales-pkg-contracts-v3`로 로컬 DB를 재계산했으나, 이후 공식 백필 경로에 같은 계산식을 반영하면서 임시 스크립트와 root package script는 제거했다.
- v3 HTML 비교성 보강: `active-daou-vs-portal-v3.html` 상단에 다우 PKG금액 합계, 포탈 v3 계약금 합계, 다우 잔액 합계, 포탈 잔액 합계, 잔액 차이 합계/절대값 카드 12개를 추가했다. 파일 파싱 검증 결과 카드 12개, 활성 계약 섹션 127개, 다우 사용행 387개가 존재한다.
- 지정 예시 재검증: 로컬 DB에서 `Sales10213`과 `Sales10410`은 모두 `CO-ET-002 Promotion package 100 (For Korea)` 1,000,000원 한 줄만 계약상품으로 남아 있고 각각 계약금/잔액은 `Sales10213=1,000,000/220,000`, `Sales10410=1,000,000/1,000,000`이다.
- 정식 경로 반영: 임시 `scripts/recalculate-sales-pkg-contracts-v3.mjs`와 root package script는 제거했다. 대신 `apps/server/scripts/backfill-pkg-contracts.ts`의 `--sync-daou-contracts` 경로를 복구해 다우 Sales 후보를 `Contract`로 합성하되, 다우 금액을 강제 반영하지 않고 source Sales 주문의 v3 원금 제품과 DB 저장 `PackageContractUsage` 관계로 잔액을 계산하게 했다. 기존 `sf` importSource Sales 계약도 이 공식 경로에서 갱신 가능하도록 포함했다.
- 스펙 반영: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/proc/10_spec/rules/포탈_업무규칙_정리.md`와 `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/proc/10_spec/work-rules/00-master-checklist.md`에 Sales PKG 원금 제품 기준, 다우 금액의 비교/관계 원장 역할, 기존 계약 잔액 공식 적용 방식을 반영했다.
- v4 공식 경로 적용: `bun run --cwd apps/server db:backfill:pkg-contracts -- --apply --skip-daou --skip-sales --sync-daou-contracts`로 로컬 DB에 적용했다. 결과는 Daou Sales 후보 507건 중 485건 upsert, ContractProduct 511건 생성, Sales 계약 485건/계약상품 511건/연결주문 1826건이다. `bun run --cwd apps/server build` 통과.
- v4 산출물: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/output/pkg-sales-dev-apply-v3-20260610_015148/reconcile-report-v3/active-daou-vs-portal-v4.html`
- v3-v4 비교: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/output/pkg-sales-dev-apply-v3-20260610_015148/reconcile-report-v3/v3-v4-comparison.md` 작성. 계약/제품 수는 동일하지만 잔액은 3건 차이난다. `Sales12181`은 `OD202601140016` 주문총액 102,600원이 추가 차감되어 -102,600원, `Sales16935`는 회사가 다른 `Sales17289` 주문 420,000원이 추가 차감되어 -420,000원, `Sales18106`은 `(분할)` 사용행 `OD202508140015` 주문총액 399,000원이 추가 차감되어 -399,000원 차이다. 따라서 v4는 v3와 완전히 동일하지 않다.
- v5 ACC3030 추정: 기존 ACC3030 전체 이력 파일 `output/2026-05-08-auto-01/ACC3030_거래처계정내역_2026-04-since-2010-01.json`과 포탈 DB의 `PackageContractUsage`/주문 연결을 함께 사용해 활성 잔액차이 30건 전체를 검토했다. 각 건마다 초기 PKG 원금 차이, 다우 사용액-포탈 주문총액 차이, 주문 미매칭, 주문 상태 제외, 회사 불일치, 단수/반올림 차이를 분리해 참값 후보를 추정했다. `Sales15705`, `Sales14356`, `Sales14966`, `Sales16128`, `Sales11804`, `Sales19534`처럼 초기 원금 차이가 주원인인 건과 `Sales19557`, `Sales14074`, `Sales20390`, `Sales12181`처럼 ACC3030 적요가 다우 사용액 쪽을 강하게 지지하는 건을 구분했다. `Sales12910`, `Sales18106`, `Sales16935`처럼 주문 상태/분할반제/회사 불일치 때문에 실제 확인이 필요한 건도 별도로 표시했다. 모두 ACC3030 적요 기반 추정이므로 실제 회계 전표/다우 결재 원문 확인 전 확정값으로 쓰면 안 된다고 v5에 강조했다.
- v5 산출물: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/output/pkg-sales-dev-apply-v3-20260610_015148/reconcile-report-v3/active-daou-vs-portal-v5.html`
- v5 근거 산출물: `amaranth-inference-v5.json`, `amaranth-inference-v5.md`, `amaranth-acc3030-v5-filtered-rows.json`, `package-usage-v5-focus.json`
- v6 prod 변경 전 덤프: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/output/db-dumps/prod-sales-pkg-contracts-v6-20260610_024215/prod_dof_portal_prod_before_sales_pkg_v6_20260610_024215.dump` 67.6MB, restore list 960 lines.
- v6 prod 적용 전 계수: local은 Sales Contract 485건, ContractProduct 511건, PackageContract link 485건, usage order link 1866건, linked child Order 1826건. prod는 Contract/ContractProduct/link/child Order 모두 0건이고 PackageContract 513건만 존재했다.
- v6 prod dry-run: 다우 원장 514건, 사용행 2029건, Sales 후보 507건 중 485건 upsert/계약상품 511건 예정, 스킵 22건.
- v6 prod apply: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/output/pkg-sales-dev-apply-v3-20260610_015148/prod-backfill-v6-apply/2026-06-09T174606199Z-apply.json`. 결과는 Sales 후보 507건 중 Contract 485건 upsert, ContractProduct 511건 생성, 스킵 22건. `ApiToken`은 건드리지 않았다.
- v6 prod 적용 후 계수: Sales Contract 485건, ContractProduct 511건, PackageContract 513건, PackageContract.contractUk link 485건, PackageContractUsage.orderUk link 1935건, Sales 계약 하위 Order 1827건. 로컬 대비 사용행 order link +69건, 하위 Order +1건이다.
- v6 HTML 산출물: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/output/pkg-sales-dev-apply-v3-20260610_015148/reconcile-report-v3/active-daou-vs-portal-v6.html`
- v3-v6 비교 산출물: `v3-v6-comparison.md`, `v3-v6-comparison.json`, `v3-v6-contract-differences.csv`. 계약 수와 활성 잔액 일치/불일치 건수는 동일하지만, 활성 7건의 표시값이 다르다. 활성 잔액 차이 절대값 합계는 v3 34,334,080원에서 v6 33,935,680원으로 398,400원 줄었다. 차이 계약은 `Sales12181`, `Sales13813-2`, `Sales14074-2`, `Sales14408-1`, `Sales16935`, `Sales18106`, `Sales18230`이다.
