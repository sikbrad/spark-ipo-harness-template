#!/usr/bin/env node

const fs = require("fs");
const path = require("path");

const ROOT = "/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04";
const BASE = path.join(ROOT, "output/dof-overseas-customer-prospects/2026-05-30/scale5000");
const DATA = path.join(BASE, "data");
const OUTLINE_PUBLISH = path.join(BASE, "outline_publish");
const OUT_DIR = path.join(OUTLINE_PUBLISH, "prospect_headless_search_update");
const COMPLETE_JSONL = path.join(DATA, "prospects_augmented_contact_complete.jsonl");
const MERGED_JSONL = path.join(OUT_DIR, "outline_first_search_updates.merged.jsonl");
const VERIFY_JSON = path.join(OUT_DIR, "outline_first_search_verification.json");
const REAPPLY_JSONL = path.join(OUT_DIR, "outline_missing_section_reapply.jsonl");
const REAPPLY_SUMMARY_JSON = path.join(OUT_DIR, "outline_missing_section_reapply_summary.json");

const OUTLINE_BASE = "https://outline.doflab.com";
const SECTION_TITLE = "## 공개 웹검색 보강 (2026-06-02)";
const MEDIA_RE = /\b(news|press|article|interview|award|awards|expo|exhibition|congress|conference|ids|aeedc|capp|sidex|event|trade fair|pavilion)\b/i;

function parseArgs() {
  const args = { concurrency: 6, limit: null, rerun: false };
  for (let i = 2; i < process.argv.length; i += 1) {
    const arg = process.argv[i];
    if (arg === "--concurrency") args.concurrency = Number(process.argv[++i]);
    else if (arg === "--limit") args.limit = Number(process.argv[++i]);
    else if (arg === "--rerun") args.rerun = true;
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

function appendJsonl(file, row) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.appendFileSync(file, `${JSON.stringify(row)}\n`);
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
  if (response.status >= 400 || json.success === false) {
    throw new Error(`${endpoint} failed ${response.status}: ${JSON.stringify(json).slice(0, 600)}`);
  }
  return json.data;
}

function loadSourceRows() {
  const rows = readJsonl(COMPLETE_JSONL);
  const byKey = new Map();
  rows.forEach((row, idx) => {
    byKey.set(`company:${stableCompanyId(row, idx + 1)}`, row);
  });
  return byKey;
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

function completedReapply() {
  const done = new Set();
  if (!fs.existsSync(REAPPLY_JSONL)) return done;
  for (const row of readJsonl(REAPPLY_JSONL)) {
    if ((row.updated || row.skipped_present) && row.doc_id) done.add(row.doc_id);
  }
  return done;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function reapplyOne(apiKey, target, result, sourceRow) {
  const before = await outlineApi(apiKey, "documents.info", { id: target.doc_id });
  if (String(before.text || "").includes("공개 웹검색 보강 (2026-06-02)")) {
    return { ...target, skipped_present: true, updated: false, checked_at: new Date().toISOString() };
  }
  const section = buildSection(result, sourceRow);
  const text = replaceSection(before.text || "", section);
  for (let attempt = 1; attempt <= 3; attempt += 1) {
    await outlineApi(apiKey, "documents.update", {
      id: target.doc_id,
      title: before.title || target.title,
      text,
      publish: true,
      fullWidth: true,
    });
    await sleep(350 * attempt);
    const after = await outlineApi(apiKey, "documents.info", { id: target.doc_id });
    if (String(after.text || "").includes("공개 웹검색 보강 (2026-06-02)")) {
      return { ...target, updated: true, attempts: attempt, updated_at: new Date().toISOString() };
    }
  }
  return { ...target, updated: false, error: "section not present after update retries", failed_at: new Date().toISOString() };
}

async function main() {
  const args = parseArgs();
  const apiKey = readEnv("DOF_OUTLINE_KEY");
  const verification = JSON.parse(fs.readFileSync(VERIFY_JSON, "utf8"));
  const sourceRows = loadSourceRows();
  const results = loadResults();
  const already = args.rerun ? new Set() : completedReapply();
  let targets = verification.readback.missing.filter((target) => !already.has(target.doc_id));
  if (args.limit !== null && Number.isFinite(args.limit)) targets = targets.slice(0, args.limit);
  const summary = {
    started_at: new Date().toISOString(),
    target_count: targets.length,
    concurrency: args.concurrency,
    updated: 0,
    skipped_present: 0,
    failed: 0,
  };
  fs.writeFileSync(REAPPLY_SUMMARY_JSON, JSON.stringify(summary, null, 2));
  console.log(JSON.stringify({ start: true, target: targets.length, concurrency: args.concurrency }));
  let cursor = 0;
  let updated = 0;
  let skipped = 0;
  let failed = 0;
  async function worker(workerId) {
    while (cursor < targets.length) {
      const index = cursor;
      cursor += 1;
      const target = targets[index];
      const result = results.byDoc.get(target.doc_id) || results.byKey.get(target.key);
      if (!result) {
        appendJsonl(REAPPLY_JSONL, { ...target, updated: false, error: "missing merged search result", failed_at: new Date().toISOString() });
        failed += 1;
      } else {
        try {
          const row = await reapplyOne(apiKey, target, result, sourceRows.get(target.key));
          appendJsonl(REAPPLY_JSONL, row);
          if (row.updated) updated += 1;
          else if (row.skipped_present) skipped += 1;
          else failed += 1;
        } catch (error) {
          appendJsonl(REAPPLY_JSONL, { ...target, updated: false, error: String(error.message || error).slice(0, 800), failed_at: new Date().toISOString() });
          failed += 1;
        }
      }
      if ((updated + skipped + failed) % 50 === 0 || updated + skipped + failed === targets.length) {
        const progress = { processed: updated + skipped + failed, target: targets.length, updated, skipped_present: skipped, failed, worker: workerId };
        console.log(JSON.stringify(progress));
        fs.writeFileSync(REAPPLY_SUMMARY_JSON, JSON.stringify({ ...summary, ...progress, updated_at: new Date().toISOString() }, null, 2));
      }
    }
  }
  await Promise.all(Array.from({ length: Math.max(1, Math.min(args.concurrency, targets.length)) }, (_, idx) => worker(idx + 1)));
  fs.writeFileSync(
    REAPPLY_SUMMARY_JSON,
    JSON.stringify({ ...summary, processed: updated + skipped + failed, updated, skipped_present: skipped, failed, finished_at: new Date().toISOString() }, null, 2),
  );
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
