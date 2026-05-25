# Portal DB / Prisma schema refresh result

Date: 2026-05-25
Initial check: 2026-05-25 15:19 KST
Refresh completed: 2026-05-25

## Scope

- A: local PostgreSQL `dof_portal`
- B: dev PostgreSQL `dof_portal_dev`
- C: prod PostgreSQL `dof_portal_prod`
- D: `dof-order-app/dof-order-web-3-az/apps/server/prisma/schema.prisma`
- E: `dofing-order-portal-data-3-az/data/prisma/schema.prisma`

Connection strings were read from local env values. This note intentionally keeps passwords out of the document.

## Result

Prod was treated as read-only. The only prod operation was `pg_dump`.

Dev and local were refreshed from the prod dump. Their original `ApiToken` rows were preserved and restored after the prod data restore.

Final state:

| Target | Tables / models | Public scalar columns | `dofbot` tables | State |
| --- | ---: | ---: | ---: | --- |
| A local DB | 45 | 684 | 23 | Refreshed from prod. Matches prod public schema. |
| B dev DB | 45 | 684 | 23 | Refreshed from prod. Matches prod public schema. |
| C prod DB | 45 | 684 | 23 | Source dump only; not modified. |
| D web Prisma schema | 45 | 684 | n/a | Matches prod/dev/local public schema. |
| E portal-data Prisma schema | 45 | 684 | n/a | Pulled from refreshed dev. Matches D. |

Diff verification:

| Comparison | Result |
| --- | --- |
| A local DB vs C prod DB | 0 table diffs, 0 column diffs |
| B dev DB vs C prod DB | 0 table diffs, 0 column diffs |
| C prod DB vs D web schema | 0 table diffs, 0 column diffs |
| D web schema vs E portal-data schema | 0 table diffs, 0 column diffs |

## Before refresh

The user's expectation was correct:

- C prod DB and D web Prisma schema were the current latest structural source.
- A local DB and B dev DB matched each other, but were behind prod/web schema.
- E portal-data Prisma schema was partially refreshed, but still behind D by `erpInfo` fields.

Missing before refresh:

| Target | Missing columns |
| --- | --- |
| A/B | `Company.contactMemo`, `Company.email2`, `Company.erpInfo`, `Company.mobile1`, `Company.mobile2`, `Order.erpInfo`, `OrderCollection.erpInfo` |
| E | `Company.erpInfo`, `Order.erpInfo`, `OrderCollection.erpInfo` |

## Final data indicators

Selected final row counts:

| Target | `Order` | `OrderProduct` | `OrderCollection` | `OrderClosing` | `Company` | `Product` |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| A local DB | 26,127 | 95,359 | 33,697 | 3,800 | 3,289 | 4,967 |
| B dev DB | 26,127 | 95,359 | 33,697 | 3,800 | 3,289 | 4,967 |
| C prod DB | 26,127 | 95,359 | 33,697 | 3,800 | 3,289 | 4,967 |

Extension state:

| Target | Extensions |
| --- | --- |
| A local DB | `pg_trgm:1.6`, `plpgsql:1.0`, `vector:0.8.0` |
| B dev DB | `pg_trgm:1.6`, `plpgsql:1.0`, `vector:0.8.2` |
| C prod DB | `pg_trgm:1.6`, `plpgsql:1.0`, `vector:0.8.0` |

The extension version difference on dev is pre-existing target infrastructure. Public schema and data restored successfully with dev's existing `vector` extension.

## ApiToken preservation

`ApiToken` was not overwritten with prod tokens.

Final token state:

| Target | Total tokens | Active tokens | Max lastUsedAt |
| --- | ---: | ---: | --- |
| A local DB | 3 | 2 | 2026-05-13 05:41:01.189 |
| B dev DB | 8 | 3 | 2026-05-23 12:45:57.708 |
| C prod DB | 4 | 3 | 2026-05-25 06:05:29.472 |

Implementation detail:

- `ApiToken` rows were copied into `refresh_preserve."ApiToken_20260525"` before restore.
- `scope` was stored as `text`, not as enum, so `pg_restore --clean` could drop/recreate `public."ApiTokenScope"` safely.
- After restore, preserved rows were inserted back into `public."ApiToken"` with `scope::public."ApiTokenScope"`.
- The `ApiToken` sequence was reset with `setval`.
- `refresh_preserve` was dropped after token restore.

## Dump artifacts

Created from prod using read-only `pg_dump`:

- `output/db-dumps/2026-05-25/prod-full-20260525_152558.dump`
- `output/db-dumps/2026-05-25/prod-schema-20260525_152558.sql`
- `output/db-dumps/2026-05-25/prod-full-20260525_152558.no-extension.list`

Treat these files as sensitive.

## Restore notes

The prod dump includes `pg_trgm` and `vector` extension entries. Target restore used a filtered restore list excluding extension create/drop/comment entries:

```bash
pg_restore --list prod-full-20260525_152558.dump \
  | awk '!(($0 ~ / EXTENSION - (pg_trgm|vector) /) || ($0 ~ / COMMENT - EXTENSION (pg_trgm|vector) /))' \
  > prod-full-20260525_152558.no-extension.list
```

Then restore used:

```bash
pg_restore \
  --clean \
  --if-exists \
  --exit-on-error \
  --single-transaction \
  --no-owner \
  --no-acl \
  --use-list prod-full-20260525_152558.no-extension.list \
  --dbname "$TARGET_DATABASE_URL" \
  prod-full-20260525_152558.dump
```

Local-specific issue:

- Local container was running `postgres:17-alpine`, while `docker-compose.yml` points to `pgvector/pgvector:pg17`.
- Local initially lacked `vector`, so restoring `dofbot.product_search_document.embedding public.vector(1536)` failed and rolled back.
- `pgvector` 0.8.0 was built inside the local PG17 container from source and `CREATE EXTENSION vector` was applied before retrying local restore.

## Repeatable refresh procedure

Use env vars with masked or local-only values:

```bash
export LOCAL_DATABASE_URL='postgresql://.../dof_portal'
export DEV_DATABASE_URL='postgresql://.../dof_portal_dev'
export PROD_DATABASE_URL='postgresql://.../dof_portal_prod'
```

1. Dump prod read-only:

```bash
pg_dump "$PROD_DATABASE_URL" --format=custom --no-owner --no-acl --file prod-full.dump
pg_dump "$PROD_DATABASE_URL" --schema-only --no-owner --no-acl --file prod-schema.sql
```

2. Preserve target `ApiToken` with enum-safe text scope:

```sql
DROP SCHEMA IF EXISTS refresh_preserve CASCADE;
CREATE SCHEMA refresh_preserve;
CREATE TABLE refresh_preserve."ApiToken_20260525" AS
SELECT
  id, uk, name, "tokenHash", prefix, "lastChars", scope::text AS scope,
  "expiresAt", "lastUsedAt", "isRevoked", "revokedAt", "revokedBy",
  "userUk", "createdAt", "createdIp"
FROM public."ApiToken";
```

3. Restore prod dump into dev/local using a restore list that excludes extension entries.

4. Restore target `ApiToken`:

```sql
BEGIN;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM refresh_preserve."ApiToken_20260525" p
    LEFT JOIN public."User" u ON u.uk = p."userUk"
    WHERE u.uk IS NULL
  ) THEN
    RAISE EXCEPTION 'preserved ApiToken rows reference missing User.uk values';
  END IF;
END $$;

TRUNCATE TABLE public."ApiToken" RESTART IDENTITY;

INSERT INTO public."ApiToken" (
  id, uk, name, "tokenHash", prefix, "lastChars", scope,
  "expiresAt", "lastUsedAt", "isRevoked", "revokedAt", "revokedBy",
  "userUk", "createdAt", "createdIp"
)
SELECT
  id, uk, name, "tokenHash", prefix, "lastChars", scope::public."ApiTokenScope",
  "expiresAt", "lastUsedAt", "isRevoked", "revokedAt", "revokedBy",
  "userUk", "createdAt", "createdIp"
FROM refresh_preserve."ApiToken_20260525";

SELECT setval(
  pg_get_serial_sequence('public."ApiToken"', 'id'),
  COALESCE((SELECT max(id) FROM public."ApiToken"), 1),
  (SELECT count(*) > 0 FROM public."ApiToken")
);

DROP SCHEMA refresh_preserve CASCADE;

COMMIT;
```

5. Pull E schema from refreshed dev:

```bash
cd /Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dofing-order-portal-data-3-az
npm run pull:schema:remote
```

6. Verify:

```bash
cd /Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dofing-order-portal-data-3-az
npm run db:test

cd /Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az
bun run db:generate
bun run build:server
```

## Verification performed

- Prod dump created with `pg_dump`; no write operation was run against prod.
- Dev/local restored from prod dump with `pg_restore --single-transaction`.
- Dev/local original `ApiToken` rows restored after prod data restore.
- `npm run pull:schema:remote` regenerated E from refreshed dev.
- Public table/column diff:
  - local vs prod: zero
  - dev vs prod: zero
  - prod vs D: zero
  - D vs E: zero
- Tooling:
  - `npm run db:test` succeeded against local DB.
  - `bun run db:generate` succeeded.
  - `bun run build:server` succeeded.
