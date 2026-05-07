---
name: teams-activity
description: Microsoft Teams web(teams.cloud.microsoft)에서 Activity 피드(알림)와 Chat 리스트(DM/그룹) 조회·분석. "Teams 알림", "Teams Activity", "나한테 온 알림", "@멘션 모아줘", "DM 답 안 한 거", "내가 대답 안 한 메시지", "Teams 미답 채팅", "팀즈 unread", "팀즈 알림 분석" 등 Teams 알림·DM 관련 요청 시 사용.
---

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

## API 한계 — Activity는 여전히 DOM, Chat은 DOM
Teams는 fetch가 Web Worker에서 일어나는데, playwright-cli의 `requests` 명령은 CDP-native라 워커 트래픽도 잡힌다(이전 browser-harness 한계 해소). 다만:
- Activity 피드 데이터는 worker에서 렌더된 후 SignalR/WebSocket으로 push되는 구조라 일관된 REST 응답이 별로 없음 → DOM 스크레이핑이 여전히 안정적.
- Chat 리스트 동일.

`s.requests()` 로 시도해 보고, 노이즈 많으면 DOM 경로를 쓴다.

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

| 이름 | 용도 |
|---|---|
| `ready(s)` | 셸 렌더 여부 |
| `open_activity(s)` | Activity(종) 클릭 |
| `activity_items(s)` | 현재 DOM에 보이는 알림 행 |
| `collect_activity_full(s)` | virtual-tree 스크롤로 누락 없이 누적 수집 (**Activity 권장**) |
| `open_chat(s)` | Chat(채팅) 클릭 |
| `chat_list(s)` | 파싱된 chat 리스트 |
| `unanswered_chats(s, unread_only=False)` | 본인이 마지막 발화자가 **아닌** 채팅 (**DM 미답 권장**) |
| `unread_chats(s)` | Unread 배지가 있는 채팅만 |

## 표준 호출

### 1) Activity 피드 모든 알림

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

### 2) DM/Chat 미답 분석

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

### 3) Unread만

```bash
python3 -c "
import sys; sys.path.insert(0, 'proc/lib')
from pwc import S
from pwc_teams import open_chat, unread_chats
import time
s = S('teams')
open_chat(s); time.sleep(2)
for c in unread_chats(s):
    print(f\"{c['time']} | {c['name']} | {c['last_msg']}\")
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
