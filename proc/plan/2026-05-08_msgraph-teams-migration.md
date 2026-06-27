# MS Graph API + MSAL로 Teams 데이터 접근 마이그레이션

## 목표
playwright-cli 기반 Teams 자동화(`teams-activity`/`teams-channel`/`teams-chat`)를 **브라우저 프로세스 없이** Microsoft Graph API + MSAL device-code 플로우로 대체. 첫 로그인 1회 후 refresh token(~90일) 만으로 헤드리스 동작.

## 배경
현재 Teams 스킬은 모두 `playwright-cli -s=teams` 위에서 동작:
- 첫 부트스트랩 시 SSO + Authenticator 승인 필요
- 이후에도 매번 Chrome 띄움 → 무겁고, 토큰 만료 시 헤드리스 실행 깨짐
- 내부 endpoint(`/api/chatsvc/...`, `/api/csa/.../posts`)를 페이지 컨텍스트에서 fetch — 비공식

Graph API로 옮기면:
- 순수 `requests` 호출 (브라우저 0개)
- cron / 백그라운드 자동화 깔끔
- 공식 API → 스키마 안정적

다만 **테넌트 admin consent**가 필요한 스코프가 있어 IT 협조가 변수.

## 핵심 결정 사항

### 인증 플로우
- **MSAL Public Client + Device Code Flow**
  - `msal.PublicClientApplication.acquire_token_by_device_flow()`
  - 첫 호출 → 콘솔에 `https://microsoft.com/devicelogin` 코드 표시 → 폰에서 1회 승인
  - 이후 `acquire_token_silent()`로 자동 갱신 (refresh token 90일)
  - `MSAL_TOKEN_CACHE` 파일로 디스크 캐시

### 필요 스코프 (delegated)
| 스킬 | 필요 권한 | admin consent |
|---|---|---|
| `/teams-activity` (Activity 피드, chat list) | `Chat.ReadBasic`, `Chat.Read` | Chat.Read는 필요 |
| `/teams-channel` (채널 게시물) | `ChannelMessage.Read.All` | 필요 |
| `/teams-chat` (DM/그룹 본문) | `Chat.Read` | 필요 |
| (조직도) | `User.Read.All` | 필요 |

→ 사실상 admin consent는 불가피. **doflab IT팀에 앱 등록 + consent 요청** 필요.

### Azure AD 앱 등록 정보 (요청용 템플릿)
- App name: `dof-work-skills-graph-cli`
- Type: **Public client / native** (PKCE 사용 가능, secret 없음)
- Redirect URI: `http://localhost` (device code flow엔 사실 무의미하지만 등록은 필요)
- Required permissions (delegated):
  - `Chat.Read`
  - `ChannelMessage.Read.All`
  - `User.Read`
  - `User.Read.All` (조직도용 — optional)
  - `offline_access` (refresh token)
- Tenant: `doflab.onmicrosoft.com` (또는 doflab 테넌트 ID)

### 매핑 테이블 (현재 endpoint → Graph endpoint)

| 용도 | 현재 (chatsvc 내부 API) | Graph |
|---|---|---|
| Chat 목록 | `/api/chatsvc/.../users/ME/conversations` | `GET /me/chats?$expand=lastMessagePreview` |
| Chat 메시지 | `/api/chatsvc/.../conversations/{tid}/messages` | `GET /me/chats/{chat-id}/messages` |
| Channel 게시물 | `/api/csa/.../containers/{cid}/posts` | `GET /teams/{team-id}/channels/{channel-id}/messages` (+ `/replies`) |
| Activity 피드 | `48:notifications` 가상 conversation | Graph에 1:1 대응 없음 → `/me/chats` + `/me/teamwork/installedApps` 조합 또는 `change notifications` 구독 |
| 조직도 | `gw102A02` (아마란스) | (별개) — 아마란스는 Graph 적용 대상 아님 |

⚠️ **Activity 피드는 Graph에 직접 대응이 없음**. 옵션:
1. 각 chat의 `unreadMessageCount`를 polling — Graph가 unread 카운트 노출하나 검증 필요
2. `Microsoft.Graph.ChatMessage` change notifications (webhook) — 인프라 필요(공개 endpoint)
3. activity 자체는 빼고 unread chat 리스팅으로 대체 — 가장 현실적

### thread_id 형식 차이
- 현재: `19:abc...@thread.v2`, `19:abc..._def...@unq.gbl.spaces`
- Graph chat-id: 같은 형식 그대로 사용 가능 (`19:...@thread.v2` 등) — 변환 불필요
- Graph team/channel은 별도 GUID 필요 → 한 번 매핑 캐시 만들어둘 것

## 작업 항목

### Phase 0: 사전 조사 & IT 협의 ✅ 2026-05-08
- [x] doflab Azure 테넌트 ID 확인 → `157be4ae-85e2-465d-b741-e92c2db1df96`
- [x] Azure AD 앱 등록 (`ins@doflab.com` admin 권한으로 직접 진행, Entra admin center)
  - App name: `dof-work-skills-graph-cli`
  - **Client ID**: `dd47ab1b-ef6f-4ab3-a364-2106389890c1`
  - **Object ID**: `4bfc55b7-e65b-4a0f-984e-a40d2a0eb915`
  - Audience: Single tenant - DOF Inc.
  - Redirect URI: `Public client/native (mobile & desktop)` + `http://localhost`
  - **Allow public client flows**: Enabled ✓
- [x] Delegated permissions 일괄 추가 — admin consent 불필요한 모든 Microsoft Graph 스코프 (148개 + 기본 `User.Read`/`offline_access` 포함 150개). 주요 항목:
  - Chat: `Chat.Read`, `Chat.ReadWrite`, `Chat.Create`, `Chat.ReadBasic`, `ChatMessage.Read`, `ChatMessage.Send`
  - Channel(쓰기 측): `Channel.ReadBasic.All`, `ChannelMessage.Edit`, `ChannelMessage.Send`
  - Mail: `Mail.Read`, `Mail.ReadWrite`, `Mail.Send`, `Mail.Read.Shared` 등
  - Calendars / Files / Notes / Tasks / Contacts / Presence / People 광범위
  - 기타 Bookings, Acronym, AppCatalog 등
  - **❌ 빠진 것 (admin consent 필요)**: `ChannelMessage.Read.All`, `User.Read.All`, `Group.*`, `Directory.*`
- [x] **Grant admin consent for DOF Inc.** ✓ (모든 150개 scope 사전 승인 완료)
- [x] `.env`에 저장 (기존 `MSFT_<APP>_*` 컨벤션 따름):
  - `MSFT_MYAGENT_CLIENT_ID`
  - `MSFT_MYAGENT_TENANT_ID`
  - `MSFT_MYAGENT_OBJECT_ID`
- [ ] Graph API에서 Activity 피드 대체 가능 여부 검증 (`/me/chats?$top=...&$orderby=lastMessagePreview/createdDateTime desc` + `unreadCount`)
- [ ] **읽기 전용 채널 메시지 정책 결정**: `ChannelMessage.Read.All`은 admin consent 필요 → ① 별도 신청, ② Application permissions(인증서 기반)로 우회, ③ 채널 글은 playwright fallback 유지 중 택일

### Phase 1: 라이브러리 + 인증 모듈 ✅ 2026-05-08
- [x] `msal 1.36.0`, `requests`, `python-dotenv` 설치 (전역 pip)
- [x] `proc/lib/msgraph.py` 작성:
  - `GraphClient`: device-code 로그인, 토큰 캐시(`~/.cache/dof-msgraph-msal.json`), silent refresh
  - `get` / `post` / `patch` / `delete` / `paged` (`@odata.nextLink` 자동)
  - CLI: `python proc/lib/msgraph.py {login|whoami|logout}`
- [x] 첫 로그인 완료 — `백인식 Brad <ins@doflab.com>` ([Authority](https://login.microsoftonline.com/<tenant>) 인식 OK)
- [x] 동작 검증: `/me` 응답 OK, `/me/chats?$top=3` 정상 (group + oneOnOne 반환)
- [x] 토큰 캐시 파일 25KB 생성 → 이후 호출은 헤드리스/무인 동작

### Phase 2: Chat 마이그레이션 ✅ 2026-05-08
- [x] `proc/lib/teams_graph.py` 작성 — pwc_teams.py와 병행
- [x] `chat_list(g, top=50)` — `GET /me/chats?$top=50&$expand=lastMessagePreview&$orderby=lastMessagePreview/createdDateTime desc`
- [x] `chat_messages(g, chat_id, since=None)` — `GET /me/chats/{id}/messages` + `@odata.nextLink` 자동 페이지네이션 (`max_pages` 캡)
- [x] 응답 정규화: 기존 `parse_chat_messages` 스키마(`{ts, who, text, quote, id, type}`)와 호환
- [x] 인용(quote) 파싱: HTML `<blockquote>` 기존 정규식 재사용 (Graph가 reply HTML 그대로 노출)
- [x] AdaptiveCard: `attachments[].contentType` 검사 + content가 string이면 JSON 파싱 후 `body[].text` 합침
- [x] `find_chat(g, query)` — topic / last sender 이름 substring 매칭
- [x] `send_chat_message(g, chat_id, text, html_body=False)` — `POST /me/chats/{id}/messages` (Chat.ReadWrite 사전 승인됨)
- [x] **스킬 분리**:
  - 기존 `/teams-chat` (브라우저) → `/teams-chat-browser` 로 rename + description을 fallback 명시로 변경
  - 신규 `/teams-chat` 스킬 (Graph 기반) 작성 — `.claude/skills/teams-chat/`, `.gemini/skills/teams-chat/`
  - 두 스킬 모두 SKILL.md에 fallback 트리거 명시 (사용자 명시 지정 / Graph 실패 시)
- [x] CLAUDE.md 스킬 표 업데이트 (default + fallback 두 줄)
- [x] 동작 검증: 102 chats 목록, 조소연 DM 본문 정상 파싱(시간/quote/AdaptiveCard 포함)

### Phase 3: Channel 마이그레이션 ✅ 2026-05-08
- [x] **추가 권한**: `ChannelMessage.Read.All`, `Team.ReadBasic.All` 신청 → admin consent grant ✓
- [x] `joined_teams(g)`, `channels(g, team_id)` — raw 헬퍼
- [x] `channel_map(g, cache_path=...)` — 모든 (team, channel) 매핑 (`output/teams-channel-map.json`에 저장)
- [x] `find_channel_graph(g, query, cache=None)` — 채널/팀 이름 substring 매칭
- [x] `channel_posts(g, team_id, channel_id, since, until, page_size, max_pages, include_replies)` — `pwc_teams.parse_posts` 호환 출력
- [x] **스킬 분리**: 기존 `/teams-channel` → `/teams-channel-browser` rename + fallback 명시 / 신규 `/teams-channel` (Graph) 작성
- [x] 동작 검증: 4 teams / 28 channels / `order-web-dev` 30일치 20 threads (replies 포함) 정상

### Phase 4: Activity 대체 전략 ✅ 2026-05-08
- [x] `unanswered_chats(g, top=100)` — `/me/chats` + last_by_me=False 휴리스틱
- [x] `at_mentions(g, since, max_chats, max_msgs_per_chat)` — `mentions[].mentioned.user.id` 매칭 (N+1 polling)
- [x] **스킬 분리**: 기존 `/teams-activity` → `/teams-activity-browser` rename / 신규 `/teams-activity` (Graph 휴리스틱) 작성
- [x] 한계 명시: **Activity 피드 자체(시스템 알림 등)는 Graph 미노출** → fallback이 unique-feature 역할로 유지
- [x] 동작 검증: 52 미답 chats 휴리스틱 정상 (오늘 시점 기준)

### Phase 5: 정리 & 검증 ✅ 2026-05-08
- [x] CLAUDE.md 스킬 표 업데이트 — Graph default + browser fallback 6개 항목 (3쌍)
- [x] 모든 신규 스킬 SKILL.md에 fallback 트리거 (사용자 명시 지정 / Graph 실패) 명시
- [x] 통합 테스트:
  - DM 본문: 조소연 DM (텍스트 + AdaptiveCard + quote 모두 정상 파싱)
  - 채널 글: order-web-dev 30일치 (parent + replies)
  - 미답 분석: chat_list 기반 52건
  - 메일 1주일치: `/me/messages` 5건 정상
  - SharePoint sites enumeration: 3 sites
- [x] 토큰 caching: `~/.cache/dof-msgraph-msal.json` (25KB) — 이후 silent refresh
- [ ] **남은 항목**: 1시간 후 silent refresh 실제 검증 / cron 헤드리스 무인 실행 검증 (운영 단계)
- [ ] **남은 항목**: `pwc_teams.py`의 chat/channel API 함수에 deprecation 주석 (선택)

## 위험 / 미해결
- **admin consent 거부 / 지연** — Phase 0가 막히면 차선 (편법 옵션 2: 토큰만 빼서 requests로) 으로 후퇴 검토. 별도 문서로.
- **Graph rate limit** — 사용자 단위 throttling 있음. 채널 enumerate처럼 N+1 호출 패턴은 batch endpoint(`$batch`) 활용 필요.
- **Activity 1:1 대응 부재** — 사용자가 "오늘 알림 다" 류 요청 시 결과가 playwright 버전과 미세 차이. 스킬 문서에 명시.
- **doflab 컴플라이언스** — `Chat.Read`는 사용자의 모든 채팅 본문을 읽음. legal/IT 검토 필요.

## 참고
- MSAL Python: https://github.com/AzureAD/microsoft-authentication-library-for-python
- Graph Teams reference: https://learn.microsoft.com/graph/api/resources/teams-api-overview
- Device code flow: https://learn.microsoft.com/entra/identity-platform/v2-oauth2-device-code
