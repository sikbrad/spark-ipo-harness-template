#!/usr/bin/env node

const fs = require("fs");
const path = require("path");

const ROOT = "/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04";
const BASE = path.join(ROOT, "output/dof-overseas-customer-prospects/2026-05-30/scale5000");
const OUT_DIR = path.join(BASE, "outline_publish/middle_docs_update");
const DOC_CACHE = path.join(BASE, "outline_publish/outline_docs.json");
const TODAY_JSON = path.join(BASE, "outline_publish/prospect_headless_search_update/today_added_prospect_docs_2026-06-02.json");
const LOCALIZED_VERIFY_JSON = path.join(BASE, "outline_publish/prospect_headless_search_update/today_added_localized_verification_2026-06-02.json");
const OUTLINE_BASE = "https://outline.doflab.com";
const ROOT_DOC_ID = "89c2b595-26e3-43fd-b4d2-23d514515e2d";
const ROOT_URL = "https://outline.doflab.com/doc/7jib7jef7lky7zue67o0-c0ae88mpyc";
const SECTION_TITLE_TEXT = "현재 하위 현황 (자동 갱신)";
const SECTION_TITLE = `## ${SECTION_TITLE_TEXT}`;
const KST_DATE = "2026-06-03";
const STATUS_LABELS = ["기존고객", "잠재고객-치과", "잠재고객-교정치과", "잠재고객-치기공", "잠재고객-유통사"];
const API_TIMEOUT_MS = 60000;

function parseArgs() {
  const args = { dryRun: false, verifyOnly: false, concurrency: 8, sample: false, idsFile: "", fromCache: false, skipRoot: false };
  for (let i = 2; i < process.argv.length; i += 1) {
    const arg = process.argv[i];
    if (arg === "--dry-run") args.dryRun = true;
    else if (arg === "--verify-only") args.verifyOnly = true;
    else if (arg === "--sample") args.sample = true;
    else if (arg === "--from-cache") args.fromCache = true;
    else if (arg === "--skip-root") args.skipRoot = true;
    else if (arg === "--concurrency") args.concurrency = Number(process.argv[++i]);
    else if (arg === "--ids-file") args.idsFile = process.argv[++i];
  }
  return args;
}

function loadCachedOutlineDocs(rootInfo) {
  const cache = JSON.parse(fs.readFileSync(DOC_CACHE, "utf8"));
  const byId = new Map();
  byId.set(ROOT_DOC_ID, {
    id: ROOT_DOC_ID,
    title: rootInfo.title || "영업처후보",
    urlId: rootInfo.urlId || "7jib7jef7lky7zue67o0-c0ae88mpyc",
    parentDocumentId: rootInfo.parentDocumentId || "",
  });
  for (const doc of Object.values(cache.docs || {})) {
    if (!doc || !doc.id || doc.id === ROOT_DOC_ID) continue;
    byId.set(doc.id, {
      id: doc.id,
      title: doc.title || "",
      urlId: doc.url_id || "",
      parentDocumentId: doc.parent_document_id || "",
      archivedAt: doc.archived_at || null,
      deletedAt: doc.deleted_at || null,
    });
  }
  return Array.from(byId.values());
}

function readEnv(name) {
  const env = fs.readFileSync(path.join(ROOT, ".env"), "utf8");
  for (const line of env.split(/\r?\n/)) {
    if (line.startsWith(`${name}=`)) return line.split("=").slice(1).join("=").trim().replace(/^['"]|['"]$/g, "");
  }
  throw new Error(`${name} not found`);
}

function safeText(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function mdEscape(value) {
  return safeText(value).replace(/([\\`*_{}[\]()#+\-.!|])/g, "\\$1");
}

function mdLink(label, url) {
  return `[${mdEscape(label || url)}](${url})`;
}

function bump(map, key, by = 1) {
  const label = key || "미상";
  map[label] = (map[label] || 0) + by;
}

function addMaps(target, source) {
  for (const [key, value] of Object.entries(source || {})) bump(target, key, value);
}

async function outlineApi(apiKey, endpoint, body) {
  for (let attempt = 1; attempt <= 6; attempt += 1) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), API_TIMEOUT_MS);
    try {
      const response = await fetch(`${OUTLINE_BASE}/api/${endpoint}`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${apiKey}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
        signal: controller.signal,
      });
      const json = await response.json().catch(() => ({}));
      if (response.status < 400 && json.success !== false) return json;
      if ([429, 500, 502, 503, 504].includes(response.status) && attempt < 6) {
        await new Promise((resolve) => setTimeout(resolve, attempt * 1500));
        continue;
      }
      throw new Error(`${endpoint} failed ${response.status}: ${JSON.stringify(json).slice(0, 600)}`);
    } catch (error) {
      if (attempt < 6 && /fetch failed|network|timeout|aborted|AbortError|ECONN|UND_ERR/i.test(String(error.message || error))) {
        await new Promise((resolve) => setTimeout(resolve, attempt * 1500));
        continue;
      }
      throw error;
    } finally {
      clearTimeout(timeout);
    }
  }
}

async function documentInfo(apiKey, id) {
  for (let attempt = 1; attempt <= 4; attempt += 1) {
    const json = await outlineApi(apiKey, "documents.info", { id });
    if (json.data && typeof json.data.text !== "undefined") return json.data;
    await new Promise((resolve) => setTimeout(resolve, attempt * 1000));
  }
  throw new Error(`documents.info returned no document data for ${id}`);
}

async function documentUpdate(apiKey, body) {
  for (let attempt = 1; attempt <= 4; attempt += 1) {
    const json = await outlineApi(apiKey, "documents.update", body);
    if (json.data) return json.data;
    await new Promise((resolve) => setTimeout(resolve, attempt * 1000));
  }
  throw new Error(`documents.update returned no document data for ${body.id}`);
}

async function documentsListAll(apiKey, params) {
  const first = await outlineApi(apiKey, "documents.list", { limit: 100, offset: 0, ...params });
  const firstBatch = first.data || [];
  const total = Number(first.pagination?.total || firstBatch.length);
  const offsets = [];
  for (let offset = firstBatch.length; offset < total; offset += 100) offsets.push(offset);
  const docs = [...firstBatch];
  let cursor = 0;
  let fetched = firstBatch.length;
  async function worker() {
    while (cursor < offsets.length) {
      const offset = offsets[cursor++];
      const json = await outlineApi(apiKey, "documents.list", { limit: 100, offset, ...params });
      const batch = json.data || [];
      docs.push(...batch);
      fetched += batch.length;
      if (fetched % 1000 < batch.length || fetched >= total) {
        console.log(JSON.stringify({ list_fetched: fetched, list_total: total }));
      }
    }
  }
  await Promise.all(Array.from({ length: Math.min(8, offsets.length) }, () => worker()));
  return docs;
}

function pathOf(doc, byId) {
  const parts = [];
  let cur = doc;
  const seen = new Set();
  while (cur && !seen.has(cur.id)) {
    seen.add(cur.id);
    parts.push(cur.title);
    cur = byId.get(cur.parentDocumentId);
  }
  return parts.reverse();
}

function firstAncestor(pathParts, candidates) {
  return pathParts.find((part) => candidates.includes(part)) || "";
}

function inferCompanyStatus(pathParts) {
  return firstAncestor(pathParts, STATUS_LABELS);
}

function inferRegion(pathParts) {
  return pathParts.length >= 2 ? pathParts[1] : "";
}

function inferCountry(pathParts, status) {
  const idx = pathParts.indexOf(status);
  if (idx >= 0 && pathParts[idx + 1]) return pathParts[idx + 1];
  return "";
}

function topEntries(map, limit = 8) {
  return Object.entries(map || {})
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .slice(0, limit);
}

function loadTodayAddedByDocId() {
  if (!fs.existsSync(TODAY_JSON)) return new Set();
  const docs = JSON.parse(fs.readFileSync(TODAY_JSON, "utf8")).docs || [];
  return new Set(docs.map((doc) => doc.doc_id).filter(Boolean));
}

function loadLocalizedVerifiedCount() {
  if (!fs.existsSync(LOCALIZED_VERIFY_JSON)) return null;
  try {
    const obj = JSON.parse(fs.readFileSync(LOCALIZED_VERIFY_JSON, "utf8"));
    return obj.readback?.localized_marker_present ?? null;
  } catch {
    return null;
  }
}

function buildTree(allDocs) {
  const byId = new Map(allDocs.map((doc) => [doc.id, doc]));
  const childrenByParent = new Map();
  for (const doc of allDocs) {
    if (doc.archivedAt || doc.deletedAt) continue;
    const parent = doc.parentDocumentId || "";
    if (!childrenByParent.has(parent)) childrenByParent.set(parent, []);
    childrenByParent.get(parent).push(doc);
  }
  for (const children of childrenByParent.values()) {
    children.sort((a, b) => String(a.title).localeCompare(String(b.title)));
  }
  return { byId, childrenByParent };
}

function collectReachable(root, childrenByParent) {
  const reachable = new Set();
  const stack = [root.id];
  while (stack.length) {
    const id = stack.pop();
    if (reachable.has(id)) continue;
    reachable.add(id);
    for (const child of childrenByParent.get(id) || []) stack.push(child.id);
  }
  return reachable;
}

function computeStats(root, allDocs, byId, childrenByParent, todayAddedDocIds) {
  const reachable = collectReachable(root, childrenByParent);
  const docs = allDocs.filter((doc) => reachable.has(doc.id) && !doc.archivedAt && !doc.deletedAt);
  const internalIds = new Set(docs.filter((doc) => (childrenByParent.get(doc.id) || []).length > 0).map((doc) => doc.id));
  const companyIds = new Set(docs.filter((doc) => doc.id !== root.id && !internalIds.has(doc.id)).map((doc) => doc.id));
  const info = new Map();

  function visit(doc) {
    if (info.has(doc.id)) return info.get(doc.id);
    const pathParts = pathOf(doc, byId);
    const children = (childrenByParent.get(doc.id) || []).filter((child) => reachable.has(child.id) && !child.archivedAt && !child.deletedAt);
    const directFolderCount = children.filter((child) => internalIds.has(child.id)).length;
    const directCompanyCount = children.filter((child) => companyIds.has(child.id)).length;
    const stats = {
      id: doc.id,
      title: doc.title,
      urlId: doc.urlId,
      url: `${OUTLINE_BASE}/doc/${doc.urlId}`,
      parentDocumentId: doc.parentDocumentId || null,
      path: pathParts.join(" / "),
      depth: pathParts.length - 1,
      direct_child_count: children.length,
      direct_folder_count: directFolderCount,
      direct_company_count: directCompanyCount,
      descendant_folder_count: 0,
      descendant_company_count: companyIds.has(doc.id) ? 1 : 0,
      statuses: {},
      regions: {},
      countries: {},
      today_added_prospects: todayAddedDocIds.has(doc.id) ? 1 : 0,
      direct_children: children.map((child) => ({
        id: child.id,
        title: child.title,
        url: `${OUTLINE_BASE}/doc/${child.urlId}`,
        kind: internalIds.has(child.id) ? "중간 문서" : "업체 문서",
      })),
    };

    if (companyIds.has(doc.id)) {
      const status = inferCompanyStatus(pathParts);
      const region = inferRegion(pathParts);
      const country = inferCountry(pathParts, status);
      bump(stats.statuses, status || "미분류");
      if (region) bump(stats.regions, region);
      if (country) bump(stats.countries, country);
    }

    for (const child of children) {
      const childStats = visit(child);
      if (internalIds.has(child.id)) stats.descendant_folder_count += 1 + childStats.descendant_folder_count;
      stats.descendant_company_count += childStats.descendant_company_count;
      stats.today_added_prospects += childStats.today_added_prospects;
      addMaps(stats.statuses, childStats.statuses);
      addMaps(stats.regions, childStats.regions);
      addMaps(stats.countries, childStats.countries);
    }

    info.set(doc.id, stats);
    return stats;
  }

  visit(root);
  return { reachable, docs, internalIds, companyIds, info };
}

function listLine(label, entries) {
  if (!entries.length) return `- ${label}: 없음`;
  return `- ${label}: ${entries.map(([key, value]) => `${mdEscape(key)} ${value.toLocaleString("ko-KR")}건`).join(", ")}`;
}

function buildSection(stats, rootStats, localizedVerifiedCount) {
  const folderLabel = stats.depth === 0 ? "전체 루트" : stats.depth === 1 ? "지역 문서" : stats.depth === 2 ? "상태 문서" : "국가/세부 분류 문서";
  const childFolders = stats.direct_children.filter((child) => child.kind === "중간 문서").slice(0, 12);
  const directCompanies = stats.direct_children.filter((child) => child.kind === "업체 문서").slice(0, 8);
  const lines = [
    SECTION_TITLE,
    "",
    `- 기준: ${KST_DATE} KST live Outline tree. 이 문서는 **${mdEscape(folderLabel)}**이며 업체 카드가 아니라 하위 업체/분류를 찾기 위한 중간 문서다.`,
    `- 경로: ${mdEscape(stats.path)}.`,
    `- 하위 업체 문서: ${stats.descendant_company_count.toLocaleString("ko-KR")}건. 하위 중간 문서: ${stats.descendant_folder_count.toLocaleString("ko-KR")}건.`,
    `- 직속 하위: 중간 문서 ${stats.direct_folder_count.toLocaleString("ko-KR")}개, 업체 문서 ${stats.direct_company_count.toLocaleString("ko-KR")}개.`,
    listLine("상태 분포", topEntries(stats.statuses, 8)),
  ];

  if (stats.depth <= 1) lines.push(listLine("주요 국가/분류", topEntries(stats.countries, 10)));
  else if (Object.keys(stats.countries).length > 1) lines.push(listLine("국가/분류", topEntries(stats.countries, 10)));

  if (stats.today_added_prospects) {
    const verifiedText = localizedVerifiedCount === null ? "전수 readback 진행/확인 필요" : `${localizedVerifiedCount.toLocaleString("ko-KR")}건 live readback 확인`;
    lines.push(`- 2026-06-02 추가 잠재고객 중 이 문서 하위 포함: ${stats.today_added_prospects.toLocaleString("ko-KR")}건. 업체명+국가/현지어 치과 키워드 웹검색 보강 상태: ${mdEscape(verifiedText)}.`);
  }

  if (stats.id === ROOT_DOC_ID) {
    lines.push(`- 전체 루트 기준 하위 업체 총계: ${rootStats.descendant_company_count.toLocaleString("ko-KR")}건, 중간 문서 총계: ${rootStats.descendant_folder_count.toLocaleString("ko-KR")}건.`);
    lines.push(`- 루트 링크: ${mdLink("영업처후보", ROOT_URL)}`);
  }

  if (childFolders.length) {
    lines.push("", "### 바로 아래 중간 문서", "");
    for (const child of childFolders) lines.push(`- ${mdLink(child.title, child.url)}`);
  }

  if (directCompanies.length) {
    lines.push("", "### 바로 아래 업체 예시", "");
    for (const child of directCompanies) lines.push(`- ${mdLink(child.title, child.url)}`);
  }

  lines.push("", "### 해석", "");
  lines.push("- 이 섹션은 현재 Outline 계층을 기준으로 한 자동 현황이다. 업체별 영업정보, 치과 관련 활동, 언론/행사 노출 및 신뢰도 판단은 각 업체 문서의 `공개 웹검색 보강` 섹션에서 확인한다.");
  return `${lines.join("\n")}\n`;
}

function replaceSection(text, section) {
  const pattern = /\n?## 현재 하위 현황 \(자동 갱신\)\n[\s\S]*?(?=\n## |\s*$)/;
  const source = String(text || "");
  if (pattern.test(source)) return source.replace(pattern, `\n${section.trimEnd()}\n`);
  const insertBefore = /\n## (?:하위|전체|지역|국가|업체|분류|영업|메모|목록)/;
  const match = source.match(insertBefore);
  if (match && typeof match.index === "number" && match.index > 0) {
    return `${source.slice(0, match.index).trimEnd()}\n\n${section.trimEnd()}\n${source.slice(match.index)}`;
  }
  return `${source.trimEnd()}\n\n${section}`;
}

async function updateOne(apiKey, doc, stats, rootStats, localizedVerifiedCount, args) {
  const info = await documentInfo(apiKey, doc.id);
  const section = buildSection(stats, rootStats, localizedVerifiedCount);
  const beforeText = String(info.text || "");
  const nextText = replaceSection(beforeText, section);
  if (args.dryRun) {
    return { id: doc.id, title: doc.title, url: `${OUTLINE_BASE}/doc/${doc.urlId}`, changed: beforeText !== nextText, dry_run: true };
  }
  if (args.verifyOnly) {
    const ok = beforeText.includes(SECTION_TITLE_TEXT);
    return { id: doc.id, title: doc.title, url: `${OUTLINE_BASE}/doc/${doc.urlId}`, verified: ok };
  }
  const updated = await documentUpdate(apiKey, {
    id: doc.id,
    title: info.title || doc.title,
    text: nextText,
    publish: true,
    fullWidth: true,
  });
  const check = await documentInfo(apiKey, doc.id);
  const ok = String(check.text || "").includes(SECTION_TITLE_TEXT);
  return {
    id: doc.id,
    title: doc.title,
    url: `${OUTLINE_BASE}/doc/${updated.urlId || doc.urlId}`,
    changed: beforeText !== nextText,
    updated: ok,
    verified: ok,
  };
}

async function main() {
  const args = parseArgs();
  const apiKey = readEnv("DOF_OUTLINE_KEY");
  fs.mkdirSync(OUT_DIR, { recursive: true });
  const rootInfo = args.fromCache
    ? { id: ROOT_DOC_ID, title: "영업처후보", urlId: "7jib7jef7lky7zue67o0-c0ae88mpyc", collectionId: null }
    : (await outlineApi(apiKey, "documents.info", { id: ROOT_DOC_ID })).data;
  const allDocs = args.fromCache ? loadCachedOutlineDocs(rootInfo) : await documentsListAll(apiKey, { collectionId: rootInfo.collectionId });
  const { byId, childrenByParent } = buildTree(allDocs);
  const root = byId.get(ROOT_DOC_ID) || rootInfo;
  const todayAddedDocIds = loadTodayAddedByDocId();
  const localizedVerifiedCount = loadLocalizedVerifiedCount();
  const computed = computeStats(root, allDocs, byId, childrenByParent, todayAddedDocIds);
  const rootStats = computed.info.get(ROOT_DOC_ID);
  let explicitIds = null;
  if (args.idsFile) {
    const data = JSON.parse(fs.readFileSync(path.resolve(args.idsFile), "utf8"));
    explicitIds = new Set(Array.isArray(data) ? data : data.ids || []);
  }
  const targets = Array.from(computed.internalIds)
    .map((id) => byId.get(id))
    .filter((doc) => doc && computed.reachable.has(doc.id))
    .filter((doc) => !args.skipRoot || doc.id !== ROOT_DOC_ID)
    .filter((doc) => !explicitIds || explicitIds.has(doc.id))
    .sort((a, b) => {
      const ap = computed.info.get(a.id).path;
      const bp = computed.info.get(b.id).path;
      return ap.localeCompare(bp);
    });

  const scan = {
    generated_at: new Date().toISOString(),
    root: { id: ROOT_DOC_ID, title: root.title, url: `${OUTLINE_BASE}/doc/${root.urlId}` },
    collection_id: rootInfo.collectionId,
    tree_source: args.fromCache ? DOC_CACHE : "outline.documents.list",
    collection_docs_seen: allDocs.length,
    reachable_docs: computed.docs.length,
    middle_doc_count: targets.length,
    company_doc_count: computed.companyIds.size,
    root_stats: rootStats,
    targets: targets.map((doc) => computed.info.get(doc.id)),
  };
  fs.writeFileSync(path.join(OUT_DIR, "middle_docs_scan_2026-06-03.json"), JSON.stringify(scan, null, 2));

  if (args.sample) {
    const samplePaths = new Set(["영업처후보 / 남유럽", "영업처후보 / 아프리카", "영업처후보 / 남유럽 / 기존고객", "영업처후보 / 남유럽 / 기존고객 / 그리스", "영업처후보 / 기타"]);
    const sample = targets
      .map((doc) => computed.info.get(doc.id))
      .filter((stats) => samplePaths.has(stats.path))
      .map((stats) => ({ path: stats.path, section: buildSection(stats, rootStats, localizedVerifiedCount) }));
    fs.writeFileSync(path.join(OUT_DIR, "middle_docs_sample_sections_2026-06-03.json"), JSON.stringify(sample, null, 2));
    console.log(JSON.stringify({ sample_count: sample.length, samples: sample.map((row) => row.path) }, null, 2));
    return;
  }

  const resultJsonl = path.join(
    OUT_DIR,
    args.idsFile
      ? args.verifyOnly
        ? "middle_docs_verify_retry_2026-06-03.jsonl"
        : "middle_docs_update_retry_2026-06-03.jsonl"
      : args.dryRun
        ? "middle_docs_update_dryrun_2026-06-03.jsonl"
        : args.verifyOnly
          ? "middle_docs_verify_2026-06-03.jsonl"
          : "middle_docs_update_2026-06-03.jsonl",
  );
  fs.writeFileSync(resultJsonl, "");
  let cursor = 0;
  let processed = 0;
  let ok = 0;
  let failed = 0;
  async function worker() {
    while (cursor < targets.length) {
      const doc = targets[cursor++];
      const stats = computed.info.get(doc.id);
      try {
        const row = await updateOne(apiKey, doc, stats, rootStats, localizedVerifiedCount, args);
        fs.appendFileSync(resultJsonl, `${JSON.stringify(row)}\n`);
        if (row.updated || row.verified || row.dry_run) ok += 1;
        else failed += 1;
      } catch (error) {
        failed += 1;
        fs.appendFileSync(resultJsonl, `${JSON.stringify({ id: doc.id, title: doc.title, path: stats.path, failed: true, error: String(error.message || error).slice(0, 600) })}\n`);
      }
      processed += 1;
      if (processed % 50 === 0 || processed === targets.length) {
        console.log(JSON.stringify({ processed, target: targets.length, ok, failed }));
      }
    }
  }

  await Promise.all(Array.from({ length: Math.max(1, Math.min(args.concurrency, targets.length)) }, () => worker()));
  const summary = {
    generated_at: new Date().toISOString(),
    dry_run: args.dryRun,
    verify_only: args.verifyOnly,
    target_count: targets.length,
    ok,
    failed,
    result_jsonl: resultJsonl,
    scan_json: path.join(OUT_DIR, "middle_docs_scan_2026-06-03.json"),
  };
  fs.writeFileSync(path.join(OUT_DIR, args.verifyOnly ? "middle_docs_verify_summary_2026-06-03.json" : "middle_docs_update_summary_2026-06-03.json"), JSON.stringify(summary, null, 2));
  console.log(JSON.stringify(summary, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
