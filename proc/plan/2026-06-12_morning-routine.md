# 2026-06-12 Morning Routine

## Scope

- 기준일: `2026-06-12` Asia/Seoul.
- 목적: DailyJot 반영, 오늘/기한/진행중 Task와 업무 신호를 모아 출근 브리핑 작성.
- 제외: KakaoTalk/kmsg, Slack/Teams 게시.

## Plan

1. DailyJot를 확인하고 Task/Note 전환 후보를 판단한다.
2. 필요한 경우 `jot_to_tasks_2026-06-12.mapping.json`을 작성하고 Notion에 반영한다.
3. 오늘 Task, overdue, Doing/Ready/Wait/Schedule Task를 조회한다.
4. 전날/최근 summary의 unresolved next action을 확인한다.
5. Teams standup/activity, Calendar, Gmail/Outlook, Atlassian, Amaranth, kubit 신호를 수집한다.
6. `data/daily/2026-06-12/morning-brief.md`를 작성한다.

## Progress

- [x] DailyJot reviewed.
- [x] DailyJot Task/Note sync handled.
- [x] Morning raw sources collected.
- [x] Today task/action triage completed.
- [x] Morning brief written.
- [x] Verification completed.

## Result

- Wrote morning brief: `data/daily/2026-06-12/morning-brief.md`.
- Created 3 Notion Tasks from DailyJot:
  - `ts 거래원장 머신 설정`
  - `ts 어제업무정리`
  - `ts Pdf 생성시 옵션 추가 ㅡ 서전임에게`
- Collected morning raw files under `data/daily/2026-06-12/raw/`.
- Teams Activity retry succeeded with top=50: 1 unanswered candidate, 0 mentions.
- kubit Slack light collect completed: `#아무말` 1 new top-level message processed.

## Known Collection Gaps

- `sikbrad` Google Calendar/Gmail/Drive failed on existing OAuth/scope state.
- Teams private channel collection had 4 failures: one timeout and three Graph 403 responses.
- Amaranth approval check failed because the `amaranth` Playwright session is not open.
