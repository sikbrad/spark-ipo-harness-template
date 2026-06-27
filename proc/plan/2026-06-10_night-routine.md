# 2026-06-10 Night Routine

## Scope

- 기준일: `2026-06-10` Asia/Seoul.
- 목적: 하루 raw 재수집, Jot/Task/standup 판정, kubit/Raindrop/Area 정리, `summary.md` 작성.
- 제외: KakaoTalk/kmsg, 외부 게시/메시지 전송.

## Plan

1. `data/daily/2026-06-10/raw/`에 night 기준 source error 기록을 갱신한다.
2. Notion DailyJot/Task DB live snapshot과 edited state를 수집한다.
3. Teams chats/channels/standup, Google Calendar/Gmail/Drive, Outlook, Atlassian, Amaranth approval을 수집한다.
4. kubit Slack conversation/people cache를 갱신한다.
5. voice/audio 후보를 확인하고, 실제 원본이 있으면 전사한다.
6. Raindrop dump/day filter/infer/untagged retag를 제한적으로 확인한다.
7. empty Areas 후보를 확인하고 필요하면 backfill 흐름을 실행한다.
8. raw를 읽어 `data/daily/2026-06-10/summary.md`를 작성한다.

## Progress

- [x] Main daily raw collection completed.
- [x] kubit Slack cache refreshed.
- [x] Amaranth approval checked.
- [x] Voice/audio candidates reviewed.
- [x] Raindrop infer/retag reviewed.
- [x] Empty Areas reviewed.
- [x] Summary written.
- [x] Verification completed.

## Result

- Wrote summary: `data/daily/2026-06-10/summary.md`.
- Wrote raw artifacts under `data/daily/2026-06-10/raw/`.
- Raindrop day items processed: 2 infer + 2 retag.
- Empty Areas backfilled: 2 tasks patched.
- Amaranth approval: 0 visible pending docs.
- kubit Slack: conversation and people caches refreshed.

## Known Collection Gaps

- Notion full dump timed out after 300s; live DailyJot/Task snapshots were collected.
- `sikbrad` Google Calendar/Gmail/Drive failed on existing OAuth/scope state.
- Teams private channels `proj-출고-예외승인`, `기술지원 운영`, `proj-월결산-생산재고회계` returned Graph 403.
