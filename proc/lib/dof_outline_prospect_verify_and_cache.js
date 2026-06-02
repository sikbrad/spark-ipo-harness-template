#!/usr/bin/env node

const fs = require("fs");
const path = require("path");

const ROOT = "/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04";
const BASE = path.join(ROOT, "output/dof-overseas-customer-prospects/2026-05-30/scale5000");
const OUTLINE_PUBLISH = path.join(BASE, "outline_publish");
const OUT_DIR = path.join(OUTLINE_PUBLISH, "prospect_headless_search_update");
const DOC_CACHE = path.join(OUTLINE_PUBLISH, "outline_docs.json");

const OUTLINE_BASE = "https://outline.doflab.com";
const SECTION_TITLE = "## 공개 웹검색 보강 (2026-06-02)";
const MERGED_JSONL = path.join(OUT_DIR, "outline_first_search_updates.merged.jsonl");
const VERIFY_JSON = path.join(OUT_DIR, "outline_first_search_verification.json");

function parseArgs() {
  const args = { concurrency: 16, skipReadback: false };
  for (let i = 2; i < process.argv.length; i += 1) {
    const arg = process.argv[i];
    if (arg === "--concurrency") args.concurrency = Number(process.argv[++i]);
    else if (arg === "--skip-readback") args.skipReadback = true;
  }
  return args;
}

function readEnv(name) {
  const env = fs.readFileSync(path.join(ROOT, ".env"), "utf8");
  for (const line of env.split(/\r?\n/)) {
    if (line.startsWith(`${name}=`)) return line.split("=").slice(1).join("=").trim().replace(/^['"]|['"]$/g, "");
  }
  throw new Error(`${name} not found`);
}

function readJsonlSafe(file) {
  const rows = [];
  let bad = 0;
  for (const line of fs.readFileSync(file, "utf8").split(/\r?\n/)) {
    if (!line.trim()) continue;
    try {
      rows.push(JSON.parse(line));
    } catch {
      bad += 1;
    }
  }
  return { rows, bad };
}

function resultFiles() {
  if (!fs.existsSync(OUT_DIR)) return [];
  return fs
    .readdirSync(OUT_DIR)
    .filter((name) => /^outline_first_search_updates(?:\.shard\d+-of-\d+)?\.jsonl$/.test(name))
    .sort()
    .map((name) => path.join(OUT_DIR, name));
}

function loadTargets() {
  const cache = JSON.parse(fs.readFileSync(DOC_CACHE, "utf8")).docs || {};
  const countryDocs = new Map();
  for (const [key, value] of Object.entries(cache)) {
    if (key.startsWith("country:")) countryDocs.set(value.id, key);
  }
  const targets = [];
  for (const [key, doc] of Object.entries(cache)) {
    if (!key.startsWith("company:") || key.startsWith("company:portal:")) continue;
    const countryKey = countryDocs.get(doc.parent_document_id) || "";
    const parts = countryKey.split(":");
    const status = parts.length >= 4 ? parts[2] : "";
    if (!status.startsWith("잠재고객-")) continue;
    targets.push({ key, doc_id: doc.id, title: doc.title, status });
  }
  targets.sort((a, b) => String(a.title || "").localeCompare(String(b.title || "")));
  return targets;
}

function latestSuccessByDoc() {
  const byDoc = new Map();
  const byKey = new Map();
  let valid = 0;
  let bad = 0;
  let failed = 0;
  for (const file of resultFiles()) {
    const parsed = readJsonlSafe(file);
    bad += parsed.bad;
    for (const row of parsed.rows) {
      valid += 1;
      if (!row.updated) {
        failed += 1;
        continue;
      }
      if (row.doc_id) byDoc.set(row.doc_id, row);
      if (row.key) byKey.set(row.key, row);
    }
  }
  return { byDoc, byKey, stats: { valid, bad, failed } };
}

async function outlineApi(apiKey, endpoint, body) {
  const response = await fetch(`${OUTLINE_BASE}/api/${endpoint}`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  const json = await response.json().catch(() => ({}));
  if (response.status >= 400) {
    throw new Error(`${endpoint} failed ${response.status}: ${JSON.stringify(json).slice(0, 600)}`);
  }
  return json.data;
}

function writeMergedCache(targets, byDoc, byKey) {
  const rows = [];
  for (const target of targets) {
    const row = byDoc.get(target.doc_id) || byKey.get(target.key);
    if (row) rows.push(row);
  }
  fs.writeFileSync(MERGED_JSONL, `${rows.map((row) => JSON.stringify(row)).join("\n")}\n`);
  return rows;
}

function summarizeMerged(rows) {
  const trust = {};
  let officialOk = 0;
  let withRelevant = 0;
  let withMedia = 0;
  for (const row of rows) {
    trust[row.trust || "미상"] = (trust[row.trust || "미상"] || 0) + 1;
    if (row.official_page?.ok) officialOk += 1;
    if (Array.isArray(row.relevant_results) && row.relevant_results.length) withRelevant += 1;
    const hasMedia = Array.isArray(row.relevant_results)
      ? row.relevant_results.some((item) => /\b(news|press|article|interview|award|expo|exhibition|congress|conference|ids|aeedc|capp|sidex|event|trade fair|pavilion)\b/i.test(`${item.title} ${item.snippet} ${item.url}`))
      : false;
    if (hasMedia) withMedia += 1;
  }
  return { trust, official_ok: officialOk, with_relevant_results: withRelevant, with_media_or_event_signal: withMedia };
}

async function verifyReadback(apiKey, targets, concurrency) {
  const missing = [];
  const failed = [];
  let cursor = 0;
  let checked = 0;
  async function worker() {
    while (cursor < targets.length) {
      const index = cursor;
      cursor += 1;
      const target = targets[index];
      try {
        const info = await outlineApi(apiKey, "documents.info", { id: target.doc_id });
        if (!String(info.text || "").includes(SECTION_TITLE)) {
          missing.push(target);
        }
      } catch (error) {
        failed.push({ ...target, error: String(error.message || error).slice(0, 500) });
      }
      checked += 1;
      if (checked % 250 === 0 || checked === targets.length) {
        console.log(JSON.stringify({ checked, target: targets.length, missing: missing.length, failed: failed.length }));
      }
    }
  }
  await Promise.all(Array.from({ length: Math.max(1, Math.min(concurrency, targets.length)) }, () => worker()));
  return { missing, failed };
}

async function main() {
  const args = parseArgs();
  const targets = loadTargets();
  const { byDoc, byKey, stats } = latestSuccessByDoc();
  const merged = writeMergedCache(targets, byDoc, byKey);
  const mergedStats = summarizeMerged(merged);
  const result = {
    generated_at: new Date().toISOString(),
    target_count: targets.length,
    merged_cache_count: merged.length,
    log_stats: stats,
    merged_stats: mergedStats,
    readback: null,
    merged_jsonl: MERGED_JSONL,
  };
  if (!args.skipReadback) {
    const apiKey = readEnv("DOF_OUTLINE_KEY");
    const readback = await verifyReadback(apiKey, targets, args.concurrency);
    result.readback = {
      checked: targets.length,
      section_present: targets.length - readback.missing.length,
      section_missing: readback.missing.length,
      request_failed: readback.failed.length,
      missing: readback.missing,
      failed: readback.failed,
    };
  }
  fs.writeFileSync(VERIFY_JSON, JSON.stringify(result, null, 2));
  console.log(JSON.stringify(result, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
