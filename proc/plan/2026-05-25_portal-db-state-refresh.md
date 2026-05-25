# Portal DB / Prisma schema state refresh

Date: 2026-05-25

## Goal

Check the current state of:

- A: local DB `dof_portal`
- B: dev DB `dof_portal_dev`
- C: prod DB `dof_portal_prod`
- D: `dof-order-web-3-az/apps/server/prisma/schema.prisma`
- E: `dofing-order-portal-data-3-az/data/prisma/schema.prisma`

Then refresh dev/local from prod without writing to prod, preserve target-specific `ApiToken` rows, pull E schema, and update `proc/research/2026-05-25_portal-db-schema-state.md`.

## Checklist

- [x] Read existing research note and repo scripts.
- [x] Collect read-only DB metadata and freshness indicators from A/B/C.
- [x] Parse D/E Prisma schemas and compare table/column shape.
- [x] Create prod dump with read-only `pg_dump`.
- [x] Preserve dev/local `ApiToken` rows with enum-safe `scope::text`.
- [x] Restore prod dump into dev/local using filtered no-extension restore list.
- [x] Build/install local PG17 `vector` extension and retry local restore.
- [x] Restore each target's original `ApiToken` rows.
- [x] Pull E Prisma schema from refreshed dev.
- [x] Verify local/dev/prod/D/E parity and token counts.
- [x] Run `npm run db:test`, `bun run db:generate`, and `bun run build:server`.
- [x] Update research note with current status and latest-refresh procedure.
- [x] Verify the research note contains no plaintext database passwords.

## Outcome

- Prod was not modified. Prod access was limited to `pg_dump` and read-only verification queries.
- Dev/local now match prod at public table/column level: 45 tables / 684 columns.
- E now matches D: 45 models / 684 scalar fields.
- Dev `ApiToken`: 8 total / 3 active, preserved from dev.
- Local `ApiToken`: 3 total / 2 active, preserved from local.
- Dump artifacts are in `output/db-dumps/2026-05-25/` and should be treated as sensitive.
