# Notion 페이지 트리 raw JSON 덤프

## 목표
지정된 노션 root 페이지(들) 하위의 모든 자식 페이지·블록·데이터베이스·DB 행을 Notion REST API(`https://api.notion.com/v1/`)로 받아 JSON으로 저장.

대상 root:
- Quick My Ocean: `e0a658bf-0f8d-4e63-84c6-903940c7e7a9`
- Databases: `bd198b22-ef9f-4461-8c23-82ce45bbf7b0`

## 인증 (OAuth public integration — `.env` 그대로 활용)

`.env`:
- `NOTION_OAUTH_CLIENT_ID` (UUID)
- `NOTION_OAUTH_CLIENT_PW` (`secret_…` client secret)
- `NOTION_OAUTH_AUTH_URL` (authorize URL, `redirect_uri=https://not-integ123`)

플로우:
1. `python proc/lib/notion_auth.py login` 실행 → 사용자가 브라우저에서 AUTH_URL 열고 공유할 페이지 선택(반드시 Quick My Ocean 트리 포함).
2. Notion이 `https://not-integ123/?code=XXX&state=...` 로 redirect — DNS 실패하지만 URL bar의 `code` 복사.
3. 스크립트가 `code` 입력 받아 `POST https://api.notion.com/v1/oauth/token` (Basic auth: client_id:client_secret, body: `grant_type=authorization_code`, `code`, `redirect_uri=https://not-integ123`) → `access_token` 획득.
4. 토큰을 `~/.cache/dof-notion/token.json` 에 캐시 (Notion v1 토큰은 만료 없음, refresh 불필요).

## 데이터 모델 / 트래버설

루트에서 시작해 BFS로 노드 수집. 각 노드 타입별 작업:

| 노드 타입 | API 호출 | 자식 확장 |
|-----------|----------|-----------|
| Page | `GET /pages/{id}` (메타) + `GET /blocks/{id}/children` (본문 블록, 페이지네이션) | 본문 블록 중 `child_page` / `child_database` / `has_children=true` |
| Database | `GET /databases/{id}` (스키마) + `POST /databases/{id}/query` (행, 페이지네이션) | 각 행은 page 객체 → 다시 Page로 처리 |
| Block (`has_children=true`, 비페이지 toggle/column 등) | `GET /blocks/{id}/children` | 동일 |
| Block (`child_page`) | 부모의 children 응답에서 발견 → Page로 처리 |
| Block (`child_database`) | `GET /databases/{id}` + 쿼리 | Database로 처리 |

### 사이클·중복 방지
- `visited: set[str]` (UUID dash-normalized) — pages, databases 모두 같은 set 사용.
- synced_block(원본/복제), 멀티-부모 행은 첫 출현만 처리.

### 페이지네이션
- 모든 list/query: `start_cursor` + `has_more`. 100개 page_size.

### 레이트 리밋
- Notion API 평균 3 req/s. 보수적으로 `time.sleep(0.34)` per request, 429 시 exponential backoff.

## 출력 레이아웃

```
output/notion-dump-2026-05-08/
├── _index.json                # {root_ids, started_at, finished_at, counts, errors[]}
├── _tree.json                 # {id: {type, parent, title, children[]}} (가벼운 트리 인덱스)
├── pages/<uuid>.json          # GET /pages/{id} raw
├── blocks/<uuid>.json         # {block_id, results: [모든 자식 블록 합본]}
├── databases/<uuid>.json      # GET /databases/{id} raw (스키마)
└── db_rows/<uuid>.json        # {database_id, results: [query 모든 row page 객체 합본]}
```

UUID는 dashed 32+4 형식. 파일명은 슬래시 없는 안전한 hex만.

## 구현 파일

| 파일 | 역할 |
|------|------|
| `proc/lib/notion_auth.py` | `.env` 로드, OAuth login CLI, 토큰 캐시 r/w |
| `proc/lib/notion_api.py` | `requests.Session` 래퍼, 페이지네이션 헬퍼 (`pages_retrieve`, `blocks_children`, `db_retrieve`, `db_query`) |
| `proc/lib/notion_dump.py` | 트래버설 + 파일 저장 + CLI (`login` / `dump --root <id>...`) |

의존성: `requests`(이미 설치) — `python-dotenv`는 굳이 안 쓰고 자체 `.env` 파서.

## 실행 단계

1. 코드 3 파일 작성.
2. `python proc/lib/notion_dump.py login` — 사용자가 OAuth 한 번 처리(AUTH_URL 공유 단계에서 "Quick My Ocean" 또는 더 위의 워크스페이스 루트를 선택해야 트리 전체 접근 가능).
3. `python proc/lib/notion_dump.py dump --root e0a658bf0f8d4e6384c6903940c7e7a9 --out output/notion-dump-2026-05-08`
4. `_index.json` 의 counts·errors 확인. 누락된 child_database 있으면 그 ID로 재실행해 보충.

## 알려진 제약

- 파일 attachment 첨부(이미지, 첨부파일)는 Notion-hosted URL이 만료(1시간). 이번 덤프 스코프는 **메타+본문 텍스트** raw JSON. 첨부 바이너리는 옵션으로 후속.
- OAuth `internal` 통합으로 access_token 자체 만료는 없으나, 사용자가 통합을 끊으면 무효.
- Linked database 블록(`link_to_page`, `unsupported`) 은 raw 그대로 저장 — 별도 fetch 불필요.

## Risks / 미정

- Quick My Ocean의 워크스페이스 권한 — OAuth install 화면에서 사용자가 "Quick My Ocean" 페이지(또는 그 부모)를 명시적으로 공유해야 함. 못 보면 `403 object_not_found` 반환 → `_index.json:errors` 로 기록.
- Databases 사이의 relation 컬럼은 ID만 raw 로 저장; 링크된 DB 자체가 트리 밖이면 별도 root 로 추가해야 할 수도 있음 (사용자 확인 후 결정).

---

## Update 2026-05-08: API v2 (`2025-09-03`) 마이그레이션

Notion이 2025년에 데이터 모델을 바꿈. `database` = "컨테이너", 안에 1개 이상의 `data_source` (실제 표). 기존 `2022-06-28`의 `/v1/databases/{id}/query`는 단일 default data_source 를 자동 연결해 주는데, 통합 권한이 data_source 레벨까지 안 propagate 된 케이스(특히 wiki / 다중 소스 / 마이그레이션된 DB)에서 400. 신규 `2025-09-03` API + `/v1/data_sources/{id}` + `/v1/data_sources/{id}/query` 로 전환.

변경 요약:
- `NOTION_VERSION = "2025-09-03"`
- `NotionClient`: `databases_query_iter` 제거 → `data_sources_retrieve` + `data_sources_query_iter` 추가.
- `Dumper._dump_database`: 메타만 저장 후 `data_sources[]` 를 child로 enqueue.
- `Dumper._dump_data_source` 신설: 스키마 → `data_sources/<ds_id>.json`, 행 → `db_rows/<ds_id>.json` (이전엔 `<db_id>.json` 키였음).
- State schema: `notion_object.kind` 에 `'data_source'` 종류 추가.
- 자동 마이그레이션: 기존 state 에 `database` 행만 있고 `data_source` 행이 없으면 `last_edited_time`을 NULL로 만들어 강제 refetch (`Dumper._maybe_migrate_state_v2`).

`data_sources: []` 로 빈 응답이 오는 DB는 metadata는 받히되 행은 못 받음 — 통합을 그 DB(또는 그 안의 data source)에 명시적으로 연결해야 함. `_index.json:errors` 에 `database_no_data_sources` 로 기록.

---

## Update 2026-05-08: Derived stages (B/C/X) — Notion → 사람 읽는 문서

raw dump가 lossless source of truth. 그 위에서 3개 derive stage로 점진적 가공.

### 스테이지

| 단계 | 스크립트 | 입력 | 출력 |
|------|----------|------|------|
| A | `notion_dump.py` | Notion API | `output/notion-dump/` (raw) **+ inline asset download** → `output/notion-assets/` |
| B | `notion_hydrate.py` | A의 `pages/` + `blocks/` | `output/notion-hydrated/<id>.json` (page + 모든 blocks 재귀 머지) |
| C | `notion_render_md.py` | B의 hydrated | `output/notion-md/<path>/<title>.md` (frontmatter + MD) |
| X (옵션) | `notion_assets.py` | 기존 dump 디렉토리 | standalone 재시도/스캐너 — 정상 흐름은 A에 통합 |

### 의존성

```
A (raw dump + inline asset download)
   └─→ B (hydrate)  ──→ C (render md)
```

### URL 만료 (해결됨 — 인라인 다운로드)

Notion-hosted signed URL은 발급 후 ~1시간 만료. 분리 단계로 두면 4h+ dump 후 후반부 단계 시작 시점엔 초반 URL 이미 expire (실제 4h dump 결과: 3248 중 2136개 403). **A에 인라인 다운로드 통합**:

- Dumper 안에 `concurrent.futures.ThreadPoolExecutor(max_workers=8)` 보유
- `_dump_page` 에서 page.cover/icon 발견 시 → `executor.submit(download_one, ...)`
- `_scan_block` 에서 image/file/video/audio/pdf 발견 시 → 동일하게 submit
- API 호출은 main 스레드 (rate limit 보존), 다운로드는 worker 스레드 → main walk 가속 안 잃음
- 발급~다운까지 latency = 수 초. 1h 만료 안에 충분
- `run()` 종료 시 `executor.shutdown(wait=True)` 로 drain
- 상태는 SQLite `notion_asset` 테이블에 즉시 commit → kill/재실행 시에도 idempotent

### Hydrated JSON 스키마

```json
{
  "id": "<uuid>",
  "object": "page",
  "url": "https://www.notion.so/...",
  "last_edited_time": "...",
  "parent": {...},
  "properties": {...},        // raw page properties
  "blocks": [                 // 모든 자식 블록을 재귀로 inline
    {
      "id": "...",
      "type": "paragraph",
      "paragraph": {...},
      "children": [...]       // has_children=true 인 경우 재귀
    },
    ...
  ],
  "_meta": {
    "title": "Quick My Ocean",
    "depth": 0,
    "child_pages": ["<uuid>", ...],
    "child_databases": ["<uuid>", ...]
  }
}
```

### Markdown 출력 규칙

- Frontmatter: `id, last_edited_time, notion_url, parent_id, title`.
- 트리 폴더링: 부모 페이지 = 폴더, 페이지 본문 = 같은 이름의 `.md`. e.g. `Quick-My-Ocean.md` + `Quick-My-Ocean/Databases.md`.
- 파일명 sanitize: `[/\\:*?"<>|]` → `-`, length cap 100.
- Block 타입 매핑 (rich_text → MD inline): paragraph, heading_1~3, bulleted_list_item, numbered_list_item, to_do, toggle (`<details>`), quote, callout, code (fenced), divider (`---`), child_page (relative link), child_database (relative link), image/file/bookmark/embed (MD media), table+table_row (MD table), column_list/synced_block (flatten).
- 모르는 타입: `<!-- unsupported: type=X -->` 주석 + raw JSON 보존.
- 내부 링크: `notion.so/<32hex>` 또는 mention page → 트리 안의 상대 경로로 rewrite (id→path 매핑 만든 뒤 2-pass).
