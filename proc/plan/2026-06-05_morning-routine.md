# 2026-06-05 Morning Routine

## Scope

- 기준일: `2026-06-05` Asia/Seoul.
- 목적: DailyJot/Task/standup/Teams/mail/calendar/kubit/approval을 확인해 오늘 움직일 우선순위를 만든다.
- 제외: KakaoTalk/kmsg, Teams/Slack 게시.
- 외부 write 허용 범위: DailyJot 항목을 Task/Note로 전환하는 Notion write만.

## Plan

1. Night raw와 충돌하지 않게 `data/daily/2026-06-05/raw/morning-*` 파일로 live 결과를 남긴다.
2. DailyJot live를 확인하고, 비어 있지 않은 unchecked to-do가 있으면 Area를 의미 기반으로 매핑해 Task DB에 등록한다.
3. Task DB의 오늘/overdue/active/carryover task를 확인한다.
4. Teams standup과 미답/멘션, Calendar, Gmail/Outlook, kubit Slack, Atlassian, Amaranth 결재를 확인한다.
5. 오늘 먼저 할 일, 답장/확인, 일정 준비, standup 제안을 정리한다.

## Progress

- Notion live checked. DailyJot has 3 non-empty unchecked to-do items.
- Jot item mapping:
  - `Pkg 관리, 송장관련, dev 에만 배포` -> reuse existing `ts PKG 관리화면 배포`; this is a semantic continuation of the 2026-06-04 PKG/deploy task and should be pulled up rather than duplicated.
  - `오후반차` -> `SelfAdmin(자기관리)`; this is personal schedule/leave administration, not a project deliverable.
  - `점심 아내. 점심 아내만나기전에 위스키 사두기.` -> `Home(부부)`; spouse/family plan and errand.
- DailyJot -> Task conversion completed: 1 existing task reused, 2 new tasks created.
- Notion task scan completed. `act_today` and `due_overdue` were empty; active/recent task candidates are stored in `data/daily/2026-06-05/raw/morning-notion-tasks-live.json`.
- Google Calendar checked: 9 events in the window. Today has spouse birthday, `한우비타민채`, and `11시 병원`; tomorrow has fitness/monthly meeting/flour test/wedding items.
- Teams checked: 14 unanswered chat candidates, 0 mentions, no collection errors. Today standup thread exists but has no replies yet.
- Mail checked: Gmail personal inbox returned 0 messages; Outlook had 0 today inbox/sent items and 28 recent unread items. Work-relevant unread signal includes DOF portal feedback from 2026-06-04.
- KUBIT Slack checked: 10 public `#ai-news` messages collected; DM/private coverage remains limited by Slack scope gaps.
- Amaranth approval checked: 0 pending docs.
- Atlassian checked: Jira/Confluence activity buckets all empty for this run.

## Final Brief Inputs

- Highest work item: `ts PKG 관리화면 배포` / PKG + invoice-related work, deploy to dev only.
- Support/communication watchlist: Teams `핑거세일즈 주문현황`, `DOF 지원요청 전용`, `국내 주문방`, and Outlook DOF portal feedback on `/orders/OD202606041025`.
- Personal schedule constraints: spouse birthday, 11:00 hospital, afternoon half-day, lunch/errand with spouse.
- Standup suggested bullets:
  - PKG 관리/송장 관련은 dev에만 배포 진행
  - 11시 병원 및 오후반차 예정으로 오전 업무 압축
  - DOF 지원요청/주문방/포탈 피드백 확인
