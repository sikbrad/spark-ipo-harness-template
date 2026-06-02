#!/usr/bin/env node

const fs = require("fs");
const path = require("path");

const ROOT = "/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04";
const BASE = path.join(ROOT, "output/dof-overseas-customer-prospects/2026-05-30/scale5000");
const DATA = path.join(BASE, "data");
const OUTLINE_PUBLISH = path.join(BASE, "outline_publish");
const OUT_DIR = path.join(OUTLINE_PUBLISH, "prospect_headless_search_update");
const TODAY_JSON = path.join(OUT_DIR, "today_added_prospect_docs_2026-06-02.json");
const MERGED_JSONL = path.join(OUT_DIR, "outline_first_search_updates.merged.jsonl");
const COMPLETE_JSONL = path.join(DATA, "prospects_augmented_contact_complete.jsonl");
const OUT_JSON = path.join(OUT_DIR, "today_added_prospect_verification_2026-06-02.json");
const REPAIR_JSONL = path.join(OUT_DIR, "today_added_prospect_repair_2026-06-02.jsonl");

const OUTLINE_BASE = "https://outline.doflab.com";
const SECTION_TITLE_TEXT = "공개 웹검색 보강 (2026-06-02)";
const SECTION_TITLE = `## ${SECTION_TITLE_TEXT}`;
const MEDIA_RE = /\b(news|press|article|interview|award|awards|expo|exhibition|congress|conference|ids|aeedc|capp|sidex|event|trade fair|pavilion)\b/i;

function parseArgs() {
  const args = { concurrency: 16, repair: true };
  for (let i = 2; i < process.argv.length; i += 1) {
    if (process.argv[i] === "--concurrency") args.concurrency = Number(process.argv[++i]);
    else if (process.argv[i] === "--no-repair") args.repair = false;
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

function readJsonl(file) {
  return fs
    .readFileSync(file, "utf8")
    .split(/\r?\n/)
    .filter((line) => line.trim())
    .map((line) => JSON.parse(line));
}

function safeText(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function compact(value, limit = 260) {
  const text = safeText(value);
  return text.length <= limit ? text : `${text.slice(0, limit - 1).trim()}…`;
}

function mdEscape(value) {
  return safeText(value).replace(/([\\`*_{}[\]()#+\-.!|])/g, "\\$1");
}

function mdLink(label, url) {
  if (!url) return mdEscape(label);
  return `[${mdEscape(label || url)}](${url})`;
}

function stableCompanyId(row, index) {
  if (row.portal_company_id) return `portal:${row.portal_company_id}`;
  if (row.osm_type && row.osm_id) return `osm:${row.osm_type}:${row.osm_id}`;
  if (row.email) return `email:${String(row.email).toLowerCase().replace(/[^a-z0-9@._+-]+/g, "-")}`;
  return `row:${index}`;
}

function appendJsonl(file, row) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.appendFileSync(file, `${JSON.stringify(row)}\n`);
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
    if (response.status < 400 && json.success !== false) return json.data;
    if ([429, 500, 502, 503, 504].includes(response.status) && attempt < 5) {
      await new Promise((resolve) => setTimeout(resolve, attempt * 1200));
      continue;
    }
    throw new Error(`${endpoint} failed ${response.status}: ${JSON.stringify(json).slice(0, 600)}`);
  }
}

function loadResults() {
  const byDoc = new Map();
  const byKey = new Map();
  for (const row of readJsonl(MERGED_JSONL)) {
    if (row.doc_id) byDoc.set(row.doc_id, row);
    if (row.key) byKey.set(row.key, row);
  }
  return { byDoc, byKey };
}

function loadSourceRows() {
  const byKey = new Map();
  readJsonl(COMPLETE_JSONL).forEach((row, idx) => {
    byKey.set(`company:${stableCompanyId(row, idx + 1)}`, row);
  });
  return byKey;
}

function resultLine(result) {
  const label = result.title || result.domain || result.url;
  return `- ${mdLink(label, result.url)}${result.snippet ? ` — ${mdEscape(compact(result.snippet, 220))}` : ""}`;
}

function buildSection(result, sourceRow) {
  const searchResults = Array.isArray(result.search_results) ? result.search_results : [];
  const relevantResults = Array.isArray(result.relevant_results) ? result.relevant_results : [];
  const primary = (relevantResults.length ? relevantResults : searchResults).filter((item, index, arr) => arr.findIndex((other) => other.url === item.url) === index);
  const hasMedia = [...relevantResults, ...searchResults].some((item) => MEDIA_RE.test(`${item.title} ${item.snippet} ${item.url}`));
  const mediaText = hasMedia ? "언론·행사성 후보 결과가 검색됨." : "명확한 언론 기사/행사 노출은 이번 headless 웹검색에서 확인하지 못함.";
  const servicesText = Array.isArray(result.services) && result.services.length ? result.services.join(", ") : "검색 결과만으로 구체 업역을 확정하기 어려움";
  const officialPage = result.official_page || {};
  const lines = [
    SECTION_TITLE,
    "",
    "### 요약",
    "",
    "- 확인 방법: headless 브라우저 다중 페이지로 검색엔진 결과를 직접 조회하고, 공식/자체 웹사이트 후보를 열어 제목·설명·본문 일부를 확인.",
    `- 검색 쿼리: \`${mdEscape(result.query || "")}\` (${mdEscape(result.engine || "unknown")})`,
    `- 치과 관련 활동: ${mdEscape(servicesText)}.`,
    `- 언론·외부 노출: ${mdEscape(mediaText)}`,
    `- 신뢰도: **${mdEscape(result.trust || "낮음")}** — ${mdEscape(result.trust_reason || "자동 웹검색 근거만으로 해석했으므로 영업 전 재확인을 권장한다.")}`,
    "",
    "### 웹검색 결과",
    "",
  ];
  if (primary.length) lines.push(...primary.slice(0, 4).map(resultLine));
  else lines.push("- 동일 업체로 확정 가능한 검색 결과가 부족함.");
  if (officialPage.ok) {
    lines.push("", "### 공식/자체 웹사이트 확인", "");
    lines.push(`- ${mdLink(compact(officialPage.title || officialPage.url, 140), officialPage.url)}`);
    if (officialPage.description) lines.push(`- 설명: ${mdEscape(compact(officialPage.description, 260))}`);
  }
  const evidence = Array.isArray(sourceRow?.evidence) ? sourceRow.evidence.slice(0, 3) : [];
  lines.push("", "### 기존 공개 수집 근거", "");
  lines.push(`- 출처 유형: ${mdEscape(sourceRow?.source_type || "미상")}`);
  if (sourceRow?.source_url) lines.push(`- 원 출처: ${mdLink(sourceRow.source_type || sourceRow.source_url, sourceRow.source_url)}`);
  for (const item of evidence) lines.push(`- 근거 메모: ${mdEscape(compact(item, 240))}`);
  lines.push("", "### 보수적 해석", "");
  lines.push("- 검색 결과 제목·스니펫·공식 페이지 일부를 자동 수집한 것이므로, 동명 업체 가능성이 있거나 신뢰도 `중간` 이하인 항목은 영업 전 재확인을 권장한다.");
  return `${lines.join("\n")}\n`;
}

function replaceSection(text, section) {
  const pattern = /\n?## 공개 (?:조사|웹검색) 보강 \(2026-06-02\)\n[\s\S]*?(?=\n## 영업 메모|$)/;
  let next = String(text || "").replace(pattern, "\n").trimEnd() + "\n";
  const marker = "\n## 영업 메모";
  if (next.includes(marker)) {
    const [before, after] = next.split(marker);
    return `${before.trimEnd()}\n\n${section.trimEnd()}\n\n## 영업 메모${after}`;
  }
  return `${next.trimEnd()}\n\n${section}`;
}

async function repairOne(apiKey, doc, result, sourceRow) {
  const before = await outlineApi(apiKey, "documents.info", { id: doc.doc_id });
  if (String(before.text || "").includes(SECTION_TITLE_TEXT)) return { ...doc, skipped_present: true, repaired: false };
  const section = buildSection(result, sourceRow);
  const text = replaceSection(before.text || "", section);
  await outlineApi(apiKey, "documents.update", {
    id: doc.doc_id,
    title: before.title || doc.title,
    text,
    publish: true,
    fullWidth: true,
  });
  const after = await outlineApi(apiKey, "documents.info", { id: doc.doc_id });
  const ok = String(after.text || "").includes(SECTION_TITLE_TEXT);
  return { ...doc, repaired: ok, skipped_present: false, repair_failed: !ok };
}

function summarizeDocs(docs, results) {
  const status = {};
  const trust = {};
  let officialOk = 0;
  let withRelevant = 0;
  let withMedia = 0;
  let missingSearchResult = 0;
  for (const doc of docs) {
    status[doc.status || "미상"] = (status[doc.status || "미상"] || 0) + 1;
    const row = results.byDoc.get(doc.doc_id) || results.byKey.get(doc.key);
    if (!row) {
      missingSearchResult += 1;
      continue;
    }
    trust[row.trust || "미상"] = (trust[row.trust || "미상"] || 0) + 1;
    if (row.official_page?.ok) officialOk += 1;
    if (Array.isArray(row.relevant_results) && row.relevant_results.length) withRelevant += 1;
    const hasMedia = Array.isArray(row.search_results)
      ? row.search_results.some((item) => MEDIA_RE.test(`${item.title} ${item.snippet} ${item.url}`))
      : false;
    if (hasMedia) withMedia += 1;
  }
  return { status, trust, official_ok: officialOk, with_relevant_results: withRelevant, with_media_or_event_signal: withMedia, missing_search_result: missingSearchResult };
}

async function main() {
  const args = parseArgs();
  const apiKey = readEnv("DOF_OUTLINE_KEY");
  const today = JSON.parse(fs.readFileSync(TODAY_JSON, "utf8")).docs || [];
  const results = loadResults();
  const sourceRows = loadSourceRows();
  const missing = [];
  const failed = [];
  const repaired = [];
  let checked = 0;
  let cursor = 0;
  async function worker() {
    while (cursor < today.length) {
      const doc = today[cursor++];
      try {
        const info = await outlineApi(apiKey, "documents.info", { id: doc.doc_id });
        if (!String(info.text || "").includes(SECTION_TITLE_TEXT)) missing.push(doc);
      } catch (error) {
        failed.push({ ...doc, error: String(error.message || error).slice(0, 500) });
      }
      checked += 1;
      if (checked % 500 === 0 || checked === today.length) {
        console.log(JSON.stringify({ checked, target: today.length, missing: missing.length, failed: failed.length }));
      }
    }
  }
  await Promise.all(Array.from({ length: Math.max(1, Math.min(args.concurrency, today.length)) }, () => worker()));

  if (args.repair && missing.length) {
    let repairCursor = 0;
    let processed = 0;
    async function repairWorker() {
      while (repairCursor < missing.length) {
        const doc = missing[repairCursor++];
        const result = results.byDoc.get(doc.doc_id) || results.byKey.get(doc.key);
        if (!result) {
          const row = { ...doc, repaired: false, error: "missing merged search result" };
          repaired.push(row);
          appendJsonl(REPAIR_JSONL, row);
        } else {
          try {
            const row = await repairOne(apiKey, doc, result, sourceRows.get(doc.key));
            repaired.push(row);
            appendJsonl(REPAIR_JSONL, row);
          } catch (error) {
            const row = { ...doc, repaired: false, error: String(error.message || error).slice(0, 500) };
            repaired.push(row);
            appendJsonl(REPAIR_JSONL, row);
          }
        }
        processed += 1;
        if (processed % 100 === 0 || processed === missing.length) {
          console.log(JSON.stringify({ repair_processed: processed, repair_target: missing.length, repaired: repaired.filter((row) => row.repaired).length }));
        }
      }
    }
    await Promise.all(Array.from({ length: Math.max(1, Math.min(6, missing.length)) }, () => repairWorker()));
  }

  const result = {
    generated_at: new Date().toISOString(),
    today_kst: "2026-06-02",
    today_added_count: today.length,
    summary: summarizeDocs(today, results),
    readback: {
      checked: today.length,
      section_present: today.length - missing.length,
      section_missing: missing.length,
      request_failed: failed.length,
      missing,
      failed,
    },
    repair: {
      attempted: repaired.length,
      repaired: repaired.filter((row) => row.repaired).length,
      skipped_present: repaired.filter((row) => row.skipped_present).length,
      failed: repaired.filter((row) => !row.repaired && !row.skipped_present).length,
    },
  };
  fs.writeFileSync(OUT_JSON, JSON.stringify(result, null, 2));
  console.log(JSON.stringify(result, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
