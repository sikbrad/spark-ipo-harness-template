---
name: teams-chat
description: Microsoft Teams web(teams.cloud.microsoft) 채팅(DM/그룹) **본문**을 내부 REST API(`/api/chatsvc/.../messages`)로 직접 받아와 파싱. "Teams DM 내용", "그룹챗 메시지 받아줘", "핑거세일즈 주문현황 1주일", "특정 채팅 본문 분석", "thread.v2 메시지 추출" 등 채팅 본문 조회 요청 시 사용. (채팅 **목록**·DM 미답 분석은 `/teams-activity`, **채널** 게시물은 `/teams-channel`.)
---

# Microsoft Teams 채팅 본문 조회 (REST 직접 호출)

`@playwright/cli` 기반. DM·그룹채팅 메시지를 **DOM 안 읽고** Teams 내부 REST로 가져온다.

## 도구 스택
- `@playwright/cli` — 사이트별 격리 세션, 워커 트래픽 캡처
- `proc/lib/pwc.py` — 세션 wrapper (`S('teams')`)
- `proc/lib/pwc_teams.py` — channel + chat helper

## 전제
1. `playwright-cli` 설치(한 번): `npm install -g @playwright/cli@latest`.
2. Teams 세션 부트스트랩(첫 1회):
   ```bash
   playwright-cli -s=teams open https://teams.cloud.microsoft/ --persistent --headed
   ```
   `.env`의 `MSFT_TEAMS_PERSONAL_ID` / `MSFT_TEAMS_PERSONAL_PW`로 SSO + Authenticator 승인.
3. **첫 호출 전에 ic3 audience Bearer 한 번은 캡처되어 있어야 함** — Teams 페이지가 한 번이라도 `/api/chatsvc/...` 호출을 일으키면 OK. (`open_chat(s)` 또는 채팅 한번 들어가는 걸로 충분)
4. 동시성: 다른 `-s=` 세션과 충돌 없음. 같은 `-s=teams`는 직렬화.

## 핵심 엔드포인트
```
GET https://teams.cloud.microsoft/api/chatsvc/apac/v1/users/ME/conversations/{threadId}/messages
    ?pageSize=200
    &startTime={epochMs}                # 선택: 이 시각 이후만
    &view=msnp24Equivalent|supportsMessageProperties
Authorization: Bearer <ic3 audience JWT>
→ 200. JSON: {messages:[{...}, ...], _metadata:{...}}
```
- `threadId` 형식
  - 그룹챗: `19:abc...@thread.v2`
  - DM: `19:abc..._def...@unq.gbl.spaces`
  - 채널 thread도 동일 엔드포인트로 호출 가능 (단, 채널은 `/teams-channel`의 `channel_posts`가 thread+replies 구조라 더 적합)
- audience: `ic3.teams.office.com` ← 채널의 `chatsvcagg`와 다르므로 토큰 잘못 쓰면 401.

## helper API (`pwc_teams.py`)

| 이름 | 용도 |
|---|---|
| `chat_thread_id_from_url(url)` | Teams 채팅 deeplink URL에서 `19:...@thread.v2`/`@unq.gbl.spaces` 추출 |
| `chat_messages(s, thread_id, since_ms=None, page_size=200, bearer=None)` | `/messages` 직접 fetch. JSON dict 반환 |
| `parse_chat_messages(data, since=None, until=None)` | flat 시간순 리스트로 정규화: `{ts, who, text, quote, id, type}`. 인용(reply blockquote) 분리, AdaptiveCard `body[].text` 본문에 합침 |
| `today_kst()` | 오늘 KST 윈도 |
| `KST` | timezone helper |

## ⚠️ 핵심 함정

- **`pageSize` 상한 200** — 201 이상 주면 서버가 **빈 배열 반환**(0건). helper가 자동 클램핑.
- **audience=ic3** — 잘못된 audience(chatsvcagg/spaces/uis) 쓰면 401. `get_bearer(s, audience='ic3')`.
- **JSON 키 lowercase** — 채팅 API는 `composetime`, `imdisplayname`, `messagetype` 등 소문자. 채널 `/posts`(camelCase)와 다름. helper는 양쪽 fallback.
- **status 200** (채널 `/posts`는 207).
- **삭제·시스템 메시지** — `properties.deletetime` 또는 `messagetype: ThreadActivity/*` → helper가 자동 제외.
- **인용/Adaptive Card** — `<blockquote itemtype="...Reply">`은 quote로 분리, AdaptiveCard `body[].text`는 본문에 합쳐짐.
- **페이지네이션 미커버** — 첫 페이지(최대 200건)만. 더 과거는 `_metadata.syncState`/추가 호출 필요(현재 helper 미커버).

## 표준 호출

### 1) URL → thread_id → 1주일치 본문
```python
import sys; sys.path.insert(0, 'proc/lib')
from pwc import S
from pwc_teams import (chat_thread_id_from_url, chat_messages,
                       parse_chat_messages, KST)
from datetime import datetime, timedelta

s = S('teams')
url = 'https://teams.cloud.microsoft/l/chat/19:a8ba842042bd4ef0a9a0a092ce048a75@thread.v2/conversations?context=...'
tid = chat_thread_id_from_url(url)

since_ms = int((datetime.now(KST) - timedelta(days=7)).timestamp() * 1000)
data = chat_messages(s, tid, since_ms=since_ms)
events = parse_chat_messages(data)

for e in events:
    print(f"[{e['ts'].strftime('%m-%d %H:%M')}] {e['who']}: {e['text'][:120]}")
    if e['quote']:
        print(f"   ↪ {e['quote']['sender']}: {e['quote']['body'][:80]}")
```

### 2) 알고 있는 thread_id로 직접 (URL 없이)
```python
data = chat_messages(s, '19:abc...@thread.v2')   # since 생략 → 전부(최대 200)
events = parse_chat_messages(data)
```

### 3) 특정 기간만
```python
from datetime import datetime
from pwc_teams import KST
since = datetime(2026, 5, 1, tzinfo=KST)
until = datetime(2026, 5, 8, tzinfo=KST)
events = parse_chat_messages(data, since=since, until=until)
```

### 4) 일별 그룹핑 + 마크다운 출력 (예: output/some.md)
```python
from collections import defaultdict
by_day = defaultdict(list)
for e in events:
    by_day[e['ts'].date()].append(e)

lines = ['# Chat dump', '']
for d in sorted(by_day):
    lines.append(f'## {d.isoformat()}  — {len(by_day[d])}건')
    for e in by_day[d]:
        ts = e['ts'].strftime('%H:%M')
        lines.append(f'**[{ts}] {e["who"]}**  ')
        if e['quote']:
            lines.append(f'> ↪ {e["quote"]["sender"]}: {e["quote"]["body"][:120]}')
        for ln in (e['text'] or '').splitlines():
            lines.append(ln)
        lines.append('')
import pathlib; pathlib.Path('output/chat.md').write_text('\n'.join(lines), encoding='utf-8')
```

## 응답 구조 메모

```json
{
  "messages": [
    {
      "id": "1778156153396",
      "sequenceId": 4196,
      "conversationid": "19:...@thread.v2",
      "messagetype": "RichText/Html",
      "contenttype": "Text",
      "imdisplayname": "김상진 Steve",
      "fromDisplayNameInToken": "김상진 Steve",
      "composetime": "2026-05-07T12:15:53.3960000Z",
      "originalarrivaltime": "2026-05-07T12:15:53.3960000Z",
      "content": "<blockquote itemtype=\"...Reply\" ...>...</blockquote>본문...",
      "properties": {
        "mentions": "[]",
        "cards": "[...]",
        "links": "[]",
        "files": "[]",
        "deletetime": <ms>          // 있으면 삭제됨
      }
    }, ...
  ],
  "_metadata": { "syncState": "...", ... },
  "tenantId": "..."
}
```

## 다른 Teams 스킬과의 분리

| 스킬 | 용도 | 데이터 소스 |
|---|---|---|
| `/teams-activity` | Activity 피드, Chat **목록**(DM 미답·unread) | DOM (가상 스크롤) |
| `/teams-channel` | 채널 게시물(thread + replies) | REST `/api/csa/.../containers/{cid}/posts` |
| **`/teams-chat`** | DM·그룹채팅 **본문** | REST `/api/chatsvc/.../messages` |

채팅 **목록**(어떤 채팅이 있는지)은 `teams-activity`, 그 안의 **본문**은 본 스킬.
