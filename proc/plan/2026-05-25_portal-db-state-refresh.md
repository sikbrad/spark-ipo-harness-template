# Portal DB / Prisma schema state refresh

Date: 2026-05-25

## Goal

Check the current state of:

- A: local DB `dof_portal`
- B: dev DB `dof_portal_dev`
- C: prod DB `dof_portal_prod`
- D: `dof-order-web-3-az/apps/server/prisma/schema.prisma`
- E: `dofing-order-portal-data-3-az/data/prisma/schema.prisma`

Then update `proc/research/2026-05-25_portal-db-schema-state.md` with the current findings and the refresh procedure.

## Checklist

- [x] Read existing research note and repo scripts.
- [x] Collect read-only DB metadata and freshness indicators from A/B/C.
- [x] Parse D/E Prisma schemas and compare table/column shape.
- [x] Update research note with current status and latest-refresh procedure.
- [x] Verify the research note contains no plaintext database passwords.
