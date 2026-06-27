---
name: teams-chat
description: Microsoft Teams 채팅(DM/그룹) **본문** 조회·전송·수정·삭제 — MS Graph API 기반(`/me/chats`, `/me/chats/{id}/messages`). 브라우저 불필요, 헤드리스 동작. "Teams DM 내용", "그룹챗 메시지 받아줘", "조소연한테 보낸 메시지", "특정 채팅 본문 분석", "thread.v2 메시지 추출", "DM으로 메시지 보내줘", "방금 보낸 DM 수정", "DM 메시지 삭제" 등 채팅 본문 조회·전송·수정 시 사용. (채팅 **목록 통계**는 `/teams-activity`, **채널** 게시물은 `/teams-channel` — 채널은 admin consent가 필요하므로 별도.)
---

# Microsoft Teams 채팅 본문 조회·전송·수정·삭제 (MS Graph API)

`msal` device-code 플로우 + `requests` 기반. 브라우저 프로세스를 띄우지 않는다.

## 도구 스택
- `proc/lib/msgraph.py` — `GraphClient` (MSAL device-code, 토큰 캐시, silent refresh)
- `proc/lib/teams_graph.py` — Teams 채팅 helper (`chat_list`, `chat_messages`, `find_chat`, `send_chat_message`)
- `.env`의 `MSFT_MYAGENT_CLIENT_ID`, `MSFT_MYAGENT_TENANT_ID` (앱 등록 시 발급)

## 전제
1. `pip install msal requests` (한 번만).
2. **첫 로그인 (1회)**:
   ```bash
   python3 proc/lib/msgraph.py login
   ```
   터미널에 표시되는 device code를 https://login.microsoft.com/device 에서 입력 + 폰 Authenticator 승인. 토큰 캐시(`~/.cache/dof-msgraph-msal.json`)에 저장 → 이후 무인 동작.
3. 토큰은 sliding 90일. 주 1회라도 호출되면 자동 갱신. 실패 시 재로그인.
4. 동시성: 여러 Python 프로세스가 동시에 호출 가능 (각자 토큰 read-only).

## 핵심 엔드포인트

```
GET https://graph.microsoft.com/v1.0/me/chats
    ?$top=50
    &$expand=lastMessagePreview
    &$orderby=lastMessagePreview/createdDateTime desc

GET https://graph.microsoft.com/v1.0/me/chats/{chat-id}/messages
    ?$top=50
    &$orderby=createdDateTime desc
    &$filter=createdDateTime gt 2026-05-01T00:00:00Z

POST https://graph.microsoft.com/v1.0/me/chats/{chat-id}/messages
Body: {"body": {"contentType": "text", "content": "hello"}}
```

`chat-id` 형식 (브라우저 버전과 동일):
- 그룹챗: `19:abc...@thread.v2`
- DM: `19:abc..._def...@unq.gbl.spaces`

## helper API (`teams_graph.py`)

| 함수 | 용도 |
|---|---|
| `chat_list(g, top=50)` | 채팅 디렉토리 — `[{chat_id, kind, name, last_msg_preview, last_who, last_ts, last_by_me, group}]`. `lastMessagePreview` 자동 expand |
| `chat_messages(g, chat_id, since=None, until=None, page_size=50, max_pages=20)` | 정규화된 본문 — `[{ts, who, text, quote, id, type}]`. 시간 오름차순 |
| `find_chat(g, query)` | topic / last sender 이름 substring 매칭 — DM 찾을 때 |
| `send_chat_message(g, chat_id, text, html_body=False)` | 메시지 전송 (Chat.ReadWrite 필요) |
| `update_chat_message(g, chat_id, message_id, text, html_body=False, mentions=None)` | 본인 메시지 PATCH (Chat.ReadWrite 필요) |
| `delete_chat_message(g, chat_id, message_id, undo=False)` | softDelete / 복원 (Chat.ReadWrite 필요) |
| `chat_thread_id_from_url(url)` | Teams 딥링크 URL → chat_id 추출 |

출력 스키마는 `pwc_teams.parse_chat_messages`와 호환 — 다운스트림 코드(파일 출력, 마크다운 변환 등) 변경 없이 사용 가능.

## 표준 호출

### 1) 특정 사람과의 DM 1주일치 받기
```python
import sys, json; sys.path.insert(0, 'proc/lib')
from datetime import datetime, timedelta
from msgraph import GraphClient
from teams_graph import find_chat, chat_messages, KST

g = GraphClient()
hits = find_chat(g, '조소연')
if hits:
    cid = hits[0]['chat_id']
    since = datetime.now(KST) - timedelta(days=7)
    msgs = chat_messages(g, cid, since=since)
    for m in msgs:
        print(f"[{m['ts'].strftime('%m-%d %H:%M')}] {m['who']}: {m['text'][:100]}")
```

### 2) 채팅 목록 + 미답 분석
```python
from msgraph import GraphClient
from teams_graph import chat_list

g = GraphClient()
chats = chat_list(g, top=100)
unanswered = [c for c in chats if not c['last_by_me'] and c['last_ts']]
for c in unanswered[:10]:
    name = c['name'] or c['last_who']
    print(f"{c['last_ts'].strftime('%m-%d %H:%M')} {name}: {c['last_msg_preview'][:60]}")
```

### 3) 메시지 전송 (DM에 답하기)
```python
from msgraph import GraphClient
from teams_graph import find_chat, send_chat_message

g = GraphClient()
hit = find_chat(g, '조소연')[0]
send_chat_message(g, hit['chat_id'], '확인했습니다 👍')
```

### 4) URL → chat_id → 본문
```python
from teams_graph import chat_thread_id_from_url, chat_messages
url = 'https://teams.cloud.microsoft/l/chat/19:abc...@thread.v2/conversations?...'
cid = chat_thread_id_from_url(url)
msgs = chat_messages(g, cid, page_size=50)
```

## ⚠️ 함정과 한계

- **`$top` 상한 50**. 더 받으려면 `chat_messages`의 `max_pages` 늘리거나 `since`로 좁히기.
- **`Chat.ReadWrite` 권한 필요** (전송용). 읽기만이면 `Chat.Read`로도 충분 — 둘 다 admin consent 사전 승인됨.
- **채널은 안 됨**. `/teams/{tid}/channels/{cid}/messages`는 `ChannelMessage.Read.All` (admin consent 필요)이 빠져있어 401 발생. 채널 글은 현재 `/teams-channel` (브라우저 fallback) 사용.
- **삭제·시스템 메시지** — `deletedDateTime`/`messageType=systemEventMessage` 자동 제외.
- **Activity 피드 직접 대응 없음** — `48:notifications` 가상 conversation은 Graph에 노출 안 됨. Activity는 `/teams-activity` (브라우저) 또는 `chat_list`의 `last_by_me=False` 휴리스틱으로 대체.
- **인용(quote)** — Graph는 reply 메시지를 `replyToId`로 표시하지만 본 helper는 HTML `<blockquote>` 파싱(브라우저 버전 호환)을 우선. 필요 시 별도 follow-up 호출로 원 메시지 가져오기.
- **AdaptiveCard** — `attachments[].content`가 string(JSON) or dict 둘 다 처리.

## 실패 시 fallback

호출이 다음 이유로 실패하면 `/teams-chat-browser` (playwright-cli) 로 자동 fallback:
- 401/403 — 토큰 만료, 권한 거부 (`GraphClient`가 silent refresh 시도 → 그래도 실패하면 명시적 재로그인 필요)
- 503/Throttling — Graph rate limit
- Connection 오류

```python
from msgraph import GraphClientError
try:
    msgs = chat_messages(g, cid, since=...)
except (GraphClientError, requests.RequestException):
    # → /teams-chat-browser 호출
    ...
```

또는 사용자가 명시적으로 "브라우저로", "playwright로", "teams-chat-browser" 라고 한 경우 본 스킬을 건너뛰고 바로 `/teams-chat-browser` 호출.

## 다른 Teams 스킬과의 분리

| 스킬 | 용도 | 데이터 소스 |
|---|---|---|
| `/teams-activity` | Activity 피드, Chat **목록**(DM 미답·unread) | DOM (가상 스크롤) |
| `/teams-channel` | 채널 게시물(thread + replies) | REST `/api/csa/.../containers/{cid}/posts` (브라우저) |
| **`/teams-chat`** | DM·그룹채팅 **본문** 조회·전송 | **MS Graph API** (브라우저 0개) |
| `/teams-chat-browser` | 위와 동일 — fallback | REST `/api/chatsvc/.../messages` (브라우저) |

채팅 **목록**은 `teams-activity`(브라우저) 또는 본 스킬의 `chat_list()` 둘 다 가능. 본 스킬은 `last_by_me`/`last_ts`까지 한 번에 주므로 미답 분석에도 효율적.
