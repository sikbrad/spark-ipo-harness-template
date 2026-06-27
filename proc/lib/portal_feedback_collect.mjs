#!/usr/bin/env node
import fs from 'node:fs';
import { createRequire } from 'node:module';
import path from 'node:path';

const DEFAULT_PORTAL_ROOT =
  '/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az';
const KST_OFFSET_MS = 9 * 60 * 60 * 1000;
let errorContext = null;

function usage() {
  return `Usage: node proc/lib/portal_feedback_collect.mjs <YYYY-MM-DD> [options]

Collect portal Feedback rows into data/daily/<date>/raw/portal-feedback.json.

Options:
  --out <path>          Output path. Defaults to daily raw portal-feedback.json.
  --portal-root <path>  Portal repo root. Defaults to known local dof-order-web-3-az.
  --env <name>          DB URL env key from portal .env. Defaults to DATABASE_URL_REMOTE, then DATABASE_URL.
  --open-limit <n>      Max active feedback snapshot rows. Defaults to 100.
  --help               Show this help.
`;
}

function parseArgs(argv) {
  const args = {
    day: null,
    out: null,
    portalRoot: process.env.PORTAL_WEB_ROOT || DEFAULT_PORTAL_ROOT,
    dbEnv: process.env.PORTAL_FEEDBACK_DB_ENV || null,
    openLimit: 100,
  };

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === '--help' || arg === '-h') {
      args.help = true;
    } else if (arg === '--out') {
      args.out = argv[++i];
    } else if (arg === '--portal-root') {
      args.portalRoot = argv[++i];
    } else if (arg === '--env') {
      args.dbEnv = argv[++i];
    } else if (arg === '--open-limit') {
      args.openLimit = Number(argv[++i]);
    } else if (!arg.startsWith('--') && !args.day) {
      args.day = arg;
    } else {
      throw new Error(`Unknown argument: ${arg}`);
    }
  }

  if (!Number.isFinite(args.openLimit) || args.openLimit < 1) {
    throw new Error('--open-limit must be a positive number.');
  }
  return args;
}

function readEnv(file) {
  const env = {};
  for (const rawLine of fs.readFileSync(file, 'utf8').split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith('#') || !line.includes('=')) continue;
    const idx = line.indexOf('=');
    env[line.slice(0, idx)] = line.slice(idx + 1).replace(/^['"]|['"]$/g, '');
  }
  return env;
}

function dayBoundsUtc(day) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(day)) {
    throw new Error('Date must be YYYY-MM-DD.');
  }
  const [year, month, date] = day.split('-').map(Number);
  const since = new Date(Date.UTC(year, month - 1, date, -9, 0, 0, 0));
  const until = new Date(since.getTime() + 24 * 60 * 60 * 1000);
  return { since, until };
}

function toKst(value) {
  if (!value) return null;
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  const kst = new Date(date.getTime() + KST_OFFSET_MS);
  return `${kst.toISOString().replace('T', ' ').slice(0, 19)} KST`;
}

function normalizeRow(row) {
  const out = { ...row };
  for (const key of ['createdAt', 'updatedAt', 'notificationSentAt']) {
    if (out[key]) {
      out[key] = out[key] instanceof Date ? out[key].toISOString() : out[key];
      out[`${key}Kst`] = toKst(out[key]);
    } else if (key in out) {
      out[`${key}Kst`] = null;
    }
  }
  if (typeof out.links === 'string') {
    try {
      out.links = JSON.parse(out.links);
    } catch {
      // Keep the raw string if old records contain non-JSON links.
    }
  }
  return out;
}

function sourceMeta(portalRoot, dbEnv) {
  return {
    source: 'portal-feedback',
    portalRoot,
    dbEnv,
    readOnly: true,
    semantics:
      'Portal feedback is treated as AX team work and as the user/company work signal during night-routine summaries.',
  };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    process.stdout.write(usage());
    return;
  }
  if (!args.day) {
    throw new Error('Missing <YYYY-MM-DD>.');
  }

  const portalRoot = path.resolve(args.portalRoot);
  const outPath =
    args.out || path.join('data', 'daily', args.day, 'raw', 'portal-feedback.json');
  errorContext = {
    day: args.day,
    outPath,
    portalRoot,
    dbEnv: args.dbEnv || null,
  };
  const envFile = path.join(portalRoot, '.env');
  const env = readEnv(envFile);
  const dbEnv = args.dbEnv || (env.DATABASE_URL_REMOTE ? 'DATABASE_URL_REMOTE' : 'DATABASE_URL');
  errorContext.dbEnv = dbEnv;
  const connectionString = env[dbEnv];
  if (!connectionString) {
    throw new Error(`Missing ${dbEnv} in ${envFile}.`);
  }

  const requireFromPortal = createRequire(path.join(portalRoot, 'package.json'));
  const { Client } = requireFromPortal('pg');
  const { since, until } = dayBoundsUtc(args.day);
  errorContext.range = {
    sinceUtc: since.toISOString(),
    untilUtc: until.toISOString(),
    sinceKst: toKst(since),
    untilKst: toKst(until),
  };

  const feedbackSelect = `
    SELECT
      f.id,
      f.uk,
      f.type::text AS type,
      f.status::text AS status,
      f.message,
      f."pageUrl",
      f."userAgent",
      f."errorStack",
      f."aiReviewMemo",
      f."adminNote",
      f."notificationSentAt",
      f."createdByUk",
      u.name AS "createdByName",
      u.email AS "createdByEmail",
      f."createdAt",
      f."updatedAt"
    FROM "Feedback" f
    LEFT JOIN "User" u ON u.uk = f."createdByUk"
  `;

  const client = new Client({
    connectionString,
    connectionTimeoutMillis: 15000,
    statement_timeout: 20000,
    query_timeout: 20000,
  });
  let began = false;
  try {
    await client.connect();
    await client.query('BEGIN READ ONLY');
    began = true;

    const daily = await client.query(
      `${feedbackSelect}
       WHERE (
         (f."createdAt" >= $1 AND f."createdAt" < $2)
         OR (f."updatedAt" >= $1 AND f."updatedAt" < $2)
         OR (f."notificationSentAt" >= $1 AND f."notificationSentAt" < $2)
       )
       ORDER BY greatest(
         f."createdAt",
         f."updatedAt",
         coalesce(f."notificationSentAt", f."createdAt")
       ) DESC`,
      [since, until],
    );

    const active = await client.query(
      `${feedbackSelect}
       WHERE f.status IN ('NEW', 'REVIEWED', 'DOING', 'PRE_DEPLOY')
       ORDER BY f."createdAt" DESC
       LIMIT $1`,
      [Math.trunc(args.openLimit)],
    );

    const notifications = await client.query(
      `SELECT
         n.id,
         n.uk,
         n."userUk",
         u.name AS "userName",
         u.email AS "userEmail",
         n.type::text AS type,
         n.title,
         n.message,
         n.read,
         n.links,
         n."createdAt"
       FROM "Notification" n
       LEFT JOIN "User" u ON u.uk = n."userUk"
       WHERE n.type = 'FEEDBACK'
         AND n."createdAt" >= $1
         AND n."createdAt" < $2
       ORDER BY n."createdAt" DESC`,
      [since, until],
    );

    await client.query('COMMIT');
    began = false;

    const payload = {
      ...sourceMeta(portalRoot, dbEnv),
      day: args.day,
      timezone: 'Asia/Seoul',
      range: {
        sinceUtc: since.toISOString(),
        untilUtc: until.toISOString(),
        sinceKst: toKst(since),
        untilKst: toKst(until),
      },
      counts: {
        dailyFeedback: daily.rows.length,
        activeFeedback: active.rows.length,
        feedbackNotifications: notifications.rows.length,
      },
      dailyFeedback: daily.rows.map(normalizeRow),
      activeFeedback: active.rows.map(normalizeRow),
      feedbackNotifications: notifications.rows.map(normalizeRow),
      notes: [
        'dailyFeedback includes Feedback rows created, updated, or notified during the KST day.',
        'activeFeedback is a current snapshot of NEW/REVIEWED/DOING/PRE_DEPLOY feedback for follow-up context.',
        'This collector only reads the portal database.',
      ],
    };

    fs.mkdirSync(path.dirname(outPath), { recursive: true });
    fs.writeFileSync(outPath, `${JSON.stringify(payload, null, 2)}\n`, 'utf8');
    process.stdout.write(
      `${JSON.stringify(
        {
          day: args.day,
          out: outPath,
          counts: payload.counts,
          dbEnv,
        },
        null,
        2,
      )}\n`,
    );
  } catch (error) {
    if (began) {
      await client.query('ROLLBACK').catch(() => {});
    }
    throw error;
  } finally {
    await client.end().catch(() => {});
  }
}

main().catch((error) => {
  if (errorContext?.outPath) {
    const payload = {
      ...sourceMeta(errorContext.portalRoot, errorContext.dbEnv),
      day: errorContext.day,
      timezone: 'Asia/Seoul',
      range: errorContext.range || null,
      counts: {
        dailyFeedback: 0,
        activeFeedback: 0,
        feedbackNotifications: 0,
      },
      dailyFeedback: [],
      activeFeedback: [],
      feedbackNotifications: [],
      error: {
        message: error.message || String(error),
        occurredAt: new Date().toISOString(),
      },
      notes: [
        'Portal Feedback collection failed. Keep the rest of the night routine running and record this failure in the daily summary.',
      ],
    };
    try {
      fs.mkdirSync(path.dirname(errorContext.outPath), { recursive: true });
      fs.writeFileSync(errorContext.outPath, `${JSON.stringify(payload, null, 2)}\n`, 'utf8');
    } catch {
      // The original error below is the useful one for the caller.
    }
  }
  console.error(error.message || error);
  process.exitCode = 1;
});
