#!/usr/bin/env node

const fs = require("fs");
const path = require("path");

const ROOT = "/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04";
const BASE = path.join(ROOT, "output/dof-overseas-customer-prospects/2026-05-30/scale5000");
const OUTLINE_PUBLISH = path.join(BASE, "outline_publish");
const DOC_CACHE = path.join(OUTLINE_PUBLISH, "outline_docs.json");
const OUT_DIR = path.join(OUTLINE_PUBLISH, "prospect_headless_search_update");
const OUT_JSON = path.join(OUT_DIR, "today_added_prospect_docs_2026-06-02.json");

const OUTLINE_BASE = "https://outline.doflab.com";
const KST_DAY_START_UTC = Date.parse("2026-06-01T15:00:00.000Z");
const KST_DAY_END_UTC = Date.parse("2026-06-02T15:00:00.000Z");

function parseArgs() {
  const args = { concurrency: 12 };
  for (let i = 2; i < process.argv.length; i += 1) {
    if (process.argv[i] === "--concurrency") args.concurrency = Number(process.argv[++i]);
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

async function outlineApi(apiKey, endpoint, body) {
  for (let attempt = 1; attempt <= 5; attempt += 1) {
    const response = await fetch(`${OUTLINE_BASE}/api/${endpoint}`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });
    const json = await response.json().catch(() => ({}));
    if (response.status < 400 && json.success !== false) return json;
    if ([429, 500, 502, 503, 504].includes(response.status) && attempt < 5) {
      await new Promise((resolve) => setTimeout(resolve, attempt * 1200));
      continue;
    }
    throw new Error(`${endpoint} failed ${response.status}: ${JSON.stringify(json).slice(0, 600)}`);
  }
}

async function documentsList(apiKey, params) {
  let offset = 0;
  const docs = [];
  while (true) {
    const json = await outlineApi(apiKey, "documents.list", { limit: 100, offset, ...params });
    const batch = json.data || [];
    docs.push(...batch);
    const total = Number(json.pagination?.total || docs.length);
    offset += batch.length;
    if (!batch.length || offset >= total) return docs;
  }
}

function loadProspectCountryParents() {
  const docs = JSON.parse(fs.readFileSync(DOC_CACHE, "utf8")).docs || {};
  const countries = [];
  for (const [key, doc] of Object.entries(docs)) {
    if (!key.startsWith("country:")) continue;
    const parts = key.split(":");
    const status = parts.length >= 4 ? parts[2] : "";
    if (!status.startsWith("잠재고객-")) continue;
    countries.push({ key, status, country: parts.slice(3).join(":"), id: doc.id, title: doc.title });
  }
  countries.sort((a, b) => a.key.localeCompare(b.key));
  return countries;
}

function isTodayKst(iso) {
  const ts = Date.parse(iso || "");
  return Number.isFinite(ts) && ts >= KST_DAY_START_UTC && ts < KST_DAY_END_UTC;
}

function cachedCompanyKeyByDocId() {
  const docs = JSON.parse(fs.readFileSync(DOC_CACHE, "utf8")).docs || {};
  const byId = new Map();
  for (const [key, doc] of Object.entries(docs)) {
    if (key.startsWith("company:") && !key.startsWith("company:portal:")) byId.set(doc.id, key);
  }
  return byId;
}

async function main() {
  const args = parseArgs();
  const apiKey = readEnv("DOF_OUTLINE_KEY");
  fs.mkdirSync(OUT_DIR, { recursive: true });
  const parents = loadProspectCountryParents();
  const keyByDocId = cachedCompanyKeyByDocId();
  const today = [];
  let cursor = 0;
  let scanned = 0;
  async function worker() {
    while (cursor < parents.length) {
      const parent = parents[cursor++];
      const children = await documentsList(apiKey, { parentDocumentId: parent.id });
      scanned += children.length;
      for (const doc of children) {
        if (doc.archivedAt || doc.deletedAt) continue;
        if (!isTodayKst(doc.createdAt)) continue;
        today.push({
          key: keyByDocId.get(doc.id) || "",
          doc_id: doc.id,
          url_id: doc.urlId,
          outline_url: `${OUTLINE_BASE}/doc/${doc.urlId}`,
          title: doc.title,
          status: parent.status,
          country_folder: parent.country,
          parent_document_id: parent.id,
          createdAt: doc.createdAt,
          updatedAt: doc.updatedAt,
        });
      }
      if (scanned % 1000 < children.length) {
        console.log(JSON.stringify({ parents_checked: cursor, parents_total: parents.length, scanned, today: today.length }));
      }
    }
  }
  await Promise.all(Array.from({ length: Math.max(1, Math.min(args.concurrency, parents.length)) }, () => worker()));
  today.sort((a, b) => String(a.createdAt).localeCompare(String(b.createdAt)) || String(a.title).localeCompare(String(b.title)));
  const result = {
    generated_at: new Date().toISOString(),
    today_kst: "2026-06-02",
    utc_range: {
      start: new Date(KST_DAY_START_UTC).toISOString(),
      end: new Date(KST_DAY_END_UTC).toISOString(),
    },
    prospect_country_parent_count: parents.length,
    scanned_company_docs: scanned,
    today_added_count: today.length,
    docs: today,
  };
  fs.writeFileSync(OUT_JSON, JSON.stringify(result, null, 2));
  console.log(JSON.stringify({ today_added_count: today.length, scanned_company_docs: scanned, output: OUT_JSON }, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
