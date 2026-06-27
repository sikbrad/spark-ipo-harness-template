# 2026-05-27 Night Routine

## Goal

Run the night routine for 2026-05-27 and leave `data/daily/2026-05-27/summary.md` backed by raw source files.

## Checklist

- [x] Confirm existing raw files and voice/audio state.
- [x] Fill missing daily raw files where available.
- [x] Refresh kubit Slack conversations and people cache.
- [x] Refresh Raindrop dump/infer and retag a bounded batch of untagged items.
- [x] Read raw files directly and write the daily summary.
- [x] Verify output files and record any skipped sources.

## Notes

- `kmsg` / KakaoTalk is excluded by the routine contract.
- Do not update Notion Task statuses unless explicitly requested.
- Google `sikbrad` refresh failed with `invalid_scope`; leave as skipped source.
- Notion incremental dump hung without file progress; use existing live Jot/Task snapshots.
- No `2026-05-27` voice/audio source was found in repo-local daily data or bispro89 Drive modified search.
- Raindrop dump/infer ran; today saved/updated 8 untagged items were inferred and retagged.
