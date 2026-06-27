# 2026-06-03 Night Routine

## Scope

- 기준일: 2026-06-03 KST
- 목적: 하루 raw 수집, Notion/Task/standup 검토, Area backfill, kubit/Raindrop archival 정리, `data/daily/2026-06-03/summary.md` 작성
- 제외: kmsg/KakaoTalk, 외부 게시/메시지 전송, `proc/archive/` 열람

## Steps

- [x] Prepare `data/daily/2026-06-03/raw/`
- [x] Run daily raw collection and record per-source errors
- [x] Review Notion DailyJot / Task DB / Teams standup
- [x] Run empty `Areas` backfill only for still-empty Task/Note pages
- [x] Refresh kubit Slack conversation/person cache
- [x] Dump/infer Raindrop and retag a bounded untagged batch
- [x] Write `summary.md` from raw files
- [x] Verify output files and source-error ledger

## Notes

- If an external source fails, continue and log the exact blocker in `raw/source-errors.json`.
- Do not auto-change Task `Status`, `ActDate`, or `DueDate`.
- `backfill_areas_2026-06-03_discover.py` found 18 active Areas and 0 empty-Area Task/Note candidates, so no mapping/push was needed.
- Raindrop default infer processed 20 backlog items; the first 5 untagged candidates all failed fetch, then 5 fetchable untagged items were inferred and retagged.
- `data/daily/2026-06-03/summary.md` was written as an early KST snapshot. Verification parsed 21 raw JSON files successfully and found no remaining collector process.
