# 2026-05-31 Night Routine Plan

## Scope
- Date: 2026-05-31, Asia/Seoul.
- Run the established `night-routine` flow.
- Exclude kmsg/KakaoTalk.
- Do not post external messages or mutate Notion task statuses.

## Steps
- [ ] Prepare `data/daily/2026-05-31/raw/`.
- [ ] Check for voice/audio transcript sources.
- [ ] Run broad daily collection: Notion, Teams, Calendar, Gmail/Outlook, Drive, Atlassian, Raindrop.
- [ ] Refresh kubit Slack conversations and people.
- [ ] Review DailyJot, Task DB, and Teams standup against the day.
- [ ] Retag a bounded batch of untagged Raindrop items when infer exists.
- [ ] Write/update `data/daily/2026-05-31/summary.md`.
- [ ] Verify raw JSON validity and summary presence.

## Notes
- Source-specific failures should be recorded in `data/daily/2026-05-31/raw/source-errors.json` and should not stop the whole routine.
