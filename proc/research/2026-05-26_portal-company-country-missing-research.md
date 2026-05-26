# Portal company missing country research

## 배경

포탈 본섭 고객사 중 `Company.country`가 비어 있는 활성 고객사를 조사했다. 대표 사례는 `/companies/1100`처럼 고객사 화면에서 국가가 정해지지 않은 레코드였고, DB 반영 전 담당자 검수용 Excel을 만드는 것이 목표였다.

## 입력과 대상

- 대상: 포탈 본섭에서 국가값이 비어 있던 고객사 419건
- 원천 감사 파일: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/output/portal-company-country-audit-20260526/prod-company-country-issues.json`
- 최종 Excel: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/output/portal-company-country-web-research-20260526/portal-company-missing-country-web-researched-20260526.xlsx`

## 조사 원칙

- DB 수정은 하지 않았다.
- 포탈에 넣을 값은 alpha-2 국가 코드(`KR`, `US`, `JP` 등) 기준으로 정리했다.
- 공개 웹/CRM 원천/SF 원천/Google Maps/LinkedIn/Facebook 등 직접 근거가 있으면 높은 신뢰도로 표시했다.
- 상호, 사업자등록명, 전화번호, 이메일, 국가·지역명, 법인형태 단서만으로 판단한 건은 `추정`으로 표시했다.
- 끝까지 직접 근거가 부족한 건도 담당자 확인을 위해 `최종 저신뢰 추정`으로 구분해 모두 국가값과 신뢰도를 채웠다.

## 수행 작업

1. 포탈 본섭 DB에서 국가 미지정 고객사 419건을 추출했다.
2. Salesforce 원천 후보(`Country__c`, 계정명, 주소/전화 등)를 매칭했다.
3. SF CRM raw 자료(`/resources/sf-crm`)에서 계정명, 연락처, 주소, 전화번호 단서를 추가 확인했다.
4. 공개 웹 검색 결과, 업체 공식 사이트, 제품/전시/협회 페이지를 확인했다.
5. Google Maps 결과를 브라우저로 확인하고, 동명이 업체가 섞이지 않도록 수동 검수한 후보만 반영했다.
6. LinkedIn/Facebook headful 로그인 세션에서 일부 강한 후보를 직접 확인했다.
7. 멀티에이전트로 남은 후보를 나누어 추가 웹 리서치를 수행했다.
8. 직접 근거가 없는 잔여 건은 상호/지역/언어/법인형태/업종 단서로 낮은 신뢰도 추정을 부여했다.
9. 최종 Excel 첫 시트 `국가미지정_목록`에 `담당자확인` 입력칸을 추가하고, 국가명·신뢰도·판정상태·근거 컬럼을 앞쪽에 배치했다.

## 주요 근거 파일

- SF 원천 후보: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/output/portal-company-country-web-research-20260526/subagent_sf_country_candidates.json`
- 웹 후보: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/output/portal-company-country-web-research-20260526/web-country-research-results.json`
- Google Maps 검수 반영: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/output/portal-company-country-web-research-20260526/google_maps_candidates_reviewed.json`
- SF CRM 추가 반영: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/output/portal-company-country-web-research-20260526/sf_crm_hint_candidates_reviewed.json`
- 브라우저 소셜 확인: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/output/portal-company-country-web-research-20260526/playwright_social_candidates.json`
- 멀티에이전트 웹 확인 1: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/output/portal-company-country-web-research-20260526/multi_agent_research_candidates.json`
- 멀티에이전트 웹 확인 2: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/output/portal-company-country-web-research-20260526/multi_agent_research_candidates_2.json`
- 최종 저신뢰 추정: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/output/portal-company-country-web-research-20260526/final_all_country_estimates.json`

## 최종 결과

- 총 대상: 419건
- 국가값 채움: 419건
- 빈 국가값: 0건
- 빈 신뢰도: 0건
- 판정상태: `확실` 293건, `추정` 126건
- 최종 저신뢰 추정: 22건
- Excel 첫 시트: `국가미지정_목록`
- 담당자 입력 컬럼: `담당자확인`

## Excel 구성 변경

- `담당자확인` 컬럼을 `사업자등록명` 왼쪽에 추가했다.
- 담당자 검수에 필요한 `국가값`, `국가명`, `신뢰도`, `판정상태`, `근거요약`, `근거URL`, `근거구분`을 앞쪽으로 이동했다.
- `담당자확인`, 국가 관련 컬럼, 근거 관련 컬럼은 색상으로 강조했다.
- `신뢰도`는 구간별로 색을 달리했다.
- `판정상태`는 `확실`과 `추정`을 색으로 구분했다.

## 검증

- Workbook 시트 순서: `국가미지정_목록`, `요약`, `근거별_집계`, `국가별_집계`, `근거상세`
- `국가미지정_목록`: 419 data rows, 23 columns
- `담당자확인` 위치: `사업자등록명` 왼쪽
- 빈 `국가값`: 0건
- 빈 `신뢰도`: 0건
- `unzip -t`: 정상

## 남은 주의사항

- `최종 저신뢰 추정`과 낮은 신뢰도 행은 담당자가 우선 검수해야 한다.
- Excel의 `담당자확인` 컬럼은 DB 반영 전 담당자가 확인/수정 의견을 적기 위한 입력칸이다.
- DB 반영은 별도 승인 후 수행해야 한다.
