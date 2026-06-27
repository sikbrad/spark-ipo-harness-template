# Gmail + Google Calendar API 접근 — 토큰 발급 & 헤드리스 구현 계획

## 목표
사용자(`ins@doflab.com` 또는 별도 개인 Google 계정)의 **Gmail 메시지**와 **Google Calendar 일정**을 코드(`proc/lib/`)에서 직접 읽고/쓰기. 첫 1회 OAuth 동의 후 refresh token 만으로 헤드리스 동작 — MS Graph(`msgraph.py`)와 동일한 패턴.

## 배경
- 회사 메일은 Microsoft 365(`doflab.com`)이지만, 사용자가 **별도 개인 Google 계정**(예: `@gmail.com`)의 메일/캘린더를 조회하길 원함.
- 회사 도메인이 Google Workspace를 같이 쓰는지 여부에 따라 인증 옵션이 달라짐 → **확인 필요**(아래 "선결 질문" 참조).
- MS Graph는 device-code flow + MSAL 캐시였는데, Google은 **`InstalledAppFlow` + `token.json`** 캐시가 동일 역할.

## 선결 질문 (사용자 확인 필요)
1. **어느 Google 계정?**
   - (A) 개인 `@gmail.com` (consumer) — 가장 일반적. OAuth 외부 사용자 타입.
   - (B) `doflab.com`이 Google Workspace도 운영 중 → 회사 워크스페이스 계정. 내부 사용자 타입 가능(verification 면제).
2. **권한 범위**
   - 읽기 전용으로 충분?(주말 메일 요약, 일정 조회) → `gmail.readonly` + `calendar.readonly`
   - 보낼 일도 있음? → `gmail.send`, `calendar.events`(쓰기)
3. **Cloud 프로젝트**
   - 기존 사용자 본인 GCP 프로젝트 있나? 없으면 신규 무료 생성 필요.

---

## 핵심 결정 사항

### 인증 플로우 — OAuth 2.0 Installed Application Flow
- **Client type**: `Desktop app` (PKCE, secret 필요 없음 — 노출돼도 사용자 동의 없이는 무용)
- **첫 호출**: `google_auth_oauthlib.flow.InstalledAppFlow.run_local_server(port=0)`
  - 로컬 임시 HTTP 서버 + 시스템 브라우저 자동 오픈 → 사용자가 Google 로그인 + scope 동의 → redirect로 코드 수신 → 토큰 교환
  - SSH/헤드리스 환경이면 `flow.run_console()` (deprecated 됐지만 아직 동작) 또는 OOB 코드 수동 복사 패턴
- **이후**: `Credentials.from_authorized_user_file(token_path)` → `creds.refresh(Request())` 자동 갱신
- **캐시 파일**: `~/.cache/dof-google-token.json` (MS Graph 캐시와 동일 위치 컨벤션)

### 필요 스코프 (delegated, 사용자 본인 데이터)
| 용도 | scope | sensitivity |
|---|---|---|
| Gmail 메시지 읽기 | `https://www.googleapis.com/auth/gmail.readonly` | **restricted** ⚠️ |
| Gmail 라벨/읽음 처리 | `https://www.googleapis.com/auth/gmail.modify` | **restricted** ⚠️ |
| Gmail 메시지 발송 | `https://www.googleapis.com/auth/gmail.send` | **sensitive** |
| Calendar 이벤트 읽기 | `https://www.googleapis.com/auth/calendar.readonly` | **sensitive** |
| Calendar 이벤트 쓰기 | `https://www.googleapis.com/auth/calendar.events` | **sensitive** |
| 프로필(이메일/이름) | `openid email profile` | non-sensitive |

⚠️ **restricted scopes**(Gmail의 `readonly`/`modify`/`compose`/`metadata`)는 Production 게시 시 Google **CASA 보안 평가**(연간 $5K~) 요구. 본인 1인 사용에는 불필요 — Testing 모드 또는 Workspace 내부 앱으로 우회.

### 게시 상태 vs Refresh Token TTL — **이게 핵심 변수**
| 게시 상태 | Refresh Token TTL | 비고 |
|---|---|---|
| **Testing**(외부 사용자) | **7일** ⚠️ | 매주 재로그인 필요 — 실용성 낮음 |
| **Production**(외부, 미인증) | 무기한* | 사용자 한도 100명, 동의화면에 "확인되지 않은 앱" 경고 — 본인만 쓰면 OK |
| **Production**(외부, 인증됨) | 무기한 | Google 검증(brand verification + sensitive scope justification + 도메인 소유 증명). Restricted scope이면 CASA 추가 |
| **Internal**(Workspace) | 무기한 | Workspace 도메인 사용자만, verification 면제 |

\* "사용자가 비밀번호 변경 + Gmail scope 포함" 시 토큰 회수, "6개월 미사용" 회수 — 일반 운용엔 영향 없음.

**권장 경로** (1인 본인 사용):
1. (B) Workspace면 → **Internal** 게시. 가장 단순.
2. (A) 개인 Gmail이면 → **External + Production**(미인증). 동의 화면 1회 "Advanced > Go to <앱이름> (unsafe)" 클릭으로 진입. 이후 무기한.
3. Testing 모드는 7일마다 끊겨서 cron 자동화에 부적합 — 피할 것.

### 라이브러리
```
google-api-python-client    # 서비스 객체 (gmail/calendar)
google-auth                  # Credentials, refresh
google-auth-oauthlib         # InstalledAppFlow
google-auth-httplib2         # transport
```
- 설치: `pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib`
- MS Graph는 `msal + requests`였는데, Google은 위 4개 패키지가 표준 — REST 직접 호출보다 client lib 권장(quota/retry/배치 내장).

### `.env` 컨벤션 — 두 계정 식별 가능하게 (계정 local-part로 구분)
```
## Google OAuth Desktop client - 개인 Gmail/Calendar API 접근 (registered 2026-05-08)
# bispro89@gmail.com
GOOGLE_BISPRO89_PROJECT_ID=bold-bastion-495705-i4
GOOGLE_BISPRO89_CLIENT_ID=...apps.googleusercontent.com
GOOGLE_BISPRO89_CLIENT_SECRET=GOCSPX-...
GOOGLE_BISPRO89_TOKEN_PATH=/Users/gq/.cache/dof-google-bispro89.json
# sikbrad@gmail.com
GOOGLE_SIKBRAD_PROJECT_ID=pelagic-pod-495705-r2
GOOGLE_SIKBRAD_CLIENT_ID=...apps.googleusercontent.com
GOOGLE_SIKBRAD_CLIENT_SECRET=GOCSPX-...
GOOGLE_SIKBRAD_TOKEN_PATH=/Users/gq/.cache/dof-google-sikbrad.json
```
- credentials.json 파일은 **만들지 않음** — client_id/secret을 .env에 직접 박고, `GoogleClient(account='bispro89')`가 환경변수 읽어서 InstalledAppFlow에 dict로 넘김.
- token.json (refresh token 캐시)은 계정별 `~/.cache/dof-google-{account}.json` 으로 분리. `.gitignore` 처리는 `.cache/` 외부라 무관.

---

## 작업 항목

### Phase 0: GCP 프로젝트 + OAuth 클라이언트 ✅ 2026-05-08
- [x] **사용자 확인**: 두 개 개인 Gmail 계정 — `bispro89@gmail.com`, `sikbrad@gmail.com`. 두 계정 모두 동일 셋업 (별도 GCP 프로젝트, 별도 OAuth 클라이언트, 별도 refresh token).
- [ ] **사용자 확인**: 필요 권한 범위 (읽기만 vs 발송 포함) — 첫 로그인 때 `--scopes` CLI 인자로 결정 예정. 일단 readonly 셋으로 시작 권장.
- [x] **`bispro89@gmail.com`** 셋업 (playwright-cli `-s=google-bispro` 세션):
  - Project: `dof-work-skills` / **Project ID: `bold-bastion-495705-i4`**
  - Gmail API ✓ enabled, Calendar API ✓ enabled
  - OAuth consent screen: External, App name `dof-work-skills-cli`, support+contact email `bispro89@gmail.com`
  - Publishing status: **In production** ✓ (refresh token 무기한)
  - OAuth client: `dof-work-skills-desktop` (Desktop app)
  - Client ID: `REDACTED.apps.googleusercontent.com`
  - Client secret: `GOCSPX-REDACTED` (생성 직후 dialog에서 캡처)
- [x] **`sikbrad@gmail.com`** 셋업 (playwright-cli `-s=google-sikbrad` 세션):
  - Project: `dof-work-skills` / **Project ID: `pelagic-pod-495705-r2`**
  - Gmail API ✓ enabled, Calendar API ✓ enabled
  - OAuth consent screen: External, App name `dof-work-skills-cli`, support+contact email `sikbrad@gmail.com`
  - Publishing status: **In production** ✓
  - OAuth client: `dof-work-skills-desktop` (Desktop app)
  - Client ID: `REDACTED.apps.googleusercontent.com`
  - Client secret: `GOCSPX-REDACTED` (Add client secret로 추가 발급 — 생성 직후 dialog 닫아서 원본 secret 캡처 못함)
- [x] `.env`에 두 계정 분리 저장 (`GOOGLE_BISPRO89_*`, `GOOGLE_SIKBRAD_*`)
- [x] playwright-cli persistent 세션 살아있음 — 다음 작업 시 재로그인 불요 (`-s=google-bispro`, `-s=google-sikbrad`)

> ⚠️ **Gotcha — client secret은 생성 순간 1회만 평문 노출됨.** Google이 2024 후반부터 client secret hashing 적용해서, 생성 dialog 닫으면 다시 못 봄. 닫혔으면 "Add client secret"으로 추가 secret 발급해서 받으면 됨 (secret 1개당 최대 2개까지 동시 보유 가능). `console.cloud.google.com/auth/clients/{id}?project=...` 화면에서 "Information and summary" 버튼 → "Add client secret".

### Phase 1: 라이브러리 + 인증 모듈 ✅ 2026-05-08
- [x] 패키지 설치: `google-api-python-client`, `google-auth-httplib2`, `google-auth-oauthlib` (pyenv 3.14.2)
- [x] `proc/lib/google_auth.py` 작성:
  - `class GoogleClient(account: str, scopes=None, token_path=None)` — `_ACCOUNTS` 딕셔너리로 alias→env prefix 매핑 (`bispro89`/`sikbrad`)
  - env에서 `GOOGLE_{ACCOUNT}_CLIENT_ID` / `_CLIENT_SECRET` / `_PROJECT_ID` / `_TOKEN_PATH` 읽음 (credentials.json 파일 안 만듦; `_client_config()`가 dict로 즉석 생성)
  - `credentials()` — token.json 캐시 로드 → expired면 `creds.refresh(Request())` → 없으면 raise (interactive 강제 회피)
  - `login()` — `InstalledAppFlow.run_local_server(port=0, prompt='consent')` 풀 플로우, 토큰 저장(perm 600)
  - `service(api, version)` — `build()` 호출 + `cache_discovery=False`
  - `whoami()` — oauth2 userinfo
  - CLI: `python proc/lib/google_auth.py {login|whoami|logout} --account {bispro89|sikbrad} [--scopes ...]`
  - shortform scope 지원 (`gmail.readonly` → `https://www.googleapis.com/auth/gmail.readonly`)
- [x] **`OAUTHLIB_RELAX_TOKEN_SCOPE=1`** import 시 자동 set — Google 토큰 endpoint가 scope 순서 정규화하면 oauthlib가 Warning을 exception으로 띄우는 문제 우회 (canonical workaround)
- [x] 동작 검증:
  - bispro89: `python proc/lib/google_auth.py login --account bispro89` → 백인식 <bispro89@gmail.com> ✓ — Gmail 166,118건, 캘린더 11개 (primary `bispro89@gmail.com`)
  - sikbrad: `python proc/lib/google_auth.py login --account sikbrad` → Brad Sik <sikbrad@gmail.com> ✓ — Gmail 27,949건, 캘린더 3개 (primary `sikbrad@gmail.com`)
- [x] 토큰 캐시 파일 생성 — `~/.cache/dof-google-bispro89.json`, `~/.cache/dof-google-sikbrad.json` (각 ~899B, perm 600)

> 💡 **Google 동의화면 gotcha**: 2024년부터 sensitive scope들은 동의 화면에서 **개별 체크박스로 표시**, 사용자가 체크 안 하면 그 scope만 빠진 채 토큰 발급. 첫 시도에서 user가 gmail/calendar 체크 안 했더니 userinfo만 잡혀서 oauthlib mismatch exception. 재시도 + 체크박스 전체 체크로 해결. 첫 로그인 안내 시 "Select all" 또는 모든 박스 체크 강조 필요.

### Phase 2: Gmail 모듈 ✅ 2026-05-08
- [x] `proc/lib/gmail_api.py` 작성:
  - `search(g, q, max_results=50, fetch_full=True, skip_body=False)` — **default 호출**, list+parse 결합
  - `list_messages(g, q, max_results, label_ids)` — id only (가벼움)
  - `get_message(g, msg_id, fmt='full')` — raw
  - `parse_message(full)` — multipart 재귀 walk, text/plain 우선 + html strip fallback, 첨부 메타 추출
  - `get_profile(g)` — 메일박스 이메일/총 메시지 수
  - `save_json(data, path)` — 출력 helper
- [x] 정규화 스키마: `{id, thread_id, ts, from_name, from_email, to, cc, subject, snippet, body_text, body_html, attachments[], labels[], is_unread, is_starred, is_important, is_inbox, category}`
- [x] CLI: `python proc/lib/gmail_api.py {search|get|profile} --account {bispro89|sikbrad} [--q ...] [--max ...] [--out ...] [--no-body]`
- [x] 동작 검증: bispro89 5월 1주차 important+starred 3건 추출 OK
- [ ] 발송(`gmail.send` scope), 라벨 수정(`gmail.modify`) — 필요 시 추가. 현재는 readonly

### Phase 3: Calendar 모듈 ✅ 2026-05-08
- [x] `proc/lib/gcal_api.py` 작성:
  - `list_calendars(g, hide_holidays=False)` — calendarList enumerate
  - `list_events(g, calendar_id, time_min, time_max, q, include_declined=False)` — 단일 캘린더, `singleEvents=True` 평탄화, `nextPageToken` auto
  - `events_in_range(g, since, until, calendars='all'|'primary'|[ids], skip_declined=True, skip_holidays=True, q)` — **default**, 모든 visible 캘린더 aggregate
  - `free_busy(g, since, until, calendars=('primary',))` — busy 슬롯
  - `parse_event(ev, calendar_summary)` — 정규화
- [x] 정규화 스키마: `{id, calendar, summary, start, end, all_day, location, description, organizer, creator, attendees[], self_response, recurring_event_id, status, html_link, hangout_link, conference_url, updated}`
- [x] 날짜 입력 유연 — `'YYYY-MM-DD'` (KST 자정/EOD), `'YYYY-MM-DDTHH:MM'` (KST), ISO with tz
- [x] CLI: `python proc/lib/gcal_api.py {calendars|events|freebusy} --account ... --since ... --until ... [--out ...]`
- [x] 동작 검증: bispro89 5월 1주차 6 events (JJBB_shared 가족 캘린더 + 공휴일 자동 제외)

### Phase 4: Skill 작성 ✅ 2026-05-08
- [x] `.claude/skills/gmail/SKILL.md` (`.gemini/skills/gmail/SKILL.md` 미러) — `/gmail` 트리거: "Gmail 검색", "지메일", "오늘 받은 이메일", "스타 이메일", "이번주 메일 요약" 등
- [x] `.claude/skills/gcal/SKILL.md` (`.gemini/skills/gcal/SKILL.md` 미러) — `/gcal` 트리거: "구글캘", "이번 주 일정", "내 캘린더", "X일에 시간 비어?", "free busy" 등
- [x] 두 스킬 모두 Gmail 검색 syntax / 캘린더 입력 형식 / 표준 호출 5개 / 함정·한계 / 출력 파일 컨벤션(`output/{gmail|gcal}-{account}-{description}.json`, description 자유) 문서화
- [x] CLAUDE.md 스킬 표에 두 줄 추가
- [x] 자동 디스커버리 확인 — 두 스킬 모두 `/gmail`, `/gcal`로 trigger 가능

### Phase 5: Write 확장 + Drive 추가 ✅ 2026-05-08
사용자 요청 — 발송·이벤트생성·문서조작까지. 양 계정 동의 화면에서 추가 scope grant.
- [x] **Drive API 활성화** — bispro89(`bold-bastion-495705-i4`), sikbrad(`pelagic-pod-495705-r2`) 양쪽 (playwright-cli 세션 재활용)
- [x] **`google_auth.py`의 `_DEFAULT_SCOPES`** 확장 — readonly 셋 → full r/w 셋:
  - `gmail.modify` (read + label + drafts, NOT send/permadelete) + `gmail.send` (send only)
  - `calendar` (full r/w)
  - `drive` (full r/w — restricted tier)
  - `openid` + `userinfo.email` + `userinfo.profile` (식별)
- [x] **양 계정 재로그인** — token cache 삭제 + login 재실행. 동의 화면에 7개 권한 (스토리지·드라이브·캘린더·메일·send·email·profile) 체크박스로 표시 — 사용자가 모두 체크. Production 미검증이라 "Advanced > Continue (unsafe)" 통과.
- [x] **`gmail_api.py` 확장** — write API 추가:
  - `send_message(g, to, subject, body_text, body_html, cc, bcc, attachments, thread_id, in_reply_to)` — `EmailMessage` 빌드 → base64url → `users.messages.send`
  - `download_attachment(g, msg_id, attachment_id, out_path)` — base64url 디코드, binary write
  - `mark_read` / `mark_unread` / `star` / `unstar` / `archive` / `trash_message` / `modify_labels(add, remove)`
  - `search_all_accounts(accounts, q, ...)` — 멀티 계정 aggregate, 결과에 `account` 태그
  - CLI: `attach`, `send`, `label` 추가 (기존 `search`/`get`/`profile`에 더해)
- [x] **`gcal_api.py` 확장** — event 쓰기 추가:
  - `create_event(g, summary, start, end, calendar_id, description, location, attendees, all_day, send_updates, add_meet)` — `add_meet=True`면 Google Meet 자동 생성
  - `update_event(g, event_id, calendar_id, patch=, summary=, start=, end=, ...)` — 부분 patch
  - `delete_event(g, event_id, calendar_id, send_updates)`
  - `respond_to_event(g, event_id, 'accepted'|'declined'|'tentative'|'needsAction')` — RSVP
  - `events_in_range_all_accounts(accounts, since, until, ...)` — 멀티 계정 aggregate, 결과에 `account` 태그
  - CLI: `create`, `delete`, `respond` 추가
- [x] **`gdrive_api.py` 신규** — full Drive 조작:
  - `search(name_contains, name_equals, mime, parent, starred, trashed, raw_q, max_results, order_by, include_shared_drives)` — friendly mime alias (document/sheet/presentation/folder/pdf/image)
  - `get_file`, `download` (binary), `export_doc(format='markdown'|'pdf'|'docx'|'csv'|...)` (Docs/Sheets/Slides 변환)
  - `upload(src, folder_id, target_name, convert_to_doc=False)` — `convert_to_doc=True`면 .docx → Google Doc
  - `create_folder`, `create_doc(name, content, parent_id)`, `update_metadata(name=, starred=, add_parents=, remove_parents=)` (이름·별·이동), `update_doc_text` (Doc 본문 통째 교체)
  - `trash` (휴지통, 30일 복구) / `delete_permanent` (즉시·복구불가)
  - `about(g)` — quota
  - CLI: `search`/`get`/`download`/`export`/`upload`/`mkdir`/`doc-create`/`trash`/`about`
- [x] **`.claude/skills/gdrive/SKILL.md` + `.gemini/skills/gdrive/SKILL.md`** 작성 — `/gdrive` 트리거: "구글 드라이브", "Drive 파일 찾아줘", "문서 만들어줘", "Google Doc 만들기", "PDF 업로드", "Sheet 다운로드" 등
- [x] 기존 `/gmail` `/gcal` SKILL.md description frontmatter 갱신 — write 능력 명시 (트리거 키워드 추가: "메일 보내줘", "회의 잡아줘" 등)
- [x] CLAUDE.md 스킬 표 — `/gmail`, `/gcal` 능력 갱신 + `/gdrive` 신규 줄 추가
- [x] 동작 검증:
  - bispro89 Drive `about`: 1.77TB 사용 / 5.50TB limit (Google One 가입자) ✓
  - sikbrad Drive `about`: 5.29GB / 5.50TB ✓ + 가족공유 storage pool 확인
  - sikbrad Drive `search(mime='document')`: 1건 (`PerplexityMemo`) ✓

### Phase 6: 정리 & 운영 (남은 작업)
- [ ] `.gitignore`에 `*credentials*.json`, `*token*.json` 추가 확인
- [ ] 토큰 갱신 시나리오: 1시간(access token TTL) 후 `refresh_token`으로 silent refresh 검증
- [ ] cron/launchd 시나리오: 헤드리스 환경에서 캐시된 token.json만으로 무인 실행
- [ ] **6개월 미사용 회수 방지**: cron으로 주 1회 `gmail.users.getProfile` ping 추가하거나, 자연스러운 사용 빈도면 무시
- [ ] (옵션) Google Docs API (`docs.googleapis.com/v1/documents`) 정밀 편집 helper — 특정 paragraph만 교체, 표 셀 수정, 댓글 처리. 현재 `update_doc_text`는 통째 교체만

---

## 위험 / 미해결
- **Testing→Production 전환 깜빡** — 7일마다 토큰 만료로 cron 자동화 망가짐. Phase 0에서 반드시 Production publish.
- **Gmail restricted scope + Production 미인증** — 동의 화면에 "unverified app" 경고 + Advanced 클릭 한번 필요. 본인만 쓰면 무관.
- **회사 정책** — `ins@doflab.com`이 Google 계정과 연결돼 있고 회사 IT가 OAuth 앱 통제하는 경우 admin 차단 가능. doflab Workspace를 안 쓰면 무관.
- **개인 Gmail 본문 노출** — `gmail.readonly`는 모든 메시지(receipts, OTP, 금융) 읽음. 토큰 파일 권한 600으로.
- **Workspace의 Calendar 공유 캘린더** — 회사 Outlook/Teams 캘린더는 Google에서 안 보임 (별개 시스템). MS Graph로 따로 처리.

---

## MS Graph(`msgraph.py`)와의 비교

| 항목 | MS Graph | Google API |
|---|---|---|
| 인증 라이브러리 | `msal` | `google-auth-oauthlib` |
| 첫 로그인 | device code (콘솔에 코드 표시) | local server (브라우저 자동 오픈) |
| 토큰 캐시 | `~/.cache/dof-msgraph-msal.json` | `~/.cache/dof-google-token.json` |
| Refresh TTL | 90일 | 무기한(Production), 7일(Testing) |
| Admin consent | 일부 scope 필요 (`Chat.Read`, `Mail.Read` 등) | 본인 데이터는 사용자 동의로 충분 — Workspace org admin은 OAuth 앱 차단 정책만 적용 |
| Client secret | public client = 없음 | desktop app = 있음(노출돼도 안전) |
| HTTP 호출 | 직접 `requests.get('https://graph.microsoft.com/v1.0/...')` | `service.users().messages().list(userId='me').execute()` (client lib) |

---

## 참고
- Gmail API quickstart: https://developers.google.com/gmail/api/quickstart/python
- Calendar API quickstart: https://developers.google.com/calendar/api/quickstart/python
- OAuth 2.0 for installed apps: https://developers.google.com/identity/protocols/oauth2/native-app
- Refresh token 정책: https://developers.google.com/identity/protocols/oauth2#expiration
- Scope 목록: https://developers.google.com/identity/protocols/oauth2/scopes
- 앱 검증(Production): https://support.google.com/cloud/answer/13463073
- CASA 보안 평가(restricted scopes): https://appdefensealliance.dev/casa
