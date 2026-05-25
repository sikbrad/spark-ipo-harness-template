# Portal DB / Prisma schema state check

Date: 2026-05-25

## Scope

- A: local PostgreSQL `dof_portal`
- B: dev PostgreSQL `dof_portal_dev`
- C: prod PostgreSQL `dof_portal_prod`
- D: `dof-order-app/dof-order-web-3-az/apps/server/prisma/schema.prisma`
- E: `dofing-order-portal-data-3-az/data/prisma/schema.prisma`

Connection strings were used from the user-provided environment values. This note intentionally keeps passwords out of the document.

## Summary

| Target | State |
| --- | --- |
| A local DB | Updated on 2026-05-25: now matches dev/prod/web schema at table/column level. |
| B dev DB | Current schema. Matches C and D at table/column level. |
| C prod DB | Current schema. Matches B and D at table/column level. Data volume is intentionally smaller than dev for imported CRM/SF objects. |
| D web Prisma schema | Current source-of-truth schema for the app. Matches B and C at table/column level. |
| E portal-data Prisma schema | Updated on 2026-05-25: now matches A/B/C/D at table/column level. |

Current structural source of truth should be treated as **D/B/C**. Local DB A and data-loader schema E have now been refreshed to match it.

## Object counts

| Target | Tables | Columns | `_prisma_migrations` |
| --- | ---: | ---: | --- |
| A local DB | 45 | 677 | absent |
| B dev DB | 45 | 677 | absent |
| C prod DB | 45 | 677 | absent |
| D web Prisma schema | 45 | 677 | n/a |
| E portal-data Prisma schema | 45 | 677 | n/a |

No database has Prisma's `_prisma_migrations` table, so these environments are not being tracked by Prisma migrate history. Schema movement is currently via Prisma `db push`, manual SQL, and loader-side idempotent ALTER scripts.

## Structural diff

### A local DB vs B dev DB

No table/column diff after the 2026-05-25 schema update.

### B dev DB vs C prod DB

No table/column diff found.

### D web Prisma schema vs B/C DB

No table/column diff found.

Relevant current D schema locations:

- `CompanyShippingAddress.importSource/importDatetime`: lines 351-365
- `OrderClosing`: lines 562-573
- `Product.productType`: line 900

### E portal-data Prisma schema vs A local DB

No table/column diff after the 2026-05-25 schema pull.

### E portal-data Prisma schema vs B/C/D current schema

No table/column diff after the 2026-05-25 schema pull.

## Applied update on 2026-05-25

Actions completed:

- A local DB: ran `bun run --cwd apps/server db:push` from `dof-order-web-3-az`, targeting local `dof_portal`.
- A local DB: Prisma Client generation completed as part of `db:push`.
- E portal-data schema: ran `npm run pull:schema` from `dofing-order-portal-data-3-az`, targeting local `dof_portal`.
- Verification: A, D, and E now all report 45 tables/models and 677 scalar columns; pairwise table/column diffs are zero.

Schema changes applied to A/E:

- `OrderClosing` table/model added.
- `Product.productType` column/field added.
- `CompanyShippingAddress.importSource` and `CompanyShippingAddress.importDatetime` fields added to E schema.

## Data freshness indicators

Core table row counts and latest timestamps observed:

| Target | Key counts / freshness |
| --- | --- |
| A local DB | `Order=25,866`, `OrderProduct=94,524`, `OrderCollection=33,363`, `Company=3,287`, `Product=4,941`; max import timestamps mostly `2026-05-12`. |
| B dev DB | `Order=26,119`, `OrderProduct=95,322`, `OrderCollection=33,688`, `Company=3,288`, `Product=4,967`, `OrderClosing=3,800`; max import timestamps mostly `2026-05-21`. |
| C prod DB | `Order=6,380`, `OrderProduct=23,807`, `OrderCollection=6,127`, `Company=2,970`, `Product=4,234`, `OrderClosing=3,800`; operational timestamps are current around `2026-05-21` to `2026-05-23`, but imported CRM/SF volumes are smaller than dev. |

Interpretation:

- A is structurally current after the 2026-05-25 schema update. Its data freshness is separate from this schema-only update.
- B is the most complete non-prod data target.
- C is schema-current, but should not be assumed to have dev-sized imported data.

## How to refresh everything to latest

### 1. Preserve current state before changing DBs

Run read-only dumps or at least schema dumps before modifying any target:

```bash
cd /Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az
mkdir -p proc/db-dumps
pg_dump "$DATABASE_URL" --schema-only > proc/db-dumps/local-schema-before-$(date +%Y%m%d_%H%M%S).sql
pg_dump "$DATABASE_URL_REMOTE" --schema-only > proc/db-dumps/dev-schema-before-$(date +%Y%m%d_%H%M%S).sql
```

For prod, use a readonly/snapshot process if available. Do not run destructive reset/load scripts against prod.

### 2. Refresh local DB schema A from D

Use D as the app schema source:

```bash
cd /Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az
DATABASE_URL='postgresql://...local.../dof_portal' bun run --cwd apps/server db:push
```

Expected local structural changes:

- create `OrderClosing`
- add nullable `Product.productType`

Then verify:

```bash
psql "$DATABASE_URL" -At -c "select count(*) from information_schema.tables where table_schema='public' and table_name='OrderClosing';"
psql "$DATABASE_URL" -At -c "select count(*) from information_schema.columns where table_schema='public' and table_name='Product' and column_name='productType';"
```

### 3. Refresh local DB data A from current loaders

The portal-data repo owns data loading. For local FG + SF refresh:

```bash
cd /Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dofing-order-portal-data-3-az
npm run db:test
npm run load:fg:full
npm run load:sf:full
```

Notes:

- `load:fg:full` loads FG and runs post-processing.
- `load:sf:full` resets only `importSource='sf'` rows and reloads SF data.
- If only SF needs to be made current, run `npm run load:sf:full`.

### 4. Refresh dev DB data B

Dev schema is already current. Refresh dev data through the remote loader path:

```bash
cd /Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dofing-order-portal-data-3-az
DATABASE_URL_REMOTE='postgresql://...dev.../dof_portal_dev' npm run db:test
DATABASE_URL_REMOTE='postgresql://...dev.../dof_portal_dev' npm run load:sf:full:dev
```

Existing project memory says `load:sf:full:dev` is the known one-shot route for dev SF reset + load. Prior runs also showed a non-fatal `Feedback_createdByUk_fkey` warning can appear during User deletion while the load still completes.

FG dev refresh is not exposed as a dedicated `:dev` script in `package.json`. If FG must be refreshed on dev too, run the local FG loader with `DATABASE_URL` temporarily pointing at dev, or add a guarded remote FG script first. Do that only after making the target explicit because FG reset/load is broad.

### 5. Keep prod DB C schema-current without resetting prod data

C already matches D/B structurally. For future schema changes:

- prefer a reviewed, idempotent SQL migration for prod when data preservation matters;
- or run `prisma db push` only after reviewing the generated diff and taking a snapshot;
- never run `load:fg:reset`, `load:fg:full`, `load:sf:reset`, or `load:sf:full` against prod unless an explicit production data reload has been approved.

For the current check, no prod schema action is needed.

### 6. Refresh E portal-data Prisma schema

E should be regenerated from the current DB after A or B is current. Since B already matches D/C, pulling from dev is the cleanest:

```bash
cd /Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dofing-order-portal-data-3-az
DATABASE_URL_REMOTE='postgresql://...dev.../dof_portal_dev' npm run pull:schema:remote
```

The script `src/loaders/portal/pull-schema.ts` masks the printed URL and runs:

```bash
npx prisma db pull --config="data/prisma/prisma.config.ts"
```

Expected E changes:

- add `OrderClosing`
- add `Product.productType`
- add `CompanyShippingAddress.importSource`
- add `CompanyShippingAddress.importDatetime`

After pulling, compare E against D and verify the loaders still typecheck/run.

### 7. Verification checklist after refresh

Run these checks before calling the refresh complete:

```bash
# DB object parity
psql "$DATABASE_URL" -At -c "select count(*) from information_schema.tables where table_schema='public' and table_type='BASE TABLE';"
psql "$DATABASE_URL" -At -c "select count(*) from information_schema.columns where table_schema='public';"

# App Prisma client
cd /Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az
bun run db:generate
bun run build:server

# Portal-data DB connectivity and schema pull sanity
cd /Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dofing-order-portal-data-3-az
npm run db:test
npm run pull:schema
```

Expected post-refresh parity:

- A local DB: 45 tables / 677 columns
- B dev DB: 45 tables / 677 columns
- C prod DB: 45 tables / 677 columns
- D web Prisma schema: 45 models / 677 scalar columns
- E portal-data Prisma schema: 45 models / 677 scalar columns

## Commands used for this check

- `psql` metadata queries against A/B/C:
  - database metadata
  - table count
  - column count
  - exact table row counts
  - selected max `importDatetime`, `createdAt`, `updatedAt`
- local Prisma schema parsing for D/E table and scalar column sets
- direct file inspection of:
  - D schema
  - E schema
  - `dofing-order-portal-data-3-az/src/loaders/portal/pull-schema.ts`
  - `dofing-order-portal-data-3-az/package.json`
  - `dof-order-web-3-az/apps/server/package.json`
