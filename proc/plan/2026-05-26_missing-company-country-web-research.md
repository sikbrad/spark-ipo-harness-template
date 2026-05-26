# Missing company country web research

## 목표

포탈 본섭에서 국가가 비어 있는 고객사 419건에 대해 공개 웹 근거, Facebook/LinkedIn/Google Maps/검색 근거, 상호/사업자등록명에 포함된 국가·지역·법인형태 단서, 그리고 낮은 신뢰도 최종 추정까지 구분해 모든 대상의 `국가값`과 `신뢰도`를 채운 새 Excel을 만든다. 첫 시트는 반드시 `국가미지정_목록`으로 둔다.

## 작업 항목

- [x] 기존 419건 원천 목록 확인
- [x] 웹 검색/근거 수집 스크립트 작성
- [x] 멀티에이전트로 SF 원천/웹 고주문/웹 패턴 후보 수집
- [x] 확실한 건만 국가 코드 채움
- [x] 새 Excel 생성 (`국가미지정_목록` 첫 시트)
- [x] Workbook 검증
- [x] 추가 브라우저 검색 및 상호/지역명 추정 후보 반영
- [x] `확실`/`추정` 판정상태 분리
- [x] LinkedIn/Facebook/멀티에이전트 추가 리서치 반영
- [x] 남은 전건 최종 저신뢰 추정 반영

## 원칙

- DB 수정 없음.
- `Company.country`에 들어갈 값은 포탈 스키마 기준 alpha-2 국가 코드(`JP`, `IN` 등)로 채운다.
- 회사명과 공개 근거가 직접 연결되는 경우는 `확실`로 둔다.
- 상호/사업자등록명 안의 국가명·지역명·법인형태 단서는 `추정`으로 구분한다.
- 동명이인/상호가 일반명사라 국가를 붙이면 위험한 건은 `최종 저신뢰 추정` 또는 낮은 `신뢰도`로 구분한다.

## 결과

- 총 대상: 419건
- 국가값 채움: 419건
- 확실: 293건
- 추정: 126건
- 미확인/검토필요: 0건
- 주문 이력이 있는 미확인: 0건
- 첫 시트: `국가미지정_목록`
- 산출물: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/output/portal-company-country-web-research-20260526/portal-company-missing-country-web-researched-20260526.xlsx`

## 근거 수집

- SF 원천 고신뢰 매칭: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/output/portal-company-country-web-research-20260526/subagent_sf_country_candidates.json`
- 웹 고주문 후보: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/output/portal-company-country-web-research-20260526/subagent_web_high_order_candidates.json`
- 웹 패턴 후보: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/output/portal-company-country-web-research-20260526/subagent_web_pattern_candidates.json`
- 브라우저 확인: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/output/portal-company-country-web-research-20260526/browser_page_evidence.json`
- 브라우저 추가 검색: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/output/portal-company-country-web-research-20260526/browser_more_candidates.json`
- 상호/지역명 추정: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/output/portal-company-country-web-research-20260526/name_region_inference_candidates.json`
- 포탈 고객정보 추정: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/output/portal-company-country-web-research-20260526/customer_contact_candidates.json`
- Google Maps raw: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/output/portal-company-country-web-research-20260526/google_maps_candidates.json`
- Google Maps 수동 검수 반영: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/output/portal-company-country-web-research-20260526/google_maps_candidates_reviewed.json`
- SF CRM raw 추가 검토: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/output/portal-company-country-web-research-20260526/sf_crm_hint_review.json`
- SF CRM raw 추가 반영: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/output/portal-company-country-web-research-20260526/sf_crm_hint_candidates_reviewed.json`
- SF Account top-match 리포트: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/output/portal-company-country-web-research-20260526/sf_accounts_top_matches_for_remaining.json`
- 브라우저 소셜 확인: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/output/portal-company-country-web-research-20260526/playwright_social_candidates.json`
- 멀티에이전트 웹 확인 1: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/output/portal-company-country-web-research-20260526/multi_agent_research_candidates.json`
- 멀티에이전트 웹 확인 2: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/output/portal-company-country-web-research-20260526/multi_agent_research_candidates_2.json`
- 최종 전건 저신뢰 추정: `/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/output/portal-company-country-web-research-20260526/final_all_country_estimates.json`

## 검증

- Workbook 시트 순서 확인: `국가미지정_목록`, `요약`, `근거별_집계`, `국가별_집계`, `근거상세`
- `국가미지정_목록`: 420 rows x 23 cols, 국가값 채움 419건, 빈 `국가값` 0건, 빈 `신뢰도` 0건
- 판정상태: `확실` 293건, `추정` 126건
- 근거구분: SF 원천 155건, 멀티에이전트 웹 확인 94건, 상호/지역명 추정 58건, 최종 저신뢰 추정 22건, Google Maps 확인 21건, 고객정보 추정 16건, 웹 리서치 11건, 브라우저 추가 검색 11건, 웹 패턴 리서치 25건, SF CRM 추가 확인 5건, 브라우저 공식/검색 확인 1건
- 주문 이력이 있는 미확인: 0건
- 수식 오류 문자열 스캔: 0건
- `unzip -t`: 정상
