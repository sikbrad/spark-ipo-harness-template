---
name: morning-routine
description: 아침 루틴 브리핑. DailyJot를 Task/Note로 등록하고 Notion Task DB의 오늘/기한/진행중 태스크를 확인한 뒤 Teams standup, Teams 미답/멘션, kubit Slack 신호, Google Calendar, Gmail/Outlook, Jira/Confluence, 전날 daily summary, 아마란스 결재/일정 등을 모아 오늘 해야 할 일과 바로가기 링크를 우선순위로 보고한다. 그날 standup을 아직 안 했으면 Jot, Task DB, Calendar, 전날 액션을 근거로 standup에 넣을 내용을 제안한다. "모닝루틴", "아침 루틴", "오늘 뭐 해야 해", "오늘 할일 브리핑", "morning routine" 요청 시 사용. kmsg/KakaoTalk은 제외한다.
---

# Morning Routine

아침에는 새 raw archive를 완성하는 것이 아니라, 오늘 움직일 판단을 만든다. 가능한 한 원문 링크를 많이 붙이고, 사용자가 바로 들어갈 수 있게 한다.

## Core Flow

1. 기준일을 정한다. 명시가 없으면 Asia/Seoul 오늘.
2. `daily-jot-to-tasks`를 먼저 실행해 DailyJot 체크박스/bullet을 Task/Note로 반영한다.
3. Notion Task DB에서 오늘 ActDate/DueDate, overdue, `Doing`/`Ready`/`Wait` 태스크를 확인한다.
4. 어제와 오늘의 `data/daily/<date>/summary.md`가 있으면 읽고 unresolved next action을 끌어온다.
5. Teams standup을 확인한다. 오늘 본인 아침 standup이 없으면 넣을 내용을 제안한다.
6. Teams, kubit Slack, Calendar, Gmail/Outlook, Jira/Confluence, Amaranth를 확인한다.
7. 최종 응답은 "오늘 해야 할 일" 중심으로 정리한다.

## Sources

공통 source routing은 [routine-sources.md](references/routine-sources.md)를 따른다. `kmsg`는 이 루틴에서 사용하지 않는다.

Morning 우선순위:

| Source | Use |
|---|---|
| `daily-jot-to-tasks` | Jot에 적은 할일/생각을 Task/Note로 전환 |
| Notion Task DB | 오늘 할 태스크, overdue, 진행중/대기 태스크 확인 |
| Teams standup | 오늘 아침 standup 작성 여부 확인, 미작성 시 제안문 생성 |
| `teams-activity` | 미답 DM, 오늘 멘션, 놓치면 안 되는 Teams 신호 |
| `teams-chat` / `teams-channel` | 중요한 채팅/채널 thread 본문과 링크 |
| kubit Slack cache/light collect | kubit 운영, 학생/팀 대응, weekly/future-self 이슈 |
| `gcal` | 오늘 일정, 회의 준비, 충돌 |
| `gmail` / `outlook` | 답장할 메일, 오늘 처리할 메일 |
| `daily_atlassian.py` | Jira/Confluence에서 오늘 관련 이슈/페이지 |
| `amaranth-approval` | 결재할 문서 |
| `amaranth-calendar` / `amaranth-resource` | 회사 일정/자원 확인이 필요한 날 |

## Notion Task DB

`daily-jot-to-tasks` 실행 후 Task DB를 별도로 본다. 목적은 새로 만든 Task 확인이 아니라 오늘 실제로 움직여야 할 목록을 만드는 것이다.

확인할 것:

- `ActDate`가 오늘인 Task
- `DueDate`가 오늘이거나 지난 Task
- `Status`가 `Doing`, `Ready`, `Wait`, `Schedule`인 Task
- 최근 7일 내 생성됐고 아직 `Done`/`Close`가 아닌 Task
- DailyJot에서 방금 만들어졌거나 끌올된 Task

보고할 때는 Task 제목, 상태, 날짜, Area, Notion page 링크를 가능하면 붙인다.

## Teams Standup

standup source는 다음 순서로 사용한다:

1. 전용 standup 스킬/스크립트가 생겨 있으면 그것을 우선한다.
2. 없으면 `teams-channel`로 `standup-daily-ax` 채널의 오늘 thread/replies를 조회한다.
3. 이미 수집된 경우 `data/daily/<date>/raw/teams-standup.json`을 읽는다.

아침 standup 판단:

- 오늘 본인 아침 standup이 있으면 그 내용을 오늘 계획에 반영한다.
- 오늘 본인 아침 standup이 없으면 아래 근거를 합쳐 3~5개 bullet로 제안한다:
  - 오늘 DailyJot 항목
  - Notion Task DB의 오늘/overdue/Doing Task
  - 오늘 Calendar 일정
  - 어제 `summary.md`의 다음 액션
  - Teams/Gmail/Outlook에서 놓치면 안 되는 응답

사용자가 명시적으로 게시를 요청하지 않으면 standup을 Teams에 게시하지 않는다.

## kubit Slack

kubit Slack은 sibling workspace를 사용한다:

```bash
cd /Users/gq/works/lecture/kubit/kubit-bitbot-slack-01
node src/collect-conversations.js --no-render
```

Morning에서는 전체 재수집보다 최근 cache와 light incremental collect를 우선한다. 사람별 장기 profile 갱신은 `night-routine`에 맡긴다.

## Output Shape

응답은 짧고 실행 가능해야 한다.

```markdown
## 오늘 먼저 할 것
1. ...

## 답장/확인
- ...

## 회의/일정 준비
- ...

## kubit
- ...

## 링크
- [대상](url) — 왜 봐야 하는지

## Standup 제안
- 오늘 standup 미작성 시에만 표시
```

가능한 링크 종류:

- Teams message/thread link
- Slack permalink
- Notion page URL
- Google Calendar event link
- Gmail/Outlook message link 또는 raw 파일 위치
- Jira issue / Confluence page URL
- local `data/daily/...` raw/summary path

## Guardrails

- `kmsg` / KakaoTalk 수집은 하지 않는다.
- Slack/Teams에 글을 게시하지 않는다. 명시 요청이 있으면 별도 스킬로 처리한다.
- 외부 시스템 write는 `daily-jot-to-tasks`의 Notion Task/Note 등록 범위에 한정한다.
- 링크가 없으면 local raw 파일 경로와 source id라도 남긴다.
