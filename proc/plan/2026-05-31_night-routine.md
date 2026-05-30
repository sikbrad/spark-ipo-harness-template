# 2026-05-31 Night Routine Plan

## Scope
- Date: 2026-05-31, Asia/Seoul.
- Run the established `night-routine` flow.
- Exclude kmsg/KakaoTalk.
- Do not post external messages or mutate Notion task statuses.

## Steps
- [x] Prepare `data/daily/2026-05-31/raw/`.
- [x] Check for voice/audio transcript sources.
- [x] Run broad daily collection: Notion, Teams, Calendar, Gmail/Outlook, Drive, Atlassian, Raindrop.
- [x] Refresh kubit Slack conversations and people.
- [x] Review DailyJot, Task DB, and Teams standup against the day.
- [x] Retag a bounded batch of untagged Raindrop items when infer exists.
- [x] Write/update `data/daily/2026-05-31/summary.md`.
- [x] Verify raw JSON validity and summary presence.

## Notes
- Source-specific failures should be recorded in `data/daily/2026-05-31/raw/source-errors.json` and should not stop the whole routine.

## Result Notes
- Summary written: `data/daily/2026-05-31/summary.md`.
- This is an early snapshot because execution began shortly after midnight KST.
- No 2026-05-31 Raindrop retag target was available.
- Verification: 19 raw JSON files parsed successfully; summary exists and contains no OpenAI temporary code text.
