# Outline 잠재고객 업체정보 보강 계획

대상 루트: `https://outline.doflab.com/doc/7jib7jef7lky7zue67o0-c0ae88mpyc`

## 목표
- 루트 하위 `잠재고객-*` 업체 문서에 공개 조사 기반 업체정보를 추가한다.
- 치과 관련 업역, 공개 출처, 공식 웹사이트/디렉터리/행사·언론성 노출 여부를 정리한다.
- 찾은 정보의 신뢰도를 문서에 명시한다.
- 조사 결과를 바로 Outline 업체 문서에 반영한다.

## 진행
- [x] 잠재고객 업체 문서 범위 확인.
- [x] 기존 공개 수집 데이터와 Outline 문서 캐시 매핑.
- [x] 출처 유형별 신뢰도/업역/노출 판단 로직 작성.
- [x] 사용자 정정 반영: 기존 수집 출처 요약만이 아니라 업체별 웹 검색을 실제 수행.
- [x] headless 브라우저 다중 페이지 실행으로 업체별 검색엔진 결과와 공식/자체 웹사이트 후보 조회.
- [x] 검색 완료 즉시 Outline 문서 갱신 후, 성공/실패 결과를 사후 JSONL에 기록하도록 순서 변경.
- [x] 기존 문서 내용을 덮어쓰지 않고, 영업처 카드/연락처/데이터 취득/영업 메모를 보존한 채 웹검색 보강 섹션을 적절한 위치에 병합.
- [x] 웹 검색 결과 기반으로 잠재고객 업체별 `공개 웹검색 보강` 섹션 생성.
- [x] 검색 완료 즉시 Outline 문서 갱신.
- [x] Outline-first 실행 결과를 병합해 사후 캐시에 역반영.
- [x] API readback 검증.

## 확인된 범위
- 잠재고객 업체 문서: 16,019개. (`company:portal:*` 제외, parent 국가 문서가 `잠재고객-*`인 업체 문서 기준)
- 초기 카테고리 분포 산출값은 13,728개였으나, headless 실행 selector 재검증 결과 전체 대상은 16,019개로 확정했다.

## 방법
- 공개 출처/근거: OSM, 공식 웹사이트 추출, Gelbe Seiten, VZLS, Meditrader, VDDI, LMTmag, HealthSpace Philippines, NBC, vhf, Myerson, Ivoclar, German Pavilion, Bredent, Italian Trade Agency, Henry Schein, Modern Dentistry Media 등 기존 수집 소스.
- 웹 검색: 업체명, 국가, dental/dental lab/distributor/orthodontic 등 키워드를 조합해 검색엔진 HTML 결과를 실제 조회한다.
- 실행 순서: 캐시 선반영 없이 headless 검색 → Outline `documents.info`/`documents.update` → 성공/실패 JSONL append.
- 병합 원칙: 문서 전체 overwrite가 아니라 기존 본문을 readback한 뒤 `영업 메모` 앞에 보강 섹션을 삽입한다. 이미 보강 섹션이 있는 문서는 중복 삽입하지 않고, 필요 시 기존 섹션 범위만 조정한다.
- 공식성/신뢰도: 공식 홈페이지, 협회·전시·제조사 locator, 정부/공공성 디렉터리, 업계 미디어/디렉터리, 지도/일반 디렉터리 순으로 가중.
- Facebook/LinkedIn은 로그인·약관 리스크가 큰 직접 대량 크롤링 없이, 기존 공개 수집 결과나 공개 검색 근거가 있을 때만 언급한다.

## 완료 결과
- Outline 반영: 잠재고객 업체 문서 16,019개 전체에 `공개 웹검색 보강 (2026-06-02)` 섹션 반영.
- 병합 방식: 기존 본문 전체 보존, `영업 메모` 앞에 보강 섹션 삽입. 이미 섹션이 있거나 readback에서 확인되는 문서는 중복 삽입하지 않음.
- 검증: Outline API `documents.info` readback 16,019개 확인, 섹션 누락 0건, API 요청 실패 0건.
- 사후 캐시: `output/dof-overseas-customer-prospects/2026-05-30/scale5000/outline_publish/prospect_headless_search_update/outline_first_search_updates.merged.jsonl`에 16,019개 병합.
- 신뢰도 분포: 높음 6,037건, 중간 11건, 낮음 9,971건.
- 공식/자체 웹사이트 본문 확인: 6,037건.
