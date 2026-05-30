# 2026-05-30 Night Routine Plan

## Scope
- Date: 2026-05-30, Asia/Seoul.
- This is the just-ended day at the time of execution (`2026-05-31 00:35 KST`).
- Run the established `night-routine` flow.
- Exclude kmsg/KakaoTalk.
- Do not post external messages or mutate Notion task statuses.

## Steps
- [ ] Prepare `data/daily/2026-05-30/raw/`.
- [ ] Check voice/audio transcript sources.
- [ ] Collect raw sources: Notion, Teams, Calendar, Gmail/Outlook, Drive, Atlassian, Raindrop.
- [ ] Use already refreshed kubit Slack conversation/people logs as the nightly cache update evidence.
- [ ] Review DailyJot, Task DB, and Teams standup against the day.
- [ ] Record Raindrop infer/retag status.
- [ ] Write `data/daily/2026-05-30/summary.md`.
- [ ] Verify raw JSON validity and summary presence.

## Notes
- Source-specific failures should be recorded in `data/daily/2026-05-30/raw/source-errors.json`.
