---
name: raindrop-retag
description: Raindrop.io 북마크의 태그를 LLM이 컨텐츠를 직접 읽고 정확히 3개로 재부여 + "언제 다시 보면 좋을지" AI 메모를 note에 append. 키워드 매칭이 아니라 `/raindrop-infer`로 이미 생성된 본문 분석(`data/raindrop/infer/<id>.md`)을 LLM이 한 건씩 읽고 판단. 기존 user note 보존, `--- ai memo ----` 마커로 idempotent. "raindrop 태그 정리해줘", "북마크 태그 줄여줘", "raindrop 재태깅", "AI가 직접 읽고 태그 달아", "raindrop에 AI 메모 달아", "북마크 언제 볼지 메모", "ai memo 부여" 등의 요청 시 사용.
---

# raindrop-retag: LLM이 직접 읽고 태그 3개 + AI 메모 부여

`/raindrop` 으로 받은 dump + `/raindrop-infer` 가 생성한 `data/raindrop/infer/<id>.md`
를 입력 삼아, **각 북마크 1건씩 LLM이 본문 요약을 읽고**
- 가장 적합한 태그 **정확히 3개**
- "언제 다시 보면 좋을지" 80자 이내 한국어 메모

를 만들어 raindrop.io API에 직접 push.

키워드 룰 기반 매칭이 아니라 **infer_md 통째로 LLM에 넘기고 판단**시키는
컨텐츠 기반 접근.

## 사전 준비

1. `/raindrop` 로 dump: `python3 proc/lib/raindrop_dump.py dump`
2. `/raindrop-infer` 로 본문 요약: `python3 proc/lib/raindrop_infer.py run`
3. `.env`:
   - `RAINDROP_TEST_TOKEN=...` (raindrop.io Settings → Integrations → For developers → Test token)
   - `OPENAI_API_KEY=...`

## 도구

- `proc/lib/raindrop_retag.py` — 드라이버 (CLI)
- `proc/lib/raindrop_api.py` — `RaindropClient.request("PUT", "/raindrop/{id}", ...)` 사용
- `proc/lib/llm.py` — OpenAI Chat Completions, JSON mode

## note 포맷

```
{유저가 기존에 적어둔 note 그대로}

--- ai memo ----
{LLM이 만든 한 줄 메모 — '언제 다시 보면 좋을지'}
----------------
```

- 유저 note가 비어 있으면 위 블록만.
- **유저 note는 어떤 경우에도 수정하지 않음.** AI 메모만 그 아래 append.
- `--- ai memo ----` 마커가 이미 있으면 skip (idempotent). `--force` 로 덮어쓰기.

## 태그 규칙 (system prompt에 박아둠)

- 정확히 3개. 중복 / 의미 겹침 금지 (`AI`+`인공지능` X).
- `data/raindrop/dump/tags.json` 상위 80개 vocab을 LLM에게 grounding으로 제공
  → 사용자가 이미 쓰는 어휘로 수렴.
- 그래도 안 맞으면 새 태그 1-2개 만들 수 있음.
- `기술/비즈니스` 같은 슬래시 묶음은 금지.
- `current_tags` 는 참고만, 그대로 복사 금지.

## CLI

```bash
# 진행 상황
python3 proc/lib/raindrop_retag.py status

# 단건 — 먼저 dry-run으로 결과 확인
python3 proc/lib/raindrop_retag.py run --id 1112329686 --dry-run --force

# 단건 — 실제 push
python3 proc/lib/raindrop_retag.py run --id 1112329686

# 스모크 5건
python3 proc/lib/raindrop_retag.py run --limit 5

# 전체 (마커 없는 것만 — incremental)
python3 proc/lib/raindrop_retag.py run

# 마커 있어도 다시 (덮어쓰기)
python3 proc/lib/raindrop_retag.py run --force
```

## 동작 흐름 (per raindrop)

1. `data/raindrop/dump/raindrops/<id>.json` 로드 → 현재 tags / note / title
2. `--- ai memo ----` 마커가 note에 있으면 skip (`--force` 미사용 시)
3. `data/raindrop/infer/<id>.md` 로드 (없으면 `no-infer` 로 skip)
4. LLM에 `{raindrop meta, infer_md 본문, top_tags 80개}` 전달 → JSON `{tags, memo}` 받기
5. dedupe + 길이 검증 (정확히 3개)
6. note 합성: `{기존 note}\n\n--- ai memo ----\n{memo}\n----------------`
7. `PUT /raindrop/{id} {tags, note}` — 429/5xx 백오프는 `RaindropClient` 가 처리
8. 로컬 `dump/raindrops/<id>.json` 도 동일하게 mirror update (재실행 시 skip되게)

## 안전 / Rate limit

- raindrop API 120 req/min (≈0.51s/req). 1292건 ≈ 11분 + OpenAI 호출 시간.
- 비용: gpt-4o-mini, 평균 ~$0.0003/req → 1292건 ≈ $0.4 미만.
- OpenAI 호출 실패는 `llm-failed` 카운터로 분리; 다음 실행 때 다시 시도.
- raindrop API 실패(`api-failed`)는 로컬 mirror 안 함 → 재실행 시 자동 재시도.

## 출력 카운터 의미

- `ok`: 정상 push
- `dry-run`: `--dry-run` 으로 LLM만 호출, API push 안 함
- `skip-already-tagged`: 마커 발견, idempotent skip
- `no-dump`: `dump/raindrops/<id>.json` 없음 (먼저 `/raindrop` 돌릴 것)
- `no-infer`: `infer/<id>.md` 없음 (먼저 `/raindrop-infer` 돌릴 것)
- `bad-llm-output`: LLM이 태그 3개를 안 줬거나 메모가 비어있음
- `llm-failed`: OpenAI 호출 실패
- `api-failed`: raindrop PUT 실패

## 알려진 한계

- **사용자 note는 보존**하지만, 마커(`--- ai memo ----`/`----------------`) 자체를
  유저가 손으로 수정하면 idempotent 검사가 깨질 수 있음. 마커는 손대지 말 것.
- **revisit_after_days** (`/raindrop-infer` 출력의 필드)는 직접 안 씀 — 메모 문장 안에
  녹여달라고 LLM에 맡김.
- **태그 통합**은 LLM heuristic. 동의어 정리(`인공지능`→`AI` 등)는 별도 cleanup 필요 시
  raindrop UI 의 tag rename 사용.

## 참고
- `/raindrop` — dump 전제
- `/raindrop-infer` — infer md 전제
- 코드: `proc/lib/raindrop_retag.py`
