# 포털 고객사 좌표 OSM 연동

## 목표
포털 로컬 DB의 고객사 주소를 OSM Nominatim으로 지오코딩해 고객사에 EPSG:3857 좌표를 저장하고, 고객사 상세 페이지에서 OSM 지도를 표시한다.

## 작업 항목
- [x] 포털 고객사 스키마, API 계약, 상세 페이지의 현재 주소/상세 렌더링 구조 확인
- [x] OSM/Nominatim 호출 정책 확인 후 저속/캐시형 백필 방식 설계
- [x] 고객사 DB/API 타입에 EPSG:3857 lon/lat 필드 추가
- [x] 고객사 주소 10건만 Nominatim으로 지오코딩해 로컬 DB에 반영
- [x] 고객사 상세 페이지에 OSM 지도 표시 추가
- [x] 브라우저에서 10건 중 좌표 저장 및 지도 표출 검증
- [x] 검증 후 전체 백필/운영 방식 정리
- [x] PostGIS 설치/이미지 전환 및 `geometry(Point,3857)` 저장 스키마 적용
- [x] 주소가 있는 전체 고객사 좌표 백필 실행
- [x] 상세페이지 지도를 deck.gl 기반으로 교체
- [x] 사이드바 지도 섹션과 고객사지도 화면 추가
- [x] 전체 백필 결과와 지도 화면 브라우저 검증
- [x] Playwright로 고객사지도 렌더링/인터랙션 재검증
- [x] 고객사지도 기본 검색 UX 보강
- [x] 검색/지도 상호작용 브라우저 검증
- [x] 고객사지도 기본 시작 위치를 서울 중심/적정 줌으로 조정
- [x] 주소 매칭 실패 고객사는 도시/지역 중심 근사 좌표를 저장하고 정밀도 필드로 구분
- [x] 도시명 검색 시 거래처가 없어도 해당 도시로 지도 이동
- [x] 고객사지도 목록 스크롤 영역이 화면 높이를 채우도록 수정
- [x] DB 마이그레이션/백필 후 정확 좌표와 근사 좌표 건수 검증
- [x] Playwright로 서울 시작 위치, 도시 검색 이동, 좌표없음 태그, 스크롤 높이 검증

## 진행 메모
- Nominatim public API는 공식 정책상 앱 식별 User-Agent/Referer가 필요하고, 무거운 사용은 최대 1 req/sec 이하로 제한된다. 큰 정기/장시간 배치는 더 보수적으로 캐시와 단일 스레드를 써야 한다.
- OSM tile은 지도 위 visible attribution과 브라우저 기본 캐시/Referer 정책을 지켜야 한다. 최종 구현은 iframe이 아니라 deck.gl TileLayer/BitmapLayer 기반 OSM raster tile로 통일했다.
- 로컬 DB에는 좌표가 있는 고객사 10건을 확보했다. 저장값은 EPSG:3857 X/Y(`lon`, `lat`)이고, 상세 화면에서만 WGS84로 되돌려 OSM embed에 넘긴다.
- 백필 스크립트는 `bun --env-file=../../.env scripts/backfill-company-coordinates.ts --limit N --delay-ms 1500` 형태다. `--target-updates`를 붙이면 not-found를 넘겨 목표 성공 건수까지 뒤쪽 후보를 계속 본다.
- 브라우저 검증: `http://localhost:54221/companies/1`에서 `company-location-map`이 렌더링됐고 OSM embed/tile 요청이 200으로 내려왔다.
- 검증 메모: API 계약/백엔드 직접 빌드는 통과, Vite 번들 빌드도 통과. 프론트 전체 `tsc -b && vite build`는 기존 `TODO` 엔티티 매핑 누락으로 실패한다.
- 확장 작업: 상세/전체 고객사지도 모두 deck.gl로 통일한다. OSM 배경 타일은 deck.gl TileLayer/BitmapLayer로 표시하고, attribution은 UI에 명시한다.
- 사용자 정정으로 PostGIS를 사용한다. 내부 원본 저장은 `Company.location geometry(Point,3857)`로 두고, UI/API는 필요한 경우 `ST_X(location)`, `ST_Y(location)`에서 EPSG:3857 X/Y 값을 내려준다. 기존 `lon`/`lat` 숫자 컬럼은 호환 캐시/이행용으로만 취급한다.
- Docker DB 이미지는 `dof-postgres-postgis-pgvector:pg17`로 전환했다. 기존 데이터 볼륨을 유지했고 `postgis 3.6.3`, `vector 0.8.0` 확장이 활성화됐다. `lon`/`lat`은 이제 일반 컬럼이 아니라 `ST_X(location)`, `ST_Y(location)` 생성 컬럼이다.
- `CompanyLocationMap`은 iframe을 제거하고 deck.gl 기반 OSM raster tile + marker 레이어를 사용한다. `/company-map` 고객사지도 화면과 사이드바 `지도 > 고객사지도` 진입점을 추가했다.
- 빌드 검증: `packages/api-contract build`, `apps/server build`, `apps/front build`, `bunx vite build` 통과.
- 전체 백필 완료: 주소가 있는 고객사 1,858건 중 `location` 저장 1,356건, Nominatim 미발견 502건. 결과 리포트는 `output/company-geocode/company-geocode-2026-05-30T18-20-33-780Z.json`.
- DB 검증: `Company.location`은 `geometry(Point,3857)`, `lon`/`lat`은 `ST_X(location)`, `ST_Y(location)` 생성 컬럼이며 좌표 보유 1,356건 모두 SRID 3857이다.
- 브라우저 검증: `http://localhost:54221/company-map`에서 `전체 3,291개 / 좌표 1,356개 / 미좌표 502개`, deck.gl canvas 1개, iframe 0개, OSM tile 2xx 응답 26건을 확인했다. `http://localhost:54221/companies/1` 상세 화면도 `company-location-map` + deck.gl canvas 1개, iframe 0개로 확인했다.
- 검증 스크린샷: `output/company-geocode/company-map-browser-verify.png`, `output/company-geocode/company-detail-map-browser-verify.png`.
- 추가 요청: Playwright로 고객사지도 렌더링/상호작용을 다시 검증하고, 검색 기본 UX를 보강한다.
- 검색 보강 완료: 검색어 입력 시 전체/좌표/미좌표 수와 별도로 검색 결과 수를 보여주고, 지도 표시 수와 목록 수를 분리한다. 좌표가 없는 검색 결과도 목록에 남기고 `좌표 없음` 배지를 표시한다. 검색어 초기화 버튼과 결과 없음 상태를 추가했다.
- Playwright 최종 검증: `/company-map`에서 초기 `지도 1,356 / 목록 3,291개`, `덴티움` 검색 `지도 3 / 목록 5개`, `GT-MEDICAL` 검색 `지도 0 / 목록 1개` + `좌표 없음`, 무결과 검색 `지도 0 / 목록 0개`, 초기화 후 원복, 지도 wheel/drag 후 canvas 유지, `레피오` 목록 클릭 후 `/companies/62` 이동을 확인했다.
- 최종 검증 스크린샷: `output/company-geocode/company-map-search-interaction-verify.png`.
- 추가 요청: 지도 기본 시작 위치는 서울로 두고, 주소가 상세하지 않아 정확 주소 좌표가 없는 고객사는 도시/지역 중심 근사 좌표를 저장한다. 프론트의 `좌표 없음` 배지는 유지하되, 저장 좌표의 정밀도는 `locationAccuracy`로 `ADDRESS`/`CITY`를 구분한다.
- 구현 반영: `Company.locationAccuracy` 컬럼을 추가했다. 기존 좌표 보유 행은 `ADDRESS`로 마킹하고, 백필 스크립트는 주소 본문의 국가/도시 힌트를 우선해 정확 주소 매칭은 `ADDRESS`, 도시/지역 중심 fallback은 `CITY`로 저장한다.
- 최종 백필 결과: 주소가 있는 고객사 1,858건 중 `ADDRESS` 1,361건, `CITY` 432건, 좌표 없음 65건. 좌표 저장 행 1,793건은 모두 SRID 3857이다. 최신 리포트는 `output/company-geocode/company-geocode-2026-05-31T00-15-26-167Z.json`.
- 프론트 반영: 고객사지도 기본 뷰포트는 서울 `126.978/37.5665`, zoom `10.5`다. 도시명 검색은 고객사가 없어도 도시 중심으로 이동하며, `capetown`은 `18.4241/-33.9249`, zoom `10.0`으로 이동한다.
- `좌표 없음` 배지는 좌표 필드 null 여부가 아니라 `locationAccuracy !== 'ADDRESS'` 기준으로 유지한다. 따라서 `CITY` 근사 좌표는 지도에 찍히지만 목록/상세에서 계속 `좌표 없음`으로 표시된다.
- 스크롤 버그 수정: 고객사지도 우측 목록은 `max-h-[560px]` 고정에서 화면 높이를 채우는 flex 스크롤로 바꿨다. 2048x1200 Playwright 검증에서 목록 스크롤 영역 `1057px`, aside/map `1102px`로 확인했다.
- 빌드 검증: `bun run --cwd packages/api-contract build`, `bun run --cwd apps/server build`, `bun run --cwd apps/front build` 통과. 프론트 빌드는 기존 큰 chunk/dynamic import 경고만 남았다.
- Playwright 검증: `/company-map` 초기 `좌표 1,361개 / 미좌표 497개 / 지도 1,793 / 목록 3,291개`, deck.gl canvas 1개, iframe 0개, 서울 중심/zoom 10.5 확인. `capetown` 검색은 결과 0개여도 Cape Town으로 이동했고, `GT-MEDICAL`은 CITY 좌표가 지도에 표시되면서 `좌표 없음` 배지를 유지했다. 상세 `/companies/29`도 deck.gl 지도와 `좌표 없음` 배지를 확인했다.
- 새벽 2시 automation `portal-company-coordinate-backfill`의 prompt를 `locationAccuracy=ADDRESS/CITY`, 도시 fallback, 새 집계 항목 기준으로 업데이트했다.
