---
name: chatgpt
description: ChatGPT(chatgpt.com) 개인 계정 대화 토픽 목록·본문 export. playwright-cli 기반, Apple ID 로그인. "GPT 대화 받아줘", "내 ChatGPT 질문 목록", "GPT 토픽 백업", "chatgpt export", "GPT 대화 본문 다운로드", "내가 GPT에 물어본 거 정리" 등 ChatGPT 개인 대화 export 요청 시 사용.
---

# ChatGPT 개인 대화 export

`@playwright/cli` 기반. `proc/lib/pwc_chatgpt.py`의 helper로 chatgpt.com에
로그인된 세션의 Bearer 토큰을 추출 → `/backend-api/conversations` 와
`/backend-api/conversation/{id}` 를 직접 호출한다. SPA가 평소 쓰는 API
그대로라 안정적이고, 본인 계정 본인 데이터만 다룬다.

## 도구 스택

- `@playwright/cli` (전역 `playwright-cli`) — `-s=chatgpt` 격리 세션, 영속 프로필
- `proc/lib/pwc.py` — 세션 wrapper (`S('chatgpt')`)
- `proc/lib/pwc_chatgpt.py` — ChatGPT helper

## 전제

1. `playwright-cli` 설치 (`npm install -g @playwright/cli@latest`).
2. `.env`에 Apple ID 자격증명:
   ```
   OPENAI_PERSONAL_APPLIE_ID=sikbrad@icloud.com
   OPENAI_PERSONAL_APPLIE_PW=...
   ```
3. **ChatGPT 세션 부트스트랩** (첫 1회 헤디드):
   ```bash
   playwright-cli -s=chatgpt open https://chatgpt.com/ --persistent --headed
   ```
   브라우저 창에서 "Log in" → "Continue with Apple" → 이메일/비밀번호 입력
   → 신뢰된 Mac 알림으로 받은 6자리 2FA 코드 입력. 이후 persistent 프로필이
   로그인을 유지. **2FA는 Mac 푸시라 자동화 불가** — 사용자가 직접 코드 입력.
4. 동시성: 다른 `-s=` 세션과 별개 브라우저라 충돌 없음.

## 위험 안내 (필독)

ChatGPT consumer ToS는 programmatic 데이터 추출을 금지한다. 본 스킬은
**본인 계정의 본인 데이터를 사람-사용 수준 rate(≈1.5 RPS)로 SPA-equivalent
endpoint에서 fetch**하는 시나리오라 ban 사례가 거의 없지만, 제로는 아니다.

**더 안전한 대안**: ChatGPT 자체 공식 export
- 설정 → Data Controls → Export Data → 메일로 ZIP 도착
- 1번이면 모든 대화 본문 포함. ToS-안전.

스킬 사용 시에는 다음 안전장치가 자동 적용된다:
- 호출 간 0.6s sleep
- 429 응답 시 60s → 120s → 240s 백오프
- 4회 연속 429 시 abort
- **Resume + change-detect** — sqlite `update_time` 비교, 변경 없으면 skip (API 호출 0)
- Atomic write (`.tmp` → rename)
- 에러 로그 (sqlite `errors` 테이블)

## 변경 감지 (`data/db/chatgpt.sqlite`)

다운로드 상태·메타·에러를 sqlite 한 파일에 보관. 기본 경로 `data/db/chatgpt.sqlite`.

### 스키마

```sql
CREATE TABLE conversations (
  id          TEXT PRIMARY KEY,
  title       TEXT,
  create_time TEXT,
  update_time TEXT,           -- ISO Z 마이크로초 (인덱스 형식 그대로)
  fetched_at  TEXT,           -- 마지막으로 본문을 받은 ISO Z 시각
  size        INTEGER,        -- {id}.json 바이트
  status      TEXT DEFAULT 'active'   -- 'active' | 'deleted'
);
CREATE INDEX idx_conv_update ON conversations(update_time);
CREATE INDEX idx_conv_status ON conversations(status);

CREATE TABLE meta (
  key   TEXT PRIMARY KEY,
  value TEXT
);
-- 'last_index_fetch', 'last_run_at', 'index_total'

CREATE TABLE errors (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  conv_id     TEXT,
  occurred_at TEXT,
  status_code INTEGER,
  msg         TEXT
);
```

### 비교 로직

- **DB의 update_time == 인덱스의 update_time AND 파일 존재 AND status='active'** → SKIP
- **DB row 없는데 파일은 존재** → 파일의 top-level epoch을 ISO로 변환해 row 자동 backfill, 다음 단계로 진행
- **DB의 update_time 다름 OR 파일 없음** → API 호출 → atomic write → row UPSERT
- 인덱스에 없는 id는 → `status='deleted'` 마킹 (파일은 보존, summary에 `deleted_seen` 카운트)

### 빠른 분석

sqlite로 옮긴 덕에 SQL로 바로 쿼리 가능:

```bash
# 최근 10개 토픽
sqlite3 data/db/chatgpt.sqlite \
  "SELECT date(create_time), title FROM conversations ORDER BY update_time DESC LIMIT 10"

# 한 달간 새로 만든 대화 수
sqlite3 data/db/chatgpt.sqlite \
  "SELECT COUNT(*) FROM conversations WHERE create_time >= '2026-04-08'"

# 실패 누적
sqlite3 data/db/chatgpt.sqlite \
  "SELECT status_code, COUNT(*) FROM errors GROUP BY status_code"

# 가장 큰 대화 5개
sqlite3 data/db/chatgpt.sqlite \
  "SELECT title, size FROM conversations ORDER BY size DESC LIMIT 5"
```

## 운영 패턴

**처음부터 풀로 다운로드:**
```python
cg.dump_all_conversations(s, 'output/chatgpt')
# total=1652 fetched=1652 updated=0 skipped=0
```

**일/주 단위 증분 갱신 (권장):**
```python
cg.sync_new(s, 'output/chatgpt')
# total=1652 fetched=12 updated=8 skipped=1640
# fetched 12개 중 updated=8 (기존 대화 갱신), 4개는 신규
```

## 핵심 helper (`proc/lib/pwc_chatgpt.py`)

| 함수 | 용도 |
|---|---|
| `is_logged_in(s)` | `/api/auth/session` 결과로 로그인 여부 판정 |
| `access_token(s)` | Bearer 토큰 fresh 발급 (디버그용) |
| `list_conversations(s, limit=None)` | 대화 인덱스 페이지네이션. `[{title, id, create_time, update_time}]` |
| `get_conversation(s, conv_id)` | 단일 대화 raw 트리. 429/4xx 발생 시 `HTTPError` (status 속성 포함) |
| `first_user_message(conv)` | 트리에서 가장 오래된 user role 메시지 텍스트 |
| `dump_topics(s, path)` | 토픽 인덱스 JSON 저장 |
| `dump_all_conversations(s, out_dir, sleep_sec=0.6, limit=None)` | **전체 본문 export.** `out_dir/conversation_data/{id}.json` 개별 저장 + resume + 백오프 |
| `sync_new(s, out_dir)` | 인덱스 새로 받고 미존재 id만 fetch (증분 갱신) |

## 출력 구조

```
output/chatgpt/
├── conversations.json                # 토픽 인덱스 (title/id/create_time/update_time)
├── conversation_data/
│   └── {conv_id}.json                # ChatGPT raw mapping 트리 (그대로 dump)
└── errors.jsonl                      # 실패 기록 (id별 1라인 JSON)
```

각 `{conv_id}.json` 의 핵심 구조:
```jsonc
{
  "title": "...",
  "create_time": 1746...,
  "mapping": {
    "<msg_id>": {
      "id": "...",
      "message": {
        "author": {"role": "user|assistant|system|tool"},
        "content": {"content_type": "text", "parts": ["..."]},
        "create_time": 1746...
      },
      "parent": "<parent_id>",
      "children": ["<child_id>", ...]
    },
    ...
  },
  ...
}
```

## 사용 예

### 토픽 목록만 (가벼움)

```python
import sys; sys.path.insert(0, 'proc/lib')
from pwc import S
import pwc_chatgpt as cg

s = S('chatgpt')
assert cg.is_logged_in(s), '먼저 부트스트랩 필요'
cg.dump_topics(s, 'output/chatgpt/conversations.json')
```

### 본문 전체 다운로드 (느림 — 1,652개 ≈ 17~20분)

```python
from pwc import S
import pwc_chatgpt as cg
s = S('chatgpt')
summary = cg.dump_all_conversations(s, 'output/chatgpt')
print(summary)  # {'total': 1652, 'fetched': 1649, 'skipped': 0, 'failed': 3}
```

### 새로운 대화만 추가 (증분)

```python
from pwc import S
import pwc_chatgpt as cg
s = S('chatgpt')
cg.sync_new(s, 'output/chatgpt')
```

### 첫 질문(user prompt)만 빠르게 보기

```python
from pwc import S
import pwc_chatgpt as cg
import json

s = S('chatgpt')
items = cg.list_conversations(s, limit=20)
for it in items:
    conv = cg.get_conversation(s, it['id'])
    print(it['create_time'][:10], '|', it['title'])
    print('   ', (cg.first_user_message(conv) or '')[:120])
```

### 오프라인 분석 (다운로드 후)

다운로드 끝난 뒤엔 `output/chatgpt/conversation_data/*.json` 만 읽으면
브라우저 없이 분석 가능. 예: 모든 대화에서 첫 user 메시지 추출

```python
import json, glob
from pwc_chatgpt import first_user_message

rows = []
for p in glob.glob('output/chatgpt/conversation_data/*.json'):
    conv = json.load(open(p))
    rows.append({
        'id': conv.get('conversation_id'),
        'title': conv.get('title'),
        'first_q': first_user_message(conv),
    })
```

## 트러블슈팅

| 증상 | 원인 / 대처 |
|---|---|
| `is_logged_in == False` | persistent 프로필 만료 또는 비밀번호 변경. 부트스트랩 다시. |
| `HTTPError status=429` | rate-limited. helper가 자동 백오프 — 그래도 4회 연속 시 잠시 (≥10분) 쉬었다가 `sync_new` 재실행 (resume됨). |
| `HTTPError status=401` | 토큰 만료. helper는 매 호출마다 `/api/auth/session` 재취득 — 발생 시 세션 자체 만료. 부트스트랩 다시. |
| 본문 JSON parse 실패 | 일부 대화는 410(deleted) 또는 conversation 락 상태. `errors.jsonl` 확인. |
| 1,652개 다운로드 너무 김 | 증분으로 운영. 첫 회만 풀로 받고, 이후 `sync_new`. |
