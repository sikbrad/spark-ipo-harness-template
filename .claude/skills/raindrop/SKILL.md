---
name: raindrop
description: Raindrop.io 개인 계정 북마크(raindrop)·콜렉션·태그 raw JSON dump 및 증분 갱신 — REST API 직호출(`api.raindrop.io/rest/v1`), `.env` test token, SQLite 상태로 `lastUpdate` 기억. "raindrop 갱신", "북마크 백업", "raindrop dump", "raindrop sync", "Raindrop 콜렉션 받아줘", "내 북마크 export", "변경된 raindrop만 다시 받아" 등 raindrop.io 동기화 요청 시 사용.
---

# Raindrop.io 북마크 dump / sync

REST API 기반. 브라우저 불필요. `.env`의 personal test token으로 GET-only 호출 → raw JSON per object 저장 + SQLite로 `lastUpdate` 캐시 → 변경된 항목만 재스크랩.

## 도구 스택

- `proc/lib/raindrop_auth.py` — `.env` 로더, `whoami`
- `proc/lib/raindrop_api.py` — `RaindropClient` (throttle 0.51s/req, 429 백오프, 페이지네이션)
- `proc/lib/raindrop_state.py` — SQLite `raindrop_object` / `raindrop_run`
- `proc/lib/raindrop_dump.py` — CLI (`whoami` / `dump` / `status`)

## 전제

1. `.env`에 토큰:
   ```
   RAINDROP_TEST_TOKEN=...
   ```
   raindrop.io → Settings → Integrations → "For developers" → Create new app → Test token. 만료 없음, 본인 계정 전용.

2. (옵션) OAuth 모드는 reserved. `RAINDROP_CLIENT_ID` / `RAINDROP_CLIENT_SECRET` 있지만 현재 미사용.

3. Python `requests`만 있으면 동작 — 추가 의존성 없음.

## 안전 / Rate limit

- Raindrop 공식 한도: **120 req/min per user**. helper는 `MIN_INTERVAL_SEC = 0.51` 으로 sleep, 429 응답 시 `Retry-After` + 0.5s 대기 후 재시도. 500/502/503은 exponential backoff(최대 30s).
- 본인 데이터, GET-only, SPA가 부르는 동일 endpoint — ToS 안전.

## 증분 전략 (smart-resume)

`-1`(All bookmarks) 콜렉션을 `sort=-lastUpdate`로 페이지네이션:

1. 응답 항목의 `lastUpdate`와 `state.get_last_update("raindrop", id)` 비교
2. 같으면 `skipped++`, `consecutive_cached++`
3. 다르거나 신규면 `data/raindrop/dump/raindrops/<id>.json` 저장 + state upsert, `consecutive_cached = 0`
4. `consecutive_cached ≥ STOP_AFTER_CACHED_RUN`(=50, 1페이지) 시 페이지네이션 즉시 중단

정렬이 `-lastUpdate`라 새/수정된 항목은 무조건 상단 → 50연속 캐시 hit를 보면 나머지는 모두 동일하다고 결론. Notion dump 패턴 그대로.

## 출력 구조

```
data/raindrop/
├── state.sqlite                 # 증분 상태
└── dump/
    ├── _index.json              # 런 요약 {started, finished, counts, errors}
    ├── _tree.json               # {id: {type, parent, title, system, last_update, from_cache}}
    ├── collections/<id>.json    # 콜렉션 raw (real + system stub: 0=Unsorted, -1=All, -99=Trash)
    ├── raindrops/<id>.json      # 북마크 raw, 1파일/북마크
    └── tags.json                # /tags raw
```

각 raindrop JSON의 핵심 필드: `_id`, `lastUpdate`, `link`, `title`, `excerpt`, `note`, `tags[]`, `collection.$id`, `cover`, `domain`, `type`, `created`, `media[]`.

## 운영 패턴

**최초 풀 덤프 (콜드):**
```bash
python3 proc/lib/raindrop_dump.py dump
# 1274 raindrops / 26 pages / ~16s
```

**일/주 단위 증분 (권장):**
```bash
python3 proc/lib/raindrop_dump.py dump
# 변경 없으면 50개 cache-hit 후 stop → ~3s
```

**강제 전체 재수집:**
```bash
python3 proc/lib/raindrop_dump.py dump --force
```

**명시적 cutoff (특정 시점 이후만):**
```bash
python3 proc/lib/raindrop_dump.py dump --since 2026-01-01
```

**상태 / 마지막 런 확인:**
```bash
python3 proc/lib/raindrop_dump.py status
```

## CLI 옵션

| 옵션 | 기본값 | 설명 |
|---|---|---|
| `--out` | `data/raindrop/dump` | raw JSON 출력 디렉토리 |
| `--state` | `data/raindrop/state.sqlite` | SQLite 상태 파일 |
| `--force` | off | 캐시 무시, 전체 refetch |
| `--since` | none | ISO date / timestamp — lastUpdate < since 만나면 stop |
| `--stop-after` | 50 | 연속 cache-hit 임계값(=stop 트리거) |
| `--quiet` | off | 진행 로그 끄기 |

## SQL 빠른 분석

```bash
# 가장 최근 갱신 10개
sqlite3 data/raindrop/state.sqlite \
  "SELECT last_update, title FROM raindrop_object
   WHERE kind='raindrop' ORDER BY last_update DESC LIMIT 10"

# 콜렉션별 raindrop 수
sqlite3 data/raindrop/state.sqlite \
  "SELECT parent_id, COUNT(*) FROM raindrop_object
   WHERE kind='raindrop' GROUP BY parent_id ORDER BY 2 DESC"

# 런 히스토리
sqlite3 data/raindrop/state.sqlite \
  "SELECT started_at, finished_at, counts FROM raindrop_run
   ORDER BY rowid DESC LIMIT 5"
```

## Python에서 직접 호출 (skill 외부)

```python
import sys; sys.path.insert(0, 'proc/lib')
from raindrop_api import RaindropClient
from raindrop_state import State
from raindrop_dump import Dumper
from pathlib import Path

c = RaindropClient.from_env()
s = State()                            # data/raindrop/state.sqlite
d = Dumper(c, Path('data/raindrop/dump'), s)
summary = d.run()
print(summary['counts'])
```

또는 데이터만 읽기 (인덱스 캐시 활용):

```python
from raindrop_api import RaindropClient
c = RaindropClient.from_env()
# 최근 갱신 10개만 가볍게
recent = list(c.raindrops_iter(collection_id=-1, sort='-lastUpdate', perpage=10))[:10]
```

## 알려진 제약 / 한계

| 제약 | 영향 / 우회 |
|---|---|
| **삭제 감지 불가** | 사용자가 raindrop을 삭제하면 `-1`에서 사라지지만 페이지네이션이 일찍 끊겨 우리 state엔 잔존. 정확한 sync 필요 시 `--force`. |
| **System collection lastUpdate 없음** | 0/-1/-99는 stub으로 합성, `system: true` 마크. |
| **첨부/cover 다운로드 미포함** | raw JSON에 URL만. 필요 시 후속 작업으로 분리. |
| **Pro cache 미사용** | 현재 계정 `pro: false`. 영구 스냅샷은 raindrop Pro에서만. |
| **rate limit 120/min** | helper가 자동 sleep, 사실상 문제 없음. |

## 트러블슈팅

| 증상 | 원인 / 대처 |
|---|---|
| `RuntimeError: No Raindrop token found` | `.env`에 `RAINDROP_TEST_TOKEN` 없음. raindrop.io 앱 페이지에서 발급. |
| `whoami` 401 Unauthorized | 토큰 잘못 복사/만료(드묾). 앱 페이지에서 재발급. |
| 429 누적 | `--stop-after` 줄여서 페이지네이션 더 일찍 끊거나, 잠시 쉬었다가 재실행 (resume됨). |
| 같은 raindrop이 매번 fetched로 잡힘 | Raindrop 측에서 `lastUpdate`가 micro 단위로 바뀜. 정상 동작 — fetch도 idempotent하므로 무시 가능. |

## 참고 plan

`proc/plan/2026-05-11_raindrop-dump.md` — 설계·API 메모·검증 결과.
