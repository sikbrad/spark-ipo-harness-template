#!/usr/bin/env node

const fs = require("fs");
const path = require("path");

const ROOT = "/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04";
const OUT_DIR = path.join(
  ROOT,
  "output/dof-overseas-customer-prospects/2026-05-30/scale5000/outline_publish/prospect_headless_search_update",
);
const OUT_JSONL = path.join(OUT_DIR, "today_added_localized_search_updates.merged.jsonl");
const OUT_JSON = path.join(OUT_DIR, "today_added_localized_search_summary.merged.json");
const MEDIA_RE = /\b(news|press|article|interview|award|awards|expo|exhibition|congress|conference|ids|aeedc|capp|sidex|event|trade fair|pavilion)\b/i;

function readJsonlSafe(file) {
  const rows = [];
  for (const line of fs.readFileSync(file, "utf8").split(/\r?\n/)) {
    if (!line.trim()) continue;
    try {
      rows.push(JSON.parse(line));
    } catch {
      // Ignore partial/interleaved lines from concurrent runs.
    }
  }
  return rows;
}

function hasMediaSignal(row) {
  const buckets = [row.search_results, row.relevant_results].filter(Array.isArray);
  return buckets.some((items) => items.some((item) => MEDIA_RE.test(`${item.title || ""} ${item.snippet || ""} ${item.url || ""}`)));
}

function bump(map, key) {
  map[key || "미상"] = (map[key || "미상"] || 0) + 1;
}

function main() {
  const files = fs
    .readdirSync(OUT_DIR)
    .filter((name) => /^today_added_localized_search_updates(?:\.shard\d+-of-\d+)?\.jsonl$/.test(name))
    .map((name) => path.join(OUT_DIR, name))
    .sort();

  const latest = new Map();
  let parsedRows = 0;
  for (const file of files) {
    for (const row of readJsonlSafe(file)) {
      parsedRows += 1;
      latest.set(row.key || row.doc_id, row);
    }
  }

  const rows = Array.from(latest.values()).sort((a, b) => String(a.title || a.name || "").localeCompare(String(b.title || b.name || "")));
  fs.writeFileSync(OUT_JSONL, `${rows.map((row) => JSON.stringify(row)).join("\n")}\n`);

  const trust = {};
  const status = {};
  let updated = 0;
  let failed = 0;
  let officialOk = 0;
  let withRelevant = 0;
  let withMedia = 0;
  let readbackVerified = 0;

  for (const row of rows) {
    if (row.updated) updated += 1;
    else failed += 1;
    if (row.readback_verified) readbackVerified += 1;
    bump(trust, row.trust);
    bump(status, row.status);
    if (row.official_page?.ok) officialOk += 1;
    if (Array.isArray(row.relevant_results) && row.relevant_results.length) withRelevant += 1;
    if (hasMediaSignal(row)) withMedia += 1;
  }

  const summary = {
    generated_at: new Date().toISOString(),
    source_files: files.map((file) => path.basename(file)),
    parsed_rows: parsedRows,
    unique_rows: rows.length,
    updated,
    failed,
    readback_verified: readbackVerified,
    status,
    trust,
    official_page_ok: officialOk,
    with_relevant_results: withRelevant,
    with_media_or_event_signal: withMedia,
    output_jsonl: OUT_JSONL,
  };

  fs.writeFileSync(OUT_JSON, JSON.stringify(summary, null, 2));
  console.log(JSON.stringify(summary, null, 2));
}

main();
