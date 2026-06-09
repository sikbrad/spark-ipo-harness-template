# 2026-06-09 Night Routine

## Scope

- 기준일: `2026-06-09` Asia/Seoul.
- 목적: 하루 raw 수집, Jot/Task/standup 판정, kubit/Raindrop/Area 정리, `summary.md` 작성.
- 제외: KakaoTalk/kmsg, 외부 게시/메시지 전송.

## Plan

1. `data/daily/2026-06-09/raw/`를 준비하고 source error 기록을 시작한다.
2. Notion DailyJot/Task DB live snapshot과 edited state를 수집한다.
3. Teams chats/channels/standup, Google Calendar/Gmail/Drive, Outlook, Atlassian, Amaranth approval을 수집한다.
4. kubit Slack conversation/people cache를 갱신한다.
5. voice/audio 후보를 확인하고, 실제 원본이 있으면 전사한다.
6. Raindrop dump/day filter/infer/untagged retag를 제한적으로 실행한다.
7. empty Areas 후보를 확인하고 필요하면 backfill 흐름을 실행한다.
8. raw를 직접 읽어 `data/daily/2026-06-09/summary.md`를 작성한다.

## Progress

- [x] Raw directory prepared: `data/daily/2026-06-09/raw/`.
- [x] Main daily raw collection completed with 5 source errors recorded in `source-errors.json`.
- [x] kubit Slack cache refreshed: `collect:conv` and `collect:people` completed, 6 messages processed.
- [x] Amaranth approval checked: failed because `playwright-cli -s=amaranth goto` returned code 1; error captured in raw.
- [x] Voice/audio candidates reviewed: no local candidates found.
- [x] Raindrop infer/retag reviewed: today's raindrops 0, no untagged item eligible for retag because infer md is missing.
- [x] Empty Areas reviewed and patched: 2 Task pages updated (`DOF`, `Home(부부)`).
- [x] Summary written: `data/daily/2026-06-09/summary.md`.
- [x] Verification completed.

## Verification Notes

- `data/daily/2026-06-09/raw/*.json` 24개 파싱 성공.
- 필수 산출물 누락 없음: `summary.md`, `source-errors.json`, `kubit-slack.json`, `backfill-empty-areas-result.json`, `amaranth-approval.json`, `raindrop-retag-result.json`.
- Backfill result 확인: Task 2건 patched, Note 0건.
- 주요 raw count: Notion Jot 1, Notion Tasks 39, Teams chats 10, Teams channels 10, Outlook messages 19, Gmail bispro89 15, Atlassian sections 2.
