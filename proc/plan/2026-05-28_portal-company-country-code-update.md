# 포탈 고객사 국가코드 보정

## 목표
SharePoint 엑셀의 고객사 국가 추정값과 포탈 소스의 국가코드 규칙을 근거로, 포탈 고객사에 적절한 국가코드와 거래통화를 반영하고 변경 이력을 남긴다.

## 작업 항목
- [x] SharePoint 엑셀 원본을 다운로드하고 컬럼/대상 건수를 확인한다.
- [x] 포탈 소스에서 국가코드 저장 규칙, 거래통화 허용값, history 기록 방식을 확인한다.
- [x] 현재 포탈 DB의 대상 고객사 상태와 기존 해외 고객 국가코드/통화 패턴을 수집한다.
- [x] 데이터 변경 전 prod DB 전체 덤프를 생성하고 검증한다.
- [x] 엑셀 추정값과 현재 DB를 대조해 건별 보정안을 작성한다.
- [x] 데이터 변경 전 검증 쿼리와 변경 스크립트를 준비한다.
- [x] 포탈 DB에 국가코드/거래통화/history를 반영한다.
- [x] 변경 후 대상 건수, 코드 분포, history 기록을 검증한다.

## 진행 기록
- 2026-05-28: 작업 시작. 기존 메모리에서 2026-05-26 국가미지정 고객사 조사/SharePoint 전달 작업의 후속임을 확인했다. 대상 소스는 `dof-order-web-3-az`, 데이터 로더/Prisma 표면은 `dofing-order-portal-data-3-az`로 보고 수집을 시작한다.
- 2026-05-28: SharePoint 공유 엑셀 `국가미지정_목록_담당자확인_20260526.xlsx`를 `output/portal-company-country-update-20260528/`에 다운로드했다. 메인 시트는 419건, 국가값은 모두 채워져 있고 담당자확인 값이 있는 행은 37건이다.
- 2026-05-28: 포탈 소스 확인 결과 고객사 `country`는 ISO 3166-1 alpha-2 코드, API 통화 허용값은 `KRW|USD|EUR|JPY`, 고객사 수정 이력은 `AuditLog`의 `entityType=COMPANY`, `field=country|currency` 형태로 남긴다. 직접 DB 보정 시 회사 수정 서비스와 맞추기 위해 미완료 주문의 `Order.country` 스냅샷도 함께 보정해야 한다.
- 2026-05-28: prod DB 접속 대상은 `.env`의 주석 처리된 `dof_portal_prod` 연결 문자열로 확인했다. 읽기 검증 결과 전체 고객사 3,291건, 활성 고객사 중 `country IS NULL`은 현재 418건이다.
- 2026-05-28: 사용자 추가 지시에 따라 데이터 변경 전 prod DB 전체 덤프를 먼저 생성한다. 아직 DB 변경은 수행하지 않았다.
- 2026-05-28: prod DB 전체 덤프 생성 및 `pg_restore --list` 검증 완료.
  - 덤프: `output/portal-company-country-update-20260528/backup/dof_portal_prod_before_country_update_20260528_171509.dump`
  - 크기: 64,496,255 bytes
  - SHA256: `4f7167990937f25deaa1b71a4e0f09fc49f5265e1ca707da11b8b197c3a2a953`
  - 검증: `pg_restore --list` 776 lines 생성 완료
- 2026-05-28: 기존 포탈 데이터의 국가코드는 이미 alpha-2 형식(`KR`, `DE`, `US`, `JP` 등)으로 들어가 있음을 확인했다. 기존 통화 패턴은 `KR=KRW`, `DE/ES/IT/FR/JP=EUR/JPY`, `US/AE/IN=USD`처럼 `KRW|USD|EUR|JPY` 안에서 운용되고 있었다.
- 2026-05-28: 엑셀 419건과 현재 prod DB를 대조한 dry-run 산출물을 생성했다.
  - 산출물: `output/portal-company-country-update-20260528/company-country-update-dry-run.json`
  - 적용 대상: 418건
  - 제외: 1건 (`id=1100 Anand Mediproducts Pvt Ltd`)은 이미 `country=IN`으로 보정되어 있어 제외
  - 예상 국가 분포 상위: `DE 48`, `US 44`, `CN 29`, `JP 21`, `AE 15`, `KR 14`
  - 예상 통화 분포: `USD 240`, `EUR 152`, `KRW 14`, `JPY 12`
  - 통화 규칙: 기존 동일 국가 대표 통화 200건, 기존 주문/계약 외화 이력 191건, 기존 외화 유지 9건, 한국 KRW 14건, EUR 권역 fallback 3건, 해외 USD 기본값 1건
  - 고객사 수정 서비스와 맞춰 함께 보정해야 할 미완료 주문 `country` 스냅샷은 34건으로 계산됨
- 2026-05-28: 적용 스크립트 `scripts/portal_company_country_update_20260528.mjs`를 작성하고 기본 dry-run을 통과했다. 예상 적용량은 고객사 418건, 통화 변경 395건, `AuditLog` 813건이다.
- 2026-05-28: prod DB 적용 완료.
  - 고객사 국가/통화 보정: 418건
  - 고객사 통화 변경: 395건
  - `AuditLog`: 813건 (`country` 418건, `currency` 395건, 모두 `userUk=system`)
  - 미완료 주문 `Order.country` 스냅샷 보정: 34건
  - 적용 결과: `output/portal-company-country-update-20260528/company-country-update-apply-result.json`
- 2026-05-28: 적용 후 검증 완료.
  - 대상 418건의 `Company.country`/`Company.currency` 값 불일치: 0건
  - 활성 고객사 `country IS NULL`: 0건
  - 대상 418건 중 허용 외 통화: 0건
  - 미완료 주문 스냅샷 불일치: 0건
  - 검증 결과: `output/portal-company-country-update-20260528/company-country-update-verification.json`
- 2026-05-28: 전체 활성 고객사 통화 allowlist 검증 중 기존 비대상 1건(`id=6213 Shenzhen Jiahong Dental`, `CN/CNY`)을 발견했다. 사용자 규칙상 한국이 아닌 고객사의 허용 외 통화이므로 `USD`로 추가 보정하고 `AuditLog` 1건을 남겼다.
  - 추가 보정 결과: `output/portal-company-country-update-20260528/company-currency-allowlist-fix-result.json`
  - 최종 검증: 활성 고객사 `country IS NULL` 0건, 허용 외 통화 0건
  - 최종 검증 결과: `output/portal-company-country-update-20260528/company-country-update-final-verification.json`
- 2026-05-28: Teams 보고용 상세 엑셀을 생성하고 압축 무결성 검증을 완료했다.
  - 엑셀: `output/portal-company-country-update-20260528/포탈_고객사_국가코드_통화_보정상세_20260528.xlsx`
  - 시트: `요약`, `고객사별 상세`, `분포`, `백업 및 검증`
- 2026-05-28: Teams `DOF Inc. / init-crm-renew` 원글(`1779795509585`)에 비개발자용 요약 댓글과 상세 엑셀 첨부 댓글을 게시했다.
  - 요약 댓글: `1779960058330`
  - 엑셀 첨부 댓글: `1779960060748`
  - 게시 결과: `output/portal-company-country-update-20260528/teams-post-result.json`
  - 게시 검증: `output/portal-company-country-update-20260528/teams-post-verification.json`
