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
