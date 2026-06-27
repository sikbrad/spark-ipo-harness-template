---
name: notion-dump
description: Notion 워크스페이스의 특정 root 페이지(들) 하위 **전체 트리**(자식 페이지·블록·DB·data source·DB 행)를 Notion REST API(`api.notion.com/v1`, `Notion-Version: 2025-09-03`)로 받아 raw JSON으로 dump + 인라인 asset 다운로드. SQLite state로 `last_edited_time` 캐시 → 변경분만 재수집. "노션 받아줘", "노션 dump", "노션 백업", "Quick My Ocean 받아", "Notion 트리 export", "노션 전체 다운로드", "노션 페이지 sync", "노션 데이터 받아오는" 등 노션 트리 수집 요청 시 사용. **할일·태스크 등록은 `/notion-task` (별 스킬)**.
---

# Notion 트리 전체 dump / sync

REST API 기반. 브라우저 불필요. OAuth public integration 토큰으로 GET-only 호출 → page/block/database/data_source/db_row를 raw JSON per object 로 저장 + 인라인 asset(cover/icon/file/image/video/audio/pdf) 다운로드 + SQLite로 `last_edited_time` 캐시 → 변경된 항목만 재수집.

## 도구 스택

- `proc/lib/notion_auth.py` — `.env` 로더, OAuth code-exchange CLI, 토큰 캐시
- `proc/lib/notion_api.py` — `NotionClient` (Notion-Version `2025-09-03`, throttle, 429/5xx 백오프, 페이지네이션 iter)
- `proc/lib/notion_state.py` — SQLite `notion_object` / `notion_child` / `notion_asset` / `notion_run`
- `proc/lib/notion_assets.py` — `AssetDownloader` (Notion-hosted signed URL 인라인 받기, 1h 만료 회피)
- `proc/lib/notion_dump.py` — CLI (`login` / `dump` / `status`) + `Dumper` BFS walker
- `proc/lib/notion_hydrate.py` — (선택) raw → blocks 재귀 머지 1파일/페이지
- `proc/lib/notion_render_md.py` — (선택) hydrated → 트리 구조 .md

설계·API·v2 마이그레이션 메모: [proc/plan/2026-05-08_notion-tree-dump.md](../../../proc/plan/2026-05-08_notion-tree-dump.md)

## 전제 (인증)

OAuth public integration. `.env`에 다음 키 필요:
```
NOTION_OAUTH_CLIENT_ID=<UUID>
NOTION_OAUTH_CLIENT_PW=secret_...
NOTION_OAUTH_AUTH_URL=https://api.notion.com/v1/oauth/authorize?...redirect_uri=https://not-integ123
```

최초 1회:
```bash
python proc/lib/notion_dump.py login
```
→ 사용자가 브라우저에서 AUTH_URL 열고 dump하려는 root 페이지(또는 그 부모 워크스페이스)를 **명시적으로 공유**해야 함. 공유하지 않은 페이지는 `403 object_not_found` 으로 `_index.json:errors` 에 기록.

→ Notion이 `https://not-integ123/?code=XXX&state=...` 로 redirect (DNS 실패하지만 URL bar의 `code` 복사) → CLI에 붙여넣음 → 토큰을 `~/.cache/dof-notion/token.json` 캐시. **만료 없음**, refresh 불필요.

대안: `.env`에 직접 `NOTION_INTEG_ACCESS_TOKEN_*` 넣어도 됨 (`/notion-task` 와 토큰 공유).

## 안전 / Rate limit

- Notion 공식: 평균 3 req/s. helper는 보수적으로 `time.sleep(0.34)` per request, 429 시 `Retry-After`+exponential backoff.
- 본인이 공유한 페이지에 대한 GET-only — ToS 안전.
- Asset 다운은 별도 ThreadPool(`max_workers=8`), API 호출은 main 스레드 → rate limit 보존.

## 증분 전략

루트에서 BFS. 각 node 별:

1. `GET /pages/{id}` 또는 `GET /databases/{id}` 또는 `GET /data_sources/{id}` 호출 → 응답의 `last_edited_time` 추출
2. `state.get_let(kind, id)` 비교
3. 같으면 → `*_skipped++`, 캐시된 `notion_child` 그래프 따라 자식만 enqueue (재fetch X)
4. 다르거나 신규면 → JSON 저장 + 자식 전부 다시 walk + assets enqueue + state upsert

따라서 한번 풀 dump 후엔 변경된 page/db만 fetch — 큰 워크스페이스도 분 단위.

## v2 (Notion-Version 2025-09-03) 데이터 모델

`database` = 컨테이너, 안에 1개 이상 `data_source` (실제 표). 기존 `2022-06-28`의 `databases/{id}/query`는 default data_source만 자동 연결. 신규 모델은:

```
database (container, no schema)
   └── data_source[] (schema + rows)
          └── page[] (each row)
```

`db.data_sources` 가 빈 배열이면 통합이 그 DB(또는 안의 data source)에 명시적으로 연결되지 않은 상태 → `errors` 에 `database_no_data_sources` 기록 → Notion UI에서 추가 공유 필요.

## 출력 구조

```
data/notion/
├── dump/
│   ├── _index.json              # 런 요약 {roots, started, finished, counts, errors}
│   ├── _tree.json               # {id: {type, parent, title, children[], last_edited_time, from_cache}}
│   ├── pages/<uuid>.json        # GET /pages/{id} raw
│   ├── blocks/<uuid>.json       # {block_id, results: [...all children blocks recursively scanned...]}
│   ├── databases/<uuid>.json    # GET /databases/{id} raw (container meta)
│   ├── data_sources/<uuid>.json # GET /data_sources/{id} raw (schema)
│   └── db_rows/<uuid>.json      # {data_source_id, results: [...all rows...]}
├── assets/                      # 인라인 다운로드된 cover/icon/file/image 등
│   ├── _index.json              # 자산 매니페스트
│   └── <hash>.<ext>
└── logs/                        # tee 로그 (수동 생성 권장)
```

UUID는 dashed 32+4 형식. 파일명은 hex만.

## 운영 패턴

**최초 풀 dump (콜드, 큰 워크스페이스 1~4시간):**
```bash
mkdir -p data/notion/logs
python proc/lib/notion_dump.py dump \
  --root e0a658bf0f8d4e6384c6903940c7e7a9 \
  --root bd198b22ef9f44618c2382ce45bbf7b0 \
  --out data/notion/dump 2>&1 | tee data/notion/logs/dump_$(date +%Y%m%d_%H%M%S).log
```

**증분 갱신 (권장, 변경분만):**
```bash
python proc/lib/notion_dump.py dump \
  --root e0a658bf0f8d4e6384c6903940c7e7a9 \
  --root bd198b22ef9f44618c2382ce45bbf7b0 \
  --out data/notion/dump
# 대부분 CACHE 라인 → 분 단위 종료
```

**강제 전체 재수집 (state 무시):**
```bash
python proc/lib/notion_dump.py dump --root <id> --force
```

**상태 / 통계 확인:**
```bash
python proc/lib/notion_dump.py status
# → {"objects_by_kind": {"page": N, "database": N, "data_source": N}, "run_count": N}
```

**Asset 다운 비활성:**
```bash
python proc/lib/notion_dump.py dump --root <id> --assets ""
```

## CLI 옵션

| 옵션 | 기본값 | 설명 |
|---|---|---|
| `--root <id>` | (필수, 반복 가능) | dump 시작 root page 또는 database id (dashed/hex 모두 OK) |
| `--out` | `data/notion/dump` | raw JSON 출력 디렉토리 |
| `--state` | `data/db/notion_state.sqlite` | SQLite state 경로 (`notion_state.DEFAULT_STATE_PATH`) |
| `--assets` | `data/notion/assets` | 인라인 asset 다운로드 디렉토리. 빈 문자열(`""`)이면 비활성 |
| `--asset-workers` | `8` | concurrent asset download 스레드 수 |
| `--force` | off | state 캐시 무시, 모든 노드 refetch |
| `--quiet` | off | per-node 로그 억제 |

## 알려진 root ID

| 이름 | UUID (dashed) | 비고 |
|---|---|---|
| Quick My Ocean | `e0a658bf-0f8d-4e63-84c6-903940c7e7a9` | 메인 워크스페이스 root |
| Databases | `bd198b22-ef9f-4461-8c23-82ce45bbf7b0` | 다수 DB 부모 페이지 |

다른 페이지를 추가하려면 Notion URL 끝의 32-hex를 그대로 `--root` 인자로 넘기면 됨 — `notion_api.normalize_id` 가 dashed 변환.

## 옵션 후처리 (B/C 단계)

raw dump 위에서 점진적 가공 가능 (필수 아님):

```bash
# B: hydrate — page + 모든 blocks 재귀 머지 → data/notion/hydrated/<id>.json
python proc/lib/notion_hydrate.py

# C: render — hydrated → 트리 구조 .md (frontmatter + Notion block→MD 매핑)
python proc/lib/notion_render_md.py
```

세부 매핑·내부 링크 rewrite 규칙은 [plan 문서](../../../proc/plan/2026-05-08_notion-tree-dump.md)의 "Update 2026-05-08: Derived stages" 섹션 참고.

## SQL 빠른 분석

```bash
# kind별 객체 수
sqlite3 data/db/notion_state.sqlite \
  "SELECT kind, COUNT(*) FROM notion_object GROUP BY kind"

# 가장 최근 갱신 page 10개
sqlite3 data/db/notion_state.sqlite \
  "SELECT last_edited_time, title FROM notion_object
   WHERE kind='page' ORDER BY last_edited_time DESC LIMIT 10"

# 런 히스토리
sqlite3 data/db/notion_state.sqlite \
  "SELECT started_at, finished_at, counts FROM notion_run
   ORDER BY rowid DESC LIMIT 5"

# data_source 가 0개라 행을 못 받은 DB 목록
sqlite3 data/db/notion_state.sqlite \
  "SELECT o.id, o.title FROM notion_object o
   WHERE o.kind='database'
     AND NOT EXISTS (SELECT 1 FROM notion_child c
                     WHERE c.parent_kind='database' AND c.parent_id=o.id)"
```

## Python에서 직접 호출

```python
import sys; sys.path.insert(0, "proc/lib")
from pathlib import Path
from notion_api import NotionClient
from notion_state import State, DEFAULT_STATE_PATH
from notion_dump import Dumper

c = NotionClient.from_cache()
s = State(DEFAULT_STATE_PATH)
d = Dumper(
    c,
    out_dir=Path("data/notion/dump"),
    state=s,
    assets_dir=Path("data/notion/assets"),
)
index = d.run([
    "e0a658bf0f8d4e6384c6903940c7e7a9",  # Quick My Ocean
])
print(index["counts"])
s.close()
```

## 알려진 제약 / 한계

| 제약 | 영향 / 우회 |
|---|---|
| **삭제 감지 불가** | Notion에서 페이지를 삭제해도 state·dump엔 잔존. 정확 동기화 필요 시 `--force` 후 dump 디렉토리도 비우고 재실행. |
| **archived page** | API가 응답하면 그대로 저장됨. UI에서 휴지통 비우면 404 → `errors` 에 기록. |
| **Notion-hosted asset URL 만료(1h)** | `Dumper`가 URL 발견 즉시 ThreadPool로 다운 → state에 commit. 4h+ dump 도중 kill 후 재시작도 idempotent. |
| **`data_sources: []` DB** | 통합이 그 안의 data source에 명시 공유 안 됨 → 행 못 받음. Notion UI에서 추가 공유. |
| **wiki / 다중 source DB** | v2 (`2025-09-03`) API로 자동 처리. 마이그레이션은 `Dumper._maybe_migrate_state_v2` 가 1회 실행. |
| **Notion mention 내부 링크** | raw에 ID로만 저장. md 렌더 단계(C)에서 path rewrite. |
| **rate limit 3 req/s** | helper가 자동 sleep, 사실상 문제 없음. |

## 트러블슈팅

| 증상 | 원인 / 대처 |
|---|---|
| `RuntimeError: no notion token in cache or .env` | 첫 인증 안 됨 → `python proc/lib/notion_auth.py login` |
| 대량 `403 object_not_found` | 통합이 해당 페이지에 공유되지 않음. Notion UI → 페이지 우상단 ⋯ → "연결 추가" → 통합 선택 |
| `database_no_data_sources` 다수 | wiki/2022 마이그레이션 DB에 통합이 page-level 만 공유됨. 각 DB → "연결 추가" 다시 |
| 런 도중 kill → 재실행 시 처음부터 도는 듯 보임 | 정상. CACHE 라인이 빠르게 흘러가며 변경분만 FETCH |
| `_index.json:errors` 에 `assets_403` 다수 | URL 만료 — asset만 별도 재시도(현재는 다음 dump 런이 다시 발급) |
| Quick My Ocean root는 보이는데 자식 일부만 누락 | 그 자식 페이지·DB에 통합 공유 필요. 부모 공유는 자동 propagation 안 됨 |

## 운영 메모

- 처음 풀 dump는 **백그라운드** 권장 (수 시간 가능). `run_in_background=true` + tee 로그.
- 증분은 빠름 (보통 1~10분). 정기적(주 단위)으로 돌리면 `_index.json:counts` 변화로 워크스페이스 활동 감지 가능.
- `_tree.json` 의 `from_cache: true/false` 로 이번 런에서 바뀐 노드 식별.
- 토큰을 `/notion-task` 와 공유하므로 둘 중 한 곳에서 login 하면 양쪽 다 동작.
