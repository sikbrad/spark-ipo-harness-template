# Raindrop.io 북마크 raw JSON 덤프

## 목표
개인 Raindrop.io 계정의 모든 raindrop(북마크) + collection + tag을 raw JSON으로 받아 `data/raindrop/dump/`에 저장. Notion 덤프 패턴 그대로 — SQLite 상태로 `lastUpdate` 기억하고, 이후 edit된 대상만 재스크랩.

## 인증
`.env`:
- `RAINDROP_TEST_TOKEN` — raindrop.io → Settings → Integrations → For developers → Create new app → Test token (개인 계정용, 만료 없음)
- `RAINDROP_CLIENT_ID` / `RAINDROP_CLIENT_SECRET` — OAuth용 reserved, 현재 미사용

토큰 해석 순서 (`proc/lib/raindrop_auth.py:access_token`):
1. 환경변수 `RAINDROP_TOKEN`
2. `.env` `RAINDROP_TEST_TOKEN`
3. `.env` `RAINDROP_TOKEN`

## API 메모
- Base: `https://api.raindrop.io/rest/v1`, `Authorization: Bearer <token>`
- Rate limit: 120 req/min → `MIN_INTERVAL_SEC = 0.51`, 429 시 `Retry-After`
- 핵심 엔드포인트:
  - `GET /user`
  - `GET /collections` (root), `GET /collections/childrens` (nested) — 페이지네이션 없음
  - `GET /raindrops/{cid}?page=N&perpage=50&sort=-lastUpdate` — 최대 perpage=50
    - `cid`: 0=Unsorted, **-1=All bookmarks**, -99=Trash, 그 외=특정 collection
  - `GET /tags` — 전체 태그 목록

각 raindrop 객체는 `_id`, `lastUpdate`, `link`, `title`, `excerpt`, `note`, `tags[]`, `collection.$id`, `cover`, `domain`, `type`, `created`, `media[]` 등을 raw로 가짐. `list` 응답이 이미 full 객체이므로 `GET /raindrop/{id}`를 따로 부를 필요 없음.

## 출력 레이아웃
```
data/raindrop/
├── state.sqlite                 # 증분 상태 (lastUpdate per object)
└── dump/
    ├── _index.json              # 런 요약 {started, finished, counts, errors}
    ├── _tree.json               # {id: {type, parent, title, system, last_update, from_cache}}
    ├── collections/<id>.json    # 콜렉션 raw (real + system stub: 0, -1, -99)
    ├── raindrops/<id>.json      # 북마크 raw (1파일/북마크)
    └── tags.json                # /tags raw
```

## 증분 전략 — Smart resume

`-1`(All) 콜렉션을 `sort=-lastUpdate`로 페이지네이션. 각 항목에서:
1. `state.get_last_update("raindrop", id)`와 응답의 `lastUpdate` 비교
2. 동일 → `skipped++`, `consecutive_cached++`
3. 다르거나 새 항목 → 파일 저장 + state upsert, `consecutive_cached = 0`
4. `consecutive_cached ≥ STOP_AFTER_CACHED_RUN`(=50, 1페이지) 시 페이지네이션 중단

근거: 정렬이 `-lastUpdate`라서 새/수정된 항목은 반드시 상단에 위치. 50연속(=1페이지) cache-hit를 만나면 나머지는 모두 캐시와 동일하다고 결론.

옵션:
- `--force` — state 무시하고 전체 refetch
- `--since YYYY-MM-DD` — 명시적 cutoff (lastUpdate < since에서 stop)
- `--stop-after N` — consecutive cache-hit 임계값 조정

## 알려진 제약 / 한계

1. **삭제 감지 불가**: 사용자가 raindrop을 삭제하면 `-1`에서 사라지지만 페이지네이션이 빨리 끊겨 우리 state에는 잔존. 정확한 삭제 동기화가 필요하면 `--force` 또는 별도 `--reconcile`(미구현) 필요.
2. **System collection lastUpdate 없음**: 0/-1/-99는 stub으로 합성. `system: true` 마크.
3. **첨부/cover 다운로드 제외**: 사용자 결정에 따라 raw JSON만. 필요 시 `notion_assets.py` 패턴으로 추가 가능.
4. **Pro 전용 cache(영구 스냅샷)는 미사용** — 현재 계정 `pro: false`.

## 구현 파일

| 파일 | 역할 |
|------|------|
| `proc/lib/raindrop_auth.py` | `.env` 로드, 토큰 해석, `whoami` CLI |
| `proc/lib/raindrop_api.py` | `RaindropClient` — throttle/backoff, collections/raindrops/tags 헬퍼 |
| `proc/lib/raindrop_state.py` | SQLite `raindrop_object`/`raindrop_run` 테이블 |
| `proc/lib/raindrop_dump.py` | `Dumper` + CLI (`whoami` / `dump` / `status`) |

의존성: `requests`만.

## 실행

```bash
# 1회 확인
python3 proc/lib/raindrop_dump.py whoami

# 풀 덤프 (콜드 실행)
python3 proc/lib/raindrop_dump.py dump

# 증분 (이후)
python3 proc/lib/raindrop_dump.py dump

# 강제 전체 재수집
python3 proc/lib/raindrop_dump.py dump --force

# 명시적 cutoff
python3 proc/lib/raindrop_dump.py dump --since 2026-01-01

# 상태 확인
python3 proc/lib/raindrop_dump.py status
```

## 검증 결과 (2026-05-11)

| 런 | counts | 소요 |
|-----|--------|------|
| Cold | collections_fetched=6/skipped=3, raindrops_fetched=**1274**/skipped=0, pages=26, errors=0 | 15.8s |
| Warm | collections_fetched=3/skipped=6, raindrops_fetched=0/skipped=**50**, pages=1, errors=0 | 2.9s |

증분 동작 — 페이지 0에서 50연속 cache-hit 후 stop 확인.
