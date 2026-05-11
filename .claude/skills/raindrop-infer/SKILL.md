---
name: raindrop-infer
description: Raindrop.io dump의 각 북마크 링크를 실제로 들어가 컨텐츠를 가져오고 OpenAI로 요약·인사이트·재방문 가이드를 생성해 `data/raindrop/infer/<id>.md`에 저장. YouTube는 자막(transcript), GitHub은 README, 일반 웹은 requests+HTML→text. SQLite로 raindrop `lastUpdate` 비교 → 변경분만 재처리. "raindrop 분석", "북마크 요약", "내 raindrop 인사이트", "북마크 다시 봐야 하는 것만 추려줘", "raindrop 정리해줘" 등의 요청 시 사용. `/raindrop`(원본 dump)과 다른 점은 본 스킬은 **컨텐츠 분석**까지 한다.
---

# raindrop-infer: 북마크 컨텐츠 분석·요약·재방문 가이드

`/raindrop` 스킬로 받은 `data/raindrop/dump/raindrops/*.json`을 입력 삼아,
각 링크를 실제 fetch → 본문 추출 → OpenAI LLM이 한국어 요약·핵심 인사이트·
재방문 가이드(언제 다시 보면 좋을지)를 만들어 `data/raindrop/infer/<id>.md`로 저장.

## 사전 준비

1. **북마크 dump 먼저**: `python3 proc/lib/raindrop_dump.py dump`
   (또는 `/raindrop` 스킬)
2. `.env`에 `OPENAI_API_KEY=...` (기본 모델 `gpt-4o-mini`)
3. 패키지: `python3 -m pip install youtube-transcript-api requests`
   (`yt-dlp`, `ffmpeg`은 시스템 설치 필요. 메타데이터에만 사용.)

## 도구 스택

- `proc/lib/llm.py` — OpenAI Chat Completions (JSON 모드), throttle/backoff
- `proc/lib/infer_state.py` — SQLite `raindrop_infer` (status·raindrop_lu·content_hash·error·retry_count)
- `proc/lib/fetchers/` 패키지 — 도메인별 컨텐츠 추출
- `proc/lib/raindrop_infer.py` — 드라이버 CLI

## 도메인 → fetcher 라우팅

| 패턴 | fetcher | 출력 |
|---|---|---|
| `youtube.com`, `youtu.be` | youtube | `youtube-transcript-api`로 한국어/영어 transcript + `yt-dlp --print`로 메타 |
| `github.com/o/r` | github | GitHub REST `/repos/{o}/{r}` + `/readme` (raw) |
| `share.google` | share_google | redirect 해소 후 generic 재호출 |
| `threads.com`, `instagram.com`, `linkedin.com` | auth_wall | OG meta만 (raindrop excerpt/tags가 보충 신호). `status=partial` |
| 그 외 (`news.hada.io`, naver, 일반 블로그 등) | generic | `requests` + `<script>` 제거 + HTML→text |

## 출력 md 스키마

```markdown
---
id: "1551038347"
link: "https://youtube.com/watch?v=..."
title: "..."
type: "video"
domain: "youtube.com"
fetcher: "youtube"
status: "ok" | "partial" | "failed"
raindrop_tags: ["...", ...]
raindrop_created: "2026-..."
raindrop_last_update: "2026-..."
inferred_at: "2026-..."
revisit_after_days: 0 | 7 | 30 | 90 | 180 | 365
revisit_trigger: "..."
category: "news|reference|tutorial|tool|opinion|entertainment|tech-trend|product|other"
freshness: "evergreen|short|medium|long"
---

# {title}
<{link}>

## 요약
TL;DR 3-5문장

## 핵심 인사이트
- ...

## 상세 메모
(컨텐츠에서 추출된 1000자 이내)

## 재방문 가이드
- **다시 안 봐도 됨** — {trigger}                      ← revisit_after_days=0
- 또는 **다시 볼 시점**: {N}일 후, **트리거**: {조건}    ← revisit_after_days>0
- **카테고리**: ...
- **유통기한**: ...
```

## 증분 / 재시도

| 상태 | 조건 | 행동 |
|---|---|---|
| skip | DB `raindrop_lu == raindrop.lastUpdate` AND md 존재 AND status=ok | 패스 |
| 처리 | 위 조건 불만족 OR `--force` | fetch → LLM → md write |
| failed | fetcher exception OR HTTP 4xx (text 없음) | DB에 `failed` 기록 + retry_count++ |
| llm-failed | OpenAI 호출 실패 | 동일 |

## CLI

```bash
# 인프라 부트스트랩 (1회)
python3 -m pip install youtube-transcript-api

# 스모크 (10건만)
python3 proc/lib/raindrop_infer.py run --limit 10

# 특정 도메인만
python3 proc/lib/raindrop_infer.py run --domain youtube.com

# 단일 raindrop id
python3 proc/lib/raindrop_infer.py run --id 1551038347

# 전체 (incremental — 변경/신규만)
python3 proc/lib/raindrop_infer.py run

# 캐시 무시
python3 proc/lib/raindrop_infer.py run --force

# 상태
python3 proc/lib/raindrop_infer.py status
```

## 운영 메모

- **소요/비용**: 평균 ~8s/item (fetch 5-7s + LLM 1-2s). 1274건 ≈ 3시간, OpenAI ~$1 미만.
- **YouTube 인증**: 처음엔 `yt-dlp --cookies-from-browser`로 자막을 받았지만 IP 429에 취약 +
  사용자 브라우저 의존도 부담. 현재는 `youtube-transcript-api`(no auth) 사용.
- **auth-wall 사이트**: IG/LinkedIn/Threads는 OG meta + raindrop excerpt만으로 LLM 요약.
  세션 부트스트랩 후 fetcher 교체로 본문 확보 가능 — 후속 작업.
- **Shorts**: 1분 미만 영상도 자막 있으면 동일하게 처리. 자막 없으면 `status=partial`.

## SQL 빠른 분석

```bash
# 카테고리 분포
grep -h "^category" data/raindrop/infer/*.md | sort | uniq -c | sort -rn

# 다시 안 봐도 되는 raindrop 수
grep -l "^revisit_after_days: 0$" data/raindrop/infer/*.md | wc -l

# 실패한 raindrop
sqlite3 data/raindrop/infer_state.sqlite \
  "SELECT id, domain, error FROM raindrop_infer WHERE status='failed' LIMIT 20"

# fetcher별 status 매트릭스
sqlite3 data/raindrop/infer_state.sqlite \
  "SELECT fetcher, status, COUNT(*) FROM raindrop_infer GROUP BY 1,2"
```

## 알려진 한계

- **삭제 감지 안 함**: raindrop이 삭제되면 md 파일은 잔존. 정리 필요 시 별도 청소.
- **이미지 type**: OG meta + raindrop fields만. Vision 분석은 후속.
- **`auth_wall.py`는 fallback**: 실제 본문이 필요하면 pwc 세션 부트스트랩 후
  fetcher 교체 (`fetchers/threads.py`, `fetchers/instagram.py` 등으로 확장).

## 참고
- 설계: `proc/plan/2026-05-11_raindrop-infer.md`
- dump 스킬: `/raindrop` (전제 조건)
