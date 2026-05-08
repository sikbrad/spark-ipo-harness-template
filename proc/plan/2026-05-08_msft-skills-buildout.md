# MSFT 스킬 풀 빌드 (Outlook · SharePoint · OneDrive · Teams 채널 쓰기)

## 목표
이미 발급된 `MSFT_MYAGENT` Graph 토큰을 이용해 회사 MSFT 자산 전 영역에 대한 read+write 스킬을 만든다. **destructive 동작은 매 단계 사용자 승인** 후에만 실행.

## 스코프 매핑 (이미 사전 승인됨)

| 스킬 | 핵심 Graph scope | 상태 |
|---|---|---|
| `/outlook` | `Mail.Read`, `Mail.ReadWrite`, `Mail.Send` | 권한 있음, helper/스킬 미구현 |
| `/sharepoint` | `Sites.Read.All`, `Files.Read.All` | 권한 있음, 스킬 미구현 |
| `/onedrive` | `Files.ReadWrite`, `Files.Read.All` | 권한 있음, 스킬 미구현 |
| `/teams-channel` 쓰기 | `ChannelMessage.Send` | 권한 있음, helper만 추가 |

## 테스트 정책
- **READ 테스트**: 자유 실행 (영향 없음)
- **WRITE 테스트**: 매번 사용자에게 메시지 본문/파일 내용을 보여주고 승인 받은 후 실행
- 테스트 후 생성된 파일·메시지는 사용자가 정리 결정 (자동 cleanup 안 함)
- 모든 테스트 자료는 `output/msft-test-<skill>-<date>/` 에 사본 저장 (디버깅용)

## 작업 항목 — 모두 완료 ✅ 2026-05-08

### Phase A: Outlook 스킬 ✅
- [x] `proc/lib/outlook.py` — `MailClient` (init from `GraphClient`):
  - `list_messages(folder='inbox', q=None, since=None, top=50)` — `/me/messages` + `$search`/`$filter`
  - `get_message(msg_id, with_body=True)` — 본문 fetch
  - `download_attachments(msg_id, dest_dir)` — 첨부 다운로드
  - `send_mail(to, subject, body, cc=None, html=False, attachments=None)` — `/me/sendMail`
  - `reply(msg_id, body, html=False)` — `/me/messages/{id}/reply`
  - `move(msg_id, dest_folder_id_or_name)` — `/me/messages/{id}/move`
  - `mark_read(msg_id, read=True)`, `flag(msg_id)`
- [x] `.claude/skills/outlook/SKILL.md` + `.gemini/skills/outlook/SKILL.md`
- [x] CLAUDE.md 표 추가
- **테스트**: 1주일치 받은 편지함 list (read), 본인에게 테스트 메일 1건 발송 (write — **승인 필요**)

### Phase B: SharePoint 스킬
- [x] `proc/lib/sharepoint.py` — `SharePointClient`:
  - `list_sites(query='*', top=20)` — `/sites?search=...`
  - `get_site(site_id_or_path)` — `/sites/{id}` 또는 `/sites/{host}:/sites/{path}`
  - `list_drives(site_id)` — 사이트의 document libraries
  - `list_items(drive_id, path='/')` — 폴더 내용
  - `download_file(drive_id, item_id_or_path, dest)` — 파일 다운로드
  - `search(query, top=20)` — 전체 검색
- [x] `.claude/skills/sharepoint/SKILL.md` + `.gemini`
- [x] CLAUDE.md 표 추가
- **테스트**: doflab 사이트 enumerate (read), 첫 번째 사이트의 첫 번째 파일 다운로드 (read)

### Phase C: OneDrive 스킬
- [x] `proc/lib/onedrive.py` — `OneDriveClient` (`/me/drive` 기반):
  - `list_root()`, `list_folder(path)`
  - `get_item(path_or_id)`
  - `download(path_or_id, dest)`
  - `upload(local_path, remote_path, conflict='rename')` — `/me/drive/root:/path:/content`
  - `create_folder(path)`
  - `delete(path_or_id)` — **승인 필요**
  - `share(path_or_id, scope='view')` — 공유 링크 생성
- [x] `.claude/skills/onedrive/SKILL.md` + `.gemini`
- [x] CLAUDE.md 표 추가
- **테스트**: 루트 list (read), 작은 텍스트 파일 업로드 (write — **승인**), 같은 파일 다운로드 verify, 삭제 (write — **승인**)

### Phase D: Teams 채널 쓰기 helper
- [x] `teams_graph.py` 에 `send_channel_message(g, team_id, channel_id, text, html_body=False)` 추가
- [x] `reply_channel_message(g, team_id, channel_id, parent_id, text)` 추가
- [x] `/teams-channel` SKILL.md 에 쓰기 섹션 추가
- **테스트**: 안전한 테스트 채널(예: AX Team의 onboarding-ax 또는 신규 thread) 글 1건 (write — **승인**)

### Phase E: 정리
- [x] CLAUDE.md 스킬 표 갱신 — 4개 신규 row
- [x] 본 plan md에 모든 테스트 결과 누적 기록 (시간·결과·생성된 파일·메시지 ID)
- [x] 본 작업 모두 완료 후 사용자에게 정리·삭제 결정 요청

## 테스트 로그

### Outlook
| 시각 | 종류 | 결과 |
|---|---|---|
| 2026-05-08 ~15:30 | READ | `list_folders()` 11개, `list_messages('inbox', since=2d)` 5건 200ms, `q='입금'` 검색 242ms, `get_message(body=True)` 3.3s |
| 2026-05-08 15:31 | **WRITE (승인됨)** | `send_mail` to `ins@doflab.com` — 본인에게 테스트 메일 1건. **Sent 15:31:42 → Inbox 15:31:48**. 사용자 결정에 따라 정리 |

### SharePoint
| 시각 | 종류 | 결과 |
|---|---|---|
| 2026-05-08 ~15:35 | READ | `list_sites('*', top=20)` 2.0s, `list_drives(DOF Inc.)` 698ms (3 라이브러리), `list_items(root)` 474ms, search 'AX' 2.2s (5 hits) |
| 2026-05-08 ~15:36 | READ (download) | `download_file('team.config.json', 31B)` → `output/sp-test/team.config.json`, 533ms |

### OneDrive
| 시각 | 종류 | 결과 |
|---|---|---|
| 2026-05-08 ~15:38 | READ | `drive_info()` 10GB used / 1TB. `list_root()` 13 entries 366ms. `search('test')` 5 hits 1844ms |
| 2026-05-08 ~15:40 | **WRITE (승인됨)** | full smoke cycle — folder 생성·파일 업로드 (141B)·다운로드 md5 MATCH·share-link·삭제. 휴지통으로 정리됨 (verify removed OK). 추가 파일 잔존물 없음 |

### Teams 채널 쓰기
| 시각 | 종류 | 결과 |
|---|---|---|
| 2026-05-08 15:40 | **WRITE (승인됨)** | AX Team / `onboarding-ax` 에 `send_channel_message` 1건 (id=1778222450676) 812ms + `reply_channel_message` 1건 (id=1778222451098) 458ms. **두 메시지 채널에 잔존 — 사용자가 Teams 웹UI에서 정리 결정** |

## 외부 잔존물 (사용자 정리 필요)

- **Outlook**: ins@doflab.com 의 받은편지함 + 보낸편지함에 `[TEST] outlook.py send_mail smoke test (2026-05-08)` 1건씩 — 검토 후 삭제 가능
- **Teams (AX Team / onboarding-ax)**: 테스트 메시지 1건 + thread reply 1건 (5/8 ~15:40) — Teams 웹에서 우클릭 → 삭제 가능
  - 부모 메시지 webUrl: `https://teams.microsoft.com/l/message/...1778222450676`
  - reply webUrl: `https://teams.microsoft.com/l/message/...1778222451098`
- **OneDrive**: 자동 정리됨 (잔존 없음)
- **SharePoint**: read-only이라 잔존 없음
- **로컬**: `/tmp/onedrive_smoke_test.txt`, `/tmp/onedrive_roundtrip.txt`, `output/sp-test/team.config.json` — 필요 없으면 그냥 삭제

## 4개 스킬 + 1개 helper 추가 산출물

- `proc/lib/outlook.py` — Outlook(Mail) helper
- `proc/lib/sharepoint.py` — SharePoint Online helper (read 전용)
- `proc/lib/onedrive.py` — OneDrive 개인 드라이브 helper (read+write)
- `proc/lib/teams_graph.py` — `send_channel_message`, `reply_channel_message` 추가
- `.claude/skills/outlook/SKILL.md` + `.gemini/...`
- `.claude/skills/sharepoint/SKILL.md` + `.gemini/...`
- `.claude/skills/onedrive/SKILL.md` + `.gemini/...`
- `.claude/skills/teams-channel/SKILL.md` 갱신 (쓰기 섹션 추가)
- CLAUDE.md 스킬 표에 3행 추가 (`/outlook`, `/sharepoint`, `/onedrive`)
