---
name: teams-activity
description: Microsoft Teams 알림·미답 분석 — MS Graph API 기반. **DM 미답 채팅**(`/me/chats` + last_by_me=False 휴리스틱)과 **@멘션 모음**(`mentions[].mentioned.user.id`) 위주. "Teams 미답 채팅", "DM 답 안 한 거", "@멘션 모아줘", "내가 대답 안 한 메시지", "팀즈 unread", "오늘 받은 멘션" 등 알림성 분석 시 사용. (Activity 피드 자체 — 시스템 알림, "X님이 좋아요" 등 — 가 필요하면 Graph 미노출이라 `/teams-activity-browser` fallback.)
---

# Microsoft Teams 알림·미답 분석 (MS Graph API)

`msal` device-code 플로우 + `requests` 기반. Activity 피드의 핵심 use-case(미답 chat, @멘션)를 휴리스틱으로 대체한다.

## 도구 스택
- `proc/lib/msgraph.py` — `GraphClient`
- `proc/lib/teams_graph.py` — activity helper (`unanswered_chats`, `at_mentions`, `chat_list`)

## 전제
1. Graph 첫 로그인 1회 완료 (`python3 proc/lib/msgraph.py login`).
2. 사전 승인된 권한:
   - `Chat.Read` / `Chat.ReadWrite` (admin consent ✓) — 채팅 메시지 읽기
3. **Graph는 `48:notifications` 가상 conversation을 노출하지 않음**. 시스템 알림(좋아요, "X 님이 멤버로 추가됨" 등)이 필요하면 `/teams-activity-browser` 사용.

## 핵심 엔드포인트

```
GET /v1.0/me/chats?$top=50&$expand=lastMessagePreview&$orderby=lastMessagePreview/createdDateTime desc
GET /v1.0/me/chats/{chat-id}/messages?$top=50&$filter=createdDateTime gt {iso}
```

## helper API (`teams_graph.py`)

| 함수 | 용도 |
|---|---|
| `unanswered_chats(g, top=100)` | 마지막 발신자가 내가 아닌 chat — Activity-feed 미답 surrogate |
| `at_mentions(g, since=None, max_chats=50, max_msgs_per_chat=50)` | 최근 chat을 돌며 `mentions[]`에 내 oid가 있는 메시지 추출 |
| `chat_list(g, top)` | 풀 채팅 디렉토리 (kind/last_who/last_ts/last_by_me 포함) |

## 표준 호출

### 1) DM 미답 분석 (오늘)
```python
import sys; sys.path.insert(0, 'proc/lib')
from datetime import datetime, timedelta
from msgraph import GraphClient
from teams_graph import unanswered_chats, KST

g = GraphClient()
today = datetime.now(KST).replace(hour=0, minute=0, second=0, microsecond=0)
cands = [c for c in unanswered_chats(g, top=200) if c['last_ts'] >= today]
for c in cands[:20]:
    name = c['name'] or c['last_who']
    print(f"{c['last_ts'].strftime('%H:%M')} {name[:18]:18} | {c['last_msg_preview'][:80]}")
```

### 2) 1주일치 @멘션 모음
```python
from datetime import datetime, timedelta
from teams_graph import at_mentions, KST

since = datetime.now(KST) - timedelta(days=7)
mentions = at_mentions(g, since=since, max_chats=30, max_msgs_per_chat=30)
for m in mentions:
    print(f"[{m['ts'].strftime('%m-%d %H:%M')}] in {m['chat_name']}")
    print(f"  {m['who']}: {m['text'][:120]}")
```

### 3) 마지막 24시간 내 받은 메시지 (DM/group 통합)
```python
from teams_graph import chat_list, chat_messages
import datetime as _dt

since = _dt.datetime.now(KST) - _dt.timedelta(hours=24)
for c in chat_list(g, top=50):
    if not c['last_ts'] or c['last_ts'] < since:
        continue
    msgs = chat_messages(g, c['chat_id'], since=since, max_pages=1)
    if not msgs:
        continue
    name = c['name'] or c['last_who']
    print(f"\n=== {name} ({len(msgs)} msgs) ===")
    for m in msgs[-3:]:
        print(f"  [{m['ts'].strftime('%H:%M')}] {m['who']}: {m['text'][:100]}")
```

## ⚠️ 함정과 한계

- **Activity 피드 자체 부재** — Graph에 `48:notifications` 대응 endpoint 없음. 시스템 알림류는 `/teams-activity-browser` 만 가능.
- **`last_by_me` 정확도** — `/me/chats?$expand=lastMessagePreview`의 `lastMessagePreview.from.user.id`가 내 oid인지로 판정. 봇·앱이 보낸 메시지면 `from.user`가 없을 수 있어 false-positive 가능.
- **Unread count** — Graph가 chat-level unread 카운트를 노출하나 `chat_list()`에는 미포함 (필요 시 `?$expand=lastMessageReadDateTime` 등으로 추가).
- **`at_mentions` 비용** — N개 chat × M개 메시지 fetch → throttling 위험. `max_chats`/`max_msgs_per_chat`/`since`로 좁혀라.
- **자기 멘션 스킵** — 내가 나를 멘션한 메시지(드뭄)도 잡힘. 필요 시 `m['who'] != me` 추가 필터.

## 실패 시 fallback

- 401/403 / 토큰 만료 → silent refresh → 그래도 안 되면 재로그인
- **Activity 피드 자체** (시스템 알림) 가 필요한 경우 → `/teams-activity-browser`
- 사용자가 "브라우저로", "playwright로", "teams-activity-browser" 명시 지정

```python
from msgraph import GraphClientError
try:
    cands = unanswered_chats(g)
except GraphClientError:
    # → /teams-activity-browser 호출
    ...
```

## 다른 Teams 스킬과의 분리

| 스킬 | 용도 | 데이터 소스 |
|---|---|---|
| **`/teams-activity`** | DM 미답 / @멘션 분석 | **MS Graph API** |
| `/teams-activity-browser` | Activity 피드 자체 (시스템 알림 포함) — fallback / unique-feature | DOM (가상 스크롤) |
| `/teams-chat` | DM·그룹채팅 본문 조회·전송 | MS Graph API |
| `/teams-channel` | 채널 게시물 | MS Graph API |
