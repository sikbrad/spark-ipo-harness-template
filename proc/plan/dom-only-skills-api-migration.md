# Plan: 순수 DOM 스킬 → API 보강

작성: 2026-05-08

## 1. 전체 스킬 데이터 경로 진단

| 스킬 | 헬퍼 | 데이터 경로 | API 가능성 |
|---|---|---|---|
| amaranth-acc-balance | `acc3020_query` | 서명 POST 재사용 | ✅ 이미 API |
| amaranth-acc-ledger | `acc3030_query` | 서명 POST 재사용 | ✅ 이미 API |
| amaranth-approval | `approval_docs` | XHR(`eap105A04`) 캡처 | ✅ 이미 API |
| amaranth-resource | `resource_bookings` | XHR(`rs121A05`) 캡처 | ✅ 이미 API |
| amaranth-org | `search_org` | 다이얼로그 + XHR(`gw102A02`) 캡처 | ✅ 이미 API |
| salesforce-record | `record_lineitems` | Aura RPC 캡처 + `while(1);` strip | ✅ 이미 API |
| teams-channel | `channel_posts` | `/api/csa/.../posts` 직접 fetch | ✅ 이미 API |
| teams-chat | `chat_messages` | `/api/chatsvc/.../messages` 직접 fetch | ✅ 이미 API |
| **amaranth-calendar** | `calendar_list_rows`, `calendar_events`, `dev_events` | 🔴 **순수 DOM** (`<table>` rows 스크레이핑) | 미확인 |
| **teams-activity** | `activity_items`, `collect_activity_full`, `chat_list_raw`, `chat_list` | 🔴 **순수 DOM** (virtual-tree / treeitem 스크레이핑) | 미확인 |

→ 미API 후보: **`amaranth-calendar`** + **`teams-activity`** (Activity 피드 + Chat 리스트 두 패널)

## 2. 두 후보 비교

| 측면 | amaranth-calendar | teams-activity |
|---|---|---|
| 스크레이핑 대상 | 일정 목록 테이블(월별) | Activity 피드 + Chat 리스트 |
| 데이터량 | 월 100~수백 행 | Activity 12~14건 한계 / Chat 35건 |
| DOM 한계 | 월별 페이지네이션, 목록 view 전환 필요 | Virtual scroll race, unread 자동 클리어, 항목 수 한계 |
| 추정 엔드포인트 | `/sc111A03` 또는 `/gw101*` 류 (DOF 내부 명명) | `/api/csa/...` 또는 `/api/chatsvc/...` 류 |
| 영향 | 연구소·팀 일정 쿼리 효율 ↑ | 알림·미답 채팅 분석 정확도 ↑ |

→ **둘 다 진행**. 계열별로 분리해서 병렬 PR 형태로.

## 3. 단계별 계획

### Step 1 — 엔드포인트 정찰 (각 스킬당)

**amaranth-calendar**:
- 일정 페이지 진입 → 월/일 변경 → 목록 view 전환 → `s.requests()` dump
- 후보 키워드: `cal`, `sc111`, `sched`, `gw10*A*`, `bk0*`
- 응답 구조 분석 (resultData / map / list / 행 필드 매핑)

**teams-activity**:
- Activity 패널 클릭 → `s.requests()` dump
- 후보 키워드: `alert`, `feed`, `notif`, `activity`, `mention`
- Chat 패널 클릭 → `s.requests()` dump
- 후보 키워드: `conversations`, `chat`, `recent`

### Step 2 — helper 구현

**`pwc_amaranth.py`에 추가**:
```python
def calendar_query(s, ystart_yyyymmdd, end_yyyymmdd) -> dict
def parse_calendar(data) -> list[dict]   # 기존 calendar_events와 같은 shape
def dev_events_api(s, start, end) -> list  # research_members + calendar_query 결합
```

**`pwc_teams.py`에 추가**:
```python
def activity_feed_api(s, page_size=50, bearer=None) -> dict
def parse_activity_feed(data) -> list[dict]

def recent_chats_api(s, top=50, bearer=None) -> dict
def parse_chat_list_api(data) -> list[dict]   # name, last_msg, last_by_me, unread, group, thread_id
```

기존 DOM 헬퍼는 보존 (이름 동일) → backward compat.

### Step 3 — 스킬 MD 업데이트

각 스킬 MD에 "API 경로(권장)" 섹션 추가. 기존 DOM 경로는 fallback으로 명기.

### Step 4 — 테스트 (parity)

- 같은 시점에 DOM·API 둘 다 호출 → 결과 비교
- `len(api) >= len(dom)` (API가 더 많거나 같아야 함)
- 첫 N개 항목의 핵심 필드(시간, 발신자, 제목) 일치 여부 spot-check
- unread 플래그 일관성

테스트 스크립트는 일회성 → `output/_test_*.py` 또는 inline python (커밋 X)

### Step 5 — 정리·커밋

각 스킬별로 분리 커밋 권장:
- `feat(amaranth-calendar): add REST API path (calendar_query)`
- `feat(teams-activity): add REST API path (activity_feed_api, recent_chats_api)`

또는 묶어서:
- `feat: add REST API path to DOM-only skills (amaranth-calendar, teams-activity)`

## 4. 위험 / 함정

- **엔드포인트 못 찾을 수도** — Activity 데이터가 SignalR/WebSocket push 위주면 REST 빈약. 그 경우 DOM 유지 + 견고화.
- **Bearer audience 미스매치** — Teams는 4종 audience. 잘못 쓰면 401.
- **status 207** — chatsvcagg 계열은 207. helper에서 2xx 통과.
- **pageSize 서버 한도** — chat=200, activity 미지수.
- **DOF ERP 서명 헤더** — 직접 fetch는 601. 캡처-재사용 패턴(`_amaranth_latest_auth` + `_amaranth_post`) 필수.
- **세션 만료** → `--persistent --headed`로 재로그인.

## 5. Plan B (REST 못 찾는 경우)

- 가능하면 IndexedDB 캐시 추출(`cdp Storage.getDatabaseNames`).
- 그도 안 되면 DOM 유지 + 더 견고한 스크롤 + retry.

## 6. 진행 순서

1. **이 plan 확정** → 진행
2. amaranth-calendar 정찰 → 구현 → 테스트
3. teams-activity 정찰 → 구현 → 테스트
4. 최종 커밋

각 단계가 끝날 때마다 plan 파일에 결과 노트 추가.

## 7. 완료 기준

- [x] amaranth-calendar: `calendar_bootstrap` + `calendar_query` + `parse_calendar` + `dev_events_api` 추가
- [x] teams-activity: `activity_feed_api` + `parse_activity_feed` + `conversations_api` + `parse_conversations` + `unanswered_chats_api` + `my_user_id` 추가
- [x] 양쪽 스킬 MD 업데이트 (.claude + .gemini 미러)
- [x] 실측 결과: API 결과가 DOM 대비 우월 (parity 만족)
- [ ] 커밋

## 8. 실행 결과 (2026-05-08)

### 엔드포인트

**amaranth-calendar**:
- `POST https://erp.doflab.com/schres/sc111A03` (events)
- `POST https://erp.doflab.com/gw/APIHandler/gw114A14` (holidays — 부수)
- 인증: SPA-bound HMAC sign 헤더, 직접 fetch 시 601 → 캡처+재사용 필수
- body: `{companyInfo, startDate, endDate, mySchYn, calList[], tcalList[], acalList[], ...}`
- resp: `{resultData:{resultList:[{schSeq, schTitle, calTitle, startDate, endDate, partName, createName, alldayYn, delYn, ...}]}}`

**teams-activity**:
- `GET /api/chatsvc/apac/v1/users/ME/conversations/48:notifications/messages` — Activity 피드 (`properties.activity` JSON에 `activityType`, `sourceUserImDisplayName`, `messagePreview`, `activityContext.ClumpTitle`)
- `GET /api/chatsvc/apac/v1/users/ME/conversations` — Chat 디렉토리 (`lastMessage`, `properties.lastimreceivedtime`, `properties.consumptionhorizon`, `threadProperties.topic`)
- audience: `ic3.teams.office.com`
- me_id: 캡처된 Bearer JWT의 `oid` 클레임 → `8:orgid:<oid>` mri

### 실측 (2026-05-08 KST)

| 패널 | DOM | API | 비율 |
|---|---|---|---|
| amaranth-calendar (5월) | ~50건 (목록 뷰 한달) | **226건** (지난달 시작~다음달 끝) | 4.5x |
| amaranth-calendar dev events | 부분 | **41건 (5월)** | 누락 없음 |
| teams-activity Activity | 12~14 (UI 한계) | **100+** | 7x+ |
| teams-activity Chats | ~35 | **88** | 2.5x |
| `last_by_me` 정확도 | "You:"/"나:" 접두 휴리스틱 | JWT oid 비교 | ✅ 정확 |
| `unread` 정확도 | UI 배지(열면 자동 클리어) | `lastimreceivedtime` vs `consumptionhorizon[0]` | ✅ 영구 |

### 신규 helper

`pwc_amaranth.py`:
- `calendar_bootstrap(s, wait=5.0) -> int`
- `calendar_query(s, start_yyyymmdd, end_yyyymmdd, my_only=False) -> Optional[dict]`
- `parse_calendar(data) -> list[dict]`
- `dev_events_api(s, start, end) -> list[dict]`

`pwc_teams.py`:
- `activity_feed_api(s, page_size=200, bearer=None) -> dict`
- `parse_activity_feed(data) -> list[dict]`
- `conversations_api(s, page_size=100, bearer=None) -> dict`
- `parse_conversations(data, exclude_system=True, me_id=None) -> list[dict]`
- `unanswered_chats_api(s, exclude_system=True, unread_only=False) -> list[dict]`
- `my_user_id(s) -> Optional[str]`
- [ ] 커밋
