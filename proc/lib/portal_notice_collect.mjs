#!/usr/bin/env node
import fs from 'node:fs';
import { createRequire } from 'node:module';
import path from 'node:path';

const DEFAULT_PORTAL_ROOT =
  '/Users/gq/works/projs/dofing-order-app/order-web/dof-order-app/dof-order-web-3-az';
const KST_OFFSET_MS = 9 * 60 * 60 * 1000;
let errorContext = null;

function usage() {
  return `Usage: node proc/lib/portal_notice_collect.mjs <YYYY-MM-DD> [options]

Collect portal Notice rows into data/daily/<date>/raw/portal-notices.json.

Options:
  --out <path>          Output path. Defaults to daily raw portal-notices.json.
  --portal-root <path>  Portal repo root. Defaults to known local dof-order-web-3-az.
  --env <name>          DB URL env key from portal .env. Defaults to DATABASE_URL_REMOTE, then DATABASE_URL.
  --release-limit <n>   Max release-note snapshot rows. Defaults to 50.
  --published-limit <n> Max published notice snapshot rows. Defaults to 30.
  --help               Show this help.
`;
}

function parseArgs(argv) {
  const args = {
    day: null,
    out: null,
    portalRoot: process.env.PORTAL_WEB_ROOT || DEFAULT_PORTAL_ROOT,
    dbEnv: process.env.PORTAL_NOTICE_DB_ENV || null,
    releaseLimit: 50,
    publishedLimit: 30,
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
    } else if (arg === '--release-limit') {
      args.releaseLimit = Number(argv[++i]);
    } else if (arg === '--published-limit') {
      args.publishedLimit = Number(argv[++i]);
    } else if (!arg.startsWith('--') && !args.day) {
      args.day = arg;
    } else {
      throw new Error(`Unknown argument: ${arg}`);
    }
  }

  for (const key of ['releaseLimit', 'publishedLimit']) {
    if (!Number.isFinite(args[key]) || args[key] < 1) {
      throw new Error(`--${key.replace(/[A-Z]/g, (c) => `-${c.toLowerCase()}`)} must be a positive number.`);
    }
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

function isReleaseNote(row) {
  const text = `${row.title || ''}\n${row.content || ''}`.toLowerCase();
  return /릴리즈|release|release note|릴리스|배포\s*노트|v\d+\.\d+|버전\s*\d/.test(text);
}

function normalizeRow(row) {
  const out = {
    ...row,
    isReleaseNote: isReleaseNote(row),
  };
  for (const key of ['startAt', 'endAt', 'createdAt', 'updatedAt', 'deletedAt']) {
    if (out[key]) {
      out[key] = out[key] instanceof Date ? out[key].toISOString() : out[key];
      out[`${key}Kst`] = toKst(out[key]);
    } else if (key in out) {
      out[`${key}Kst`] = null;
    }
  }
  return out;
}

function sourceMeta(portalRoot, dbEnv) {
  return {
    source: 'portal-notices',
    portalRoot,
    dbEnv,
    readOnly: true,
    semantics:
      'Portal notices and release notes are treated as AX team work and as the user/company work signal during night-routine summaries.',
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
    args.out || path.join('data', 'daily', args.day, 'raw', 'portal-notices.json');
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

  const noticeSelect = `
    SELECT
      n.id,
      n.uk,
      n.title,
      n.content,
      n."authorUk",
      u.name AS "authorName",
      u.email AS "authorEmail",
      n."isPinned",
      n."isPublished",
      n.views,
      n.type,
      n.severity,
      n."startAt",
      n."endAt",
      n."createdAt",
      n."updatedAt",
      n."deletedAt"
    FROM "Notice" n
    LEFT JOIN "User" u ON u.uk = n."authorUk"
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
      `${noticeSelect}
       WHERE (
         (n."createdAt" >= $1 AND n."createdAt" < $2)
         OR (n."updatedAt" >= $1 AND n."updatedAt" < $2)
       )
       ORDER BY greatest(n."createdAt", coalesce(n."updatedAt", n."createdAt")) DESC`,
      [since, until],
    );

    const releaseNotes = await client.query(
      `${noticeSelect}
       WHERE n."deletedAt" IS NULL
         AND (
           n.title ILIKE '%릴리즈%'
           OR n.content ILIKE '%릴리즈%'
           OR n.title ILIKE '%릴리스%'
           OR n.content ILIKE '%릴리스%'
           OR n.title ILIKE '%release%'
           OR n.content ILIKE '%release%'
           OR n.title ILIKE '%배포 노트%'
           OR n.content ILIKE '%배포 노트%'
           OR n.title ~* 'v[0-9]+\\.[0-9]+'
           OR n.content ~* 'v[0-9]+\\.[0-9]+'
         )
       ORDER BY n."createdAt" DESC
       LIMIT $1`,
      [Math.trunc(args.releaseLimit)],
    );

    const published = await client.query(
      `${noticeSelect}
       WHERE n."deletedAt" IS NULL
         AND n."isPublished" = true
       ORDER BY n."isPinned" DESC, n."createdAt" DESC
       LIMIT $1`,
      [Math.trunc(args.publishedLimit)],
    );

    await client.query('COMMIT');
    began = false;

    const dailyNotices = daily.rows.map(normalizeRow);
    const releaseNoteSnapshot = releaseNotes.rows.map(normalizeRow);
    const publishedNotices = published.rows.map(normalizeRow);
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
        dailyNotices: dailyNotices.length,
        dailyReleaseNotes: dailyNotices.filter((row) => row.isReleaseNote).length,
        releaseNoteSnapshot: releaseNoteSnapshot.length,
        publishedNotices: publishedNotices.length,
      },
      dailyNotices,
      releaseNoteSnapshot,
      publishedNotices,
      notes: [
        'dailyNotices includes Notice rows created or updated during the KST day.',
        'releaseNoteSnapshot is a current snapshot of non-deleted notices whose title/content looks like release notes.',
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
        dailyNotices: 0,
        dailyReleaseNotes: 0,
        releaseNoteSnapshot: 0,
        publishedNotices: 0,
      },
      dailyNotices: [],
      releaseNoteSnapshot: [],
      publishedNotices: [],
      error: {
        message: error.message || String(error),
        occurredAt: new Date().toISOString(),
      },
      notes: [
        'Portal Notice collection failed. Keep the rest of the night routine running and record this failure in the daily summary.',
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
