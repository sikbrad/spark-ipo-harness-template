---
name: outlook
description: 회사 Outlook (Office 365) 메일 검색·본문·첨부·**발송·답장·이동·읽음/플래그·삭제** — MS Graph API. "Outlook 메일", "회사 메일 보내줘", "Outlook 검색", "받은편지함", "X에게 답장", "메일 옮겨줘", "읽음 처리", "첨부 다운로드" 등 회사 메일 관련 요청 시 사용. 개인 Gmail은 `/gmail`.
---

# Outlook 메일 (MS Graph API)

회사 메일은 본 스킬, 개인 Google 메일은 `/gmail`. 둘은 토큰 분리.

## 도구 스택
- `proc/lib/msgraph.py` — `GraphClient` (MSAL device-code, 토큰 캐시)
- `proc/lib/outlook.py` — `MailClient` (folders/list/get/send/reply/move/flag/markRead/delete)

## 전제
1. Graph 첫 로그인 (`python3 proc/lib/msgraph.py login`).
2. 사전 승인된 권한: `Mail.Read`, `Mail.ReadWrite`, `Mail.Send` (admin consent ✓).
3. 토큰 캐시 `~/.cache/dof-msgraph-msal.json`. 다른 MSFT 스킬과 공유.

## 핵심 endpoint

```
GET /v1.0/me/mailFolders
GET /v1.0/me/mailFolders/{folder}/messages?$top=50&$orderby=receivedDateTime desc
GET /v1.0/me/messages/{id}
GET /v1.0/me/messages/{id}/attachments
POST /v1.0/me/sendMail
POST /v1.0/me/messages/{id}/reply | replyAll | forward | move
PATCH /v1.0/me/messages/{id}   # isRead, flag, categories...
DELETE /v1.0/me/messages/{id}
```

`folder`: `inbox`, `sentitems`, `drafts`, `deleteditems`, `archive`, `junkemail` 같은 well-known 이름 그대로 사용 가능. 사용자 정의 폴더는 `MailClient.folder_id(name)`이 displayName으로 lookup.

## helper API (`outlook.py`)

| 메서드 | 용도 |
|---|---|
| `list_folders()` | 메일함 목록 |
| `list_messages(folder='inbox', q=None, since=None, until=None, top=50, order_by=..., select=...)` | 정규화된 dict 리스트 — `{id, subject, from, to, cc, received_ts, is_read, has_attachments, importance, preview, web_link, conversation_id, parent_folder_id, categories, flag}`. `q` 사용 시 $search, 아니면 $filter+$orderby |
| `get_message(id, with_body=True, body_type='text'|'html')` | 위 + `body` 추가 |
| `list_attachments(id)` | metadata only |
| `download_attachments(id, dest_dir)` | fileAttachment 일괄 저장 (referenceAttachment/itemAttachment skip) |
| `send_mail(to, subject, body, cc=, bcc=, html=, attachments=, save_to_sent=True)` | `'Name <a@b>'` 또는 `'a@b'` 모두 OK |
| `reply(id, body, html=, reply_all=)` | 그래프 reply/replyAll. text는 `comment`, html은 message.body |
| `forward(id, to, comment='')` | |
| `mark_read(id, read=True)`, `flag(id, status='flagged'|'complete'|'notFlagged')` | PATCH |
| `move(id, dest_folder)` | 폴더명 또는 id |
| `delete(id)` | DELETE — 휴지통으로 이동 |

## 표준 호출

### 1) 1주일치 받은편지함 + 발신자별 그룹
```python
import sys; sys.path.insert(0, 'proc/lib')
from datetime import datetime, timedelta
from outlook import MailClient, KST
from collections import Counter

mc = MailClient()
since = datetime.now(KST) - timedelta(days=7)
mails = mc.list_messages('inbox', since=since, top=200, max_pages=10)
senders = Counter(m['from'] for m in mails)
for s, c in senders.most_common(10):
    print(f'{c:3} {s}')
```

### 2) 키워드 검색 + 본문 fetch
```python
hits = mc.list_messages('inbox', q='입금', top=10)
for m in hits[:3]:
    full = mc.get_message(m['id'], with_body=True, body_type='text')
    print(full['subject'])
    print(full['body'][:300])
    print('---')
```

### 3) 메일 보내기 (텍스트 + 첨부)
```python
mc.send_mail(
    to=['이병익 <lbi@doflab.com>'],
    subject='회의록 공유',
    body='어제 미팅 메모 첨부합니다.',
    attachments=['output/meeting-notes.md'],
)
```

### 4) HTML 답장
```python
mc.reply(msg_id, body='<p>확인했습니다. 감사합니다.</p>', html=True)
```

### 5) 자동 분류: 'TODO' 카테고리 + read 처리
```python
for m in mc.list_messages('inbox', q='action required', top=20):
    mc.flag(m['id'], status='flagged')
    mc.mark_read(m['id'], read=False)
```

## ⚠️ 함정

- **`$top` 상한 50**. 더 받으려면 `max_pages` 늘리거나 `since`로 좁히기.
- **`q`($search) 사용 시 `$filter`/`$orderby` 무시됨** — 검색은 relevance 순, 시간 필터 못 거는 게 표준.
- **`$search`는 본문/제목/from 모두** — "입금"으로 검색하면 본문에 "입금자명" 들어간 dofshop 메일도 hit. 원치 않으면 `$filter` (예: `subject:eq '입금'`) 별도 사용.
- **HTML reply의 컨벤션이 미묘** — Graph가 `comment` 와 `message.body.content` 둘을 다르게 다룸. helper는 html=True면 `message.body`만 보냄.
- **첨부 4MB 초과** — 단순 base64 inline 안 됨. uploadSession 별도 (이 helper는 미커버).
- **delete는 deleteditems 폴더로 이동**. 영구 삭제는 폴더 안에서 다시 delete.

## 실패 시 fallback
- 401/403 → token silent refresh 실패 → `python3 proc/lib/msgraph.py login` 재실행
- 503/Throttling → 잠시 후 재시도
- Graph 점검 시 → 회사 Outlook 웹 직접 사용 (별도 스킬 없음)

## 다른 메일 스킬과의 분리

| 스킬 | 메일함 | 인증 |
|---|---|---|
| **`/outlook`** | 회사 ins@doflab.com (Office 365) | Graph + MSAL |
| `/gmail` | 개인 bispro89/sikbrad@gmail.com | Google API + OAuth |

## 검증 결과 (2026-05-08)
- READ: folders 11개, inbox 5/2일 200ms, 검색 "입금" 242ms, body fetch 3.3s (top:10 + 본문)
- WRITE: 본인 ins@doflab.com 으로 테스트 메일 1건 송수신 ✓ (Sent 15:31:42 → Inbox 15:31:48)
