---
name: teams-activity-browser
description: (Fallback) Microsoft Teams Activity 피드(알림) — playwright-cli + 내부 REST(`48:notifications`/DOM 가상 스크롤) 방식. **Activity 피드는 Graph API에 1:1 대응이 없어 본 fallback이 default-equivalent** 역할. 사용자가 명시적으로 "브라우저로", "playwright로", "teams-activity-browser" 라고 한 경우, 또는 Graph 기반 `/teams-activity` 휴리스틱(미답 chat / @멘션)으로 충분치 않은 경우(시스템 알림 자체가 필요할 때)에 호출.
---

> **이 스킬은 fallback 입니다.** 일반적인 "DM 미답 / @멘션 모음" 분석은 `/teams-activity` (MS Graph API, 브라우저 불필요) 가 default. 하지만 **Teams Activity 피드 자체**(시스템 알림, "X님이 좋아요", 채널 멘션 알림 등)는 Graph가 노출하지 않으므로, 그게 필요하면 본 스킬을 사용한다. 또는 사용자가 "브라우저로/playwright로/teams-activity-browser" 라고 명시 지정한 경우.


# Microsoft Teams 알림 + Chat 리스트 조회·분석

`@playwright/cli` 기반. 좌측 사이드바 두 패널을 긁는다:
1. **Activity 피드**(종 아이콘) — @멘션·답글·반응 알림 스트림
2. **Chat 리스트**(채팅 아이콘) — DM/그룹챗 목록과 마지막 메시지

## 도구 스택
- `@playwright/cli` (전역 `playwright-cli` 명령) — 사이트별 격리 세션, 영속 프로필, 워커 트래픽까지 잡힘
- `proc/lib/pwc.py` — 세션 wrapper (`S('teams')`)
- `proc/lib/pwc_teams.py` — Teams 사이트 helper

## 전제
1. `playwright-cli` 설치 — 한 번만: `npm install -g @playwright/cli@latest`.
2. **Teams 세션 부트스트랩**(첫 1회):
   ```bash
   playwright-cli -s=teams open https://teams.cloud.microsoft/ --persistent --headed
   ```
   브라우저 창이 뜨면 `.env`의 `MSFT_TEAMS_PERSONAL_ID` / `MSFT_TEAMS_PERSONAL_PW` 로 SSO 진행, Microsoft Authenticator 푸시 승인. 이후 `--persistent` 디스크 프로필이 로그인 유지.
3. 동시성: 다른 `-s=` 세션(Salesforce, Amaranth)은 별개 브라우저라 충돌 없음. 같은 `-s=teams`는 동시 호출 시 race — 직렬화 필요.

## 데이터 경로 — REST(권장) + DOM(fallback)

| 패널 | REST 엔드포인트 | audience | helper |
|---|---|---|---|
| Activity 피드 | `GET /api/chatsvc/.../users/ME/conversations/48:notifications/messages` | ic3 | `activity_feed_api` + `parse_activity_feed` |
| Chat 리스트 | `GET /api/chatsvc/.../users/ME/conversations` | ic3 | `conversations_api` + `parse_conversations` |

REST 경로 장점:
- Activity는 100+ 건 (DOM은 12~14건 한계)
- Chat 리스트는 88+ (DOM은 약 35)
- `unread`/`last_by_me`가 timestamp·consumptionhorizon·JWT oid 비교 기반이라 정확
- DOM 변경에 영향 안 받음, virtual-scroll race 없음

DOM 경로는 (a) 사용자가 보는 화면 그대로의 결과만 필요한 좁은 use case, (b) REST 호출 실패 시 fallback.

## DOM 셀렉터 (Dec 2025 검증)

### Activity 피드
| 역할 | 셀렉터 |
|---|---|
| Activity 버튼 | `button[aria-label*="Activity"]` (한글: `[*="활동"]`) |
| 패널 컨테이너 | `[data-tid="activity-list-container"]` |
| 가상스크롤 컨테이너 | `div.virtual-tree` ← **실제 스크롤 element** |
| 알림 한 줄 | `[data-tid="activity-feed-list-item"]` |

### Chat 리스트
| 역할 | 셀렉터 |
|---|---|
| Chat 버튼 | `button[aria-label*="Chat"]` (한글: `[*="채팅"]`) |
| chat row | `[role="treeitem"]` (단, x좌표 50–360, height 30–130 필터) |

Chat row `innerText`는 **`\n` 구분자**:
```
[Unread]      # (옵션) 미열람 배지
{name}        # 사람 이름 또는 그룹명
{time}        # "4:19 PM" / "5/6"
{last_msg}    # 마지막 메시지 (그룹이면 "발신자: 본문")
```

`last_msg`가 `You: `/`나: `로 시작하면 본인이 마지막 발화.

## 핵심 helper (`proc/lib/pwc_teams.py`)

### 권장 — REST API

| 이름 | 용도 |
|---|---|
| `activity_feed_api(s, page_size=200)` | `48:notifications` 가상 conversation의 messages를 GET. raw JSON 반환 |
| `parse_activity_feed(data)` | `[{ts, who, type, subtype, preview, location, location_kind, source_thread_id, source_message_id, unread, id}]` (newest first) |
| `conversations_api(s, page_size=100)` | `/users/ME/conversations` 전체 chat 디렉토리 |
| `parse_conversations(data, exclude_system=True, me_id=None)` | `[{thread_id, kind, name, last_msg_preview, last_who, last_ts, last_by_me, unread, group}]`. `me_id` = JWT oid 기반 mri (`my_user_id(s)`) |
| `unanswered_chats_api(s, unread_only=False)` | `last_by_me=False` 채팅만 |
| `my_user_id(s)` | 캡처된 Bearer JWT의 `oid` 클레임에서 `8:orgid:<oid>` mri 추출 |

### Fallback — DOM 스크레이핑

| 이름 | 용도 |
|---|---|
| `ready(s)` | 셸 렌더 여부 |
| `open_activity(s)` | Activity(종) 클릭 |
| `activity_items(s)` | 현재 DOM에 보이는 알림 행 |
| `collect_activity_full(s)` | virtual-tree 스크롤로 누락 없이 누적 수집 |
| `open_chat(s)` | Chat(채팅) 클릭 |
| `chat_list(s)` | 파싱된 chat 리스트 |
| `unanswered_chats(s, unread_only=False)` | 본인이 마지막 발화자가 아닌 채팅 |
| `unread_chats(s)` | Unread 배지가 있는 채팅만 |

## 표준 호출 — API (권장)

### 1) Activity 피드 — 최근 알림 (정렬 desc)

```bash
python3 -c "
import sys; sys.path.insert(0, 'proc/lib')
from pwc import S
from pwc_teams import activity_feed_api, parse_activity_feed
s = S('teams')
events = parse_activity_feed(activity_feed_api(s, page_size=100))
print(f'collected: {len(events)}')
for e in events[:30]:
    flag = '🔴' if e['unread'] else '  '
    ts = e['ts'].strftime('%m-%d %H:%M') if e['ts'] else '?'
    print(f\"{flag} {ts} {e['type']:8} {e['who'][:15]:15} | {e['location'][:30]:30} | {e['preview'][:70]}\")
"
```

### 2) @멘션만 필터 — API

```bash
python3 -c "
import sys; sys.path.insert(0, 'proc/lib')
from pwc import S
from pwc_teams import activity_feed_api, parse_activity_feed
s = S('teams')
events = parse_activity_feed(activity_feed_api(s, page_size=200))
mentions = [e for e in events if e['type'] == 'mention' or e['subtype'] == 'mention']
for e in mentions:
    print(f\"{e['ts']:%m-%d %H:%M} {e['who']} @ {e['location']}: {e['preview'][:120]}\")
"
```

### 3) Chat 리스트 / 미답 채팅 — API

```bash
python3 -c "
import sys; sys.path.insert(0, 'proc/lib')
from pwc import S
from pwc_teams import unanswered_chats_api
s = S('teams')
for c in unanswered_chats_api(s):
    flag = '🔴' if c['unread'] else '  '
    ts = c['last_ts'].strftime('%m-%d %H:%M') if c['last_ts'] else '?'
    print(f\"{flag} {c['kind']:7} {ts} | {c['name'][:25]:25} | {c['last_who'][:12]}: {c['last_msg_preview'][:60]}\")
"
```

### 4) Unread만 — API

```bash
python3 -c "
import sys; sys.path.insert(0, 'proc/lib')
from pwc import S
from pwc_teams import conversations_api, parse_conversations, my_user_id
s = S('teams')
me = my_user_id(s)
chats = parse_conversations(conversations_api(s), me_id=me)
for c in [x for x in chats if x['unread']]:
    print(f\"{c['kind']:7} | {c['name']} | {c['last_who']}: {c['last_msg_preview'][:80]}\")
"
```

## 표준 호출 — DOM (Fallback)

### 5) DOM Activity 피드 (가상스크롤 누적)

```bash
python3 -c "
import sys; sys.path.insert(0, 'proc/lib')
from pwc import S
from pwc_teams import open_activity, collect_activity_full
import time
s = S('teams')
open_activity(s); time.sleep(2)
items = collect_activity_full(s)
print(f'collected: {len(items)}')
for i, it in enumerate(items, 1):
    lines = [l for l in (it['raw_text'] or '').split('\n') if l.strip()]
    print(f'[{i}] {lines[0] if lines else \"\"}')
    for l in lines[1:]:
        print(f'    {l[:140]}')
"
```

### 6) DOM 미답 채팅

```bash
python3 -c "
import sys; sys.path.insert(0, 'proc/lib')
from pwc import S
from pwc_teams import open_chat, unanswered_chats
import time
s = S('teams')
open_chat(s); time.sleep(2)
for c in unanswered_chats(s):
    flag = '🔴' if c['unread'] else '  '
    typ = 'GRP' if c['group'] else 'DM '
    print(f\"{flag} {typ} {c['time']:>9} | {c['name'][:25]:<25} | {c['last_msg'][:90]}\")
"
```

### 4) @멘션만 필터

```bash
python3 -c "
import sys; sys.path.insert(0, 'proc/lib')
from pwc import S
from pwc_teams import open_activity, collect_activity_full
import time
s = S('teams')
open_activity(s); time.sleep(2)
items = collect_activity_full(s)
mentions = [it for it in items if 'mentioned' in (it['raw_text'] or '').split('\n')[0].lower()]
for it in mentions:
    print(it['raw_text'][:300]); print('---')
"
```

## 가상 스크롤 동작
Activity 피드의 스크롤 컨테이너는 `div.virtual-tree`(`scrollHeight`>`clientHeight`인 element). 단순히 끝까지 스크롤하면 가상 row가 한꺼번에 교체되어 중간이 누락됨. `collect_activity_full()`은 step_px(기본 400)씩 점진적으로 내리며 매 step마다 dedupe 누적.

## 주의 / 함정

### 공통
- **로그인 풀린 상태** → `playwright-cli -s=teams open ... --persistent --headed` 로 재로그인.
- **여러 탭** → `s.tab_list()` 로 확인, `s.tab_select(idx)` 로 전환. browser-harness와 달리 다른 사이트 세션 간섭 없음.
- **워커 fetch 캡처는 가능** — `s.requests()`가 잡지만 Activity/Chat은 결국 DOM 스크레이핑이 안정적.

### Activity 피드
- "최근 N건"만 노출 — 일반 12~14건. 더 과거는 Microsoft Graph API 별도 권한 필요(미커버).
- `unread` 플래그는 패널을 한 번 열면 자동 클리어 — 정확한 unread 상태 캡처는 페이지 진입 직후 즉시.

### Chat 리스트
- Chat row innerText 구분자는 **`\n`**, `|`로 split하면 안 잡힘.
- `group` 플래그는 휴리스틱 — 이름에 `and ` / `+` / `📢`가 있으면 group. 커스텀 그룹명은 DM으로 오분류될 수 있음.
- "You: " 접두 = 본인 마지막 발화. 한국어 UI는 `나: `도 처리.
- Bot 채팅(Jira Cloud 등)도 unanswered에 포함 — caller가 필요하면 `name`으로 별도 필터.
- chat 리스트도 가상스크롤 — 더 과거 채팅은 좌측 리스트 영역을 스크롤한 뒤 재호출 필요(현재 helper 미커버).
