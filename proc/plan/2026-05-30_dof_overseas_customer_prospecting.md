# DOF 해외 잠재 고객사 발굴

## 목표
DOF의 해외 잠재 고객사를 많이 발굴해 업체별 고객카드를 만들고, 왜 고객사가 될 수 있다고 판단했는지 근거와 출처를 남긴다.

## 작업 항목
- [x] 조사 범위와 출력 폴더를 만든다.
- [x] Playwright 브라우저 검색으로 해외 후보군을 수집한다.
- [x] 후보사의 제품/서비스/구매 가능성을 공식 사이트와 공개 자료로 확인한다.
- [x] 업체별 Markdown 고객카드를 작성한다.
- [x] 전체 인덱스와 우선순위/세그먼트 통계를 작성한다.
- [x] 링크와 파일 수를 검증한다.

## 결과
- 출력 폴더: `output/dof-overseas-customer-prospects/2026-05-30/`
- 고객카드: 57개
- 공식 페이지 보조 확인 성공: 51개
- 지역 분포: North America 25개, Europe 23개, APAC 8개, Global 1개
- 검증: README의 카드 링크 57개가 모두 실제 파일로 연결되고, 모든 카드에 구매/판매 항목, DOF 관점의 구매 가능성, 공개 근거, 다음 액션 섹션이 있다.

## 5000개 확장 조건 변경

사용자 추가 요구: 연락처, 이메일, 주소, 선정이유가 모두 찾아져야 한다.

### 새 valid 기준
- `name`: 업체명/병원명/기공소명
- `email`: 공개 이메일
- `phone`: 전화번호 또는 직접 연락 가능한 번호
- `address`: 공개 주소
- `selection_reason`: DOF 고객 후보로 선정한 이유
- `source_url`: 연락정보와 업종 판단 근거 URL

### 실행 계획
- [x] 기존 57개 카드는 시장 적합성 시드로 격하하고, 5000개 목표용 strict schema를 별도 생성한다.
- [x] `output/dof-overseas-customer-prospects/2026-05-30/scale5000/` 산출물 영역을 만든다.
- [x] Playwright MCP로 dental lab/directory/email/address 계열 검색을 수행해 대량 소스 방향을 확인한다.
- [x] GeoNames 주요 도시 좌표 + OpenStreetMap 공개 사업자 태그 기반 수집 스크립트를 만든다.
- [x] `email + phone + address` 필수 필드가 모두 있는 해외 후보만 valid로 저장한다.
- [x] 목표 5000개까지 도시/국가 배치를 계속 확장한다.
- [x] valid 후보별 카드와 CSV/JSONL 인덱스를 생성하고 카운트를 검증한다.

### 새 산출물
- 스키마: `output/dof-overseas-customer-prospects/2026-05-30/scale5000/schema.md`
- 데이터: `output/dof-overseas-customer-prospects/2026-05-30/scale5000/data/prospects_valid.jsonl`
- CSV: `output/dof-overseas-customer-prospects/2026-05-30/scale5000/data/prospects_valid.csv`
- 카드: `output/dof-overseas-customer-prospects/2026-05-30/scale5000/cards/`

### 5000개 확장 결과
- valid 후보: 5151개
- 카드: 5151개
- 필수값 누락 검증: 0건
- 이메일 중복 검증: 0건
- 국가 상위: Germany 2231, Netherlands 535, Poland 388, United States 328, Spain 260
- 세그먼트: Dental clinic/practice 4331, orthodontics 450, implant/surgery 287, dental laboratory/technician 83
- 실행 스크립트: `proc/lib/dof_prospect_scale5000.py`

## 포탈 해외 고객사 오버레이

사용자 추가 요구: 기존에 찾은 해외 잠재고객 목록과 DOF 포탈 고객사를 비교하고, 포탈에 있는 해외 고객사도 추가한다.

### 실행 기준
- 포탈 원천: `dof-order-web-3-az/.env`의 로컬 `DATABASE_URL` 기준 active `Company`
- 국가 기준: `Company.country`가 있으면 우선 사용하고, 로컬 DB의 빈 국가값은 `output/portal-company-country-update-20260528/`의 검증된 국가 보정 결과로 보완한다.
- 기존 리서치 목록과의 매칭은 보수적으로 제한한다.
  - 이메일 exact
  - 포탈 `website` 도메인 exact
  - 정규화 업체명 exact + 같은 국가
  - Facebook/Instagram/LinkedIn/지도/메신저 등 공용 도메인과 이메일 도메인만으로는 매칭하지 않는다.
- 포탈 추가분의 `contact complete`는 유효한 이메일, 숫자가 포함된 전화/연락처, 의미 있는 주소가 모두 있는 경우만 인정한다.

### 결과
- 포탈 active 회사: 3289개
- 포탈 해외 회사: 753개
- 기존 5151개 리서치 목록과 확정 매칭된 포탈 회사: 0개
- 포탈 해외 회사 신규 추가: 753개
- 포탈 추가분 중 연락처 3종 완비: 498개
- 포탈 추가분 중 연락처 미완비: 255개
- 전체 오버레이 행 수: 5904개
- 연락처 완비 기준 최종 행 수: 5649개
- 포탈 추가 고객카드: 753개

### 산출물
- 요약: `output/dof-overseas-customer-prospects/2026-05-30/scale5000/portal_overlay_report.md`
- 포탈 해외 고객 전체: `output/dof-overseas-customer-prospects/2026-05-30/scale5000/data/portal_foreign_companies.jsonl`
- 포탈 신규 추가 전체: `output/dof-overseas-customer-prospects/2026-05-30/scale5000/data/portal_foreign_additions.jsonl`
- 포탈 신규 추가 중 연락처 완비: `output/dof-overseas-customer-prospects/2026-05-30/scale5000/data/portal_foreign_additions_contact_complete.jsonl`
- 포탈 신규 추가 중 연락처 미완비: `output/dof-overseas-customer-prospects/2026-05-30/scale5000/data/portal_foreign_additions_contact_incomplete.jsonl`
- 기존 5151 + 포탈 해외 전체: `output/dof-overseas-customer-prospects/2026-05-30/scale5000/data/prospects_augmented_with_portal.jsonl`
- 기존 5151 + 포탈 연락처 완비: `output/dof-overseas-customer-prospects/2026-05-30/scale5000/data/prospects_augmented_contact_complete.jsonl`
- 포탈 추가 고객카드: `output/dof-overseas-customer-prospects/2026-05-30/scale5000/portal_addendum_cards/`
- 실행 스크립트: `proc/lib/dof_portal_customer_overlay.py`, `proc/lib/dof_portal_query_companies.mjs`

### 검증
- `python3 -m py_compile proc/lib/dof_portal_customer_overlay.py proc/lib/dof_prospect_scale5000.py`
- `node --check proc/lib/dof_portal_query_companies.mjs`
- 연락처 완비 최종 파일 `prospects_augmented_contact_complete.jsonl`: 5649행
- 필수값/이메일/전화/주소 형식 문제: 0건

## HTML 지도 리포트

사용자 추가 요구: HTML 보고서에서 OSM 기반 지도로 고객사 위치를 표출한다.

### 지도 좌표 처리
- 공개 리서치 5151건: OSM `node/way/relation` ID를 Overpass로 배치 조회해 좌표를 복원한다.
- 포탈 항목: 포탈 주소 문자열에서 GeoNames 도시명을 찾고, 실패 시 국가 기준 근사 좌표를 사용한다.
- 좌표 정밀도는 HTML 지도 팝업에 `exact`, `center`, `city`, `country`로 표시한다.

### 지도 결과
- 지도 좌표 생성: 5904/5904건
- 정밀도 분포: exact 4831, center 320, city 456, country 297
- 좌표 데이터: `output/dof-overseas-customer-prospects/2026-05-30/scale5000/data/prospect_map_points.json`
- OSM 좌표 캐시: `output/dof-overseas-customer-prospects/2026-05-30/scale5000/data/osm_coordinate_cache.json`
- HTML 리포트: `output/dof-overseas-customer-prospects/2026-05-30/scale5000/dof_overseas_customer_prospects.html`
- 실행 스크립트: `proc/lib/dof_customer_prospect_map_points.py`, `proc/lib/dof_customer_prospects_html_report.py`

### 지도 검증
- `python3 -m py_compile proc/lib/dof_customer_prospects_html_report.py proc/lib/dof_customer_prospect_map_points.py`
- 브라우저 렌더링 확인: Leaflet 로드, OSM 타일 18개 로드, 기본 지도 5649개 위치 표시
- 검색 연동 확인: `ATD JAPAN` 검색 시 테이블 1건, 지도 1개 위치 표시

## 2026-05-31 deck.gl 지도 전환 및 추가 리서치

사용자 추가 요구: 지도는 deck.gl을 사용하고, OSM 기반으로 표출한다. 동남아·일본·미국 관련 고객사를 2000개 정도 더 찾아 지도에도 표출한다.

### 추가 수집 방식
- `proc/lib/dof_prospect_scale5000.py`
  - 동남아 대상 국가 추가: `MY, TH, VN, ID, PH, KH, LA, MM, BN, TL`
  - 일본/동남아 country sweep 실행
  - 미국은 country sweep이 실효 데이터를 반환하지 않아 `US-AL` 등 ISO3166-2 주 단위 area sweep 모드를 추가해 실행
- `proc/lib/dof_enrich_incomplete_websites.py`
  - OSM에는 이름/전화/주소/웹사이트가 있지만 이메일이 빠진 후보를 대상으로 공식 웹사이트를 확인
  - 이메일을 찾은 경우 `OSM public tag + official website contact extraction` 출처로 valid 고객카드 승격
  - 웹사이트 확인 캐시: `data/website_enrichment_cache.json`
  - 승격 로그: `data/website_enrichment_promotions.jsonl`

### 추가 수집 결과
- 공개 valid: 5151개 -> 7164개
- 공개 valid 추가: 2013개
- 주요 대상 지역 현재 공개 valid:
  - United States: 2157
  - Japan: 81
  - Philippines: 37
  - Thailand: 21
  - Singapore: 13
  - Malaysia: 12
  - Cambodia: 6
  - Vietnam: 6
  - Indonesia: 5
  - Myanmar: 3
- 필수값/이메일/전화 형식 검증: `prospects_valid.jsonl` 7164행, 문제 0건

### 포탈 오버레이 재생성 결과
- 포탈 active 회사: 3291개
- 포탈 해외 회사: 754개
- 포탈 신규 추가: 754개
- 포탈 추가분 중 연락처 완비: 499개
- 포탈 추가분 중 연락처 미완비: 255개
- 포탈 포함 연락처 완비 최종: 7663개
- 포탈 포함 전체: 7918개
- 필수값/이메일/전화 형식 검증: `prospects_augmented_contact_complete.jsonl` 7663행, 문제 0건

### deck.gl 지도 결과
- HTML 지도 엔진: deck.gl `TileLayer` + `BitmapLayer`로 OSM 타일 표시, `ScatterplotLayer`로 고객사 표시
- 좌표 생성: 7918/7918건
- 좌표 정밀도: exact 6442, center 722, city 457, country 297
- 지도 데이터: `output/dof-overseas-customer-prospects/2026-05-30/scale5000/data/prospect_map_points.json`
- HTML: `output/dof-overseas-customer-prospects/2026-05-30/scale5000/dof_overseas_customer_prospects.html`

### 검증
- `python3 -m py_compile proc/lib/dof_customer_prospects_html_report.py proc/lib/dof_customer_prospect_map_points.py proc/lib/dof_prospect_scale5000.py proc/lib/dof_enrich_incomplete_websites.py proc/lib/dof_portal_customer_overlay.py`
- `node --check proc/lib/dof_portal_query_companies.mjs`
- Playwright 검증: deck.gl 로드, WebGL 사용 가능, canvas 1개, 기본 지도 `7663개 위치 표시`
- 검색 연동 검증: `ATD JAPAN` 검색 시 테이블 1건, 지도 1개 위치 표시

## 2026-06-01 Outline 영업처후보 트리 게시

사용자 추가 요구: `영업처후보` Outline 문서 하위에 해외 영업처 후보를 서버 문서 트리로 올린다. 구조는 Region -> Country -> 업체 문서이며, 각 단계마다 요약을 둔다.

### 실행 계획
- [x] 대상 Outline 루트 문서와 API 인증 방식을 확인한다.
- [x] `prospects_augmented_contact_complete.jsonl`의 국가값을 정규화하고 Region을 부여한다.
- [x] Region/Country/업체 문서를 생성하거나 기존 문서를 갱신한다.
- [x] 선정이유와 영업 표시 문구를 한국어로 변환한다.
- [x] 대표 문서와 전체 문서 수를 API로 검증한다.

### 게시 구조
- 루트: 전체 후보 수, 국가 수, 지역 수, 고객군/출처 분포, Region 문서 링크
- Region 문서: 지역 내 후보 수, 국가 수, 주요 국가, 고객군/출처 분포, Country 문서 링크
- Country 문서: 국가 요약, 대표 업체, 업체별 하위 문서 안내
- 업체 문서: 개별 업체의 고객군, DOF 적합성, 선정 이유, 이메일, 전화, 주소, 웹사이트, 출처, 근거, 영업 메모 공간

### 산출물
- 게시 스크립트: `proc/lib/dof_prospect_outline_publish.py`
- 게시 데이터 요약: `output/dof-overseas-customer-prospects/2026-05-30/scale5000/outline_publish/outline_publish_dataset.json`
- Outline 문서 캐시: `output/dof-overseas-customer-prospects/2026-05-30/scale5000/outline_publish/outline_docs.json`
- 게시 결과: `output/dof-overseas-customer-prospects/2026-05-30/scale5000/outline_publish/outline_publish_result.json`

### 게시 결과
- 루트 문서: `https://outline.doflab.com/doc/7jib7jef7lky7zue67o0-c0ae88mpyc`
- 대상 후보: 7663건
- Region 문서: 11개
- Country 문서: 103개
- 업체 문서: 7663개
- 루트 포함 총 문서: 7778개
- 기존 range batch 문서: 캐시/트리에서 제거, `United States 2001-2170` 같은 제목이 남지 않도록 검증
- 큰 국가 하위 업체 문서: United States 2170개, Germany 2262개

### 게시 검증
- API 검증: 루트 하위 region 11개, region 하위 country 103개, country 하위 업체 문서 7663개
- 루트 본문 검증: 전체 후보 `7,663`, `지역 트리`, 업체 문서 단계 구조 확인
- Region 본문 검증: `WestEurope` 문서의 `국가별 문서` 섹션 확인
- Country 본문 검증: `United States` 문서의 대표 50개 표시 안내와 업체별 문서 섹션 확인
- 업체 본문 검증: 샘플 업체 문서의 `선정 이유`가 한국어이고 기존 영어 선정이유 문장이 남지 않음
- 트리 검증: `0001-0200`, `2001-2170` 같은 range 제목 0건
- 문법 검증: `python3 -m py_compile proc/lib/dof_prospect_outline_publish.py proc/lib/dof_customer_prospect_map_points.py`

## 2026-06-01 Outline 트리 재정렬: 기존고객/잠재고객 + 짧은 지역명

사용자 추가 요구: 국가 폴더를 중간에 두지 않고 `영업처후보/{지역}/{기존고객|잠재고객}/{업체}` 구조로 묶는다. 지역명은 영업팀이 빠르게 읽을 수 있도록 `북미`, `남미`, `동북아`, `동남아`, `인니`, `중유럽`, `서유럽`, `동유럽`, `CIS`, `중동` 등 짧은 한국어 표기로 바꾼다.

### 실행 계획
- [x] 실행 중이던 기존 게시 프로세스가 남아 있으면 중단하고 상태를 확인한다.
- [x] 기존 업체 문서를 중복 생성하지 않도록 캐시 호환 로직을 추가한다.
- [x] 기존 `Region/Country/업체` 구조를 `지역/기존고객|잠재고객/업체` 구조로 바꾸는 게시 스크립트로 수정한다.
- [x] 긴 영어 지역명을 짧은 영업용 라벨로 재분류한다.
- [x] 업체 제목의 국가 괄호도 `United States` 대신 `미국`, `Indonesia` 대신 `인니`처럼 줄인다.
- [x] Outline 문서를 실제로 이동/이름변경한다.
- [x] 기존 영어 region/status/country 폴더가 트리에 남지 않았는지 API로 검증한다.

### 목표 트리
- `영업처후보/북미/기존고객/{업체}`
- `영업처후보/북미/잠재고객/{업체}`
- `영업처후보/동북아/기존고객/{업체}`
- `영업처후보/동남아/잠재고객/{업체}`
- `영업처후보/인니/잠재고객/{업체}`
- `영업처후보/중유럽/잠재고객/{업체}`
- 같은 방식으로 `서유럽`, `동유럽`, `CIS`, `중동`, `남미`, `남아시아`, `오세아니아`, `아프리카`, `기타`를 둔다.

### 완료 결과
- 게시 스크립트: `proc/lib/dof_prospect_outline_publish.py`
- 업체 카드 본문 refresh 스크립트: `proc/lib/dof_prospect_outline_refresh_company_cards.py`
- 전체 업체 문서: 7663개
- 기존고객: 499개
- 잠재고객: 7164개
- 최종 구조: `영업처후보/{짧은지역}/{기존고객|잠재고객}/{업체}`
- 루트 하위 지역 문서: 14개 (`북미`, `남미`, `동북아`, `동남아`, `인니`, `중유럽`, `서유럽`, `동유럽`, `CIS`, `중동`, `남아시아`, `오세아니아`, `아프리카`, `기타`)
- 상태 문서: 21개
- 상태 문서 하위 업체 문서: 7663개
- 업체 카드 본문 refresh: 7663개 성공, 실패 0건, 캐시 누락 0건
- 기존 국가 폴더 archive: 103개
- 기존 영어 region 폴더 archive: 11개
- 기존 영어 status 폴더 archive: 4개
- 추가 정리: 데이터셋 범위 밖 루트 하위 `대한민국` 폴더 archive
- API 검증 결과: 루트 예상 외 제목 0개, 지역 하위 비상태 폴더 0개, 예전 range/영어 region 제목 0개
- 검증 파일: `output/dof-overseas-customer-prospects/2026-05-30/scale5000/outline_publish/outline_tree_verification.json`

## 2026-06-01 Outline 트리 보정: 대한민국 복구 + 국가 폴더 재도입 + 랩/디자인/유통 후보 확장

사용자 추가 요구:
- `대한민국` 폴더는 나중에 사용할 예정이므로 archive 상태에서 복구하고 하위 문서도 유지한다.
- 기존 `영업처후보/{지역}/{기존고객|잠재고객}/{업체}` 구조를 `영업처후보/{지역}/{기존고객|잠재고객}/{국가명짧게}/{업체}` 구조로 바꾼다.
- 잠재고객에 덴탈 기공소, 덴탈 디자인샵, 덴탈 제품 유통사 관련 해외 업체를 약 4000개 추가 수집하고 저장한 뒤 Outline에도 올린다.
- 최신 보정: `기존고객`은 단일 폴더로 유지하고, `잠재고객`만 `잠재고객-치과`, `잠재고객-교정치과`, `잠재고객-치기공`, `잠재고객-유통사`로 나눈다.
- 추가 수집 목표는 우선 약 2000개이며, 덜 찾았던 국가를 중심으로 `치기공소`의 현지어 표현을 사용해 찾는다.

### 실행 계획
- [x] `대한민국` 문서를 restore하고 하위 문서가 보이는지 확인한다.
- [x] 게시 스크립트를 `지역/상태/국가/업체` 구조로 수정한다.
- [x] 기존 업체 문서를 국가 폴더 아래로 이동하고 요약 문서를 갱신한다.
- [x] 새 트리 구조를 Outline API로 검증한다.
- [ ] 기존고객은 단일 폴더로 유지하고 잠재고객만 업종 카테고리 포함 명칭으로 재분류한다.
- [ ] 랩/디자인샵/유통사 후보 수집 쿼리와 현지어 검색어를 확장한다.
- [ ] 추가 후보를 기존 데이터셋에 병합하고 중복/필수 필드를 검증한다.
- [ ] 추가 후보를 포함해 Outline에 게시하고 최종 검증한다.

### 현재 확인
- `대한민국` 문서 restore 완료: archive 해제됨.
- `대한민국` 하위 문서: `대전`, `서울`.

### 국가 폴더 재도입 결과
- 최종 기존 데이터 구조: `영업처후보/{짧은지역}/{기존고객|잠재고객}/{국가명짧게}/{업체}`.
- Region 문서: 14개.
- Status 문서: 21개.
- Country 문서: 128개.
- Country 문서 하위 업체 문서: 7663개.
- 상태 문서 바로 아래 남은 업체 문서: 0개.
- 검증 파일: `output/dof-overseas-customer-prospects/2026-05-30/scale5000/outline_publish/outline_country_tree_verification.json`.
