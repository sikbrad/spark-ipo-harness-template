# ChatGPT 대화 export — playwright-cli 기반

## 목적
`chatgpt.com` 개인 계정(sikbrad@icloud.com, Apple ID 로그인)의 모든 대화를
local에 JSON으로 보관. 토픽 목록 + 각 대화 본문(mapping 트리) 모두.

## 결과물
```
output/chatgpt/
├── conversations.json                # 토픽 인덱스 (백업용; 진실은 sqlite)
└── conversation_data/
    └── {conv_id}.json                # 각 대화 raw mapping (ChatGPT API response 그대로)

data/
└── chatgpt.sqlite                    # 다운로드 상태·메타·에러 — 단일 source of truth
```

## SQLite 스키마 (`data/chatgpt.sqlite`)

```sql
CREATE TABLE conversations (
  id           TEXT PRIMARY KEY,         -- ChatGPT 대화 UUID
  title        TEXT,
  create_time  TEXT,                     -- ISO (인덱스가 주는 그대로)
  update_time  TEXT,                     -- ISO (변경 감지의 핵심 키)
  fetched_at   TEXT,                     -- ISO Z (로컬 시간) — 마지막으로 본문을 받은 순간
  size         INTEGER,                  -- {id}.json 바이트
  status       TEXT DEFAULT 'active'     -- 'active' | 'deleted'
);
CREATE INDEX idx_conv_update ON conversations(update_time);

CREATE TABLE meta (
  key   TEXT PRIMARY KEY,
  value TEXT
);
-- 키 예시: 'last_index_fetch', 'last_run_at', 'index_total'

CREATE TABLE errors (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  conv_id     TEXT,
  occurred_at TEXT,                      -- ISO Z
  status_code INTEGER,                   -- HTTP status (없으면 NULL)
  msg         TEXT
);
CREATE INDEX idx_err_conv ON errors(conv_id);
```

## 동작 흐름 (변경 감지)

1. `dump_all_conversations(s, out_dir)` 호출
2. `/backend-api/conversations` 풀 페이지네이션 → 인덱스를 메모리에 적재
3. `meta.last_index_fetch = now` 기록, `conversations.json` 백업 dump
4. 각 인덱스 항목 `(id, title, update_time)` 에 대해:
   - `SELECT update_time FROM conversations WHERE id=?`
   - **DB에 없는 경우**: 로컬 파일 존재하면 → 파일 top-level `update_time` 읽어서 backfill row insert (status='active'), 다음 단계로 진행
   - **DB의 update_time == 인덱스의 update_time AND 파일 존재**: SKIP
   - **그 외 (신규 / 변경 / 파일 손상)**: `/backend-api/conversation/{id}` 호출 → atomic write → row UPSERT
5. 인덱스 풀스윕 후 deletion 처리:
   - `UPDATE conversations SET status='deleted' WHERE id NOT IN (인덱스의 id들)`
6. `meta.last_run_at = now` 기록, summary 출력

## API 변경

| 함수 | 변경점 |
|---|---|
| `dump_all_conversations(s, out_dir, db_path=None, ...)` | `db_path` 추가. 기본 `data/chatgpt.sqlite`. JSON manifest 코드 모두 제거. |
| `sync_new(s, out_dir, db_path=None)` | 동일 |
| (제거) `_load_state` / `_save_state` / `_backfill_manifest_entry` | sqlite로 대체 |
| (신규) `_db_open(path)` / `_db_init(conn)` / `_db_get` / `_db_upsert` / `_db_log_error` / `_db_mark_deleted` | 내부 헬퍼 |

`errors.jsonl` 파일은 더 이상 안 쓴다 (sqlite `errors` 테이블).

## 마이그레이션

`_state.json`은 dry-run 단계에서만 잠깐 도입됐고 production에 없음 → 마이그레이션 코드 불필요. 기존 다운로드된 `output/chatgpt/conversation_data/*.json` 파일들은 다음 sync_new 호출 시 자동으로 sqlite에 backfill 된다.

## 왜 sqlite (사용자 요청 — 검토 결과)

- **장점**: 트랜잭션 안전·index·status enum·errors join — 향후 query 가능
- **단점**: 32KB JSON 한 파일이면 충분한 규모. 다만 사용자 요청.
- **위치**: `data/` (사용자 지정) — `.gitignore`에 추가 필요 (대용량·개인정보)

## 진행 로그
- 2026-05-08 06:39 — chatgpt session open + Apple ID 로그인 (사용자 2FA)
- 2026-05-08 06:43 — `/api/auth/session` 200 OK, 토큰 확보
- 2026-05-08 06:44 — `conversations.json` dump 완료 (1,652건)
- 2026-05-08 06:5x — `pwc_chatgpt.py` 헬퍼 정착 (list/get/first_user_message)
- 2026-05-08 07:0x — `dump_all_conversations` (resume + 429 backoff) → background 다운로드 시작
- 2026-05-08 07:2x — 217/1652까지 fetch한 시점에 4회 연속 429 → 자동 abort. JSON manifest 도입 직후, **사용자 요청으로 SQLite로 전환**.
- 2026-05-08 07:3x — `data/chatgpt.sqlite` 스키마 적용, JSON manifest 제거. 217 기존 파일 sqlite로 자동 backfill 검증.
- 다음 — rate-limit 회복 대기(10~15분) 후 `sleep_sec=1.0`으로 재시작 → 나머지 1435개 fetch

## 아키텍처
- 세션: `S('chatgpt')` (persistent profile, Apple ID 로그인)
- 인증: `/api/auth/session` → `accessToken` (Bearer) — 매 호출 fresh 발급
- 목록: `GET /backend-api/conversations?offset=N&limit=28&order=updated`
- 본문: `GET /backend-api/conversation/{id}` → `{mapping, ...}` 트리

## 위험 검토 (2026-05-08)
**판정: 낮음 (제로 아님). 안전장치 적용 후 진행.**

ChatGPT consumer ToS는 programmatic data extraction을 금지하지만, 본인
계정의 본인 데이터를 사람-사용 수준 rate로 SPA-equivalent endpoint에서
fetch하는 것은 ban으로 이어진 사례가 거의 없음.

**실제 ban 위험 트리거 (회피)**
- 5+ RPS의 burst → 0.6s sleep로 ~1.5 RPS 유지
- Cloudflare challenge 우회 → 실제 브라우저(Chrome) 안에서 fetch 호출
- 신규/일회용 계정 자동 생성 → 본인 계정만 사용
- 429 무시 강행 → 60s/120s/240s 지수 백오프

**더 안전한 대안**: 설정 → Data Controls → Export Data (공식 ZIP).
사용자가 검토 후 스크립트 진행 결정.

## 안전장치
1. **Rate limit**: 호출 간 0.6초 sleep (≈1.5 RPS)
2. **429 backoff**: 60s → 120s → 240s, 그래도 실패 시 abort
3. **Resume + change-detect**: sqlite `conversations.update_time` 비교 — 변경 없으면 skip
4. **Progress log**: 25개마다 stderr 출력
5. **Atomic write**: `.tmp` → rename (data 파일)
6. **Error log**: sqlite `errors` 테이블
7. **Deletion detection**: 인덱스에 없는 id는 `status='deleted'` 마킹 (파일은 보존)

## 스킬 등록
- `.claude/skills/chatgpt/SKILL.md` (+ `.gemini/skills/chatgpt/SKILL.md`)
- 트리거: "ChatGPT 대화", "내 GPT 질문 목록", "GPT 토픽", "GPT 백업"
- 코어: `proc/lib/pwc_chatgpt.py`

## 재실행
세션 persistent라 재로그인 불필요. Apple ID 토큰 만료(>30일)나 비밀번호
변경 시에만 재로그인. 새 대화만 추가하려면:
```python
from pwc import S
import pwc_chatgpt as cg
s = S('chatgpt')
cg.sync_new(s)  # 미존재 id만 fetch (resume 로직 그대로)
```
