# 거래처계정내역(ACC3030) 포탈 엔티티 페이지 + facade live 연동

작성 2026-06-26. 로컬호스트 개발(포탈 + facade).

## 요구사항 (사용자)
1. 포탈의 기존 '거래처원장'(per-company `CompanyLedger`, 타이틀 "거래원장", ACC3030 뱃지) 라벨을 **거래처계정내역**으로 변경.
2. 사이드바에 **다른 페이지처럼 top-level 엔티티 페이지**로 신설.
3. 운송상태(`ShippingStatusPage`)처럼 `마지막 갱신 … · 다음 자동 갱신 …` 표기 + **모두갱신** 버튼.
4. 데이터는 **ama-erp-facade**(`/Users/gq/works/projs/dofing-order-auto/ama-erp-facade/ama-erp-facade-01`)의 ACC3030 세목 API를 호출해 받아온다.
   - 계정과목: `1080000 외상매출금`, `1080001 외상매출금_패키지`, `1080002`, `1080003`, `2590000 선수금`, `2590002 선수금_패키지`.
5. 페이지 형태: **거래처별 요약 리스트** (운송상태식 요약카드 + 행=거래처, 계정과목별 차변/대변/잔액; 행 확장 시 거래·이월 상세).
6. facade의 **live ERP 스크레이퍼까지 구현** (현재 `acc3030_history`/`acc3030_period_view` 미존재).

## 아키텍처 사실 (조사 완료)
- **운송상태 패턴**: NestJS `shipping-status` 모듈 = controller(ts-rest) + service(in-memory 캐시 `cache`/`cacheUpdatedAt`, `REFRESH_INTERVAL_MS=15분`, `getStatuses()` stale 시 백그라운드 refresh) + scheduler(`@Cron('*/15 * * * *')`) + module. summary 스키마에 `lastRefreshedAt`/`nextRefreshAt`/`refreshIntervalMinutes`.
- **facade**: Bun 서버 `bun run back` → `:8787`(기본; ecosystem은 54311). Job 비동기:
  - `POST /api/jobs/acc3030-query` body `{startDate,endDate,accountCodes}` → 202 `{id,status,...}`.
  - `GET /api/jobs/:id` 폴링(queued/running/succeeded/failed + summarized result).
  - `GET /api/jobs/:id/preview` → `{preview:{sections:[{id:'acc3030Rows',rows:[...],totalCount}],period}}` (전체 rows, in-memory previewCache).
  - `requireApiToken:true` → `Authorization: Bearer <t>` 또는 `x-api-token`.
  - 기본 계정코드가 이미 사용자 지정 6개와 일치. capability 라벨 이미 "ACC3030 거래처계정내역".
  - acc3030 CLI는 `${AMA_STARTPOINT_ROOT ?? STARTPOINT_ROOT}/proc/lib`의 python `pwc`/`pwc_amaranth`를 `python3 -c`로 호출.
- **facade gap**: startpoint `proc/lib/pwc_amaranth.py`에 `acc3030_history`/`acc3030_period_view` **없음** → 현재 job 런타임 import 실패. 완전 구현은 **hong-ledger-and-packages-02** `proc/lib/pwc_amaranth.py`(L956~1691)에 존재(ACC3030 split out됨). deploy_prod.sh도 fallback helper 전제. dep `_amaranth_latest_auth`(L107)/`_amaranth_post`(L137)/`_filter_requests`(L76)/`ERP_URL`는 startpoint에 이미 존재.
- **ACC3030 raw row 필드**: `trCd`(거래처코드), `attrNm`, `divCd/divNm`, `acctCd`(계정과목), `acctNm`, `fillDt`(YYYYMMDD), `fillNb`(전표), `rmkDc`(적요; '이 월'=이월), `drAm`(차변), `crAm`(대변), `janAm`(잔액).
- **포탈 정규화 타입**: `company-ledger/types.ts` `Acc3030LedgerRow{date,accountSubjectCode,accountSubjectName,description,debit,credit,balance,fillNo,voucherNo,docuInfo,type,erpCode,erpName}`, `AccountSummary`. 신규 contract 스키마는 이 명명을 미러 → 기존 company-ledger 컴포넌트 재사용 용이.
- 거래처명: ACC3030 row에 없음 → 포탈 `company.erpId == trCd` 매칭으로 보강(매칭 안 되면 `trCd`/`attrNm`).

## 작업 분해 (진행)
### Phase 1 — Facade live 스크레이퍼 (startpoint proc/lib) ✅
- [x] hong-ledger `pwc_amaranth.py`의 ACC3030 region 포팅 → startpoint `proc/lib/pwc_amaranth.py`:
  `EARLIEST_GISU/EARLIEST_FY_YEAR`, `_gisu_for_year`, `_year_bounds`, `acc3030_query`, `acc3020_query`, `acc303x_bootstrap`, `acc3030_history`, `acc3030_period_view`. dep 추가 불필요(전부 기존재).
- [x] python 스모크 `import ok 13 2024`.
- [x] facade: `back-server.ts`에 `AMA_REQUIRE_API_TOKEN` env 토글(미설정 시 기존 true). `.env.local.example` 생성. `bun run build`(tsc+vite) clean. `/healthz` ok + `POST /api/jobs/acc3030-query` 202(로그인 preflight까지 진행 — live는 amaranth 로그인 필요).

### Phase 2 — api-contract ✅
- [x] `schemas/company-account-ledger.ts` (codes/labels 상수 포함).
- [x] `contracts/company-account-ledger.ts` (get + refresh).
- [x] `contract.ts` + `index.ts` 등록. `bun run build`(tsup) 성공.

### Phase 3 — 포탈 server ✅ (typecheck clean)
- [x] `company-account-ledger/ama-facade.client.ts`: facade HTTP 클라이언트(create job→poll→preview), env `AMA_FACADE_BASE_URL`(기본 `http://127.0.0.1:8787`)+`AMA_FACADE_API_TOKEN`.
- [x] 모듈: controller + service(in-memory 캐시, summary, refreshNow, trCd→company.erpId aggregate) + scheduler(`@Cron('*/15')`). app.module 등록. `tsc --noEmit` clean.

### Phase 4 — 포탈 front (typecheck 진행 중)
- [x] `CompanyAccountLedgerPage.tsx`: 운송상태식 헤더(마지막/다음 갱신 + 지금 모두갱신 + 목록 새로고침) + 요약카드 + 거래처 테이블(행 확장 → 계정과목별 요약 + 거래내역).
- [x] `layoutNavigation.ts` 도구 섹션 `{path:'/company-account-ledger', label:'거래처계정내역', icon:BookOpen}` + testId + getPageTitle.
- [x] `App.tsx` route + import. `api/client.ts` `companyAccountLedgerApi`.
- [x] 라벨 변경: `CompanyLedger.tsx`/`CompanyDetail.tsx` "거래원장"→"거래처계정내역".

### Phase 5 — 검증
- [x] api-contract build, 서버 typecheck 통과. facade build 통과.
- [ ] front typecheck (진행 중) → 통과 확인.
- [ ] 로컬 기동(facade :8787, 포탈 server+front) E2E: 페이지 로드 → 모두갱신 → 갱신 표기 갱신.

## 개정 (2026-06-26) — 보조원장 처리
사용자 지시: 거래처계정내역은 **보조원장**이므로 ① 아직 주문/거래처(Company)와 **연계하지 않음**, ② **DB 구조는 만들되 실데이터는 적재하지 않음**.
- **연계 제거**: contract entry에서 `companyId`/`companyName`/`matched`, summary에서 `matchedAccounts` 제거. ERP `trCd`/`erpName`만 보관. service `loadCompanyMap`(company.erpId 매칭) 삭제. front 매칭필터·매칭카드·`/companies/:id/ledger` 링크 제거. (기존 per-company `CompanyLedger`는 그대로 — 별개)
- **DB 구조만**: prisma 모델 `ErpCustomerAccountLedgerSnapshot` + `ErpCustomerAccountLedgerEntry`(Company/Order relation 없음) 추가 → `prisma generate` 완료. 마이그레이션 [`apps/server/prisma/migrations/034_company_account_ledger.sql`] 생성(미적용 — DB 기동 시 `db:push` 또는 해당 SQL 적용). `PrismaService`에 두 getter 추가.
- **실데이터 미적재 게이트**: service `COMPANY_ACCOUNT_LEDGER_INGEST_ENABLED`(기본 false). false면 facade 조회·DB 저장 안 함 → 빈 스냅샷(`ingestEnabled:false`, fetchStatus idle), scheduler·모두갱신 no-op. true로 켜면 facade 조회→aggregate→DB persist→read 동작. `loadLatestSnapshot`은 테이블 미적용에도 try/catch로 graceful.
- front: `ingestEnabled:false`일 때 "보조원장 — 구조만 준비됨" 안내 배너 + 모두갱신 버튼 비활성 + 빈 상태 문구.
- 재검증: api-contract rebuild, server `tsc` clean, front `tsc` clean.

## 개정2 (2026-06-26) — 상세페이지 + 필터 + Excel 형식
사용자 지시: 사이드바 "(개발중)" 표기 / 다른 엔티티처럼 필터 / 행 클릭 시 **상세페이지**(collapse 폐기) / 아마란스 ACC3030 실제화면+Excel(`gridMain_excel_2026-06-26_14-31.xlsx`) 확인 후 진행 / 상세표는 Excel 형식(공통 4열 거래처코드·명·회계단위코드·명 제외).
- **조사**: 아마란스 ACC3030 스크린샷 `output/acc3030-shots/acc3030_full.png` (거래처별 그룹 그리드 + 합계행). Excel 36열 = 공통4 + 32열. 검증: trCd 03180 raw 1행 비교 → **잔액은 raw `janAm`(0) 아니라 거래처별 누적(차-대) 계산값** (−3,000,000 → 45,480,000 Excel 일치). 전표 = `docuInfo` 18자리 → `YYYYMMDD-FILLNB-SEQ` 포맷.
- **contract**: list/detail 분리. entry(목록)=요약(rows 제외)+divCd/divNm. `companyAccountLedgerDetailRowSchema`(32필드) + `companyAccountLedgerDetailSchema`. route `getCompanyAccountLedgerDetail` GET `/company-account-ledger/:trCd`. `COMPANY_ACCOUNT_LEDGER_DETAIL_COLUMNS`(Excel 순서, 공통4열 제외) 중앙 정의.
- **server**: aggregate가 거래처별 raw rows를 전월이월 먼저+승인일·dispSq·lnSq 오름차순 정렬 후 누적 잔액 계산. 캐시는 FullEntry(rows 포함), 목록은 rows strip, 상세는 trCd로 1건. controller에 detail 핸들러(없으면 404).
- **front**: 목록 = 필터바(검색·잔액방향·정렬 + 계정과목 칩) + 거래처 테이블, 행 클릭 → `navigate('/company-account-ledger/:trCd')` (collapse 제거). 신규 `CompanyAccountLedgerDetailPage` = 헤더(거래처/회계단위/합계 StatBox) + 계정과목별 요약 + 와이드 grid(32열, 숫자 우정렬·0은 공백, 이월행 하이라이트, sticky/스크롤). 사이드바 "거래처계정내역(개발중)", App route, getPageTitle 추가.
- 재검증: contract rebuild, server `tsc` clean, front `tsc` clean, 신규 detail route 등록 확인(HTTP 401=route exists), 누적잔액 Excel 일치 확인.

## 결정/주의
- facade 포팅은 split 되돌리기처럼 보이나, facade spec(2026-06-17/06-22)이 split 이후 작성되어 startpoint `pwc_amaranth.py`에 ACC3030 symbol을 재요구 → spec 정합.
- playwright `-s=amaranth` 프로필은 **cwd별 namespace** → facade live 데이터는 facade cwd에서 amaranth 1회 로그인 필요(운영 이슈, 코드와 분리).
- 신규 페이지는 **live(facade)**; 기존 `/companies/:id/ledger`(erpInfo offline)는 유지하되 라벨만 변경.
