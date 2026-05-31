# 2026-05-31 Night Routine Area Backfill

## Scope
- Backfill empty `Areas` relation for Notion Task DB and Note DB.
- This completes the Area step that was added to `night-routine` after the initial nightly archive run.

## Guardrails
- Only pages whose `Areas` relation is empty are candidates.
- Re-fetch each page before PATCH; skip if `Areas` is no longer empty.
- Exclude Area pages whose status is `Closed`.
- Do not change Task `Status`, `ActDate`, `DueDate`, or Note content.
- Area mapping must be semantic judgement from page title/body and Area meaning, not keyword rules.

## Steps
- [x] Discover empty-Areas Task/Note candidates and active Areas.
- [x] Build mapping JSON with reasons.
- [x] Run dry-run.
- [x] Apply guarded PATCH.
- [x] Verify no mapped page still has empty Areas.

## Artifacts
- `proc/plan/backfill_areas_2026-05-31.candidates.json`
- `proc/plan/backfill_areas_2026-05-31.mapping.json`
- `proc/plan/backfill_areas_2026-05-31.result.json`
- `proc/plan/backfill_areas_2026-05-31.verify.json`

## Result
- Discovered 5 Task DB pages and 3 Note DB pages with empty `Areas`.
- Patched all 8 with guarded re-fetch:
  - Tasks: 5 patched, 0 skipped.
  - Notes: 3 patched, 0 skipped.
- Verification re-read all mapped pages and found 0 pages still missing `Areas`.
- Candidate artifact was redacted for account-note credential text; mapping/result files contain no password values.
