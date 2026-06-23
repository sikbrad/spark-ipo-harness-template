# 2026-06-22 Night Routine

## Scope

- 기준일: `2026-06-22` Asia/Seoul.
- 목적: 하루 raw 보강 수집, Jot/Task/standup 판정, kubit/Raindrop/Area 정리, `summary.md` 작성.
- 제외: KakaoTalk/kmsg, 외부 게시/메시지 전송.

## Progress

- [x] Main daily raw collection completed.
- [x] Portal feedback/notices reviewed.
- [x] Teams archive status checked.
- [x] kubit Slack conversation/people refreshed.
- [x] Voice/audio candidates reviewed and late Drive upload backfilled.
- [x] Raindrop infer/retag reviewed.
- [x] Empty Areas reviewed.
- [x] Summary written.
- [x] Verification completed.

## Result

- Wrote summary: `data/daily/2026-06-22/summary.md`.
- Wrote raw artifacts under `data/daily/2026-06-22/raw/`.
- Portal feedback: 9 daily feedback, 36 active feedback, 19 feedback notifications.
- Portal notices: 0 daily notices, 30 published notices, 34 release-note snapshots.
- kubit Slack: `collect:conv` and `collect:people` completed.
- Raindrop: 5 day items infer + retag completed.
- Empty Areas: 0 task candidates, 0 note candidates.
- Voice/audio: initial raw had no candidates, but a later live Drive check found `음성 260619_124619 ax 김채원 퇴사1주일전.m4a` uploaded at 2026-06-23 01:04 KST. The file name points to content date 2026-06-19, so the audio/transcript were stored under `data/daily/2026-06-19/raw/`, with 6/22 upload metadata in `data/daily/2026-06-22/raw/gdrive-audio-upload-260619_124619.json`.

## Known Collection Gaps

- Notion full dump was skipped; live Notion snapshots were used.
- Teams private channel collection had 4 Graph 403 failures.
- Teams full archive full-history retry was interrupted after a long Graph wait; existing archive summary is `2026-06-17 23:05:24 +0900`.
- Amaranth approval check failed because the `amaranth` Playwright session is not open.
