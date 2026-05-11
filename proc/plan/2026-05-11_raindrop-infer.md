# raindrop-infer: 북마크 링크별 컨텐츠 분석·요약·재방문 인사이트 생성

## 목표
`data/raindrop/dump/raindrops/*.json`의 각 북마크 링크를 실제로 들어가 컨텐츠를 가져온 뒤, `data/raindrop/infer/<id>.md`에 **요약 + 핵심 인사이트 + 언제 다시 보면 좋을지** 정보를 마크다운으로 생성. 증분: raindrop `lastUpdate`나 fetch 실패가 있으면 재처리.

## 데이터 분포 (1274건)

| 그룹 | 건수 | 처리 전략 |
|---|---|---|
| YouTube (regular + Shorts) | 762 | `yt-dlp` 자막 → 없으면 audio→whisper → LLM 요약 |
| Threads | 102 | `/threads` 세션 + DOM 본문 추출 |
| Instagram | 73 | playwright `-s=instagram` (로그인 wall) — 1st pass는 OG metadata만, 점진 확장 |
| LinkedIn | 70 | `-s=linkedin` 세션 (로그인 wall) — 본문 DOM |
| news.hada.io | 53 | playwright headless (open web) |
| GitHub | 35 | README 직접 fetch (raw.githubusercontent / API) |
| share.google | 32 | redirect resolve → 재분류 |
| Naver blog / news / etc. | ~50 | playwright headless + readability |
| 기타 (130 domains) | ~100 | generic playwright headless + LLM |
| 이미지 | 71 | OG meta + URL 만 (vision 분석은 v2) |

## 컴포넌트 / 파일

```
proc/lib/
├── raindrop_infer.py         # main driver: queue, dispatch, write md, state
├── infer_state.py            # SQLite: raindrop_infer 테이블 (status, fetched_at, content_hash, error, retry)
├── fetchers/
│   ├── __init__.py
│   ├── youtube.py            # yt-dlp + whisper fallback
│   ├── threads.py            # pwc S('threads') wrapper
│   ├── instagram.py          # pwc S('instagram')
│   ├── linkedin.py           # pwc S('linkedin')
│   ├── github.py             # readme fetch
│   ├── share_google.py       # redirect resolver
│   └── generic.py            # playwright headless + readability
└── llm.py                    # OpenAI API wrapper (.env OPENAI_API_KEY) — chat completion + prompt template
```

## 도메인 → fetcher 라우팅

| host 패턴 | fetcher |
|---|---|
| `youtube.com`, `youtu.be` | youtube |
| `threads.com`, `threads.net` | threads |
| `instagram.com` | instagram |
| `linkedin.com` | linkedin |
| `github.com`, `gist.github.com`, `raw.githubusercontent.com` | github |
| `share.google` | share_google → 재분류 |
| 그 외 | generic |

## 출력 md 스키마

```markdown
---
id: 1234567890
link: https://...
title: ...
type: video|link|article|image
domain: youtube.com
raindrop_tags: [tag1, tag2]
raindrop_created: 2025-09-29T15:09:41.195Z
raindrop_last_update: 2026-02-07T05:40:03.087Z
inferred_at: 2026-05-11T...
fetcher: youtube
status: ok|partial|failed
revisit_after_days: 30           # LLM 추정 (관련성 반감기)
revisit_trigger: "관련 주제 작업 시" | "절대 다시 볼 필요 없음" | "구체 조건..."
---

# {title}

## 요약 (TL;DR)
3-5줄

## 핵심 인사이트
- 인사이트 1
- 인사이트 2
- 인사이트 3

## 상세 메모
컨텐츠에서 발췌·정리한 본문 (≤ 1500자)

## 재방문 가이드
- **언제 다시?**: ...
- **다시 안 봐도 되는 이유**: ...
- **관련 개념/도구**: ...
```

## LLM 프롬프트

`OPENAI_API_KEY` 사용. 모델 우선순위: `gpt-4o-mini` (비용/성능 균형). 입력: title + excerpt + fetched content. 출력: 위 스키마의 본문 부분 일관성 위해 JSON으로 받음 → md 렌더.

## 증분/재시도 정책

| 상태 | 의미 | 다음 행동 |
|---|---|---|
| ok | md 파일 있고 raindrop.lastUpdate == state.last_update | skip |
| stale | raindrop.lastUpdate 변경 | refetch |
| failed (retry < 3) | 일시 오류 (네트워크/429) | 재시도 (다음 run에서) |
| failed (retry ≥ 3) | 영구 오류 (404/login wall) | skip + partial md (메타만) |
| auth-required | 로그인 wall이 발견되었지만 세션 없음 | partial md + sentinel |

SQLite `raindrop_infer`:
```sql
CREATE TABLE raindrop_infer (
    id            TEXT PRIMARY KEY,    -- raindrop _id
    link          TEXT,
    domain        TEXT,
    fetcher       TEXT,
    status        TEXT,                -- ok|stale|failed|auth-required
    raindrop_lu   TEXT,                -- raindrop.lastUpdate at time of fetch
    fetched_at    TEXT,
    content_hash  TEXT,                -- sha256 of fetched content
    error         TEXT,
    retry_count   INTEGER DEFAULT 0
);
```

## CLI

```bash
python3 proc/lib/raindrop_infer.py run                     # 처리 가능한 것 모두
python3 proc/lib/raindrop_infer.py run --domain youtube.com
python3 proc/lib/raindrop_infer.py run --id 1362373671
python3 proc/lib/raindrop_infer.py run --limit 10          # 스모크
python3 proc/lib/raindrop_infer.py run --force             # 캐시 무시
python3 proc/lib/raindrop_infer.py status                  # SQLite 통계
```

## 작업 항목

### 0단계 — 인프라
- [ ] `proc/lib/llm.py` — OpenAI 클라이언트 + JSON-mode 프롬프트 wrapper (`requests` 또는 `openai` SDK, throttle/backoff)
- [ ] `proc/lib/infer_state.py` — SQLite `raindrop_infer` 테이블
- [ ] `proc/lib/raindrop_infer.py` 스켈레톤 — 큐, 라우팅, md 렌더, CLI

### 1단계 — fetcher 구현
- [ ] `fetchers/generic.py` — playwright-cli headless + DOM 텍스트 추출 (article body heuristic). **모든 fetcher의 fallback.**
- [ ] `fetchers/youtube.py` — yt-dlp으로 자막(`--write-auto-sub --skip-download --sub-format vtt`) 시도 → 없으면 audio + whisper. 길이 캡(쇼츠는 1분, 일반 영상은 20분 상한).
- [ ] `fetchers/github.py` — `repo/blob/branch` URL에서 owner/repo 추출 → `https://api.github.com/repos/{o}/{r}/readme` (Accept: raw) + repo description/topics
- [ ] `fetchers/share_google.py` — HEAD/GET으로 final URL 추출 → 라우터 재호출
- [ ] `fetchers/threads.py` — `pwc.S('threads')`로 post URL 열어 본문 DOM 추출 (기존 `/threads` 세션 활용 — 단 그 스킬은 발행 전용이라 read helper만 추가)
- [ ] `fetchers/instagram.py` — `pwc.S('instagram')` — 미부트스트랩 시 OG meta만 + auth-required 마크
- [ ] `fetchers/linkedin.py` — `pwc.S('linkedin')` — 미부트스트랩 시 OG meta만 + auth-required 마크

### 2단계 — LLM 요약 통합
- [ ] 프롬프트 템플릿: system role + (title, excerpt, tags, raw_text) → JSON 출력 (summary, insights[], detail, revisit_after_days, revisit_trigger)
- [ ] 토큰 제한: 입력 컨텐츠를 ~12k tokens로 truncate (gpt-4o-mini context 128k이지만 비용 절약)
- [ ] md 렌더링 (위 스키마)

### 3단계 — 드라이버 + CLI
- [ ] domain 라우팅 dispatcher
- [ ] 증분 로직 (raindrop.lastUpdate ↔ state.raindrop_lu)
- [ ] 재시도 로직 (retry_count, 지수 backoff between runs)
- [ ] CLI 옵션 (`--domain`, `--id`, `--limit`, `--force`, `--quiet`)
- [ ] `status` 명령 — 상태별 카운트, fetcher별 카운트, 최근 에러

### 4단계 — 검증 / 점진 확장
- [ ] **스모크**: `--limit 10` 으로 youtube/github/generic 각각 1-2건 처리하고 md 검사
- [ ] 50건 배치 → 실패율·소요시간 측정
- [ ] 전체 1274건 — youtube가 대다수이므로 yt-dlp throttle 주의
- [ ] auth wall (Instagram/LinkedIn) — partial md만 생성하고 부트스트랩은 사용자 결정 후 후속 PR
- [ ] skill 등록 `/raindrop-infer` (혹은 `/raindrop infer` 서브명령)

### 5단계 — 옵션
- [ ] 이미지 type — OG meta만 (v1), 추후 vision 분석 (v2)
- [ ] 태그 자동 보완 (LLM이 raindrop_tags 외 추천 태그 제안 → raindrop API로 PUT)
- [ ] 인사이트 인덱스 (`data/raindrop/infer/_index.md` — 전체 요약 모음 + 필터 가이드)

## 알려진 제약

- **로그인 wall (IG/LinkedIn)**: 세션 부트스트랩이 사용자 개입 필요. 1차에선 OG meta만 + `auth-required` 마크.
- **YouTube rate limit**: yt-dlp의 자막 fetch도 IP-based throttling 가능. 동시성 1~2로 시작.
- **OpenAI 비용**: 1274 * 평균 토큰. 처음 50건 배치 후 비용 보고 옵션 조정.
- **Whisper 속도**: 로컬 whisper.cpp 사용 시 영상 길이의 0.3x 정도. 쇼츠 위주 + 길이 캡.
- **Threads 세션**: 기존 `/threads` 스킬은 발행만 — read 헬퍼 분리해 추가.

## Risks / 미정

- 동시성: 도메인별 별도 throttle? 단일 worker로 시작.
- 콘텐츠 hash 비교로 LLM 재호출 최소화 (raindrop.lastUpdate만 바뀌고 컨텐츠 동일하면 skip).
- "재방문 시점" 정확도는 도메인 카테고리(뉴스 vs 평생용 ref vs 트렌드) 별 다름 — LLM 프롬프트에 카테고리 힌트 포함.

---

## 진행 상황 (2026-05-11)

### 인프라 완료
- [x] `proc/lib/llm.py` — OpenAI 클라이언트 + JSON-mode prompt
- [x] `proc/lib/infer_state.py` — SQLite `raindrop_infer` 테이블
- [x] `proc/lib/fetchers/` 패키지 — generic / youtube / github / share_google / auth_wall
- [x] `proc/lib/raindrop_infer.py` — main 드라이버 (OpenAI 사용)
- [x] `proc/lib/raindrop_infer_fetch.py` — manual mode helper (fetch JSON only, no LLM)
- [x] `.claude/skills/raindrop-infer/SKILL.md` — `/raindrop-infer` 스킬 등록

### YouTube 자막 추출
- [x] `yt-dlp --cookies-from-browser edge` → IP 429 + cookie 의존 부담 → **폐기**
- [x] `youtube-transcript-api` Python 패키지로 전환 → no auth, 안정

### 처리 진행률 (1274 / 50 처리됨 = 3.9%)
| 그룹 | 총 | 처리 | 상태 |
|---|---|---|---|
| github.com | 35 | **35** | 수동 작성 완료 (28 ok + 7 partial w/ rate limit) |
| youtube.com (스모크) | 762 | 7 | OpenAI API 스모크 — 자막 + 메타 OK |
| news.hada.io / 기타 generic (스모크) | ~50 | 7 | OpenAI API 스모크 OK |
| linkedin.com (스모크) | 70 | 1 | auth-wall, partial |
| **나머지** | ~1224 | 0 | 미처리 |

### 수동 모드 페이스 측정
- github 35건 + 5건 인프라 디버그 = ~1.5시간 세션
- 평균 5min/item (텍스트 큰 README는 더 오래)
- **1274건 수동은 35+ 세션 분량 = 비현실적**

### 권장 다음 단계 (사용자 결정)

**A. OpenAI gpt-4o-mini 대량 처리 (Recommended)**
   - 1239 남은 항목 × ~$0.001 ≈ $1.5
   - 3시간 batch run
   - `python3 proc/lib/raindrop_infer.py run`
   - 품질: GPT-4o-mini는 일반 요약 OK. 메타 추론(중복 감지·"sunsetting" 같은 사실 발견)은 사람 수준 못 미침.

**B. 우선순위 큐레이션 후 수동**
   - 사용자가 "다시 볼 가능성 높은" 카테고리만 추림 (예: github 외 추가 50건)
   - 100건 ≈ 2-3 세션

**C. 하이브리드**
   - github(완료) + news.hada.io 53건 + 기타 100건 ≈ 153건 수동
   - 나머지 1100건 = OpenAI batch
   - github partial 7건은 GitHub TOKEN 추가 후 자동 refetch

### Partial 항목 (rate limit) — 1시간 후 refetch 권장
- 1638227200, 1649750993, 1650424959, 1654357955, 1656597732, 1656783514, 1707421325, 1712117059
- 명령: `python3 proc/lib/raindrop_infer_fetch.py fetch --id <id>` 각각

### 검색 가능한 인사이트 (현재 50 md 상에서)
```bash
# 카테고리 분포
grep -h "^category" data/raindrop/infer/*.md | sort | uniq -c | sort -rn

# 도메인 분포
grep -h "^domain" data/raindrop/infer/*.md | sort | uniq -c | sort -rn

# 다시 볼 필요 없음 (revisit 0)
grep -l "^revisit_after_days: 0$" data/raindrop/infer/*.md | wc -l

# "sunsetting"/"중복" 등 사람 인사이트만 추출
grep -l "sunsetting\|중복" data/raindrop/infer/*.md
```
