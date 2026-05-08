---
name: gmail
description: Google Gmail 메일 검색·본문 조회·**발송·라벨수정·첨부 다운로드**. 두 개 개인 계정(bispro89@gmail.com, sikbrad@gmail.com) 지원. "Gmail 검색", "지메일 받은편지함", "오늘 받은 이메일", "스타 이메일", "이번주 메일 요약", "보낸 사람 ~한테 온 메일", "메일 보내줘", "답장 보내줘", "스타 표시", "읽음 처리", "첨부 받아줘" 등 Gmail 관련 요청 시 사용. (캘린더는 `/gcal`, 드라이브는 `/gdrive`)
---

# Google Gmail 검색·조회 (Gmail API)

`google-api-python-client` + OAuth Desktop client 기반. 브라우저 0개, 헤드리스. 두 계정(bispro89/sikbrad) 각각 별도 GCP 프로젝트·refresh token 사용.

## 도구 스택
- `proc/lib/google_auth.py` — `GoogleClient(account)` (OAuth, 토큰 캐시, silent refresh)
- `proc/lib/gmail_api.py` — Gmail helper (`search`, `list_messages`, `get_message`, `parse_message`)
- `.env`의 `GOOGLE_BISPRO89_*` / `GOOGLE_SIKBRAD_*`
- 토큰 캐시: `~/.cache/dof-google-{account}.json`

## 전제
1. `pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib` (1회).
2. **첫 로그인 (계정당 1회)**:
   ```bash
   python proc/lib/google_auth.py login --account bispro89
   python proc/lib/google_auth.py login --account sikbrad
   ```
   브라우저 자동 오픈 → unverified 경고 → Advanced → 진행 → **체크박스 전부 체크** (Gmail readonly + Calendar readonly + email + profile) → 동의.
3. Refresh token은 Production 게시 → 무기한 (6개월 미사용 시만 회수). 주 1회 호출만 있어도 영원히 살아있음.

## 핵심 함수 (`gmail_api.py`)

| 함수 | 용도 |
|---|---|
| `search(g, q, max_results=50, fetch_full=True, skip_body=False)` | Gmail 쿼리 → 정규화된 메시지 list. **default 호출** |
| `list_messages(g, q, max_results, label_ids)` | id만 필요할 때 (가벼움) |
| `get_message(g, msg_id, fmt='full')` | 단일 메시지 raw |
| `parse_message(full)` | raw → 정규화 dict |
| `get_profile(g)` | 메일박스 메타(이메일, 총 메시지 수) |
| `save_json(data, path)` | 결과 저장 |

정규화 스키마:
```python
{
  'id', 'thread_id',
  'date_raw', 'ts',                # ISO datetime
  'from_name', 'from_email', 'to', 'cc', 'subject',
  'snippet',                        # Gmail's auto-extracted preview
  'body_text', 'body_html',         # 'no-body' 옵션 시 빈 문자열
  'attachments': [{filename, mime, size, attachment_id}],
  'labels': [...],
  'is_unread', 'is_starred', 'is_important', 'is_inbox',
  'category',                       # primary/social/promotions/updates/forums
}
```

## Gmail 검색 쿼리 (Gmail search syntax)

```
from:foo@bar.com               # 보낸이
to:me                          # 받는이 (me = 본인)
subject:"제목 substring"
after:2026/05/01               # YYYY/MM/DD
before:2026/05/08
newer_than:7d                  # 7일 이내
is:unread                      # 안 읽은
is:starred is:important
has:attachment
filename:pdf
in:inbox  in:sent  in:drafts
in:anywhere                    # spam/trash 포함
category:primary               # primary/social/promotions/updates/forums
-category:promotions           # 빼기
larger:5M                      # 첨부 5MB 이상
list:newsletter@x.com          # 메일링리스트
```

여러 조건 결합: 띄어쓰기 = AND, `OR` 명시, `()` 그룹화. 예: `(from:foo OR from:bar) -category:promotions newer_than:7d`.

전체 문법: https://support.google.com/mail/answer/7190

## 표준 호출

### 1) 지난주 중요 메일 + 스타 메일 받기 (요약용)
```python
import sys; sys.path.insert(0, 'proc/lib')
from google_auth import GoogleClient
from gmail_api import search, save_json

g = GoogleClient('bispro89')
msgs = search(g,
    q='after:2026/05/01 (is:starred OR is:important) -category:promotions -category:social',
    max_results=80,
)
save_json(msgs, 'output/gmail-bispro89-2026-05-01-to-08-important.json')
```

### 2) 특정 사람한테 온 메일 본문
```python
g = GoogleClient('bispro89')
msgs = search(g, q='from:cho@frix.io newer_than:30d', max_results=20)
for m in msgs:
    print(f"[{m['ts'][:10]}] {m['subject']}")
    print(m['body_text'][:500])
```

### 3) 첨부 PDF 있는 메일
```python
msgs = search(g, q='has:attachment filename:pdf newer_than:30d', skip_body=True)
for m in msgs:
    for att in m['attachments']:
        if att['mime'] == 'application/pdf':
            print(f"{m['from_email']} | {att['filename']} ({att['size']/1024:.0f}KB)")
```

### 4) 두 계정 동시 — 한쪽만 받는 알림 비교
```python
for acct in ('bispro89', 'sikbrad'):
    g = GoogleClient(acct)
    msgs = search(g, q='subject:"security alert" newer_than:14d', max_results=20)
    print(f'\n[{acct}]')
    for m in msgs:
        print(f"  {m['ts'][:16]} {m['from_email']}: {m['subject']}")
```

### 5) CLI — JSON 덤프
```bash
# 파일명은 기간/주제에 맞춰 유연하게
python proc/lib/gmail_api.py search --account bispro89 \
    --q 'from:cho@frix.io newer_than:30d' --max 30 \
    --out output/gmail-bispro89-frix-last30d.json

# 본문 없이 헤더만 (가벼움)
python proc/lib/gmail_api.py search --account sikbrad \
    --q 'after:2026/05/01 -category:promotions' --max 50 --no-body \
    --out output/gmail-sikbrad-may-w1-headers.json

# 단일 메시지
python proc/lib/gmail_api.py get --account bispro89 --id 198a3c4b5
```

## 출력 파일 컨벤션

`output/gmail-{account}-{description}.json` — description은 자유. 예시:
- `output/gmail-bispro89-2026-05-01-to-08-important.json` — 기간 명시
- `output/gmail-sikbrad-frix-poc-thread.json` — 주제별
- `output/gmail-bispro89-attachments-pdf-q2.json`

날짜·주제 따라 사용자 요청에 맞춰 이름 정할 것. 고정 패턴 강제하지 않음.

## ⚠️ 함정과 한계

- **Scope `gmail.readonly`만 grant됨**. 발송·라벨 수정은 별도 scope(`gmail.send`, `gmail.modify`) 추가 필요. `GoogleClient(..., scopes=[...])`로 호출하면 첫 호출 시 재동의 트리거.
- **본문 `body_text`는 `text/plain` 우선**, 없으면 `text/html` 강제 strip. 첨부만 있는 메시지는 빈 문자열.
- **`max_results` 큰 값은 비용 큼** — `fetch_full=True`면 메시지당 별도 API 호출. 헤더만이면 `skip_body=True` (gmail.users.messages.get format='metadata') 사용.
- **OAuth scope mismatch** — 첫 로그인 시 동의 화면에서 체크박스 빠뜨리면 `OAUTHLIB_RELAX_TOKEN_SCOPE=1` (자동 set돼있음) 덕에 token은 발급되지만 실제 API 호출 시 403. 다시 `login` 명령 + 체크박스 전부 체크.
- **Gmail rate limit**: per-user quota는 25M units/day, 메시지당 10units 정도. 일반 사용은 무관.
- **`in:anywhere`** — spam/trash 포함. 일반 검색은 inbox/sent 자동 포함.

## 다른 Google 스킬과의 분리

| 스킬 | 용도 | API |
|---|---|---|
| **`/gmail`** | Gmail 메일 검색·본문·첨부 | gmail.users.messages |
| `/gcal` | Google 캘린더 일정 | calendar.events |

두 스킬 모두 `proc/lib/google_auth.GoogleClient`를 공유 — refresh token도 같은 캐시에 누적.
