# 기술지원 OneNote 고객응대 지식 엔티티화

## 목표
`data/techsupport/onenote/mdfiles`의 OneNote Markdown을 고객응대/기술지원 지식 엔티티로 정리해 `data/techsupport/onenote/entities`에 저장한다. 회사 전산자원관리규칙, 사내 행정/운영 규칙, 계정/비밀번호성 문서는 포함하지 않는다.

## 작업 항목
- [x] 고객응대 포함/사내규칙 제외 기준을 코드로 고정
- [x] Markdown 913개를 파싱해 구조화 엔티티와 제외 목록 생성
- [x] 제품/영역/유형별 인덱스와 요약 리포트 생성
- [x] 누락/오분류 가능성이 높은 샘플을 검증
- [x] 기술지원 이력 검색용 정적 HTML 뷰어 생성
- [x] 브라우저 기준 검색/상세/제외 탭 동작 검증
- [x] 상세 화면을 고객응대 카드/이미지/원본 탭 구조로 재정리
- [x] 이미지·첨부 로컬 경로를 뷰어 데이터에 포함
- [x] Playwright MCP로 검색/이미지/원본 iframe/제외 탭 회귀 검증
- [x] OneNote 덤프 스크립트에 SQLite 기반 증분 동기화 추가
- [x] 기존 raw/md 결과를 초기 state DB로 bootstrap해서 불필요한 재다운로드 방지
- [x] 증분 동기화 로직 문법/스모크 검증
- [x] OneNote 이미지 누락 원인 수정 및 뷰어 기본 화면 이미지 노출
- [x] 원본 OneNote HTML 기반 로컬 raw 렌더 생성
- [x] 검색 뷰어의 `원본 보기`를 raw 렌더로 연결
- [x] 913개 페이지 이미지/원본 렌더 전수검사 및 결과 JSON 저장
- [x] Playwright MCP로 대표 페이지 화면 검수

## 결과 메모
- 2026-05-31 KST: `scripts/build_techsupport_onenote_entities.py`로 `data/techsupport/onenote/entities`를 생성했다.
- source Markdown 913개 중 고객응대/기술지원 엔티티 881개를 포함했고, 사내 행정/전산자원/계정성 문서 등 32개를 제외했다.
- 포함 결과는 `entities.jsonl`, `entities.json`, `records/<product_area>/*.md`, `indexes/by_product_area.json`, `indexes/by_support_type.json`, `summary.json`으로 저장했다.
- 제외 결과는 `excluded.jsonl`, `excluded.json`에 제외 사유와 함께 저장했다.
- 금지 성격 키워드(`다오우오피스`, `자산관리`, `일일보고`, `쏘카`, `지출품의`, `통장사본`, `AJ파크`, `ID/PASS`, `ID_PASS`, `비밀번호` 등)가 포함 엔티티에 남지 않았음을 `rg`로 확인했다.
- 2026-05-31 KST: `data/techsupport/onenote/entities/viewer/index.html` 정적 뷰어를 생성했다. 제품/영역, 유형, 태그 필터와 본문 검색, 상세 원문/링크, 제외 문서 검색 탭을 제공한다.
- Puppeteer로 `file://` 렌더링을 검증했다. 초기 881건, `NC 파일` 검색 40건, 제외 탭 `자산관리` 검색 1건, 상세 링크(Markdown/검토 HTML/Raw/OneNote) 노출을 확인했고 스크린샷을 `data/techsupport/onenote/entities/viewer/screenshots/`에 저장했다.
- 2026-05-31 KST: 사용자 검토 피드백에 따라 Playwright MCP 검수를 시작했다. MCP는 `file://` 접근이 차단되어 로컬 HTTP 서버(`127.0.0.1:8765`)로 검수한다.
- 상세 화면을 `응대 정리`, `이미지`, `원본 보기`, `원문 텍스트` 탭으로 재구성했다. `응대 정리`에는 상황 요약, 먼저 확인, 조치 순서, 고객 안내 포인트, 주의/에스컬레이션을 자동 추출해 보여준다.
- `scripts/build_techsupport_entities_viewer.py`에서 이미지 2,032개와 첨부 390개의 로컬 href를 생성하도록 보강했고, 경로 누락 0건을 확인했다.
- Playwright MCP 검증 결과: 초기 881건 중 120건 표시, `임프레션 스캔 데이터 반전` 검색 1건, 이미지 탭 4/4 로드, 원본 iframe 4/4 이미지 로드, 제외 탭 `자산관리` 1건, 콘솔 error/warning 0건. 결과는 `data/techsupport/onenote/entities/viewer/screenshots/playwright-mcp-verify-result.json`에 기록했다.
- 2026-05-31 KST: OneNote 재스크랩 비용을 줄이기 위해 page `lastModifiedDateTime` 기반 SQLite 증분 동기화를 추가한다. 수정일이 같고 raw content/resources/md가 모두 있으면 content/resource 다운로드를 건너뛴다.
- `scripts/dump_techsupport_onenote.py`에 `data/techsupport/onenote/state/onenote_sync.sqlite` 상태 DB를 추가했다. 테이블은 `pages`, `sync_runs`이며 page id, title, section, `lastModifiedDateTime`, raw/md 경로, content status, hash, resource count, last seen/downloaded/error를 저장한다.
- 기본 실행은 최신 페이지 메타데이터를 Graph에서 조회한 뒤 SQLite와 비교한다. `--force-pages`는 전체 재다운로드, `--no-incremental`은 skip 로직 비활성화, `--use-cached-pages-index`는 오프라인/디버그용 cached index 사용이다.
- 실제 실행 검증: `python3 scripts/dump_techsupport_onenote.py --sleep 0` 결과 913 pages, 909 skipped unchanged, 909 bootstrapped unchanged, 0 downloaded, 4 page_errors, 0 resource_errors. SQLite 상태는 `ok=909`, `error=4`, `deleted=0`으로 확인했다.
- 2026-05-31 KST: 이미지가 안 보이던 원인은 두 가지였다. 첫째, OneNote 일부 이미지의 `data-fullres-src-type`이 `application/octet-stream`이라 EMF `.bin`을 우선 저장했고 브라우저가 표시하지 못했다. 둘째, 원본 HTML에서 `ul/ol` 바로 아래에 붙은 이미지가 Markdown 변환 중 누락됐다.
- `scripts/dump_techsupport_onenote.py`를 수정해 브라우저 표시 가능한 `src` PNG를 우선 사용하고, 리스트 직계 이미지도 Markdown에 포함하도록 했다. `--resume --rebuild-md --use-cached-pages-index`로 기존 raw content에서 재생성했으며 리소스가 2,525개에서 2,551개로 늘었다.
- 뷰어 `응대 정리` 탭에서 이미지가 요약보다 먼저 나오게 바꿨고, 요약은 원문 개행을 보존하도록 했다. `PC 최적화 - 스캔/캐드가 느릴 때(완료)!` 문서는 이미지 6개 모두 `.png`로 잡히며 file URL 및 Playwright MCP에서 6/6 로드됨을 확인했다.
- 2026-06-01 KST: OneNote 원본 HTML의 배치/스타일을 보존하고 Graph 이미지 URL만 로컬 resource로 바꾸는 `data/techsupport/onenote/raw_review/` 렌더를 추가했다. 검색 뷰어 `원본 보기` 탭은 이 raw 렌더를 우선 사용한다.
- 913개 raw 렌더 전수 브라우저 검사 결과는 `data/techsupport/onenote/qa/full_render_audit.json`에 저장했다. 결과: 913/913 통과, 브라우저 image node 2,000개 로드, broken/pending 0개, 첨부 링크 398개, 검색 뷰어 엔티티 880개 모두 raw 렌더 링크 보유.
- 단, 원본/Graph 한계가 있다. OneNote content endpoint 오류 페이지 4개는 원문 HTML이 없고, 원본 HTML 자체에 이미지 URL이 없는 자리 12개와 Graph가 계속 빈 이미지 본문을 반환하는 자리 147개는 실제 이미지를 복구하지 못했다. 해당 자리는 깨진 이미지 대신 명시적 플레이스홀더로 표시한다.
- Playwright MCP 대표 검수: `PC 최적화 - 스캔/캐드가 느릴 때(완료)!` 검색 결과 3건, 상세 이미지 6/6 로드, raw iframe 이미지 6/6 로드, broken 0. `X Axis, Z Axis Sensor Replacement Guide`는 표시 가능한 이미지 8/8 로드, Graph 빈 이미지 2개는 플레이스홀더로 표시, 콘솔 warning/error 0.
