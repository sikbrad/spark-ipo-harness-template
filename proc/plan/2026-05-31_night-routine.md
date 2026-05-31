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

## Rerun Notes — 2026-05-31 23:49 KST
- User requested the 2026-05-31 night routine again at end-of-day.
- Reuse the existing raw directory and refresh collectors for the full day window.
- Keep `kmsg` excluded and do not post external messages or mutate Task statuses.
- Update `source-errors.json` for partial/failed sources, then rewrite `summary.md` from the refreshed raw.

## Rerun Result — 2026-06-01 00:10 KST
- Rewrote `data/daily/2026-05-31/summary.md` as an end-of-day archive.
- Refreshed Notion live Jot/Task, Teams, Calendar/Gmail/Drive, Outlook, Atlassian, Raindrop, kubit Slack, and source error records.
- Notion dump remained partial at the 300s timeout, but live Jot/Task succeeded and `notion-edited.json` was derived from the updated SQLite state.
- Google `sikbrad` remained blocked by OAuth `invalid_scope`; `bispro89` sources succeeded.
- Drive audio files dated 2026-05-27, 2026-05-28, and 2026-05-29 were downloaded and transcribed into their filename-date daily raw folders.
- Area backfill rerun discovered 0 additional empty-Areas Task/Note pages.
- Raindrop infer succeeded for the new 2026-05-31 YouTube bookmark, but retag failed at the LLM step and is recorded in `source-errors.json`.
