# Portal DB / Prisma schema state check

Date: 2026-05-25
Checked at: 2026-05-25 15:19 KST

## Scope

- A: local PostgreSQL `dof_portal`
- B: dev PostgreSQL `dof_portal_dev`
- C: prod PostgreSQL `dof_portal_prod`
- D: `dof-order-app/dof-order-web-3-az/apps/server/prisma/schema.prisma`
- E: `dofing-order-portal-data-3-az/data/prisma/schema.prisma`

Connection strings were read from the local `.env` / user-provided values. This note intentionally keeps passwords out of the document.

## Conclusion

The user's expectation is correct:

- **C prod DB and D web Prisma schema are the current latest structural source.**
- **A local DB and B dev DB match each other, but are behind prod/web schema.**
- **E portal-data Prisma schema is partially refreshed, but still behind D by 3 `erpInfo` fields.**
- No DB currently has Prisma `_prisma_migrations`; schema state is managed by `db push`, SQL/restore, and loader scripts rather than Prisma migrate history.

## Current status

| Target | Tables / models | Scalar columns | State |
| --- | ---: | ---: | --- |
| A local DB | 45 | 677 | Behind C/D by 7 columns. Same shape as B. |
| B dev DB | 45 | 677 | Behind C/D by 7 columns. Same shape as A. |
| C prod DB | 45 | 684 | Latest DB structure. Matches D. |
| D web Prisma schema | 45 | 684 | Latest schema source for the app. Matches C. |
| E portal-data Prisma schema | 45 | 681 | Behind D by 3 columns. |

Additional DB metadata:

| Target | PostgreSQL | Enums | Indexes | Constraints | `_prisma_migrations` |
| --- | --- | ---: | ---: | ---: | --- |
| A local DB | 17.9 | 30 | 262 | 430 | absent |
| B dev DB | 17.7 | 30 | 262 | 430 | absent |
| C prod DB | 17.7 | 30 | 262 | 430 | absent |

## Structural diff

### A local DB vs B dev DB

No table/column diff. They are structurally the same old version.

### C prod DB vs D web Prisma schema

No table/column diff. Treat **C/D** as the current structural source of truth.

### A/B vs C/D

A and B are missing these 7 columns:

| Table | Missing columns in A/B |
| --- | --- |
| `Company` | `contactMemo`, `email2`, `erpInfo`, `mobile1`, `mobile2` |
| `Order` | `erpInfo` |
| `OrderCollection` | `erpInfo` |

Relevant D schema locations:

- `Company.erpInfo`: line 300
- `Company.email2/mobile1/mobile2/contactMemo`: lines 314-317
- `Order.erpInfo`: line 437
- `OrderCollection.erpInfo`: line 856

### E portal-data Prisma schema vs D

E already has `Company.email2/mobile1/mobile2/contactMemo`, but is missing these 3 fields:

| Table/model | Missing in E |
| --- | --- |
| `Company` | `erpInfo` |
| `Order` | `erpInfo` |
| `OrderCollection` | `erpInfo` |

## Data freshness indicators

Selected row counts and latest timestamps:

| Target | Key counts / freshness |
| --- | --- |
| A local DB | `Order=25,866`, `OrderProduct=94,524`, `OrderCollection=33,356`, `OrderClosing=0`, `Company=3,287`, `Product=4,941`; many `importDatetime` values are `2026-05-25 04:00-04:01`, but schema is old and `OrderClosing` is empty. |
| B dev DB | `Order=26,119`, `OrderProduct=95,322`, `OrderCollection=33,688`, `OrderClosing=3,800`, `Company=3,288`, `Product=4,967`; import timestamps mostly `2026-05-22`. |
| C prod DB | `Order=26,127`, `OrderProduct=95,359`, `OrderCollection=33,697`, `OrderClosing=3,800`, `Company=3,289`, `Product=4,967`; import timestamps mostly `2026-05-25 04:09-04:12`. |

Interpretation:

- Prod C is both structurally current and the freshest full data source in this check.
- Dev B is close, but older than prod and structurally missing the 7 current columns.
- Local A has recent loader timestamps for several tables, but it is not fully current because schema is old and `OrderClosing` has no rows.

## ApiToken preservation requirement

Do not overwrite target environment API tokens when refreshing dev/local from prod.

Observed `ApiToken` state:

| Target | Total tokens | Active tokens | Max createdAt | Max lastUsedAt |
| --- | ---: | ---: | --- | --- |
| A local DB | 3 | 2 | 2026-04-17 04:54:36.815 | 2026-05-13 05:41:01.189 |
| B dev DB | 8 | 3 | 2026-05-22 07:01:50.859 | 2026-05-23 12:45:57.708 |
| C prod DB | 4 | 3 | 2026-05-22 06:51:15.905 | 2026-05-25 06:05:29.472 |

`ApiToken` has a FK to `User(uk)` with `ON DELETE CASCADE`.

Current safety check: all A/B token `userUk` values exist in prod `User`, so current A/B tokens can be restored after a prod-based refresh without FK failure.

Important loader caveat:

- `load:fg:reset` eventually truncates `User` with `CASCADE`, so it can delete `ApiToken` even though `ApiToken` is not explicitly listed in `truncateAllTables()`.
- `load:sf:reset` only deletes `importSource='sf'` rows and does not directly target `ApiToken`; it also has a prod guard. Still, a prod-clone restore is the cleaner path for this full refresh.

## How to refresh everything to latest

Recommended source of truth for this refresh: **prod DB C + web Prisma schema D**.

Use environment variables such as:

```bash
export LOCAL_DATABASE_URL='postgresql://.../dof_portal'
export DEV_DATABASE_URL='postgresql://.../dof_portal_dev'
export PROD_DATABASE_URL='postgresql://.../dof_portal_prod'
```

Do not paste plaintext passwords into committed docs or scripts.

### 1. Create prod dump

Use a custom-format full dump so schema and data move together:

```bash
cd /Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04
mkdir -p output/db-dumps/2026-05-25

pg_dump "$PROD_DATABASE_URL" \
  --format=custom \
  --no-owner \
  --no-acl \
  --file output/db-dumps/2026-05-25/prod-full-$(date +%Y%m%d_%H%M%S).dump
```

Also keep schema-only evidence if needed:

```bash
pg_dump "$PROD_DATABASE_URL" \
  --schema-only \
  --no-owner \
  --no-acl \
  --file output/db-dumps/2026-05-25/prod-schema-$(date +%Y%m%d_%H%M%S).sql
```

Treat these dump files as sensitive.

### 2. Preserve target ApiToken before restoring prod into dev/local

For each target DB, preserve its current `ApiToken` rows inside a separate schema before `pg_restore`.
Do not put the preserve table in `public`; a `pg_restore --clean` path may drop/recreate `public` objects.

Example for dev:

```bash
psql "$DEV_DATABASE_URL" -v ON_ERROR_STOP=1 <<'SQL'
DROP SCHEMA IF EXISTS refresh_preserve CASCADE;
CREATE SCHEMA refresh_preserve;
CREATE TABLE refresh_preserve."ApiToken_20260525" AS TABLE public."ApiToken";
SQL
```

Example for local:

```bash
psql "$LOCAL_DATABASE_URL" -v ON_ERROR_STOP=1 <<'SQL'
DROP SCHEMA IF EXISTS refresh_preserve CASCADE;
CREATE SCHEMA refresh_preserve;
CREATE TABLE refresh_preserve."ApiToken_20260525" AS TABLE public."ApiToken";
SQL
```

This avoids writing token hashes to a separate disk dump. If an external backup is required, use `pg_dump --data-only --table='"ApiToken"'` and store it in a protected, gitignored location.

### 3. Restore prod dump into dev/local

Do not drop and recreate the whole database if you rely on the in-DB `refresh_preserve."ApiToken_20260525"` table. Restore into the existing database with `--clean`.

Example for dev:

```bash
pg_restore \
  --clean \
  --if-exists \
  --exit-on-error \
  --single-transaction \
  --no-owner \
  --no-acl \
  --dbname "$DEV_DATABASE_URL" \
  output/db-dumps/2026-05-25/prod-full-YYYYMMDD_HHMMSS.dump
```

Example for local:

```bash
pg_restore \
  --clean \
  --if-exists \
  --exit-on-error \
  --single-transaction \
  --no-owner \
  --no-acl \
  --dbname "$LOCAL_DATABASE_URL" \
  output/db-dumps/2026-05-25/prod-full-YYYYMMDD_HHMMSS.dump
```

### 4. Restore each target's original ApiToken rows

After the prod dump is restored, replace the prod `ApiToken` rows with the preserved target rows.

Run this on each target DB:

```bash
psql "$TARGET_DATABASE_URL" -v ON_ERROR_STOP=1 <<'SQL'
BEGIN;

-- Stop if preserved tokens reference users that are not present after the prod restore.
DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM refresh_preserve."ApiToken_20260525" p
    LEFT JOIN "User" u ON u.uk = p."userUk"
    WHERE u.uk IS NULL
  ) THEN
    RAISE EXCEPTION 'Preserved ApiToken rows reference missing User.uk values';
  END IF;
END $$;

TRUNCATE TABLE "ApiToken" RESTART IDENTITY;

INSERT INTO "ApiToken" (
  id, uk, name, "tokenHash", prefix, "lastChars", scope,
  "expiresAt", "lastUsedAt", "isRevoked", "revokedAt", "revokedBy",
  "userUk", "createdAt", "createdIp"
)
SELECT
  id, uk, name, "tokenHash", prefix, "lastChars", scope,
  "expiresAt", "lastUsedAt", "isRevoked", "revokedAt", "revokedBy",
  "userUk", "createdAt", "createdIp"
FROM refresh_preserve."ApiToken_20260525";

SELECT setval(
  pg_get_serial_sequence('"ApiToken"', 'id'),
  COALESCE((SELECT max(id) FROM "ApiToken"), 1),
  (SELECT count(*) > 0 FROM "ApiToken")
);

DROP SCHEMA refresh_preserve CASCADE;

COMMIT;
SQL
```

Use `TARGET_DATABASE_URL="$DEV_DATABASE_URL"` for dev and `TARGET_DATABASE_URL="$LOCAL_DATABASE_URL"` for local.

### 5. Refresh E portal-data Prisma schema from latest source

After dev is refreshed from prod, pull E from dev:

```bash
cd /Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dofing-order-portal-data-3-az
npm run pull:schema:remote
```

Expected E changes:

- add `Company.erpInfo`
- add `Order.erpInfo`
- add `OrderCollection.erpInfo`

### 6. Verify parity after refresh

Run table/column count checks:

```bash
psql "$DEV_DATABASE_URL" -At -c "select count(*) from information_schema.tables where table_schema='public' and table_type='BASE TABLE';"
psql "$DEV_DATABASE_URL" -At -c "select count(*) from information_schema.columns where table_schema='public';"
psql "$LOCAL_DATABASE_URL" -At -c "select count(*) from information_schema.tables where table_schema='public' and table_type='BASE TABLE';"
psql "$LOCAL_DATABASE_URL" -At -c "select count(*) from information_schema.columns where table_schema='public';"
```

Expected after refresh:

- A local DB: 45 tables / 684 columns
- B dev DB: 45 tables / 684 columns
- C prod DB: 45 tables / 684 columns
- D web Prisma schema: 45 models / 684 scalar columns
- E portal-data Prisma schema: 45 models / 684 scalar columns

Verify `ApiToken` preservation:

```bash
psql "$DEV_DATABASE_URL" -At -c 'select count(*), count(*) filter (where not "isRevoked" and "expiresAt" > now()) from "ApiToken";'
psql "$LOCAL_DATABASE_URL" -At -c 'select count(*), count(*) filter (where not "isRevoked" and "expiresAt" > now()) from "ApiToken";'
```

Expected current preserved counts if run now:

- Dev: 8 total / 3 active
- Local: 3 total / 2 active

Finally, verify app/data tooling:

```bash
cd /Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az
bun run db:generate
bun run build:server

cd /Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dofing-order-portal-data-3-az
npm run db:test
npm run pull:schema:remote
```

## Commands used for this check

- Read-only `psql` metadata queries against A/B/C:
  - database metadata
  - table/column/enum/index/constraint counts
  - selected row counts
  - selected max `importDatetime`, `createdAt`, `updatedAt`
  - `ApiToken` counts and FK relation
- Local Prisma schema parsing for D/E table and scalar column sets.
- Direct file inspection of:
  - D schema
  - E schema
  - `dofing-order-portal-data-3-az/src/loaders/portal/pull-schema.ts`
  - `dofing-order-portal-data-3-az/src/scripts/reset-sf-data.ts`
  - `dofing-order-portal-data-3-az/src/lib/db.ts`
  - package scripts in both repos
