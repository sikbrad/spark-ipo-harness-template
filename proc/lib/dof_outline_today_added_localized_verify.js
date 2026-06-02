#!/usr/bin/env node

const fs = require("fs");
const path = require("path");

const ROOT = "/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04";
const BASE = path.join(ROOT, "output/dof-overseas-customer-prospects/2026-05-30/scale5000");
const OUT_DIR = path.join(BASE, "outline_publish/prospect_headless_search_update");
const TODAY_JSON = path.join(OUT_DIR, "today_added_prospect_docs_2026-06-02.json");
const OUT_JSON = path.join(OUT_DIR, "today_added_localized_verification_2026-06-02.json");
const OUTLINE_BASE = "https://outline.doflab.com";
const SECTION_TITLE_TEXT = "공개 웹검색 보강 (2026-06-02)";
const LOCALIZED_MARKER = "업체명, 국가명, 현지어 치과 키워드";

function parseArgs() {
  const args = { concurrency: 16 };
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
  for (let attempt = 1; attempt <= 6; attempt += 1) {
    try {
      const response = await fetch(`${OUTLINE_BASE}/api/${endpoint}`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${apiKey}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
      });
      const json = await response.json().catch(() => ({}));
      if (response.status < 400 && json.success !== false) return json.data;
      if ([429, 500, 502, 503, 504].includes(response.status) && attempt < 6) {
        await new Promise((resolve) => setTimeout(resolve, attempt * 1500));
        continue;
      }
      throw new Error(`${endpoint} failed ${response.status}: ${JSON.stringify(json).slice(0, 600)}`);
    } catch (error) {
      if (attempt < 6 && /fetch failed|network|timeout|ECONN|UND_ERR/i.test(String(error.message || error))) {
        await new Promise((resolve) => setTimeout(resolve, attempt * 1500));
        continue;
      }
      throw error;
    }
  }
}

async function main() {
  const args = parseArgs();
  const apiKey = readEnv("DOF_OUTLINE_KEY");
  const docs = JSON.parse(fs.readFileSync(TODAY_JSON, "utf8")).docs || [];
  let cursor = 0;
  let checked = 0;
  let sectionPresent = 0;
  let localizedPresent = 0;
  const missingLocalized = [];
  const missingSection = [];
  const failed = [];

  async function worker() {
    while (cursor < docs.length) {
      const doc = docs[cursor++];
      try {
        const info = await outlineApi(apiKey, "documents.info", { id: doc.doc_id });
        const text = String(info.text || "");
        const hasSection = text.includes(SECTION_TITLE_TEXT);
        const hasLocalized = text.includes(LOCALIZED_MARKER);
        if (hasSection) sectionPresent += 1;
        else missingSection.push(doc);
        if (hasLocalized) localizedPresent += 1;
        else missingLocalized.push(doc);
      } catch (error) {
        failed.push({ ...doc, error: String(error.message || error).slice(0, 500) });
      }
      checked += 1;
      if (checked % 500 === 0 || checked === docs.length) {
        console.log(JSON.stringify({ checked, target: docs.length, localized_present: localizedPresent, missing_localized: missingLocalized.length, failed: failed.length }));
      }
    }
  }

  await Promise.all(Array.from({ length: Math.max(1, Math.min(args.concurrency, docs.length)) }, () => worker()));

  const result = {
    generated_at: new Date().toISOString(),
    today_kst: "2026-06-02",
    target_count: docs.length,
    marker: LOCALIZED_MARKER,
    readback: {
      checked,
      section_present: sectionPresent,
      section_missing: missingSection.length,
      localized_marker_present: localizedPresent,
      localized_marker_missing: missingLocalized.length,
      request_failed: failed.length,
      missing_section: missingSection.slice(0, 50),
      missing_localized: missingLocalized.slice(0, 200),
      failed: failed.slice(0, 200),
    },
  };
  fs.writeFileSync(OUT_JSON, JSON.stringify(result, null, 2));
  console.log(JSON.stringify(result, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
