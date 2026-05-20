---
name: daily-collect
description: 하루치 활동 로그를 여러 데이터 소스(Notion 트리·Notion Jot DB·Raindrop·MS Teams 채팅·MS Teams 채널·Slack·Google Calendar·Gmail/Outlook·Google Drive·Jira·Confluence)에서 모아 `data/daily/<YYYY-MM-DD>/raw/`에 raw 저장하고, AI가 직접 raw를 읽고 분석한 일별 `summary.md`를 작성. "오늘 뭐했는지", "일일 로그", "데일리 정리", "daily activity 모아줘", "내가 무슨일했는지 정리해줘" 등 일별 활동 회고 요청 시 사용. 키워드 매칭이나 API 자동 요약 금지 — LLM이 raw를 한 건씩 읽고 직접 사람말로 정리.
---

# Daily Activity Collector

특정 날짜(또는 시간 역순 다일)의 활동을 여러 출처에서 raw 형태로 모으고, **AI가 직접 raw를 읽고** 사람의 시각으로 하루를 요약한다.

핵심 원칙:
- **AI가 직접 읽는다** — `grep` / 키워드 매칭 / 자동 요약 스크립트 금지. raw 파일을 진짜로 한 건씩 읽고 의미를 파악해서 summary.md를 쓴다.
- **순서대로 진행한다** — 각 출처를 순서대로 호출하고 raw를 정해진 위치에 둔다.
- **증분 우선** — Notion / Raindrop은 SQLite 캐시 기반 incremental dump를 먼저 돌려 최신 상태를 확보.
- **시간 역순** — 오늘부터 시작해 과거로 거슬러 올라간다.

## 디렉토리 레이아웃

```
data/daily/
└── <YYYY-MM-DD>/
    ├── raw/
    │   ├── notion-jot.json              # 이날의 DailyJot 페이지 본문 (Jot DB id=d16ebd32-1285-43a8-a9c1-355a91ab782b)
    │   ├── notion-edited.json           # 이날 last_edited_time이 걸친 모든 page/db (Jot 외)
    │   ├── raindrop.json                # 이날 created/lastUpdate 가 걸친 북마크
    │   ├── teams-chats.json             # 이날 모든 chat의 본문 (DM/그룹) — MS Graph
    │   ├── gcal-bispro89.json           # bispro89 계정 일정
    │   ├── gcal-sikbrad.json            # sikbrad 계정 일정
    │   ├── gmail-bispro89.json          # bispro89 메일 (헤더+본문, no-promotions)
    │   ├── gmail-sikbrad.json
    │   ├── outlook.json                 # 회사 Office 365 메일
    │   ├── gdrive-bispro89.json         # 이날 modified 파일
    │   ├── gdrive-sikbrad.json
    │   ├── teams-channels.json          # 29개 전체 Teams 채널 중 본인 발언/멘션 thread (Graph)
    │   └── atlassian.json               # Jira(본인 생성·수정 이슈+댓글·변경) + Confluence(본인 생성·기여 페이지·댓글)
    └── summary.md                       # AI 작성 — raw를 읽고 분석한 결과
```

`raw/`는 그날의 진실(원자료). `summary.md`는 그 위에 사람말로 얹는 해석.

## 출처별 수집 방법

### 0) (선행) 증분 dump 보장

오늘 분 직전에 dump를 한 번 굴려 캐시를 최신화한다 — 매일 처음 호출할 때만 필요.

```bash
# 노션 (Quick My Ocean + Databases root)
python3 proc/lib/notion_dump.py dump \
  --root e0a658bf0f8d4e6384c6903940c7e7a9 \
  --root bd198b22ef9f44618c2382ce45bbf7b0 \
  --out data/notion/dump

# Raindrop
python3 proc/lib/raindrop_dump.py dump
```

### 1) Notion Jot DB — DailyJot 페이지

Jot DB id: `d16ebd32-1285-43a8-a9c1-355a91ab782b`. 매 날짜마다 `DailyJot YYYY-MM-DD` 형식 페이지 1개.

찾는 법 (SQLite state 활용):
```bash
sqlite3 data/db/notion_state.sqlite \
  "SELECT id, title FROM notion_object
   WHERE kind='page' AND title LIKE 'DailyJot 2026-05-18%'"
```

해당 page id 가지고 `data/notion/dump/pages/<hex-id>.json` + `data/notion/dump/blocks/<hex-id>.json` 두 파일을 raw로 복사·머지하여 `notion-jot.json`으로 저장.

### 2) Notion 일반 트리 — 그날 편집된 페이지/DB

```bash
sqlite3 data/db/notion_state.sqlite \
  "SELECT kind, id, title, last_edited_time FROM notion_object
   WHERE last_edited_time LIKE '2026-05-18T%'
     AND (kind='page' OR kind='database')
   ORDER BY last_edited_time DESC"
```

Jot DB 페이지 제외하고 (parent가 Jot DB가 아닌 것), 각 page는 `data/notion/dump/pages/<hex>.json` + 옵션으로 `blocks/<hex>.json`을 묶어서 한 JSON으로.

### 3) Raindrop — 그날 저장/수정된 북마크

```python
import json, datetime as dt
from pathlib import Path
day = '2026-05-18'
out = []
for p in Path('data/raindrop/dump/raindrops').glob('*.json'):
    d = json.loads(p.read_text())
    lu = d.get('lastUpdate') or d.get('created')
    if lu and lu.startswith(day):
        out.append(d)
out.sort(key=lambda d: d.get('lastUpdate') or d.get('created') or '', reverse=True)
Path(f'data/daily/{day}/raw/raindrop.json').write_text(json.dumps(out, ensure_ascii=False, indent=2))
```

### 4) MS Teams — 이날 발생한 chat 본문

```python
import sys, json; sys.path.insert(0, 'proc/lib')
from datetime import datetime, timezone, timedelta
from msgraph import GraphClient
from teams_graph import chat_list, chat_messages, KST

day = '2026-05-18'
since = datetime.fromisoformat(f'{day}T00:00:00+09:00')
until = since + timedelta(days=1)

g = GraphClient()
chats = chat_list(g, top=100)
result = []
for c in chats:
    if not c['last_ts']: continue
    # last_ts가 since 이전이면 (정렬 desc) 더 볼 필요 없음
    if c['last_ts'] < since: break
    try:
        msgs = chat_messages(g, c['chat_id'], since=since, until=until)
    except Exception as e:
        msgs = []
    if msgs:
        result.append({'chat': c, 'messages': [
            {'ts': m['ts'].isoformat(), 'who': m['who'], 'text': m['text'][:2000]}
            for m in msgs
        ]})

with open(f'data/daily/{day}/raw/teams-chats.json', 'w') as f:
    json.dump(result, f, ensure_ascii=False, indent=2, default=str)
```

### 5) Google Calendar — 두 계정

```bash
python3 proc/lib/gcal_api.py events --account bispro89 \
  --since 2026-05-18 --until 2026-05-18 \
  --out data/daily/2026-05-18/raw/gcal-bispro89.json

python3 proc/lib/gcal_api.py events --account sikbrad \
  --since 2026-05-18 --until 2026-05-18 \
  --out data/daily/2026-05-18/raw/gcal-sikbrad.json
```

### 6) Gmail — 두 계정

```bash
python3 proc/lib/gmail_api.py search --account bispro89 \
  --q 'after:2026/05/18 before:2026/05/19 -category:promotions -category:social' \
  --max 80 \
  --out data/daily/2026-05-18/raw/gmail-bispro89.json

python3 proc/lib/gmail_api.py search --account sikbrad \
  --q 'after:2026/05/18 before:2026/05/19 -category:promotions -category:social' \
  --max 80 \
  --out data/daily/2026-05-18/raw/gmail-sikbrad.json
```

### 7) Outlook — 회사 Office 365 메일

`proc/lib/outlook.py`의 helper 또는 MS Graph로 그날 메시지 fetch. 본 스킬은 best-effort — 없으면 skip.

### 8) Google Drive — 그날 modified 파일

```bash
python3 proc/lib/gdrive_api.py search --account bispro89 \
  --raw-q "modifiedTime > '2026-05-18T00:00:00+09:00' and modifiedTime < '2026-05-19T00:00:00+09:00' and trashed = false" \
  --max 50 \
  --out data/daily/2026-05-18/raw/gdrive-bispro89.json
```

(가능하면 `--raw-q` 옵션 사용. CLI에 없다면 Python으로 직접.)

### 9) MS Teams 채널 — 29개 전체 채널 중 본인 발언/멘션

`/tmp/channels_day.py` (혹은 동등한 스크립트) — `channel_map(g)`로 전체 channel을 훑고 본인 발언 있는 thread 또는 본인 멘션(`'백인식' in text` / `@Brad` / `@백인식`)만 keep.

```bash
python3 /tmp/channels_day.py 2026-05-18
# 또는 proc/lib에 영구화한 버전이 있다면 그쪽으로
```

저장 위치: `data/daily/<day>/raw/teams-channels.json`. (단일 standup-daily-ax 채널만 보는 `teams-standup.json`과는 별도 raw.)

### 10) Atlassian — Jira + Confluence (본인 활동)

`proc/lib/daily_atlassian.py` 사용. `ATLASSIAN_EMAIL` / `ATLASSIAN_TOK` (`.env`) 기반 Basic auth, 사이트 `doflab.atlassian.net` 고정.

```bash
python3 proc/lib/daily_atlassian.py 2026-05-18
```

저장 위치: `data/daily/<day>/raw/atlassian.json`. 구조:

```
{
  "jira": {
    "created":         [...],  # creator = currentUser() 그날
    "updated_with_me": [...],  # assignee/reporter = me + updated 그날
    "my_comments":     [...],  # 위 이슈들에 본인이 단 댓글 (그날)
    "my_changes":      [...]   # 본인이 만든 changelog 항목 (status/assignee/rank 등)
  },
  "confluence": {
    "created":  [...],  # creator = currentUser() + 그날 created
    "updated":  [...],  # contributor = currentUser() + 그날 lastModified
    "comments": [...]   # creator = currentUser() + type=comment + 그날 created
  }
}
```

Jira는 비어있는 날 많고(이슈 안 만든 날), Confluence는 회의록·AX 페이지 때문에 거의 매일 1~3건 있음.

## summary.md 작성 규칙

**AI가 raw 파일들을 한 건씩 직접 읽고 의미를 파악해 사람말로 정리한다**:

1. **하루의 큰 흐름** — 오전/오후/저녁에 무슨 일이 일어났는가
2. **카테고리별 발생 일 요약** — 회의, 코딩 작업, 자료 수집(북마크), 채팅 대응, 메일 처리 등
3. **결정·아웃풋** — 그날 만들어진 결과물 (commit, 보고서, 발송한 메일, 만든 노션 페이지)
4. **다음 액션** — raw에서 발견된 follow-up. 명시되지 않았으면 빈칸.

키워드 매칭이나 통계만 늘어놓지 말 것. 사람이 일기 쓰듯이 자연스럽게 쓴다.

대략적 구조 (강제 아님 — 그날 양에 맞춰 가변):
```markdown
# 2026-05-18 (월요일)

## 하루 흐름
…

## 회의 / 캘린더
…

## 코딩 / 작업 (Notion + Drive + Jot)
…

## 입력·수집 (Raindrop)
…

## 커뮤니케이션 (Teams + Gmail + Outlook)
…

## 다음 액션
…
```

## 시간 역순 진행

오늘부터 시작:
1. `today = date.today()` 기준 raw + summary.
2. 끝나면 `today - 1` 로 이동.
3. `data/daily/<date>/summary.md`가 이미 존재하면 **skip** (이미 정리됨).
4. 더 이상 의미 있는 raw가 나오지 않는 날(모든 출처 0건)이 7일 이상 연속이면 stop — 그 이전은 사용자가 명시할 때만.

진행할 때 사용자에게 매 단계 묻지 말 것. "잘 거니까 귀찮게 하지 마라" 모드 — 막히면 그 출처만 skip하고 summary에 `(<source> 수집 실패: <이유>)` 한 줄로 남긴다.

## 실패 시 동작

| 증상 | 대처 |
|---|---|
| Notion dump 도중 token 만료 | summary에 노션 부분 skip 표시, 다음 단계 진행. |
| MS Teams Graph 401 | `python3 proc/lib/msgraph.py login` 안내만 summary에 남김. |
| Google OAuth 만료 | 해당 계정 결과 0건으로 처리, 다른 계정·다른 출처는 계속. |
| Raindrop 429 | 잠시 후 dump 재시도. |
| Outlook helper 없음 | skip, summary에 한 줄 표시. |
| Slack | 이 워크스페이스는 Slack을 별도 설정 안 함. `/Users/gq/works/lecture/kubit/kubit-bitbot-slack-01`의 `/slack` 스킬에서 별도로 수집 — 본 스킬은 noop. |

## Slack은 왜 빠져있나

Slack(kubit 워크스페이스)는 다른 워크스페이스(`kubit-bitbot-slack-01`)에 토큰/스크립트가 있다. 본 워크스페이스에서는 의도적으로 skip하고, 필요 시 사용자가 거기서 `/slack` 호출로 별도 수집한다. summary.md에는 `(Slack: 별도 ws에서 수집 — kubit-bitbot-slack-01)` 한 줄로 표시.

## 참고

- 출처별 raw 스키마 / 호출 옵션은 각 단일 스킬 SKILL.md 참고: `/notion-dump`, `/raindrop`, `/teams-chat`, `/gcal`, `/gmail`, `/outlook`, `/gdrive`.
- Jot DB id, 알려진 Notion root id 등은 [notion-dump SKILL.md](../notion-dump/SKILL.md)와 본 파일의 "1) Notion Jot DB" 섹션에 박혀 있다.
