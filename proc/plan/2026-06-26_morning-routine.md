# 2026-06-26 Morning Routine

## Scope

- 기준일: `2026-06-26` Asia/Seoul (금요일).
- 목적: DailyJot 반영, 오늘/기한/진행중 Task와 업무 신호를 모아 출근 브리핑 작성.
- 제외: KakaoTalk/kmsg, Slack/Teams 게시.

## Progress

- [x] DailyJot reviewed.
- [x] DailyJot Task/Note sync handled.
- [x] Morning raw sources collected.
- [x] Today task/action triage completed.
- [x] Morning brief written.
- [x] Verification completed.

## Steps

1. `morning_discover_2026_06_26.py` — Notion jot/tasks/recent-tasks/areas snapshot.
2. `morning_collect_2026_06_26.py` — Teams/gcal/gmail/gdrive/outlook/atlassian/portal/raindrop (night base, `--skip-notion-dump`).
3. kubit Slack light collect (sibling ws).
4. Amaranth approval/calendar (playwright session 필요).
5. daily-jot-to-tasks (LLM Area 매핑 + 1주일 dup 끌올).
6. Morning brief → `data/daily/2026-06-26/morning-brief.md`.
7. Verify.

## Result

- Wrote morning brief: `data/daily/2026-06-26/morning-brief.md`.
- DailyJot sync: 5 tasks handled (3 끌올, 2 신규), 0 notes. (chip+area verified)
  - New tasks: `ts 거래원장 포탈 상시노출·거래기록 링크·수금이력·CMS 연동 (이후)` (DOF), `ts 낼 강의 알림·구독 안내` (Lecturing).
  - Reused: `ts 거래원장 업무 시작 (ax01)`, `tk 토요일 강의 준비`, `ts 아내 인쇄해달란거 해주기`.
- Today standup already posted by self: `거래원장 발송 및 함께응대`.
- Teams DM 미답 후보 다수, 그중 actionable = `DOF 지원요청 전용` 이호연(위드치과기공소, 부산) 신규 지원요청, `order-web-dev` 서해리 배포계획 답 대기.
- Outlook 주목: `Canceled: [연차] 백인식` (오늘 연차 취소 = 정상 출근), 김채원 PKG 품목코드 문서 공유.
- Portal: feedback active 31 (신규 0), notices published 30 (신규 0). Atlassian 활동 0.
- kubit light collect: 14 files updated, +15 messages.

## Known Collection Gaps

- Teams private channel 4건 Graph 403: 마케팅/프로모션, DOF Inc./proj-출고-예외승인, DOF Inc./기술지원 운영, DOF Inc./proj-월결산-생산재고회계.
- Amaranth 미결 결재: `amaranth` Playwright 세션 미오픈으로 조회 실패.
- Notion full dump skip → live snapshot 사용.
- kubit Slack user token scope 부족 → DM/mpim/private 커버리지 제한.
