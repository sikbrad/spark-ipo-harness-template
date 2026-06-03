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

## 수집 원칙
- 기존 업체 문서는 보존하고, 같은 이메일 또는 같은 업체명+주소 dedupe key가 있으면 새 행을 무리하게 추가하지 않는다.
- OSM은 이번 요청의 핵심이 아니므로 기본 수집 소스에서 제외한다. 직접 소스만으로 부족할 때도 OSM 추가 사용 여부는 별도 로그에 명시한다.
- 현지어 검색은 국가별 표현을 섞는다: `distribuidora dental`, `depósito dental`, `equipamentos odontológicos`, `fournisseur dentaire`, `matériel dentaire`, `Dentalbedarf`, `Dentalhandel`, `forniture dentali`, `diş malzemeleri`, `مستلزمات طب الأسنان`, `thiết bị nha khoa`, `alat kedokteran gigi`, `牙科器材`, `歯科材料`.
- 신뢰도는 공개 공식 exhibitor/정부·수출기관/제조사 distributor locator를 높음, yellow page·비즈니스 디렉터리를 중간, 검색 결과·SNS 단독 노출을 낮음 또는 미승격으로 둔다.
