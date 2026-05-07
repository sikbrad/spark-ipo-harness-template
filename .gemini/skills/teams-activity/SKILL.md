---
name: teams-activity
description: Microsoft Teams web(teams.cloud.microsoft) Activity 피드(알림) 조회·분석. "Teams 알림", "Teams Activity", "나한테 온 알림", "@멘션 모아줘", "어제 누가 답글 달았어", "팀즈 알림 분석" 등 Teams 알림 관련 요청 시 사용.
---

# Microsoft Teams 알림(Activity Feed) 조회·분석

`browser-harness` + `agent_helpers.py`의 `teams_*` helper로 Teams web의 좌측 종 아이콘 Activity 피드를 긁어서 분석한다.

## 사전 조건

1. browser-harness가 사용자의 Chrome에 attach 가능한 상태.
2. `https://teams.cloud.microsoft/` 에 로그인되어 있어야 한다.
   - 미로그인 시 `.env`의 `MSFT_TEAMS_PERSONAL_ID` / `MSFT_TEAMS_PERSONAL_PW` 사용해 SSO 진행. Microsoft Authenticator 푸시 승인 단계는 화면에 뜨는 숫자를 사용자 핸드폰으로 직접 승인 (자동화 불가).
3. Teams 메인 진입 후 좌측 앱바에 Activity 버튼이 보이는 상태(`teams_ready()` True).

## API 한계 — 네트워크 캡처는 비추천

Teams web은 데이터 fetch를 **Web Worker** 안에서 수행하기 때문에 페이지 컨텍스트의 `window.fetch` 패치(`install_xhr_capture()`)로는 트래픽이 잡히지 않는다. CDP `Target.attachToTarget`으로 worker session에 직접 attach 하는 것도 daemon IPC가 타임아웃을 내며 불안정. 따라서 **DOM 스크레이핑이 가장 안정적**이다.

## DOM 셀렉터(검증됨, 2025-12 기준)

| 역할 | 셀렉터 |
|---|---|
| 좌측 앱바 Activity 버튼 | `button[aria-label*="Activity"]` (한글 UI: `button[aria-label*="활동"]`) |
| Activity 패널 컨테이너 | `[data-tid="activity-list-container"]` |
| 가상스크롤 컨테이너 | `div.virtual-tree` (이게 **실제 스크롤되는** element. `activity-list-container`는 sh==ch라 스크롤 안 됨) |
| 알림 한 줄 | `[data-tid="activity-feed-list-item"]` |
| 알림 제목 슬롯 | `[data-tid="activity-feed-item-title"]` |

각 row의 `innerText`는 줄바꿈으로 다음 정보가 이어진다:
```
{username (+N)} {action: replied to message / reacted to your message / mentioned you / posted a new message}
{message preview}
{HH:MM AM/PM 또는 5/6}
{Team or "In chat with you" 또는 "Chat with ..."}
{Channel name (Team 알림인 경우)}
```

`aria-label`은 비어있는 경우가 많아 `innerText` 파싱이 메인.

## 핵심 helper (`agent_helpers.py`)

| 이름 | 용도 |
|---|---|
| `teams_ready()` | Teams 앱 셸이 렌더되었는지(좌측 앱바 존재) |
| `teams_open_activity()` | 좌측 Activity(종) 아이콘 클릭. True/False |
| `teams_activity_items()` | 현재 DOM에 렌더된 알림 행을 dict 리스트로 추출. 키: `aria_label`/`title`/`timestamp`/`unread`/`raw_text` |
| `teams_collect_activity_full(step_px=400, max_rounds=120, pause=0.5)` | `div.virtual-tree`를 step_px씩 내리며 가상 스크롤로 누락 없이 누적 수집(중복 제거). **권장 진입점**. |
| `_teams_scroll_step(top)` | 내부용 — virtual-tree scrollTop 설정 + 메트릭 반환 |

## 표준 호출

### 1) 모든 알림 가져오기 (디폴트)

```bash
browser-harness -c "
import time
# Teams 탭으로 스위치
tabs = list_tabs()
t = next((x for x in tabs if 'teams.cloud.microsoft' in (x.get('url') or '')), None)
if not t: raise SystemExit('no Teams tab — open it first')
switch_tab(t['targetId']); time.sleep(0.8)

teams_open_activity(); time.sleep(2)
items = teams_collect_activity_full()
print(f'collected: {len(items)}')
for i, it in enumerate(items, 1):
    lines = [l for l in (it['raw_text'] or '').split('\n') if l.strip()]
    print(f'[{i}] {lines[0] if lines else \"\"}')
    for l in lines[1:]:
        print(f'    {l[:140]}')
"
```

### 2) 멘션만 필터

```bash
browser-harness -c "
import time
tabs = list_tabs()
t = next((x for x in tabs if 'teams.cloud.microsoft' in (x.get('url') or '')), None)
switch_tab(t['targetId']); time.sleep(0.8)
teams_open_activity(); time.sleep(2)
items = teams_collect_activity_full()
mentions = [it for it in items if 'mentioned' in (it['raw_text'] or '').split('\n')[0].lower()]
print(f'mentions: {len(mentions)}')
for it in mentions:
    print(it['raw_text'][:300])
    print('---')
"
```

### 3) 채널/팀별 그룹

```bash
browser-harness -c "
import time
from collections import defaultdict
tabs = list_tabs()
t = next((x for x in tabs if 'teams.cloud.microsoft' in (x.get('url') or '')), None)
switch_tab(t['targetId']); time.sleep(0.8)
teams_open_activity(); time.sleep(2)
items = teams_collect_activity_full()
buckets = defaultdict(list)
for it in items:
    lines = [l for l in (it['raw_text'] or '').split('\n') if l.strip()]
    # 마지막 1~2줄이 보통 Team / Channel 또는 'In chat with you'
    key = lines[-2] if len(lines) >= 2 else (lines[-1] if lines else 'unknown')
    buckets[key].append(lines[0])
for k, v in sorted(buckets.items(), key=lambda x: -len(x[1])):
    print(f'[{len(v)}] {k}')
    for h in v: print(f'  - {h}')
"
```

### 4) "오늘 답글만" 같은 동사별 필터

`raw_text`의 첫 줄에서 동사 추출:

| 키워드 | 의미 |
|---|---|
| `replied to message` | 채널/그룹챗 답글 |
| `reacted to your message` | 본인 메시지에 반응(이모지 등) |
| `mentioned you` | @멘션 |
| `posted a new message` | 채널 새 글(Workflows 등 봇 포함) |
| `sent a message` | 1:1 채팅 새 메시지 |

## 가상 스크롤 동작

- Activity 피드의 가상 스크롤 컨테이너는 `div.virtual-tree`. `scrollHeight=2758, clientHeight=663` 같은 식으로 일부만 렌더되고 나머지는 풀(pool)에서 재활용된다.
- 단순히 `scrollTop = scrollHeight`만 한 번 호출하면 가상 row들이 한꺼번에 교체되어 **중간 행을 놓침**. `teams_collect_activity_full()`은 step_px(기본 400)씩 점진적으로 내리며 매 step마다 `teams_activity_items()`로 누적·dedupe한다.
- 본 스킬 작성 시점 환경에선 Activity 패널이 디폴트로 ~13건만 로드(scrollHeight≈2758px). Teams 서버가 더 많은 항목을 push해야 row가 늘어나는 구조.
- "Load more" / 더 과거를 보려면 Activity 헤더의 메뉴(`activity-feed-item-media-menu` 등) 또는 필터 변경이 필요한데, 이는 미커버.

## 주의 / 함정

- **Activity 피드는 "최근 N건"만 보여줌** — 일반적으로 12~14건. 더 과거의 알림은 Teams가 자동 정리하며, web에서는 추가 페이지네이션 UI가 없을 수 있다. 더 긴 history를 원하면 Microsoft Graph API(`/me/teamwork/sentMessages` 등) 별도 권한 필요 — 본 스킬 미커버.
- **`unread` 플래그가 false로 보일 수 있음** — Teams는 Activity 패널을 한 번 열면 unread 마크가 자동 클리어된다. unread 상태로 보고 싶다면 다른 디바이스에서 안 본 상태로 두고 web을 열자마자 즉시 캡처해야 함.
- **탭 컨텍스트 고정** — Chrome에 다른 탭(특히 Salesforce/ERP)이 많으면 daemon `current_tab`이 다른 탭으로 빠지기 쉽다. 매 호출 첫머리에 `switch_tab(teams_tab['targetId'])` 명시 권장.
- **`location.reload()` 호출 시 daemon 세션 분리** — 페이지 reload는 가급적 피하고, 새 데이터가 필요하면 좌측 앱바를 Chat → Activity 순으로 클릭해 SPA 내부 fetch만 트리거.
- **로그인 풀린 상태에서는 `teams_ready()`가 False** — `login.microsoftonline.com`으로 리다이렉트 됨. 이때는 사용자가 직접 SSO + Authenticator 승인 후 진행.
- **iframe 없음, ServiceWorker 있음** — `window.fetch` 패치는 worker traffic을 못 잡는다. 외부 fetch capture에 의존하지 말 것.
- **여러 Teams 탭이 떠 있으면 첫 번째 탭이 잡힘** — 의도한 탭이 따로면 `targetId` 직접 지정.
