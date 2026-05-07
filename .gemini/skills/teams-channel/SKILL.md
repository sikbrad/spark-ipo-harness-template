---
name: teams-channel
description: Microsoft Teams web(teams.cloud.microsoft)의 채널 게시물(thread+replies)을 내부 REST API(`/api/csa/.../containers/{cid}/posts`)로 직접 받아와 파싱. "Teams 채널 메시지", "거래원장 채널 오늘 요약", "팀즈 채널 글 받아줘", "channel posts", "thread 댓글 모아줘" 등 채널(채팅 아닌 채널) 게시물 조회 요청 시 사용.
---

# Microsoft Teams 채널 게시물 조회 (REST 직접 호출)

`@playwright/cli` 기반. 채널 게시물(thread + replies)을 **DOM 스크레이핑 없이** Teams 내부 REST API로 가져온다.

## 도구 스택
- `@playwright/cli` (전역 `playwright-cli`) — 사이트별 격리 세션, 영속 프로필, 워커 트래픽 캡처
- `proc/lib/pwc.py` — 세션 wrapper (`S('teams')`)
- `proc/lib/pwc_teams.py` — Teams 사이트 helper (channel API 헬퍼 포함)

## 전제
1. `playwright-cli` 설치(한 번): `npm install -g @playwright/cli@latest`.
2. Teams 세션 부트스트랩(첫 1회):
   ```bash
   playwright-cli -s=teams open https://teams.cloud.microsoft/ --persistent --headed
   ```
   `.env`의 `MSFT_TEAMS_PERSONAL_ID` / `MSFT_TEAMS_PERSONAL_PW`로 SSO + Authenticator 승인.
3. 동시성: 다른 `-s=` 세션(Salesforce, Amaranth)과 충돌 없음. 같은 `-s=teams`는 동시 호출 시 race — 직렬화.

## 핵심 엔드포인트
```
GET https://teams.cloud.microsoft/api/csa/apac/api/v1/containers/{containerId}/posts
    ?modality=post&pageSize=20&teamId={teamId}
    &includeRcMetadata=true&filterSystemMessage=true&shouldIncludeSharedToL1Rc=true
Authorization: Bearer <chatsvcagg JWT>
→ 207 (multi-status, 정상). JSON: {posts:[{message, replies:{messages:[...], totalCount}}, ...]}
```
- `containerId` = 채널 thread id, e.g. `19:77adf...@thread.skype` (private 채널은 별도 thread.skype id).
- `teamId` = 팀의 root thread id (채널이 아니라 **팀**의 id).
- 인증: 같은 도메인 cookie + Bearer(audience: `chatsvcagg.teams.microsoft.com`).

리전(`apac`/`emea`/`amer`)은 캡처된 URL에서 그대로 차용. helper는 `apac` 하드코딩 — 다른 리전 사용자는 helper 1줄 수정.

## helper API (`pwc_teams.py`)

| 이름 | 용도 |
|---|---|
| `find_channel(s, query, navigate=True)` | 검색창(`AUTOSUGGEST_INPUT`)에 query 입력 → 첫 채널 suggestion 클릭. 반환 `{name, team, container_id, team_id}` |
| `get_bearer(s, audience='chatsvcagg')` | 캡처된 요청에서 해당 audience JWT 추출 (역순/최신 우선) |
| `channel_posts(s, container_id, team_id, page_size=20, bearer=None)` | `/posts` 직접 fetch. JSON dict 반환 |
| `parse_posts(data, since=None, until=None)` | 응답을 thread 리스트로 정규화: `{parent, parent_in_window, replies, reply_total}`. 각 메시지 = `{ts, who, text, id, type}`. `since/until`은 KST datetime |
| `today_kst()` | `(start, end)` — 오늘 00:00 / 내일 00:00 KST |

`find_channel`은 `team_id` 추출을 위해 채널 진입(navigate)이 필요 — 한 번 알아낸 `container_id`/`team_id`는 코드에 박아두고 재사용 가능(이후 `channel_posts`만 호출하면 채널 진입 불필요).

## 표준 호출

### 1) 이름으로 검색해 오늘 게시물 받기
```bash
python3 -c "
import sys; sys.path.insert(0, 'proc/lib')
from pwc import S
from pwc_teams import find_channel, channel_posts, parse_posts, today_kst

s = S('teams')
ch = find_channel(s, 'prj-경영기획-거래원장')
data = channel_posts(s, ch['container_id'], ch['team_id'])
start, end = today_kst()
for t in parse_posts(data, since=start, until=end):
    p = t['parent']
    tag = '●' if t['parent_in_window'] else '⤴'
    when = p['ts'].strftime('%H:%M') if t['parent_in_window'] else (p['ts'].strftime('%m/%d') if p['ts'] else '?')
    print(f\"{tag} [{when}] {p['who']}: {p['text'][:120]}\")
    for r in t['replies']:
        print(f\"   ↳ [{r['ts'].strftime('%H:%M')}] {r['who']}: {r['text'][:200]}\")
"
```

### 2) 알고 있는 채널 ID로 직접 (검색·진입 생략)
```python
from pwc import S
from pwc_teams import channel_posts, parse_posts
s = S('teams')
# 사전에 한번이라도 Teams 페이지 로드되어 있어야 Bearer 캡처됨
data = channel_posts(
    s,
    container_id='19:77adf8b44f9042ab8d573781509ca33a@thread.skype',
    team_id='19:cb59b09dcdc8474e9c26b8ae0e20c7d5@thread.skype',
    page_size=50,
)
threads = parse_posts(data)
```

### 3) 특정 기간 필터
```python
from datetime import datetime, timedelta
from pwc_teams import KST
since = datetime(2026, 5, 1, tzinfo=KST)
until = datetime(2026, 5, 8, tzinfo=KST)
threads = parse_posts(data, since=since, until=until)
```

## 응답 구조 메모

```json
{
  "posts": [
    {
      "containerId": "19:...@thread.skype",
      "id": "1777347778242",
      "latestMessageTime": "2026-05-07T07:52:39.802Z",
      "message": { "id":"...", "composeTime":"...", "imDisplayName":"...", "content":"<p>HTML</p>", "messageType":"RichText/Html", "properties":{ "cards":"[...]", "deletetime":... }, ... },
      "replies": { "messages":[ ...same shape... ], "totalCount": 12 }
    }, ...
  ],
  "continuationToken": "...",
  "hasMoreBackward": true
}
```
- `messageType`이 `ThreadActivity/*`이면 join/leave/topic 변경 — helper에서 자동 제외.
- `properties.deletetime` 있으면 삭제된 메시지 — 자동 제외.
- `properties.cards`(Adaptive Card) → helper가 `body[].text`만 추출해 본문 뒤에 붙임.

## 주의 / 함정

- **status 200 아니라 207** — Multi-Status. helper는 2xx 전체 통과시킴. 직접 fetch할 때 `status === 200` 체크하지 말 것.
- **Bearer audience 4종** — `/api/csa`(chatsvcagg), `/api/chatsvc`(ic3), `/api/mt`(spaces), `/api/nss`(uis). 잘못 갖다 쓰면 401. `get_bearer`는 audience 매칭으로 안전.
- **첫 호출 전에 토큰이 한 번도 캡처 안 된 상태** → `get_bearer` None. 부트스트랩 직후 또는 새 세션 시작 직후라면 `find_channel`/`open_chat` 등으로 한 번 페이지 활동을 일으켜야 함.
- **`pageSize=20`이 기본** — 더 과거는 `continuationToken` 사용 필요(현재 helper 미커버). 필요 시 helper 확장.
- **`replies.totalCount`가 `messages.length`보다 클 수 있음** — 응답에 일부만 동봉. 전체 reply는 별도 `/messages/{parentId}/replies` 호출 필요(현재 helper 미커버).
- **검색 suggestion 첫 결과 사용** — 동명 채널이 여러 개면 의도치 않은 채널 진입 가능. 모호하면 `query`에 팀명 포함하거나 `find_channel(navigate=False)`로 후보만 뽑아 검토.
- **리전 코드 하드코딩(`apac`)** — 다른 테넌트는 `pwc_teams.py:channel_posts`의 URL에서 `/csa/apac/`을 해당 리전으로 교체.
- **세션 만료** → `playwright-cli -s=teams open ... --persistent --headed`로 재로그인.

## Activity·Chat 스킬과의 관계

- Activity 알림(@멘션·반응·답글) → `/teams-activity`
- Chat 리스트(DM/그룹챗) → `/teams-activity`
- **채널 게시물(thread + 답글)** → 본 스킬 (`teams-channel`) — REST 직접 호출이 안정적이라 별도 분리.
