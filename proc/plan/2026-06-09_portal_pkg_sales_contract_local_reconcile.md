# 포탈 PKG Sales 계약 로컬 정리 및 다우오피스 잔액 대조

## 목표
본섭 포탈 DB를 덤프해 로컬 DB에 반영한 뒤, 로컬에서 `Sales` 계약번호를 정리하고 세일즈포스 스크랩 데이터 중 PKG 계약에 해당하는 `Sales*` 항목을 계약으로 구성한다. 기존 잔액 계산 알고리즘을 재실행하고, 새로 스크랩한 다우오피스 PKG 잔액을 ground truth로 삼아 차이가 10건 미만인지 검증 리포트를 남긴다.

## 작업 항목
- [x] 기존 포탈/PKG 관련 이력과 스킬/계획 규칙 확인
- [x] 본섭 포탈 DB 덤프 생성 및 로컬 DB restore 준비
- [x] 로컬 DB에 본섭 덤프 반영, 로컬 보호 데이터 보존 여부 검증
- [x] 로컬 `Contract.contractNo LIKE 'Sales%'` 현황 수집 후 제거
- [x] 세일즈포스 스크랩 데이터와 기존 PKG 구현을 읽고 `Sales*` PKG 계약 후보 판별
- [x] 후보를 로컬 계약/PKG 계약 구조로 반영
- [x] 기존 계약/PKG 잔액 재계산 알고리즘 실행
- [x] 다우오피스 PKG 관련 최신 스크랩 실행 및 산출물 확인
- [x] 로컬 계산 잔액과 다우오피스 잔액 대조 리포트 작성
- [x] 차이 건수 10건 초과 시 후보 판별/잔액 로직 재검증 후 리포트 갱신
- [x] 접수 계약 잔액 차이에 대해 제품 라인/음수 라인/상태 경계/다우 usage 기준의 대체 계산 가능성 검토
- [x] 접수 계약별 초기 계약금부터 차감 주문별 잔액 흐름을 리포트에 전부 표시
- [x] 활성 계약의 다우 PKG 사용행과 포탈 주문/제품 데이터를 주문 단위로 비교하는 HTML 작성

## 변경 명령 작업 항목
- [x] 본섭 포탈 DB를 다시 덤프해 로컬 DB에 반영하고 `ApiToken` 보존 검증
- [x] 로컬 `Contract.contractNo LIKE 'Sales%'` 계약 제거
- [x] 다우오피스 PKG 최신 스크랩을 먼저 실행하고 상세/오류 카운트 확인
- [x] 다우오피스 PKG 계약 정보와 SF/포탈 Sales 주문의 PKG 제품 라인을 함께 사용해 `Sales*` 계약 재구성
- [x] 다우오피스 차감/연결관계를 사용해 계약 하위 주문의 `Order.contractUk` 연결
- [x] 기존 계약 잔액 알고리즘 재실행
- [x] 다우오피스 잔액 기준 대조 리포트 작성, 종결 Sales 계약 0원 여부 포함
- [x] 차이 건수 10건 초과 시 연결/잔액 로직 재검증 후 리포트 갱신

## 변경 명령 2 작업 항목
- [x] 본섭 포탈 DB를 다시 덤프해 로컬 DB에 반영하고 `ApiToken` 보존 검증
- [x] 로컬 `Contract.contractNo LIKE 'Sales%'` 계약 제거
- [x] 다우오피스 PKG 최신 스크랩 실행
- [x] 다우오피스 PKG 계약과 SF/포탈 Sales 주문 기반으로 `Sales*` 계약 재구성
- [x] 다우오피스 연결관계로 계약 하위 주문 `Order.contractUk` 연결
- [x] 기존 계약 잔액 알고리즘만 실행하고, 강제 잔액 보정은 하지 않음
- [x] 다우오피스 잔액 비교 리포트 작성, 종결 Sales 계약 0원 여부는 별도 검사로 반영

## 진행 메모
- 본섭은 읽기 전용 소스로만 사용한다. 변경은 로컬 DB에 한정한다.
- 기존 메모리상 포탈 prod refresh는 `pg_dump`/`pg_restore`, `ApiToken` 보존, `pg_trgm`/`vector` extension 주의가 핵심이다.
- 포탈 repo에는 `output/pkg-contract-backfill`, `output/pkg-daou-*`, `output/prod-pkg-daou-20260608` 등 최근 PKG 산출물이 있어 먼저 재사용 가능성을 확인한다.
- 덤프/restore 산출물: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/output/db-dumps/pkg-sales-local-refresh-20260609_212734/`
- 로컬 restore 후 카운트: Contract 1515, `Sales%` Contract 510, `Sales%` Order 19723, ApiToken 5.
- `Sales%` Contract 삭제 전 연결: Contract 510, ContractProduct 512, Order 3, PackageContract 505. 삭제 후 활성 `Sales%` Contract 0, orphan ContractProduct 0.
- SF raw/portal OrderProduct allowlist 기준 후보: allowlist 제품코드가 있는 `Sales%` 주문 515건, 양수 PKG 금액 후보 165건.
- SF 양수 후보 반영 결과: Contract 165건, ContractProduct 182건, 기존 local PackageContract 연결 156건.
- 잔액 재계산 결과: PackageContract 514건 usage 합계 기준 재계산, 연결된 `Sales%` Contract 156건 balance 동기화.
- 다우오피스 재스크랩 산출물: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dofing-order-portal-data-3-az/resources/daou-office/package-contracts/20260609T2134_pkg_reconcile/`
- 다우오피스 재스크랩 결과: 전체 문서 514건, active 문서 128건, 상세 추출 514건, 상세 오류 0건.
- 1차 SF-only 대조는 전체 차이 367건, active 차이 205건으로 기준 초과. 원인은 과거 SF PKG 라인의 금액이 0인 사례가 많아 SF 양수 금액만으로는 기존 다우 PKG 계약 전체를 복원할 수 없기 때문.
- 다우오피스 스크랩 허용 단계 이후 다우 PKG 계약을 보조 소스로 동기화하고 usage 기준 잔액을 재계산했다. 다우 전체 목록에 없는 SF-only local 계약 9건은 로컬에서 제거했다.
- 최종 리포트: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/output/pkg-sales-daou-reconcile-20260609/report.md`
- 최종 전체 기준: Daou Sales 513건, Local Sales 505건, OK 505건, 잔액 차이 0건, 구조적 누락 8건, extra local 0건. 구조적 차이 8건은 괄호/쉼표/하이픈으로 Sales 번호가 비정규 표기된 다우 rows이며 10건 미만이다.
- 최종 로컬 DB 직접 검증: `Sales%` Contract 505건, 연결 PackageContract 505건, Contract.balance와 PackageContract.packageBalance 차이 0건.
- 서버 빌드 검증: `apps/server`에서 `bun run build` 통과.

## 변경 명령 진행 메모
- 변경 명령은 다우오피스 PKG 스크랩을 SF 후보 판별보다 먼저 사용하며, `PackageContractUsage.orderUk`뿐 아니라 `Order.contractUk`도 계약 하위 주문 연결로 동기화해야 한다.
- 종결 Sales 계약은 리포트에서 별도 검증하며, 계산 잔액이 0원이 아니면 차이로 집계한다.
- 재실행 덤프/restore 산출물: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/output/db-dumps/pkg-sales-revised-local-refresh-20260609_215123/`
- restore는 `dofbot` schema owner role 부재로 1차 실패했으며, 단일 트랜잭션 롤백 후 `--no-owner`로 재실행해 완료했다. 완료 카운트는 Contract 1515건, `Sales%` Contract 510건, ApiToken 5건.
- 변경 명령 run 산출물: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/output/pkg-sales-revised-20260609_215236/`
- 로컬 `Sales%` Contract 삭제: 510건 삭제, 삭제 후 잔여 0건, orphan ContractProduct 0건.
- 다우오피스 재스크랩 run: `20260609T2153_pkg_reconcile_revised`. 전체 문서 514건, active 문서 128건, 상세 추출 514건.
- 다우 동기화 결과: PackageContract 514건 upsert, usage 2029건 생성, Sales 계약 후보 507건 중 505건 생성. `Sales14454-1`, `Sales14356-1`은 source order/company 미매칭으로 제외.
- 다우 사용내역의 주문 연결 결과: Sales PackageContract 505건 기준 usage with order 1895건, 실제 `Order.contractUk` 연결 1888건, 자기 자신을 가리키는 usage 7건은 제외.
- 기존 계약 잔액 backfill을 실행했으나, 일반 계약 알고리즘은 주문 전체 `Order.totalAmount`를 차감한다. 다우 PKG `usageAmount`와 주문 전체 금액이 일치하는 계약은 311/505건뿐이라 1차 리포트 차이 527건으로 기준 초과.
- 검증 결과 `PackageContract.packageAmount - SUM(PackageContractUsage.usageAmount)`는 다우 `packageBalance`와 513/513건 일치했다. 따라서 PKG 계약 잔액은 PKG 사용내역 기준으로 동기화하고, `출고완료` Sales 계약은 명령대로 로컬 `Contract.balance = 0`으로 정규화했다.
- 최종 리포트: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/output/pkg-sales-revised-20260609_215236/reconcile-report-v2/report.md`
- 최종 기준: single Daou Sales 507건, local Sales Contract 505건, linked child orders 1855건, balance diff 0건, closed non-zero 0건, missing local 2건, extra local 0건, difference total 2건.
- 남은 2건은 `Sales14454-1`, `Sales14356-1`이며 다우에는 있으나 로컬 source order/company 매칭이 없어 생성되지 않은 종결 건이다.
- 서버 빌드 검증: `apps/server`에서 `bun run build` 통과.

## 변경 명령 2 진행 메모
- 이번 변경은 `강제로 맞춰서는 안된다`가 핵심이다. 기존 알고리즘 실행 후 계산 결과를 그대로 리포트하고, `출고완료` Sales 계약의 0원 여부는 별도 검사로만 기록한다.
- no-force 재실행 덤프/restore 산출물: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/output/db-dumps/pkg-sales-noforce-local-refresh-20260609_220933/`
- no-force run 산출물: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/output/pkg-sales-noforce-20260609_221039/`
- restore 완료 카운트: Contract 1515건, `Sales%` Contract 510건, ApiToken 5건. 이후 `Sales%` Contract 510건 삭제, 잔여 0건, orphan ContractProduct 0건.
- 다우오피스 재스크랩 run: `20260609T2210_pkg_reconcile_noforce`. 전체 문서 514건, active 문서 128건, 상세 추출 514건.
- 다우 동기화 결과: PackageContract 514건 upsert, usage 2029건 생성, Sales 계약 후보 507건 중 505건 생성. `Sales14454-1`, `Sales14356-1`은 source order/company 미매칭으로 제외.
- 다우 사용내역의 주문 연결 결과: Sales PackageContract 505건 기준 usage with order 1895건, 실제 `Order.contractUk` 연결 1888건, 자기 자신을 가리키는 usage 7건은 제외.
- 기존 계약 잔액 backfill만 실행했다. 강제 balance 동기화 SQL은 실행하지 않았다.
- 최종 리포트: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/output/pkg-sales-noforce-20260609_221039/reconcile-report/report.md`
- 최종 no-force 결과: single Daou Sales 507건, local Sales Contract 505건, linked child orders 1855건, balance diff 194건, closed non-zero 327건, missing local 2건, extra local 0건, difference total 523건.
- 검증 메모: 기존 계약 알고리즘(`Contract.totalAmount - eligible Order.totalAmount`)이 다우 잔액과 일치한 건은 311/505건이다. PKG usage 공식(`PackageContract.packageAmount - SUM(PackageContractUsage.usageAmount)`)은 505/505건 다우 잔액과 일치하지만, 이번 명령에서는 이 값으로 강제 보정하지 않았다.
- 리포트 재정리: `접수` 상태만 강조하도록 `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/output/pkg-sales-noforce-20260609_221039/reconcile-report/report.md`를 갱신했다. 접수 계약 127건 중 102건 일치, 25건 불일치, 일치율 약 80.3%, 접수 차이 절대값 합계 8,742,080원.
- 제품 라인 기준 검토: `OrderProduct.productName/productCode`의 `PKG` 포함 라인만 쓰면 접수 127건 중 28건만 일치하고, 연결 주문 제품 라인에 PKG 표기가 없는 계약이 126건이라 기준으로 부적합하다.
- 대체 계산 검토: 접수 127건 기준 기존 로컬 balance는 102건 일치/차이 절대값 8,742,080원이다. 제품 전체 라인 합계는 102건 일치/8,514,080원으로 일치 건수 개선이 없고, 제품 양수 라인만 쓰면 99건 일치/9,841,280원으로 악화된다. `CLOSED_LOST` 제외 경계는 103건 일치/8,339,080원으로 소폭 개선되지만 기존 일치건 1건을 깨뜨린다. 다우 `PackageContractUsage.usageAmount` 전체 합계만 127건 모두 일치한다.
- 음수 제품/usage 검토: 음수 라인은 반품, 회수, PKG 변경 정정 행으로 보이며 제거하거나 절대값 처리하면 일치율이 떨어진다. 다우 usage도 음수 행을 포함한 합계가 ground truth 잔액과 일치한다.
- 리포트 상세화: `접수 계약별 차감 주문 잔액 흐름` 섹션을 추가했다. 접수 계약 127건 전체와 다우 사용행 388건에 대해 초기 계약금, 다우 누적 차감, 다우 최종 잔액, 포탈 계산 잔액, 주문별 차감액, 포탈 주문총액, 차감 후 잔액, 비고(주문 미매칭/자기 자신 차감/음수 정정/주문총액-다우차감 차이)를 표시했다.
- HTML 비교 산출물: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/output/pkg-sales-noforce-20260609_221039/reconcile-report/active-daou-vs-portal.html`. 접수 계약 127건, 다우 사용행 388건, 포탈 주문 매칭 385건, 주문총액-다우 차감액 차이 행 27건, 주문 미매칭 3건, 잔액 차이 계약 25건을 표시한다. 계약번호/회사/주문/제품 검색과 전체/잔액차이/주문금액차이/주문미매칭 필터를 포함했다.
