# Daily-collect 재개 메모 — 2026-05-19, 2026-05-17

## 컨텍스트
- Teams 증분 dump 완료 (2026-05-19 17:55) → `output/teams/conversations/`
  - chat 신규 166건, channel 신규 14 thread / 48 reply, 에러 0
- 그 증분이 `data/daily/` 에 반영되도록 `/daily-collect` 실행 중이었음
- 사용자 선택: **빠진 날짜만(5/17, 5/19)** 수집. 5/16·5/18 summary는 보존
- 진행 중 일시중단 — Notion dump가 백그라운드에서 계속 cache 스캔 중

## 환경 이슈 (재개 시 주의)
- **Google sikbrad 계정 OAuth scope 만료** → `gcal/gmail/gdrive --account sikbrad` 모두 `RefreshError: invalid_scope`
  - 우회: skill 규칙대로 `[]` placeholder 작성 (이미 적용됨)
  - 근본 해결: 사용자가 별도로 sikbrad OAuth 재로그인 필요
- **`gdrive_api.py` 플래그는 `--q` (스킬 문서의 `--raw-q` 아님)** — 호환 안 됨
- **`outlook.py` 클래스명은 `MailClient` (스킬 문서의 `OutlookClient` 아님)**, 메서드 `list_messages(folder, since, until, top)`
- Teams chats는 **방금 받은 full dump(`output/teams/conversations/{dm,groupchat}`)** 에서 날짜 필터로 derive하면 Graph 추가 호출 불필요 — 헬퍼: `/tmp/derive_daily_teams.py` (생성됨)
- Raindrop도 마찬가지로 dump에서 derive — 헬퍼: `/tmp/derive_daily_raindrop.py` (생성됨)

## 현재 raw 상태

### 2026-05-19 (오늘, 화요일)
| 파일 | 상태 |
|---|---|
| gcal-bispro89.json | ✅ 2B (`[]` 일정 0건 — 본인 확인) |
| gcal-sikbrad.json | ⚠️ `[]` placeholder (OAuth 만료) |
| gmail-bispro89.json | ✅ 93.4K |
| gmail-sikbrad.json | ⚠️ `[]` placeholder |
| gdrive-bispro89.json | ✅ 작성 완료 (modifiedTime filter) |
| gdrive-sikbrad.json | ⚠️ `[]` placeholder |
| outlook.json | ✅ 16.6K (11건) |
| teams-chats.json | ✅ 22.4K (6 chats / 81 messages) |
| raindrop.json | ✅ 6.1K (4건) |
| notion-jot.json | ❌ **미수집** |
| notion-edited.json | ❌ **미수집** |
| `summary.md` | ❌ **미작성** |

### 2026-05-17 (일요일)
- 이전 daily-collect 부분 실행(5/18 22:28)에서 일부 raw가 이미 있음
- 5/17이 일요일이라 Teams 0건 / Raindrop 0건은 자연스러움

| 파일 | 상태 |
|---|---|
| gcal-bispro89.json | ✅ 737B (pre-existing) |
| gcal-sikbrad.json | ⚠️ `[]` placeholder |
| gmail-bispro89.json | ✅ 542.7K (pre-existing) |
| gmail-sikbrad.json | ⚠️ `[]` placeholder |
| gdrive-bispro89.json | ✅ 2B `[]` (pre-existing) |
| gdrive-sikbrad.json | ⚠️ `[]` placeholder |
| outlook.json | ✅ 2.7K (2건, 본 세션에서 갱신) |
| teams-chats.json | ✅ 2B `[]` (0건, 일요일 정상) |
| raindrop.json | ✅ 2B `[]` (0건) |
| notion-jot.json | ✅ 28.6K (pre-existing) |
| notion-edited.json | ✅ 2.5K (pre-existing) |
| `_collected` | ✅ (pre-existing 마커) |
| `teams-standup.json` | ✅ (pre-existing, 본 skill의 표준 입력 아님 — 별도 산출물) |
| `summary.md` | ❌ **미작성** |

## 백그라운드 작업
- `bqvzbfki7` (Notion dump 전체) — 여전히 실행 중. `tail -f /tmp/notion_dump_daily.log`로 진행 확인.
  - 현재 cache 스캔 중 (450 라인 시점에 2024-08 페이지들 처리). 이미 26.9M sqlite cache 있음 → 새 페이지만 fetch.
  - 재개 시 완료 여부 먼저 확인.

## 재개 시 실행 순서

```bash
# 0) Notion dump 완료 확인
pgrep -f notion_dump || echo "done"
tail -10 /tmp/notion_dump_daily.log

# 1) 5/19 Notion Jot 페이지 찾기 (DailyJot 2026-05-19)
sqlite3 data/db/notion_state.sqlite \
  "SELECT id, title FROM notion_object
   WHERE kind='page' AND title LIKE 'DailyJot 2026-05-19%'"

# id 찾은 뒤 — page.json + blocks.json 머지해서 data/daily/2026-05-19/raw/notion-jot.json 작성
# (참고: 5/17 notion-jot.json 만들었던 동일 패턴 따라가면 됨)

# 2) 5/19 그날 편집된 페이지/DB 목록 (Jot 제외)
sqlite3 data/db/notion_state.sqlite \
  "SELECT kind, id, title, last_edited_time FROM notion_object
   WHERE last_edited_time LIKE '2026-05-19T%'
     AND (kind='page' OR kind='database')
   ORDER BY last_edited_time DESC"

# 각 page = data/notion/dump/pages/<hex>.json + (옵션) blocks/<hex>.json 머지 → notion-edited.json

# 3) summary.md 작성 — AI가 raw 한 건씩 직접 읽고 사람말로
#    구조: 하루 흐름 / 회의·캘린더 / 코딩·작업 / 입력·수집 / 커뮤니케이션 / 다음 액션
#    참고: data/daily/2026-05-18/summary.md (직전 작성 스타일 참고)
```

## 헬퍼 스크립트 (이미 생성됨)
- `/tmp/derive_daily_teams.py <YYYY-MM-DD>` — output/teams/conversations dump에서 그날 chat 본문 추출
- `/tmp/derive_daily_raindrop.py <YYYY-MM-DD>` — data/raindrop/dump/raindrops 에서 그날 북마크 추출

## 미해결 / TODO
- [ ] Notion dump 완료 대기
- [ ] 5/19 notion-jot.json 작성
- [ ] 5/19 notion-edited.json 작성
- [ ] 5/19 summary.md 작성
- [ ] 5/17 summary.md 작성
- [ ] (별건) sikbrad Google 계정 OAuth 재로그인 — 이건 사용자가 직접
