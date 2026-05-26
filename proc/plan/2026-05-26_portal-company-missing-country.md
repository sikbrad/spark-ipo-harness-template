# Portal company missing country research

## 목표

포탈 본섭에서 고객사 국가가 정해지지 않았거나 화면에서 국가 미지정처럼 보일 수 있는 고객사 목록을 확인하고, 조사 결과를 Excel로 산출한다.

## 작업 항목

- [x] `Company.country` 저장/표시 규칙 확인
- [x] 본섭 DB에서 국가 누락/비정상 후보 추출
- [x] `https://portal.doflab.com/companies/1100` 사례 포함 여부 확인
- [x] 조사 메모와 원천 JSON 저장
- [x] Excel 리포트 생성 및 검증

## 실행 기록

### 2026-05-26 시작

- 사용자 요청: 포탈 고객사 상세에서 국가가 정해지지 않은 고객사가 있는지 조사하고 목록을 Excel로 제공.
- 범위: 읽기 전용 조사 및 산출물 생성. DB 수정은 하지 않음.
- 기준 repo: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az`

### 2026-05-26 결과

- `Company.country`는 고객사 국가의 정규 저장 필드이며 Prisma schema에서는 nullable이다.
- 본섭 `dof_portal_prod`의 활성 고객사(`deletedAt IS NULL`)는 3,289건이다.
- 국가 미지정/비정상 고객사는 419건이며, 모두 `country IS NULL`이다.
- `trim(country) = ''`인 빈 문자열 케이스와 허용 목록 외 국가값 케이스는 없었다.
- 1100번 고객사 `Anand Mediproducts Pvt Ltd`도 `country IS NULL`로 확인했다.
- 조사 보고서: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/proc/30_research/report/2026-05-26_company-missing-country-audit.md`
- Excel 산출물: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/output/portal-company-country-audit-20260526/portal-company-missing-country-20260526.xlsx`
- 검증: Excel 렌더 4개 시트 성공, 수식 오류 스캔 0건, `unzip -t` 정상.
