# 2026-06-02 Night Routine Plan

## Scope
- Date: 2026-06-02, Asia/Seoul.
- Run the established `night-routine` flow.
- Exclude kmsg/KakaoTalk.
- Do not post external messages or mutate Notion task statuses.

## Steps
- [x] Prepare `data/daily/2026-06-02/raw/`.
- [x] Check for voice/audio transcript sources.
- [x] Run broad daily collection: Notion, Teams, Calendar, Gmail/Outlook, Drive, Atlassian, Raindrop.
- [x] Refresh kubit Slack conversations and people.
- [x] Review DailyJot, Task DB, and Teams standup against the day.
- [x] Backfill empty `Areas` relation if Task/Note candidates exist.
- [x] Retag a bounded batch of untagged Raindrop items when infer exists.
- [x] Write/update `data/daily/2026-06-02/summary.md`.
- [x] Verify raw JSON validity and summary presence.

## Notes
- Execution began at `2026-06-02 00:42 KST`; expect an early-day snapshot unless same-day activity already exists.
- Source-specific failures should be recorded in `data/daily/2026-06-02/raw/source-errors.json` and should not stop the whole routine.

## Result Notes
- Summary written: `data/daily/2026-06-02/summary.md`.
- This is an early snapshot because execution began shortly after midnight KST.
- No 2026-06-02 Raindrop-created item was available; existing infer backlog was processed instead.
- `data/daily/2026-06-02/raw/gdrive-bispro89.json` contained one audio file named `260601`; it was downloaded/transcribed into `data/daily/2026-06-01/raw/`.
- Empty-Areas discover found 0 Task DB and 0 Note DB candidates.
- Verification: raw JSON parsed successfully, summary exists, and no collector process remains running.
