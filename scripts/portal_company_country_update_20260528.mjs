import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';

const webRequire = createRequire('/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/package.json');
const { Client } = webRequire('pg');
const { v5: uuidv5 } = webRequire('uuid');

const DOF_NAMESPACE = '6ba7b810-9dad-11d1-80b4-00c04fd430c8';
const WORKSPACE = '/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04';
const PORTAL_ENV = '/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/.env';
const DRY_RUN_PATH = path.join(WORKSPACE, 'output/portal-company-country-update-20260528/company-country-update-dry-run.json');
const RESULT_PATH = path.join(WORKSPACE, 'output/portal-company-country-update-20260528/company-country-update-apply-result.json');
const ALLOWED_CURRENCIES = new Set(['KRW', 'USD', 'EUR', 'JPY']);

function generateUk(entityType, identifier) {
  return uuidv5(`${entityType}:${identifier}`, DOF_NAMESPACE);
}

function prodConnectionString() {
  for (const line of fs.readFileSync(PORTAL_ENV, 'utf8').split(/\r?\n/)) {
    const raw = line.trim();
    if (raw.includes('DATABASE_URL_REMOTE') && raw.includes('dof_portal_prod')) {
      const uncommented = raw.replace(/^#\s*/, '');
      return uncommented.slice(uncommented.indexOf('=') + 1).trim().replace(/^['"]|['"]$/g, '');
    }
  }
  throw new Error('prod DATABASE_URL_REMOTE for dof_portal_prod not found');
}

function detailFor(row, field) {
  const evidence = [
    `source=SharePoint 국가미지정_목록_담당자확인_20260526.xlsx`,
    `field=${field}`,
    `evidenceType=${row.evidenceType ?? ''}`,
    `confidence=${row.confidence ?? ''}`,
    `currencyRule=${row.currencyRule ?? ''}`,
  ];
  const summary = String(row.evidenceSummary ?? '').replace(/\s+/g, ' ').slice(0, 500);
  if (summary) evidence.push(`evidence=${summary}`);
  return evidence.join('; ');
}

function validateRows(rows) {
  const ready = rows.filter((row) => row.status === 'ready');
  const errors = [];
  for (const row of ready) {
    if (!/^[A-Z]{2}$/.test(row.targetCountry ?? '')) {
      errors.push(`id=${row.id} invalid targetCountry=${row.targetCountry}`);
    }
    if (!ALLOWED_CURRENCIES.has(row.targetCurrency)) {
      errors.push(`id=${row.id} invalid targetCurrency=${row.targetCurrency}`);
    }
  }
  if (errors.length > 0) {
    throw new Error(`preflight failed:\n${errors.join('\n')}`);
  }
  return ready;
}

async function main() {
  const apply = process.argv.includes('--apply');
  const rows = JSON.parse(fs.readFileSync(DRY_RUN_PATH, 'utf8'));
  const readyRows = validateRows(rows);
  const ids = readyRows.map((row) => row.id);

  const client = new Client({
    connectionString: prodConnectionString(),
    ssl: { rejectUnauthorized: false },
  });
  await client.connect();

  const result = {
    mode: apply ? 'apply' : 'dry-run',
    requestedRows: readyRows.length,
    companyUpdated: 0,
    currencyUpdated: 0,
    auditLogInserted: 0,
    orderSnapshotUpdated: 0,
    skipped: [],
    updated: [],
  };

  try {
    await client.query('BEGIN');

    const currentRes = await client.query(
      `select id, uk, name, country, currency::text as currency, "deletedAt"
       from "Company"
       where id = any($1::int[])
       for update`,
      [ids],
    );
    const currentById = new Map(currentRes.rows.map((row) => [row.id, row]));

    for (const row of readyRows) {
      const current = currentById.get(row.id);
      if (!current) {
        result.skipped.push({ id: row.id, reason: 'missing at apply time' });
        continue;
      }
      if (current.deletedAt) {
        result.skipped.push({ id: row.id, reason: 'deleted at apply time' });
        continue;
      }
      if (current.country && String(current.country).trim() !== '') {
        result.skipped.push({ id: row.id, reason: `country already ${current.country}` });
        continue;
      }

      const oldCountry = current.country ?? null;
      const oldCurrency = current.currency ?? null;
      const targetCountry = row.targetCountry;
      const targetCurrency = row.targetCurrency;

      if (apply) {
        await client.query(
          `update "Company"
           set country = $1,
               currency = $2::"Currency",
               "updatedAt" = now()
           where id = $3`,
          [targetCountry, targetCurrency, row.id],
        );
      }
      result.companyUpdated += 1;
      if (oldCurrency !== targetCurrency) result.currencyUpdated += 1;

      const auditEntries = [
        {
          uk: generateUk('AUDIT_LOG', `2026-05-28-country-update:${current.uk}:country:${targetCountry}`),
          field: 'country',
          oldValue: oldCountry,
          newValue: targetCountry,
          details: detailFor(row, 'country'),
        },
      ];
      if (oldCurrency !== targetCurrency) {
        auditEntries.push({
          uk: generateUk('AUDIT_LOG', `2026-05-28-country-update:${current.uk}:currency:${targetCurrency}`),
          field: 'currency',
          oldValue: oldCurrency,
          newValue: targetCurrency,
          details: detailFor(row, 'currency'),
        });
      }

      if (apply) {
        for (const entry of auditEntries) {
          const inserted = await client.query(
            `insert into "AuditLog"
               (uk, action, "entityType", "entityUk", "entityName", "userUk", field, "oldValue", "newValue", details)
             values
               ($1, 'UPDATE'::"AuditAction", 'COMPANY'::"EntityType", $2, $3, 'system', $4, $5, $6, $7)
             on conflict (uk) do nothing`,
            [entry.uk, current.uk, current.name, entry.field, entry.oldValue, entry.newValue, entry.details],
          );
          result.auditLogInserted += inserted.rowCount;
        }

        const orderUpdate = await client.query(
          `update "Order"
           set country = $1
           where "companyUk" = $2
             and status <> 'COMPLETED'
             and country is distinct from $1`,
          [targetCountry, current.uk],
        );
        result.orderSnapshotUpdated += orderUpdate.rowCount;
      } else {
        result.auditLogInserted += auditEntries.length;
      }

      result.updated.push({
        id: row.id,
        name: current.name,
        oldCountry,
        targetCountry,
        oldCurrency,
        targetCurrency,
        currencyRule: row.currencyRule,
      });
    }

    if (apply) {
      await client.query('COMMIT');
    } else {
      await client.query('ROLLBACK');
    }
  } catch (error) {
    await client.query('ROLLBACK');
    throw error;
  } finally {
    await client.end();
  }

  fs.writeFileSync(RESULT_PATH, JSON.stringify(result, null, 2));
  console.log(JSON.stringify({
    mode: result.mode,
    requestedRows: result.requestedRows,
    companyUpdated: result.companyUpdated,
    currencyUpdated: result.currencyUpdated,
    auditLogInserted: result.auditLogInserted,
    orderSnapshotUpdated: result.orderSnapshotUpdated,
    skipped: result.skipped,
    resultPath: RESULT_PATH,
  }, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
