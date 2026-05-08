---
name: gcal
description: Google Calendar 일정 조회·**생성·수정·삭제·RSVP·free/busy**. 두 개 개인 계정(bispro89@gmail.com, sikbrad@gmail.com) 지원. "구글캘", "구글 캘린더 일정", "이번 주 일정", "내 캘린더", "5월 일정 받아줘", "오늘 회의 뭐 있어", "X일에 시간 비어?", "free busy", "회의 잡아줘", "Meet 미팅 만들어줘", "일정 삭제", "이벤트 옮겨줘" 등 캘린더 관련 요청 시 사용. (메일은 `/gmail`, 드라이브는 `/gdrive`)
---

# Google Calendar 일정 조회 (Calendar API)

`google-api-python-client` + OAuth Desktop client 기반. 브라우저 0개. 두 계정 각각 별도 GCP 프로젝트·refresh token. 한 계정 안에서 여러 캘린더(primary + 공유) 자동 aggregate.

## 도구 스택
- `proc/lib/google_auth.py` — `GoogleClient(account)` (`/gmail`과 공유)
- `proc/lib/gcal_api.py` — Calendar helper (`list_calendars`, `list_events`, `events_in_range`, `free_busy`)
- `.env`의 `GOOGLE_BISPRO89_*` / `GOOGLE_SIKBRAD_*`
- 토큰 캐시: `~/.cache/dof-google-{account}.json` (gmail과 동일 파일 — 둘 다 같은 OAuth 클라이언트)

## 전제
1. `pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib` (1회).
2. **첫 로그인** (계정당 1회) — `/gmail` 스킬 동의 시 calendar.readonly 같이 체크돼있다면 별도 안 해도 됨. 안 했다면:
   ```bash
   python proc/lib/google_auth.py login --account bispro89
   ```
   브라우저 → unverified 경고 → Advanced → **Calendar 체크박스 포함 전부 체크**.

## 핵심 함수 (`gcal_api.py`)

| 함수 | 용도 |
|---|---|
| `list_calendars(g, hide_holidays=False)` | calendarList — primary + 공유받은 캘린더들 |
| `list_events(g, calendar_id, time_min, time_max, q=None, include_declined=False)` | 단일 캘린더 events list, auto-pagination, 거절(self=declined) 자동 제외 |
| `events_in_range(g, since, until, calendars='all', skip_declined=True, skip_holidays=True, q=None)` | **default** — 모든 visible 캘린더에서 [since, until] 구간 aggregate |
| `free_busy(g, since, until, calendars=('primary',))` | 시간대별 free/busy 슬롯 |
| `parse_event(ev, calendar_summary)` | 단일 이벤트 정규화 |
| `save_json(data, path)` | 결과 저장 |

정규화 스키마:
```python
{
  'id', 'calendar', 'summary',
  'start', 'end',                  # ISO datetime or YYYY-MM-DD (all_day)
  'all_day',
  'location', 'description',
  'organizer', 'creator',
  'attendees': [{email, name, response, self}],
  'self_response',                  # accepted/declined/tentative/needsAction
  'recurring_event_id',
  'status',
  'html_link',                      # 이벤트 deep link
  'hangout_link', 'conference_url', # Meet/Zoom 링크 (있으면)
  'updated',
}
```

날짜 입력은 유연:
- `'2026-05-08'` — KST 자정. `until`이면 23:59:59.
- `'2026-05-08T13:00'` — KST 13:00.
- ISO with tz (`'2026-05-08T13:00+09:00'` or `Z`) — 그대로.

## 표준 호출

### 1) 임의 기간 일정 (모든 캘린더 aggregate)
```python
import sys; sys.path.insert(0, 'proc/lib')
from google_auth import GoogleClient
from gcal_api import events_in_range, save_json

g = GoogleClient('bispro89')
events = events_in_range(g, '2026-05-01', '2026-05-08')
save_json(events, 'output/gcal-bispro89-2026-05-01-to-08.json')

for e in events:
    print(f"{e['start'][:16]}  {e['summary']}  [{e['calendar']}]")
```

### 2) 특정 캘린더만
```python
events = events_in_range(g, '2026-05-01', '2026-05-31',
                         calendars=['primary'])              # primary만
# 또는 특정 ID들
events = events_in_range(g, '2026-05-01', '2026-05-31',
                         calendars=['team@dofinc.com', 'primary'])
```

### 3) 키워드 검색
```python
events = events_in_range(g, '2026-01-01', '2026-12-31', q='POC')
```

### 4) Free/busy — 약속 잡기 전 시간 비어있나
```python
fb = free_busy(g, '2026-05-12T09:00', '2026-05-12T18:00')
busy = fb['calendars']['primary']['busy']  # [{start, end}, ...]
```

### 5) 두 계정 동시 (총합 일정)
```python
all_events = []
for acct in ('bispro89', 'sikbrad'):
    g = GoogleClient(acct)
    evs = events_in_range(g, '2026-05-01', '2026-05-08')
    for e in evs:
        e['account'] = acct
    all_events.extend(evs)
all_events.sort(key=lambda e: e.get('start') or '')
```

### 6) CLI — JSON 덤프
```bash
# 파일명 자유 — 기간이나 주제에 맞춰
python proc/lib/gcal_api.py events --account bispro89 \
    --since 2026-05-01 --until 2026-05-08 \
    --out output/gcal-bispro89-may-w1.json

# primary만
python proc/lib/gcal_api.py events --account sikbrad \
    --since 2026-05-12T09:00 --until 2026-05-12T18:00 \
    --calendar primary

# 캘린더 목록
python proc/lib/gcal_api.py calendars --account bispro89

# free/busy
python proc/lib/gcal_api.py freebusy --account bispro89 \
    --since 2026-05-12T09:00 --until 2026-05-12T18:00
```

## 출력 파일 컨벤션

`output/gcal-{account}-{description}.json` — description 자유. 예시:
- `output/gcal-bispro89-2026-05-01-to-08.json` — 기간
- `output/gcal-sikbrad-q2-meetings.json` — 분기
- `output/gcal-bispro89-poc-search.json` — 키워드 검색 결과

## ⚠️ 함정과 한계

- **All-day 이벤트는 `start`/`end`가 `YYYY-MM-DD`** (datetime 아님). 시간 비교 시 `all_day` 플래그 확인.
- **`recurring_event_id` 있으면 반복 이벤트의 instance**. `singleEvents=True` 자동 사용해서 발생한 모든 인스턴스를 평탄화 — 반복 패턴 자체가 필요하면 `singleEvents=False`로 raw 받아야.
- **공유 캘린더 거부됨** — 권한 없는 캘린더는 `events.list` 시 403. `events_in_range` 자동 skip + stderr로 경고만 출력.
- **`include_declined=False` (default)** — 본인이 거절한 이벤트는 자동 제외. `self_response='declined'` 기준. 미응답(`needsAction`) / 잠정(`tentative`)는 포함.
- **Holiday 캘린더 자동 제외** — `*@group.v.calendar.google.com` 중 'holiday' 포함 ID는 skip (한국 공휴일 자동으로 시각적 노이즈).
- **시간대** — 입력은 KST 가정 (no-tz일 때). 응답의 `start`/`end`는 캘린더 timeZone 기준 ISO. Aggregating 시 비교는 문자열 ISO 정렬 (대부분 동작).
- **Calendar API quota**: per-user 1M req/day. 일반 사용은 무관.

## 다른 Google 스킬과의 분리

| 스킬 | 용도 | API |
|---|---|---|
| `/gmail` | Gmail 메일 검색·본문·첨부 | gmail.users.messages |
| **`/gcal`** | Google 캘린더 일정·free/busy | calendar.events |

두 스킬 모두 `proc/lib/google_auth.GoogleClient`를 공유.

회사 일정(MS Outlook/Teams calendar)은 별개 시스템 — `MSFT Graph (calendar)`로 따로 처리해야 함 (현 프로젝트엔 미구현).
