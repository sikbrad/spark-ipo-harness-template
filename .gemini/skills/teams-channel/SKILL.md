---
name: teams-channel
description: Microsoft Teams 채널 게시물(thread+replies) **조회·게시·답글·수정·삭제** — MS Graph API 기반. 브라우저 불필요, 헤드리스 동작. "Teams 채널 메시지", "거래원장 채널 오늘 요약", "팀즈 채널 글 받아줘", "channel posts", "thread 댓글 모아줘", "채널에 글 쓰기", "thread reply", "팀즈 채널 글 게시", "채널 글 수정", "채널 메시지 삭제", "edit channel post" 등 채널 조회·게시·수정 요청 시 사용.
---

# Microsoft Teams 채널 (MS Graph API) — 조회·게시·답글·수정·삭제

`msal` device-code 플로우 + `requests` 기반. 브라우저 프로세스를 띄우지 않는다.

## 도구 스택
- `proc/lib/msgraph.py` — `GraphClient`
- `proc/lib/teams_graph.py` — channel helper (`joined_teams`, `channels`, `channel_map`, `find_channel_graph`, `channel_posts`)

## 전제
1. Graph 첫 로그인 1회 완료 (`python3 proc/lib/msgraph.py login`).
2. 사전 승인된 권한:
   - `Team.ReadBasic.All` (admin consent ✓) — 사용자가 가입한 팀 목록
   - `ChannelMessage.Read.All` (admin consent ✓) — 채널 메시지 조회
   - `ChannelMessage.Send` (admin consent ✓) — 새 메시지·답글 게시
   - `ChannelMessage.ReadWrite` (admin consent ✓ — 2026-05-08) — 본인 게시글 PATCH·softDelete
3. 동시성: 여러 Python 프로세스 동시 호출 가능.

## 핵심 엔드포인트

```
GET /v1.0/me/joinedTeams
GET /v1.0/teams/{team-id}/channels
GET /v1.0/teams/{team-id}/channels/{channel-id}/messages
    ?$top=50&$orderby=createdDateTime desc
GET /v1.0/teams/{team-id}/channels/{channel-id}/messages/{msg-id}/replies
    ?$top=50
```

`channel-id`는 `19:abc...@thread.tacv2` 형식. team-id는 GUID.

## helper API (`teams_graph.py`)

| 함수 | 용도 |
|---|---|
| `joined_teams(g)` | 사용자가 가입한 팀 목록 (raw JSON) |
| `channels(g, team_id)` | 한 팀의 채널 목록 (raw JSON) |
| `channel_map(g, cache_path=None)` | 모든 (team, channel) 매핑 한 번에 — `[{team_id, team_name, channel_id, channel_name, membership_type}]`. 옵션으로 JSON 캐시 |
| `find_channel_graph(g, query, cache=None)` | 채널/팀 이름 substring 매칭 |
| `channel_posts(g, team_id, channel_id, since=None, until=None, page_size=50, max_pages=10, include_replies=True)` | 정규화된 thread 리스트 — `[{parent, parent_in_window, replies, reply_total}]`. 출력 스키마는 `pwc_teams.parse_posts`와 호환 |
| `send_channel_message(g, team_id, channel_id, text, html_body=False)` | **쓰기** — 새 top-level 메시지. 반환값에 `id`/`webUrl` (이후 reply에 사용) |
| `reply_channel_message(g, team_id, channel_id, parent_message_id, text, html_body=False)` | **쓰기** — thread reply |
| `update_channel_message(g, team_id, channel_id, message_id, text, html_body=False, mentions=None, parent_message_id=None)` | **수정** — 본인 게시글 PATCH. `mentions` 동시 갱신, `parent_message_id` 주면 reply 수정 |
| `delete_channel_message(g, team_id, channel_id, message_id, parent_message_id=None, undo=False)` | **삭제** — softDelete (또는 `undo=True` 로 복원). DELETE 405 — 반드시 `softDelete` 액션 사용 |

## 표준 호출

### 1) 채널명으로 찾아 어제·오늘 요약
```python
import sys; sys.path.insert(0, 'proc/lib')
from datetime import datetime, timedelta
from msgraph import GraphClient
from teams_graph import find_channel_graph, channel_posts, KST, channel_map

g = GraphClient()
cmap = channel_map(g, cache_path='output/teams-channel-map.json')
hits = find_channel_graph(g, '거래원장', cache=cmap)
if hits:
    h = hits[0]
    since = datetime.now(KST) - timedelta(days=2)
    threads = channel_posts(g, h['team_id'], h['channel_id'], since=since)
    for t in threads:
        p = t['parent']
        when = p['ts'].strftime('%m-%d %H:%M') if p['ts'] else '?'
        print(f"[{when}] {p['who']}: {p['text'][:120]}  (replies={t['reply_total']})")
        for r in t['replies']:
            print(f"  ↪ [{r['ts'].strftime('%H:%M')}] {r['who']}: {r['text'][:100]}")
```

### 2) 알고 있는 team_id/channel_id로 직접
```python
threads = channel_posts(g, team_id='3c66...', channel_id='19:abc...@thread.tacv2',
                        page_size=50, max_pages=2, include_replies=False)
```

### 3) 전체 채널 인벤토리 (cache 만들기)
```python
m = channel_map(g, cache_path='output/teams-channel-map.json')
print(f'{len(m)} channels across {len({c["team_id"] for c in m})} teams')
```

### 4) 채널에 글 게시 + thread reply
```python
from teams_graph import send_channel_message, reply_channel_message
posted = send_channel_message(g, team_id, channel_id,
    '오늘 데일리 체크인 정리:\n- AX-191 완료\n- AX-192 진행 중')
reply_channel_message(g, team_id, channel_id, posted['id'],
    '추가: 미소치과기공소 220V 재설치 4/27 일정 확인 요청')
```

### 5) HTML 메시지 (멘션·강조)
```python
send_channel_message(g, team_id, channel_id,
    '<p><b>긴급</b>: 한아치과기공소(강동훈) 미입금 follow-up 필요</p>',
    html_body=True)
```

### 6) 게시글 수정 (PATCH) — 멘션·HTML 동시 갱신
```python
from teams_graph import update_channel_message

mentions = [{
    'id': 0,
    'mentionText': '서해리 Haeri',
    'mentioned': {'user': {
        'id': '333a504a-...',          # /users 에서 displayName 으로 조회
        'displayName': '서해리 Haeri',
        'userIdentityType': 'aadUser',
    }},
}]

update_channel_message(
    g, team_id, channel_id, message_id,
    '<p><at id="0">서해리 Haeri</at> 정정합니다 — 가격: Plus $49 (180msg/day)</p>',
    html_body=True, mentions=mentions,
)
# reply 수정: parent_message_id=parent_id 추가
```

### 7) 게시글 삭제 / 복원 (softDelete)
```python
from teams_graph import delete_channel_message

delete_channel_message(g, team_id, channel_id, message_id)               # 삭제
delete_channel_message(g, team_id, channel_id, message_id, undo=True)    # 복원
# reply 삭제: parent_message_id=parent_id 추가
```

> **⚠️ 권한**: PATCH·softDelete 는 `ChannelMessage.ReadWrite` (admin consent 필수, 2026-05-08 부 기등록).
> 본인이 작성한 메시지에만 동작. 남이 쓴 글 수정 시도하면 403.

## ⚠️ 함정과 한계

- **`$top` 상한 50**. 더 받으려면 `max_pages` 늘리거나 `since`로 좁히기.
- **`include_replies=True`는 N+1 호출** — parent마다 별도 `/replies` 호출. 채널이 활발하면 비싸짐. 요약만 필요하면 False.
- **삭제·시스템 메시지** — `deletedDateTime`/`messageType=systemEventMessage` 자동 제외.
- **인용(quote) 파싱** — HTML `<blockquote>` 정규식. 브라우저 fallback과 동일 출력.
- **첨부 파일** — 파싱 안 함. 필요 시 `m['attachments']` 직접 접근.
- **사용자가 멤버가 아닌 채널** — 401. `ChannelMessage.Read.All`은 멤버십 채널만 보임.

## 실패 시 fallback

다음 경우 `/teams-channel-browser` (playwright-cli) 로 fallback:
- 401/403 — 토큰 만료, 권한 거부 (`GraphClientError` 401 → silent refresh 실패 → 명시적 재로그인)
- 503/Throttling
- Connection 오류
- "민감 채널이라 Graph가 안 보여줌" (드물지만 가능)

```python
from msgraph import GraphClientError
try:
    threads = channel_posts(g, tid, cid, since=...)
except (GraphClientError, requests.RequestException):
    # → /teams-channel-browser 호출
    ...
```

또는 사용자가 "브라우저로", "playwright로", "teams-channel-browser" 명시 지정 시 본 스킬 건너뛰고 `/teams-channel-browser` 직접 호출.

## 다른 Teams 스킬과의 분리

| 스킬 | 용도 | 데이터 소스 |
|---|---|---|
| `/teams-activity` | DM 미답 / @멘션 (Graph) | MS Graph API |
| `/teams-activity-browser` | Activity 피드 자체 (시스템 알림 포함) | DOM (가상 스크롤) |
| `/teams-chat` | DM·그룹채팅 본문 조회·전송 | MS Graph API |
| `/teams-chat-browser` | 동일 — fallback | REST `/api/chatsvc/.../messages` |
| **`/teams-channel`** | 채널 게시물 (Graph) | **MS Graph API** |
| `/teams-channel-browser` | 동일 — fallback | REST `/api/csa/.../posts` |
