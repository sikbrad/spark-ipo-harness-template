# 해외 치과 유통사·수출입 잠재고객 3,000건 확장

## 목표
OSM 의존도를 낮추고 국제 치과 전시회, 공식 exhibitor directory, 현지어 검색, 공개 yellow page/비즈니스 디렉터리, 정부·수출기관 성격의 공개 목록을 활용해 해외 치과 유통사·수출입사 잠재고객을 약 3,000건 추가한다.

완료 기준은 신규 후보를 `prospects_augmented_contact_complete.jsonl`에 dedupe 병합하고, 조사 결과 md를 저장한 뒤 Outline `영업처후보` 문서 트리에 카테고리별로 반영하고 라이브 readback으로 확인하는 것이다.

## 작업 항목
- [x] 현재 public valid 데이터셋 규모와 유통사/국가 분포 확인
- [x] 저명 국제 치과 전시회 기반 후보 수집: AEEDC, IDS, GNYDM, Hinman, Yankee, AAO, Expodental 등
- [x] 치과 유통·수출입 현지어 키워드 기반 공개 웹/비즈니스 디렉터리 검색 보강
- [x] Facebook/LinkedIn은 로그인 없는 공개 회사 페이지/검색 노출만 후보로 참고하고, 승격은 공식 사이트·공개 디렉터리 연락처 확인 건으로 제한
- [x] 업체명, 이메일, 전화, 주소, 공개 출처가 모두 있는 후보만 데이터셋에 dedupe 병합
- [x] 조사 결과와 신뢰도 기준을 md에 저장
- [x] Outline에 신규 업체 문서와 상위 지역/상태/국가 문서를 반영
- [x] 중간 문서 `현재 하위 현황` 섹션을 최신 counts로 재갱신
- [x] 데이터셋/Outline live readback/중간 문서 검증 결과를 남김

## 2026-06-03 실행 메모
- complete dataset은 17,340행에서 18,124행으로 증가했다. 이번 병합 신규는 784행이다.
- 신규 784행 중 공식 locator/table high trust가 750행, 현지어 검색 재방문 검증 medium-high가 12행이다.
- 3,000건 목표는 이메일·전화·주소·공개 출처 완비 기준으로는 달성하지 못했다. Facebook/LinkedIn 단독 노출, 검색 snippet 단독, 연락처 일부 누락 후보는 승격하지 않았다.
- 상세 요약은 `output/dof-overseas-customer-prospects/2026-05-30/scale5000/external_distributor_expansion_round8_summary.md`에 저장했다.
- Outline 증분 발행은 `outline_incremental_new_publish_result_round8.json` 기준 신규 784개 문서 처리 완료.
- 중간 문서는 live tree 기준 499개 갱신 후 verify-only 499/499 성공.
- 국가 추론 오류 7행을 정정했고, AD2 Honduras/Magno Dental/Orodent Group/SASSOUNIAN INC. 샘플 live readback에서 제목과 본문 국가 줄이 일치함을 확인했다.

## 2026-06-03 Round 9 continuation
- [x] 사용자 최신 지시에 따라 OSM 외 방법을 더 넓게 사용한다. 공식 전시회/정부·무역 파빌리온/제조사·전시 디렉터리는 high 또는 medium-high, yellow page·현지어 검색은 low-medium, Facebook/LinkedIn 공개 snippet은 low로 표기한다.
- [x] 이전 complete-contact 기준과 구분하기 위해 `partial_public_source` row를 허용한다. 이메일·전화·주소가 비어 있을 수 있으므로 `source_trust`, `contact_completeness`, `partial_contact`, `non_osm` 태그를 반드시 남긴다.
- [x] `proc/lib/dof_partial_distributor_candidate_expansion.py`를 추가했다. 기존 complete row는 보존하고, 라운드9 직전 백업 기준으로 신규 row만 붙인다.
- [x] 라운드9 후보 2,979건을 추가 병합하고 `external_partial_distributor_expansion_round9.md`에 신뢰도와 출처를 저장했다. complete dataset은 18,124행에서 21,103행이 되었다.
- [x] 라운드9 직전 백업을 baseline으로 Outline에 신규 문서만 증분 발행했다. `outline_incremental_new_publish_result_round9.json` 기준 2,979개 신규 회사 문서를 처리했다.
- [x] 국가 alias와 ICE/ITA PDF의 명백한 업체명 파싱 잡음 34건을 정리하고 재발행했다. `South Korea/Republic of Korea/Korea`, `Magyarország`, `The Netherlands`, 주소가 섞인 Pakistan 값은 canonical country로 정리했다.
- [x] 중간 문서 `현재 하위 현황`을 live tree 기준으로 다시 갱신하고 verify-only로 확인한다.
- [x] 전체 Outline publish를 다시 실행해 15개 지역, 130개 국가, 67개 상태 문서, 21,103개 dataset 기반 회사 문서를 정렬했다. 이 과정에서 레거시 alias 국가 문서 22개를 archive하고 회사 문서 13개를 올바른 상위 국가/상태 아래로 move했다.
- [x] alias/라벨 영향 국가 재게시를 추가로 실행해 7,098개 회사 문서의 제목과 본문을 정규화했다. 바레인/슬로베니아 한글 라벨을 추가했고, ICE/ITA PDF continuation line 1건은 EMERITALIA로 보정해 같은 Outline key로 갱신했다.
- [x] 최종 중간 문서 update는 495/495 성공, verify-only도 495/495 성공했다. 최신 스캔 기준 root 하위 회사형 문서는 21,108개이며, dataset 21,103개 외 기존/레거시 보존 문서 5개가 포함된 것으로 보인다.
- [x] 요청에서 지목한 중간 문서 확인: `남유럽` 42개, `남유럽/기존고객` 4개, `그리스` 35개(기존고객 4, 교정치과 1, 유통사 21, 치과 9), `기타` 2개, `아프리카` 584개로 live scan에 반영됐다.

## 2026-06-03 Round 10 continuation
- [x] round9 산출물을 덮지 않고 `round10` 전용 promotions/summary/publish result를 만든다.
- [x] OSM이 아닌 새 출처를 추가한다: CEDE 2026, Southwest Dental Conference 2026, LMT, BDIA, ADIA, SADTO, AAO/A2Z, Dental Expo NL, NDDA Nepal, manufacturer dealer PDF/list, ExportersIndia/IndiaMART 등.
- [x] 덜 찾은 국가와 치과 유통·수출입 현지어 표현을 우선한다. 직접 연락처가 없는 경우에도 `partial_public_source`로 승격하되 `source_trust`, `contact_completeness`를 반드시 남긴다.
- [x] 신규 후보 약 3,000건을 complete dataset에 dedupe append하고 md에 신뢰도/출처/국가별 분포를 저장한다. generic UI/programme 문구를 제거한 최종 신규는 2,998건, complete dataset은 24,101건이다.
- [x] 신규 row만 Outline에 증분 발행한 뒤 중간 문서를 최신 상태로 맞추고 verify-only로 확인한다. 신규 3,002건 발행 후 generic 4건을 archive했고, 중간 문서 update/verify-only는 495/495 성공했다.

## 2026-06-03 all-company contact table
- [x] 전체 24,101개 업체에 대해 `대분류=지역`, `중분류=고객군/상태`, `소분류=국가`와 연락처 필드가 들어간 단일 테이블 md/CSV를 생성했다.
- [x] 생성 파일: `output/dof-overseas-customer-prospects/2026-05-30/scale5000/all_contacts_table/all_company_contacts_table.md`(5.4MB), `all_company_contacts_table.csv`(7.9MB), Outline용 compact/tiny md.
- [x] Outline 단일 문서 발행 시도 결과: full 5.4MB는 `413 request entity too large`, 4.0MB/3.0MB/2.1MB/1.87MB/1.77MB compact table은 `read timeout`으로 실패했다. 기존 fallback 문서 `https://outline.doflab.com/doc/pfDRXFD1MJ`는 생성됐지만 전체 테이블 본문 삽입은 Outline API 한계로 완료되지 않았다.
- [x] 로컬 단일 Markdown table 검증: header에 대분류/중분류/소분류/연락처 포함, table row marker 24,102개(헤더+구분선+24,101 업체).

## 2026-06-04 Round 11 continuation
- [x] Round10 산출물과 전체 연락처 테이블은 보존하고 `round11` 전용 promotions/summary/search cache/publish result를 만들었다.
- [x] OSM 외 추가 경로를 더 넓혔다: CMS NPI 공식 Dental Laboratory/Dental/Dentist organization API, A2Z 공식 전시자 페이지, German Pavilion, CIOSP/APCD/CDA/DentalLabProfile probe. CIOSP/APCD/CDA/DentalLabProfile은 login/403/timeout으로 승격하지 않고 probe 로그만 남겼다.
- [x] 치과 유통사/수출입사와 치기공소/랩/치과 조직을 segment와 `source_family`로 분리했다. 최종 승격 3,000건은 high 2,478건, medium-high 522건이며 low/검색 snippet 단독은 이번 병합에서 제외했다.
- [x] 신규 후보 3,000건을 complete dataset에 dedupe append했다. complete dataset은 24,101행에서 27,101행이 되었고, `external_partial_distributor_expansion_round11.md`에 출처별·신뢰도별·국가별 분포를 저장했다.
- [x] 신규 row 3,000건을 Outline에 증분 발행했다. `outline_incremental_new_publish_result_round11.json` 기준 `processedNewCompanyDocs=3000`, `newRows=3000`, `completeRows=27101`.
- [x] 전체 연락처 테이블 md/CSV를 27,101건 기준으로 재생성했다. Outline 단일 테이블 발행은 대용량 본문 API timeout 위험 때문에 `--skip-outline`로 로컬 최신본만 확정했다.
- [x] 중간 문서 `현재 하위 현황`을 API 회복 후 캐시 기반 live read/update 방식으로 갱신했다. `middle_docs_update_cache_summary_2026-06-04.json` 기준 496/496 성공, `middle_docs_verify_cache_summary_2026-06-04.json` 기준 live readback 496/496 성공.
- [x] 지목된 중간 문서 확인: `남유럽` 42개, `남유럽/기존고객` 4개, `그리스` 4개, `기타` 2개, `아프리카` 673개 하위 업체로 최신 스캔에 반영됐다. 루트 스캔은 하위 중간 문서 495개와 회사형 leaf 27,102개를 계산했다.

## 2026-06-04 Round 12 scanner/milling/CAD-CAM sourcing
- [x] Round11 이후 dataset 27,101행을 baseline으로 보존하고 `round12` 전용 promotions/summary/search cache/publish result를 만들었다.
- [x] 타깃을 `덴탈 밀링기`, `구강/랩 스캐너`, `CAD/CAM`, `exocad/3Shape/Medit/Shining3D/vhf/Roland DG/imes-icore/Amann Girrbach/Planmeca/Dentsply Sirona` 리셀러·파트너·벤더로 좁혔다.
- [x] 공식 파트너/리셀러/전시자 출처는 high 또는 medium-high로, 현지어 검색/비즈니스 디렉터리/검색 snippet은 low-medium 또는 reject로 분리했다.
- [x] 현지어 쿼리를 사용했다: `distribuidor escáner intraoral`, `fresadora dental`, `CAD CAM dental`, `revendeur scanner intra-oral`, `Dental CAD CAM Händler`, `scanner intraorale rivenditore`, `歯科用ミリングマシン 販売代理店`, `口腔扫描仪 经销商` 등.
- [x] 광범위 검색으로 3,138건을 일단 append했으나 검색 잡음이 높아 Round12 품질 정리 스크립트로 2,821건을 reject하고 최종 317건만 보존했다. 최종 complete dataset은 27,418행이다.
- [x] 중단 전 잘못 발행된 Round12 Outline 회사 문서 255개를 archive했고, clean row만 다시 증분 발행했다. `outline_incremental_new_publish_result_round12.json` 기준 `processedNewCompanyDocs=285`, `completeRows=27418`.
- [x] 중간 문서 `현재 하위 현황`을 최신 캐시 기준 505개 갱신했고, verify-only live readback도 505/505 성공했다.
- [x] 전체 연락처 테이블 md/CSV를 27,418건 기준으로 재생성했다.

## 2026-06-04 Round 12 실행 메모
- 직접 출처: vhf 공식 dental reseller locator, exocad IDS 2025 공식 reseller PDF, 그리고 Medit/Shining3D/Aoralscan/3Shape/TRIOS/exocad/vhf/DGSHAPE/Roland/imes-icore/Ceramill/Zirkonzahn 관련 현지어 검색.
- 신뢰도: high 103건, medium-high 4건, low-medium 210건. low-medium은 제품 페이지와 치과 사업자 신호가 같이 있는 lead seed로만 유지했다.
- 품질 reject: 1차 broad 3,138건 중 검색결과 제목, generic 웹페이지, vendor homepage 검색 노출, 포럼/기사/비업체 페이지, DOF 자체 등 2,805건을 제거했고, 2차 audit에서 Mayo Clinic/Allied Vision/portal·directory 잡음 16건을 추가 제거했다.
- 결과 파일: `scanner_milling_cadcam_expansion_round12.md`, `data/partial_distributor_promotions_round12.jsonl`, `data/partial_distributor_promotions_round12_rejected_quality.jsonl`, `outline_publish/outline_round12_aborted_docs_archive_result.json`.

## 2026-06-04 recommended distributor report expansion
- [x] Outline `리포트260604-해외` 문서를 42개 추천 업체에서 120개 추천 업체로 확장했다.
- [x] 후보 리포트는 포탈 주문 발생/등록 업체를 제외하고 신규 영업 후보만 강조하도록 재작성했다.
- [x] 제외 기준: `DOF portal Company`, `portal_company_id`, `portal_orders_count`가 있는 470개 포탈 row와 회사명/도메인/이메일이 겹치는 후보를 제외했다.
- [x] 테이블에 `포탈/주문 상태` 컬럼을 추가했고 120개 모든 행을 `비포탈 후보 / 포탈 주문 없음`으로 표시했다.
- [x] Outline readback 검증: `row_count=120`, `has_portal_exclusion=true`, `has_table=true`, source group은 공식밀링리셀러 62, 공식딜러/유통망 21, 제품페이지/현지검색 28, CADCAM/스캐너 6, 전시/협회확인 3이다.
- [x] 로컬 산출물: `output/dof-overseas-customer-prospects/2026-05-30/scale5000/recommended_overseas_dental_distributors_260604.md`, 검증 JSON은 같은 폴더의 `recommended_overseas_dental_distributors_260604_result.json`.

## 2026-06-04 recommended distributor report expansion 2
- [x] 같은 Outline `리포트260604-해외` 문서를 기존 120개 추천 행을 보존한 채 300개로 확장했다. 이번 추가는 180개다.
- [x] 기존 조건을 유지했다: 포탈 주문/등록 업체 제외, OSM 단독·일반 병원/학교/학회/미디어·parser 잡음·검색 snippet 단독 후보 제외.
- [x] 비포탈 제외 기준을 다시 적용했다: 포탈 row 470개와 회사명/도메인/이메일 겹침 후보를 제외했고, 엄격 후보 pool 1,388개 중 상위 300개만 반영했다.
- [x] Outline live readback 검증: `row_count=300`, `nonportal_status_cells=300`, `has_portal_exclusion=true`, `text_len=119970`.
- [x] 최종 source group: 공식밀링리셀러 148, 공식딜러/유통망 92, CADCAM/스캐너 57, 전시/협회확인 3.
- [x] 최종 주요 출처: vhf 118개, 제품/회사 CAD-CAM·scanner page 51개, Ivoclar 39개, 현지어 CAD-CAM/scanner/milling 검색 28개, GC Dental 25개, Henry Schein locator 15개 등.
- [x] 국가 대분류 라벨도 함께 보정했다: UK/북유럽/코카서스/중앙아시아/중동 일부가 `Other`로 남지 않도록 수정했다.

## 2026-06-05 recommended report web enrichment
- [x] 사용자 요청에 따라 `리포트260604-해외` 300개 추천 업체에 대해 웹 부가정보를 추가 조사했다.
- [x] 새 컬럼 5개를 추가했다: `웹 링크 상태`, `출처 링크 상태`, `추가 확인 취급/브랜드`, `최근 온라인 흔적`, `링크/부가정보 신뢰도`.
- [x] 검증 방식: 회사 웹사이트 HTTP fetch, 원출처 링크 HTTP fetch, 홈페이지/제품·뉴스·이벤트 링크 본문, DuckDuckGo 공개 검색 결과를 캐시 기반으로 수집했다.
- [x] Outline live readback 검증: `row_count=300`, `has_new_columns=true`, `text_len=187673`.
- [x] 링크 상태: 회사 웹사이트 200 응답 248개, 403 차단 10개, fetch error 28개, timeout 8개, parse error 1개, no link 4개, 404 1개. 원출처 링크는 200 응답 294개, 403 2개, 404 1개, timeout 2개, fetch error 1개.
- [x] 부가정보 신뢰도: 높음 237개, 중간 58개, 낮음 5개. 브랜드/취급 신호는 286개에서 확인했고, 최근연도/SNS/검색근거/미디어 후보 중 하나 이상은 212개에서 확인했다.
- [x] 미디어/행사 후보는 디렉터리·SNS·검색 포털을 제외해 보수적으로 2건만 표시했다. 나머지는 `검색근거` 또는 `SNS/최근연도`로 표기했다.
- [x] 산출물: `outline_publish/recommended_report_web_enrichment_260605/recommended_report_web_research.jsonl`, `summary.json`, `cache.json` 및 갱신된 `recommended_overseas_dental_distributors_260604.md`.

## 2026-06-05 Playwright browser retry
- [x] requests 기반 조사에서 `403/fetch error/timeout/no link/404/낮음`으로 남은 53개 행을 `playwright-cli` 브라우저 세션에서 직접 열어 재검증했다.
- [x] 브라우저 재시도로 53개 모두에 `browser_retry` 근거를 남겼고, 38개 웹사이트와 50개 출처 링크를 브라우저 기준으로 보강했다.
- [x] Outline live readback 검증: `row_count=300`, `has_new_columns=true`, `text_len=190805`.
- [x] 최종 부가정보 신뢰도: 높음 279개, 중간 21개, 낮음 0개.
- [x] 최종 웹 링크 상태: 200 응답 251개, 브라우저 렌더/확인 34개, 403 차단 10개, no link 4개, 404 1개.
- [x] 최종 출처 링크 상태: 200 응답 290개, 브라우저 렌더/확인 7개, 403 차단 2개, 404 1개.
- [x] 남은 이슈는 실제 브라우저에서도 차단되는 사이트(Patterson Dental, Proto3000, Interdent 일부, doctorline, LabEx 등), 웹사이트 링크 자체가 없는 4개, 웹사이트 404 1개, 출처 404 1개로 테이블에 그대로 표시했다.
- [x] 산출물: `outline_publish/recommended_report_web_enrichment_260605/browser_retry_results.json`, `browser_retry_summary.json`, 갱신된 `recommended_report_web_research.jsonl`.

## 수집 원칙
- 기존 업체 문서는 보존하고, 같은 이메일 또는 같은 업체명+주소 dedupe key가 있으면 새 행을 무리하게 추가하지 않는다.
- OSM은 이번 요청의 핵심이 아니므로 기본 수집 소스에서 제외한다. 직접 소스만으로 부족할 때도 OSM 추가 사용 여부는 별도 로그에 명시한다.
- 현지어 검색은 국가별 표현을 섞는다: `distribuidora dental`, `depósito dental`, `equipamentos odontológicos`, `fournisseur dentaire`, `matériel dentaire`, `Dentalbedarf`, `Dentalhandel`, `forniture dentali`, `diş malzemeleri`, `مستلزمات طب الأسنان`, `thiết bị nha khoa`, `alat kedokteran gigi`, `牙科器材`, `歯科材料`.
- 신뢰도는 공개 공식 exhibitor/정부·수출기관/제조사 distributor locator를 높음, yellow page·비즈니스 디렉터리를 중간, 검색 결과·SNS 단독 노출을 낮음 또는 미승격으로 둔다.
