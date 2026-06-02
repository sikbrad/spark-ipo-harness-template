#!/usr/bin/env node
/**
 * Headless web-search enrichment for prospect Outline pages.
 *
 * Execution order is intentionally:
 *   1. open headless browser pages and search the web,
 *   2. update the Outline document immediately,
 *   3. append the completed result to JSONL for after-the-fact cache/audit.
 */

const fs = require("fs");
const path = require("path");
const puppeteer = require("puppeteer");

const ROOT = "/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04";
const BASE = path.join(ROOT, "output/dof-overseas-customer-prospects/2026-05-30/scale5000");
const DATA = path.join(BASE, "data");
const OUTLINE_PUBLISH = path.join(BASE, "outline_publish");
const OUT_DIR = path.join(OUTLINE_PUBLISH, "prospect_headless_search_update");
const DOC_CACHE = path.join(OUTLINE_PUBLISH, "outline_docs.json");
const COMPLETE_JSONL = path.join(DATA, "prospects_augmented_contact_complete.jsonl");
const RESULT_JSONL = path.join(OUT_DIR, "outline_first_search_updates.jsonl");
const SUMMARY_JSON = path.join(OUT_DIR, "outline_first_search_summary.json");
const TODAY_ADDED_JSON = path.join(OUT_DIR, "today_added_prospect_docs_2026-06-02.json");

const OUTLINE_BASE = "https://outline.doflab.com";
const SECTION_TITLE = "## 공개 웹검색 보강 (2026-06-02)";
const USER_AGENT =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36";

const COUNTRY_LABEL_KO = {
  Albania: "알바니아",
  Algeria: "알제리",
  Argentina: "아르헨티나",
  Armenia: "아르메니아",
  Australia: "호주",
  Austria: "오스트리아",
  Azerbaijan: "아제르",
  Bangladesh: "방글라데시",
  Belarus: "벨라루스",
  Belgium: "벨기에",
  Brazil: "브라질",
  Bulgaria: "불가리아",
  Canada: "캐나다",
  Chile: "칠레",
  China: "중국",
  Colombia: "콜롬비아",
  Croatia: "크로아티아",
  Czechia: "체코",
  Denmark: "덴마크",
  Egypt: "이집트",
  France: "프랑스",
  Georgia: "조지아",
  Germany: "독일",
  Greece: "그리스",
  "Hong Kong": "홍콩",
  Hungary: "헝가리",
  India: "인도",
  Indonesia: "인니",
  Iran: "이란",
  Iraq: "이라크",
  Italy: "이탈리아",
  Japan: "일본",
  Jordan: "요르단",
  Kazakhstan: "카자흐",
  Malaysia: "말레이시아",
  Mexico: "멕시코",
  Netherlands: "네덜란드",
  "New Zealand": "뉴질랜드",
  Philippines: "필리핀",
  Poland: "폴란드",
  Romania: "루마니아",
  Russia: "러시아",
  Singapore: "싱가포르",
  "South Africa": "남아공",
  Spain: "스페인",
  Switzerland: "스위스",
  Taiwan: "대만",
  Thailand: "태국",
  Turkey: "튀르키예",
  Ukraine: "우크라이나",
  "United Arab Emirates": "UAE",
  "United Kingdom": "영국",
  "United States": "미국",
  Vietnam: "베트남",
};

const SERVICE_RULES = [
  ["치기공/보철 제작", /\b(dental\s*lab|laborator|dentallabor|zahntechnik|prothes|prosthetic|prosthodontic|技工|치기공|랩)\b/i],
  ["CAD\/CAM·밀링", /\b(cad\s*\/?\s*cam|milling|mill|zirconia|zirkon|crown|bridge|implant bar|abutment|imes|roland|dgshape)\b/i],
  ["디지털 치과 워크플로우", /\b(digital dentistry|intraoral|scanner|scan|3d\s*print|printing|exocad|model creator|digital workflow)\b/i],
  ["치과 병·의원 진료", /\b(dental clinic|dental practice|dentist|orthodont|implantology|endodont|periodont|clinic)\b/i],
  ["치과 유통\/장비 공급", /\b(distributor|dealer|supply|supplies|equipment|trading|medical device|authorized|reseller|import|export)\b/i],
  ["교육·세미나·행사", /\b(training|course|seminar|webinar|conference|congress|expo|exhibition|ids|aeedc|capp)\b/i],
];

const MEDIA_RE = /\b(news|press|article|interview|award|awards|expo|exhibition|congress|conference|ids|aeedc|capp|sidex|event|trade fair|pavilion)\b/i;
const DENTAL_RE = /\b(dental|dentist|dentistry|orthodont|clinic|laborator|lab|milling|cad\s*\/?\s*cam|zahnarzt|zahntechnik|odont|stomatolog|prosthetic|implant)\b/i;
const BLOCKED_DOMAINS = new Set(["scamadviser.com", "similarweb.com"]);

const LOCAL_DENTAL_TERMS = {
  Albania: ["dentist", "laborator dentar", "furnizues dentar"],
  Argentina: ["dentista", "odontología", "laboratorio dental", "depósito dental"],
  Australia: ["dentist", "dental clinic", "dental laboratory", "dental supplies"],
  Austria: ["Zahnarzt", "Zahntechnik", "Dentallabor", "Dentalbedarf"],
  Belarus: ["стоматология", "стоматолог", "зуботехническая лаборатория"],
  Belgium: ["dentiste", "tandarts", "laboratoire dentaire", "tandtechnisch labo"],
  Brazil: ["dentista", "odontologia", "laboratório dental", "fornecedor odontológico"],
  Bulgaria: ["стоматолог", "зъболекар", "дентална лаборатория"],
  Canada: ["dentist", "dental clinic", "dental laboratory", "dental supplies"],
  Chile: ["dentista", "odontología", "laboratorio dental"],
  China: ["牙科", "口腔诊所", "义齿加工", "牙科经销商"],
  Colombia: ["dentista", "odontología", "laboratorio dental"],
  Croatia: ["stomatolog", "dentalni laboratorij", "zubotehnički laboratorij"],
  Czechia: ["zubní lékař", "stomatologie", "zubní laboratoř"],
  Denmark: ["tandlæge", "dentallaboratorium", "dental leverandør"],
  Egypt: ["عيادة أسنان", "طبيب أسنان", "معمل أسنان"],
  France: ["dentiste", "cabinet dentaire", "laboratoire dentaire", "fournisseur dentaire"],
  Georgia: ["სტომატოლოგია", "სტომატოლოგი", "სტომატოლოგიური ლაბორატორია"],
  Germany: ["Zahnarzt", "Zahntechnik", "Dentallabor", "Dentalbedarf"],
  Greece: ["οδοντίατρος", "οδοντιατρείο", "οδοντοτεχνικό εργαστήριο"],
  "Hong Kong": ["牙科", "牙醫", "dental clinic", "dental laboratory"],
  Hungary: ["fogorvos", "fogászat", "fogtechnikai labor", "dentál kereskedés"],
  India: ["dentist", "dental clinic", "dental lab", "dental distributor"],
  Indonesia: ["dokter gigi", "klinik gigi", "laboratorium gigi", "distributor dental"],
  Iran: ["دندانپزشکی", "کلینیک دندانپزشکی", "لابراتوار دندانسازی"],
  Iraq: ["عيادة أسنان", "طبيب أسنان", "مختبر أسنان"],
  Italy: ["dentista", "odontoiatra", "laboratorio odontotecnico", "fornitore dentale"],
  Japan: ["歯科", "歯科医院", "歯科技工所", "歯科ディーラー"],
  Kazakhstan: ["стоматология", "стоматолог", "зуботехническая лаборатория"],
  Malaysia: ["dentist", "klinik pergigian", "dental lab", "pembekal dental"],
  Mexico: ["dentista", "odontología", "laboratorio dental", "depósito dental"],
  Netherlands: ["tandarts", "tandheelkunde", "tandtechnisch laboratorium"],
  "New Zealand": ["dentist", "dental clinic", "dental laboratory"],
  Philippines: ["dentist", "dental clinic", "dental laboratory", "dental supplier"],
  Poland: ["dentysta", "stomatolog", "laboratorium dentystyczne"],
  Romania: ["medic dentist", "cabinet stomatologic", "laborator dentar"],
  Russia: ["стоматология", "стоматолог", "зуботехническая лаборатория"],
  Serbia: ["stomatolog", "zubna ordinacija", "zubotehnička laboratorija"],
  Slovakia: ["zubár", "stomatológ", "zubné laboratórium"],
  Slovenia: ["zobozdravnik", "zobni laboratorij"],
  "South Africa": ["dentist", "dental clinic", "dental laboratory", "dental supplier"],
  Spain: ["dentista", "clínica dental", "laboratorio dental", "depósito dental"],
  Switzerland: ["Zahnarzt", "dentiste", "Dentallabor", "laboratoire dentaire", "Dentalbedarf"],
  Taiwan: ["牙科", "牙醫診所", "牙技所", "牙科材料"],
  Thailand: ["ทันตแพทย์", "คลินิกทันตกรรม", "dental lab", "dental supplier"],
  Turkey: ["diş hekimi", "diş kliniği", "diş laboratuvarı", "dental depo"],
  Ukraine: ["стоматологія", "стоматолог", "зуботехнічна лабораторія"],
  "United Arab Emirates": ["عيادة أسنان", "طبيب أسنان", "dental clinic", "dental supplier"],
  "United Kingdom": ["dentist", "dental practice", "dental laboratory", "dental supplier"],
  "United States": ["dentist", "dental clinic", "dental laboratory", "dental supplies"],
  Vietnam: ["nha khoa", "phòng khám nha khoa", "labo răng", "vật liệu nha khoa"],
};

function parseArgs() {
  const args = {
    limit: null,
    start: 0,
    concurrency: 8,
    status: "",
    shard: 0,
    shards: 1,
    rerun: false,
    verifyOnly: false,
    todayAdded: false,
  };
  for (let i = 2; i < process.argv.length; i += 1) {
    const arg = process.argv[i];
    if (arg === "--limit") args.limit = Number(process.argv[++i]);
    else if (arg === "--start") args.start = Number(process.argv[++i]);
    else if (arg === "--concurrency") args.concurrency = Number(process.argv[++i]);
    else if (arg === "--status") args.status = process.argv[++i];
    else if (arg === "--shard") args.shard = Number(process.argv[++i]);
    else if (arg === "--shards") args.shards = Number(process.argv[++i]);
    else if (arg === "--rerun") args.rerun = true;
    else if (arg === "--verify-only") args.verifyOnly = true;
    else if (arg === "--today-added") args.todayAdded = true;
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

function readJsonlSafe(file) {
  if (!fs.existsSync(file)) return [];
  const rows = [];
  for (const line of fs.readFileSync(file, "utf8").split(/\r?\n/)) {
    if (!line.trim()) continue;
    try {
      rows.push(JSON.parse(line));
    } catch {
      // Multiple shard writers used the shared file during an earlier run.
      // Keep valid completed rows and let invalid/interleaved rows be retried.
    }
  }
  return rows;
}

function appendJsonl(file, row) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.appendFileSync(file, `${JSON.stringify(row)}\n`);
}

function resultJsonlFor(args) {
  if (args.todayAdded && args.shards > 1) {
    return path.join(OUT_DIR, `today_added_localized_search_updates.shard${args.shard}-of-${args.shards}.jsonl`);
  }
  if (args.todayAdded) return path.join(OUT_DIR, "today_added_localized_search_updates.jsonl");
  if (args.shards > 1) {
    return path.join(OUT_DIR, `outline_first_search_updates.shard${args.shard}-of-${args.shards}.jsonl`);
  }
  return RESULT_JSONL;
}

function summaryJsonFor(args) {
  if (args.todayAdded && args.shards > 1) {
    return path.join(OUT_DIR, `today_added_localized_search_summary.shard${args.shard}-of-${args.shards}.json`);
  }
  if (args.todayAdded) return path.join(OUT_DIR, "today_added_localized_search_summary.json");
  if (args.shards > 1) {
    return path.join(OUT_DIR, `outline_first_search_summary.shard${args.shard}-of-${args.shards}.json`);
  }
  return SUMMARY_JSON;
}

function completedJournalRows() {
  if (!fs.existsSync(OUT_DIR)) return [];
  const files = fs
    .readdirSync(OUT_DIR)
    .filter((name) => /^outline_first_search_updates(?:\.shard\d+-of-\d+)?\.jsonl$/.test(name))
    .map((name) => path.join(OUT_DIR, name));
  return files.flatMap((file) => readJsonlSafe(file));
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

function normalizeUrl(value) {
  let text = safeText(value);
  if (!text || ["-", "n/a", "none", "null", "메모에 입력요청", "메모 입력요청"].includes(text.toLowerCase())) return "";
  if (text.includes("@") && !/^https?:\/\//i.test(text)) return "";
  if (text.startsWith("www.")) text = `https://${text}`;
  else if (text && !/^https?:\/\//i.test(text)) text = `https://${text}`;
  try {
    const url = new URL(text);
    if (!url.hostname.includes(".")) return "";
    return url.toString();
  } catch {
    return "";
  }
}

function domainOf(url) {
  try {
    return new URL(url).hostname.toLowerCase().replace(/^www\./, "");
  } catch {
    return "";
  }
}

function emailDomain(email) {
  const text = safeText(email).toLowerCase();
  if (!text.includes("@")) return "";
  const domain = text.split("@").pop();
  return domain && domain.includes(".") ? domain : "";
}

function cleanCompanyName(name) {
  return safeText(name)
    .replace(/^\d{1,5}\.\s*/, "")
    .replace(/\s*\([^)]*\)\s*$/, "")
    .replace(
      /\b(co\.?\s*ltd\.?|ltd\.?|inc\.?|corp\.?|corporation|gmbh|srl|s\.r\.l\.|llc|pte\.?\s*ltd\.?|limited|ag|sas|s\.a\.|a\/s|doo|d\.o\.o\.)\b/gi,
      "",
    )
    .replace(/\s+/g, " ")
    .trim();
}

function meaningfulNameTokens(name) {
  const stop = new Set(["dental", "dent", "clinic", "lab", "laboratory", "company", "group", "medical", "service", "services", "international"]);
  return (cleanCompanyName(name).toLowerCase().match(/[a-z0-9][a-z0-9-]{2,}/g) || []).filter((token) => !stop.has(token)).slice(0, 6);
}

function stableCompanyId(row, index) {
  if (row.portal_company_id) return `portal:${row.portal_company_id}`;
  if (row.osm_type && row.osm_id) return `osm:${row.osm_type}:${row.osm_id}`;
  if (row.email) return `email:${String(row.email).toLowerCase().replace(/[^a-z0-9@._+-]+/g, "-")}`;
  return `row:${index}`;
}

function countryLabel(country) {
  return COUNTRY_LABEL_KO[country] || country || "미상";
}

function unwrapSearchUrl(raw) {
  if (!raw) return "";
  let value = raw.startsWith("//") ? `https:${raw}` : raw;
  try {
    const url = new URL(value);
    if (url.hostname.includes("duckduckgo.com") && url.pathname.startsWith("/l/")) {
      return url.searchParams.get("uddg") || value;
    }
    if (url.hostname.includes("bing.com") && url.pathname.startsWith("/ck/")) {
      const encoded = url.searchParams.get("u") || "";
      if (encoded.startsWith("a1")) {
        const decoded = Buffer.from(encoded.slice(2), "base64").toString("utf8");
        if (/^https?:\/\//i.test(decoded)) return decoded;
      }
    }
    return value;
  } catch {
    return value;
  }
}

function isDofUrl(url) {
  const host = domainOf(url);
  return host === "doflab.com" || host.endsWith(".doflab.com");
}

function isRelevant(row, result, officialDomain, mailDomain) {
  const domain = result.domain || "";
  if (domain && (domain === officialDomain || domain === mailDomain)) return true;
  const haystack = `${result.title} ${result.snippet} ${result.url}`.toLowerCase();
  const tokens = meaningfulNameTokens(row.name);
  const hasName = tokens.length === 0 ? true : tokens.some((token) => haystack.includes(token));
  const hasDental = DENTAL_RE.test(haystack);
  if (cleanCompanyName(row.name).length <= 4) return hasName && hasDental;
  return hasName && hasDental;
}

function buildQuery(row) {
  const name = cleanCompanyName(row.name || "");
  const country = row.country || "";
  const segment = String(row.segment || "").toLowerCase();
  let extra = "dental";
  if (segment.includes("laboratory") || segment.includes("lab")) extra = "dental lab";
  else if (segment.includes("distributor") || segment.includes("supplier")) extra = "dental distributor";
  else if (segment.includes("orthodont")) extra = "orthodontic dental";
  return `"${name}" ${country} ${extra}`;
}

function cityHint(row) {
  const direct = safeText(row.city_hint || row.city);
  if (direct) return direct;
  const address = safeText(row.address);
  if (!address) return "";
  const parts = address
    .split(/[,|]/)
    .map((part) => part.trim())
    .filter((part) => part && !/\b\d{3,}\b/.test(part) && part.length <= 40);
  return parts.slice(-2, -1)[0] || "";
}

function localizedQueries(row) {
  const name = cleanCompanyName(row.name || "");
  const country = row.country || "";
  const city = cityHint(row);
  const segment = String(row.segment || "").toLowerCase();
  const terms = LOCAL_DENTAL_TERMS[country] || ["dentist", "dental clinic", "dental laboratory", "dental supplier"];
  let preferred = terms[0];
  if (segment.includes("laboratory") || segment.includes("lab")) {
    preferred = terms.find((term) => /lab|labor|Zahntechnik|Dentallabor|techn|labo|技工|laborat|laboratório|laboratorio/i.test(term)) || preferred;
  } else if (segment.includes("distributor") || segment.includes("supplier")) {
    preferred = terms.find((term) => /supplier|supply|bedarf|distrib|depo|fournisseur|depósito|经销|材料|fornecedor/i.test(term)) || preferred;
  } else if (segment.includes("orthodont")) {
    preferred = terms.find((term) => /orthodont|ortho|kiefer|ortodon|矯正|矫正/i.test(term)) || terms[0];
  }
  return [
    buildQuery(row),
    `"${name}" "${preferred}"`,
    city ? `"${name}" "${city}" "${preferred}"` : "",
    `"${name}" "${country}" "${terms.slice(0, 2).join('" "')}"`,
  ]
    .filter(Boolean)
    .filter((query, index, arr) => arr.indexOf(query) === index)
    .slice(0, 4);
}

function inferServices(row, results, officialPage) {
  const text = [
    row.name,
    row.segment,
    row.dof_fit,
    row.selection_reason,
    row.source_type,
    ...(Array.isArray(row.evidence) ? row.evidence.slice(0, 5) : []),
    ...(results || []).flatMap((item) => [item.title, item.snippet, item.url]),
    officialPage?.title,
    officialPage?.description,
    officialPage?.text,
  ].join(" ");
  const found = [];
  for (const [label, re] of SERVICE_RULES) {
    if (re.test(text)) found.push(label);
  }
  return [...new Set(found)].slice(0, 5);
}

function classifyResults(row, results, officialWebsite) {
  const officialDomain = domainOf(officialWebsite);
  const mailDomain = emailDomain(row.email);
  const relevant = results.filter((result) => isRelevant(row, result, officialDomain, mailDomain));
  const officialResults = relevant.filter((result) => result.domain && (result.domain === officialDomain || result.domain === mailDomain));
  const mediaResults = relevant.filter((result) => MEDIA_RE.test(`${result.title} ${result.snippet} ${result.url}`));
  const directoryResults = relevant.filter((result) =>
    /(linkedin|facebook|instagram|youtube|zoominfo|dnb|crunchbase|opencorporates|lmtmag|dentistrytoday|dental-tribune|yellow|gelbe|maps|directory|locator)/i.test(
      `${result.domain} ${result.url} ${result.title}`,
    ),
  );
  const others = relevant.filter((result) => !officialResults.includes(result) && !mediaResults.includes(result) && !directoryResults.includes(result));
  return { relevant, officialResults, mediaResults, directoryResults, others };
}

function trustFor(row, classified, officialPage) {
  if (officialPage?.ok && classified.relevant.length > 0) {
    return ["높음", "공식/자체 웹사이트 본문을 headless로 열어 확인했고, 검색 결과에서도 같은 업체·치과 관련성이 확인된다."];
  }
  if (officialPage?.ok) {
    return ["높음", "공식/자체 웹사이트 본문을 headless로 열어 확인했다. 검색 결과와의 교차 확인은 제한적이다."];
  }
  if (classified.officialResults.length > 0) {
    return ["높음", "이메일/웹사이트 도메인과 일치하는 검색 결과가 확인된다."];
  }
  if (classified.mediaResults.length > 0 || classified.directoryResults.length > 0 || classified.others.length > 0) {
    return ["중간", "headless 웹검색에서 업체명과 치과 관련성이 함께 잡히는 공개 결과가 있으나, 공식 본문 확인까지는 제한적이다."];
  }
  return ["낮음", "headless 웹검색에서 동일 업체로 확정 가능한 추가 결과가 부족해 기존 공개 출처 근거 중심으로만 해석한다."];
}

async function gotoWithTimeout(page, url, timeout = 12000) {
  try {
    await page.goto(url, { waitUntil: "domcontentloaded", timeout });
    return true;
  } catch {
    return false;
  }
}

async function searchDuckDuckGo(page, query) {
  const url = `https://duckduckgo.com/html/?q=${encodeURIComponent(query)}`;
  const ok = await gotoWithTimeout(page, url);
  if (!ok) return [];
  try {
    return await page.evaluate(() => {
      return Array.from(document.querySelectorAll(".result"))
        .map((item) => {
          const titleEl = item.querySelector(".result__a, .result__title a");
          const snippetEl = item.querySelector(".result__snippet");
          return {
            title: titleEl?.textContent?.replace(/\s+/g, " ").trim() || "",
            url: titleEl?.getAttribute("href") || "",
            snippet: snippetEl?.textContent?.replace(/\s+/g, " ").trim() || "",
          };
        })
        .filter((item) => item.title && item.url)
        .slice(0, 8);
    });
  } catch {
    return [];
  }
}

async function searchBing(page, query) {
  const url = `https://www.bing.com/search?q=${encodeURIComponent(query)}`;
  const ok = await gotoWithTimeout(page, url);
  if (!ok) return [];
  try {
    return await page.evaluate(() => {
      return Array.from(document.querySelectorAll("li.b_algo"))
        .map((item) => {
          const titleEl = item.querySelector("h2 a");
          const snippetEl = item.querySelector(".b_caption p, p");
          return {
            title: titleEl?.textContent?.replace(/\s+/g, " ").trim() || "",
            url: titleEl?.href || "",
            snippet: snippetEl?.textContent?.replace(/\s+/g, " ").trim() || "",
          };
        })
        .filter((item) => item.title && item.url)
        .slice(0, 8);
    });
  } catch {
    return [];
  }
}

async function headlessSearch(page, row) {
  const queries = localizedQueries(row);
  const seen = new Set();
  const results = [];
  const engineRuns = [];
  for (const query of queries) {
    let raw = await searchDuckDuckGo(page, query);
    let engine = "duckduckgo";
    if (!raw.length) {
      raw = await searchBing(page, query);
      engine = "bing";
    }
    engineRuns.push(`${engine}:${query}`);
    for (const item of raw) {
      const url = unwrapSearchUrl(item.url);
      const domain = domainOf(url);
      if (!url || !domain || isDofUrl(url) || BLOCKED_DOMAINS.has(domain) || seen.has(url)) continue;
      seen.add(url);
      results.push({
        title: compact(item.title, 180),
        url,
        domain,
        snippet: compact(item.snippet, 360),
        query,
        engine,
      });
      if (results.length >= 8) break;
    }
    if (results.length >= 8) break;
  }
  return { query: queries[0], queries, engine: engineRuns.join(" | "), results };
}

async function openOfficial(page, row, results) {
  const candidate = normalizeUrl(row.website) || normalizeUrl(row.source_url);
  const officialUrl = candidate && !isDofUrl(candidate) ? candidate : "";
  const fallback = results.find((result) => {
    const domain = result.domain || "";
    return domain && !/(facebook|instagram|linkedin|youtube|maps|google|bing|duckduckgo)/i.test(domain);
  });
  const url = officialUrl || fallback?.url || "";
  if (!url) return {};
  const ok = await gotoWithTimeout(page, url, 10000);
  if (!ok) return { ok: false, url, error: "navigation timeout or failure" };
  try {
    return await page.evaluate((pageUrl) => {
      const title = document.title || "";
      const description =
        document.querySelector('meta[name="description"]')?.getAttribute("content") ||
        document.querySelector('meta[property="og:description"]')?.getAttribute("content") ||
        "";
      const text = document.body?.innerText?.replace(/\s+/g, " ").trim().slice(0, 2500) || "";
      return { ok: true, url: location.href || pageUrl, title, description, text };
    }, url);
  } catch (error) {
    return { ok: false, url, error: String(error.message || error).slice(0, 220) };
  }
}

function resultLine(result) {
  const label = result.title || result.domain || result.url;
  return `- ${mdLink(label, result.url)}${result.snippet ? ` — ${mdEscape(compact(result.snippet, 220))}` : ""}`;
}

function buildSection(row, search, officialPage, classified, services, trust) {
  const mediaText = classified.mediaResults.length
    ? `${classified.mediaResults.length}건의 언론·행사성 후보 결과가 검색됨.`
    : "명확한 언론 기사/행사 노출은 이번 headless 웹검색에서 확인하지 못함.";
  const servicesText = services.length ? services.join(", ") : "검색 결과만으로 구체 업역을 확정하기 어려움";
  const lines = [
    SECTION_TITLE,
    "",
    "### 요약",
    "",
    "- 확인 방법: headless 브라우저 다중 페이지로 업체명, 국가명, 현지어 치과 키워드를 조합해 검색하고, 공식/자체 웹사이트 후보를 열어 제목·설명·본문 일부를 확인.",
    `- 검색 쿼리: ${
      Array.isArray(search.queries) ? search.queries.map((query) => `\`${mdEscape(query)}\``).join(", ") : `\`${mdEscape(search.query)}\``
    } (${mdEscape(search.engine)})`,
    `- 치과 관련 활동: ${mdEscape(servicesText)}.`,
    `- 언론·외부 노출: ${mdEscape(mediaText)}`,
    `- 신뢰도: **${mdEscape(trust[0])}** — ${mdEscape(trust[1])}`,
    "",
    "### 웹검색 결과",
    "",
  ];
  const primary = [
    ...classified.officialResults,
    ...classified.mediaResults,
    ...classified.directoryResults,
    ...classified.others,
  ].filter((item, index, arr) => arr.findIndex((other) => other.url === item.url) === index);
  if (primary.length) lines.push(...primary.slice(0, 4).map(resultLine));
  else if (search.results.length) {
    lines.push("- 동일 업체로 확정 가능한 결과는 부족하나, 아래 검색 후보는 영업 전 수동 재확인 대상으로 남김.");
    lines.push(...search.results.slice(0, 3).map(resultLine));
  } else lines.push("- 동일 업체로 확정 가능한 검색 결과가 부족함.");
  if (officialPage?.ok) {
    lines.push("", "### 공식/자체 웹사이트 확인", "");
    lines.push(`- ${mdLink(compact(officialPage.title || domainOf(officialPage.url) || officialPage.url, 140), officialPage.url)}`);
    if (officialPage.description) lines.push(`- 설명: ${mdEscape(compact(officialPage.description, 260))}`);
  }
  const evidence = Array.isArray(row.evidence) ? row.evidence.slice(0, 3) : [];
  lines.push("", "### 기존 공개 수집 근거", "");
  lines.push(`- 출처 유형: ${mdEscape(row.source_type || "미상")}`);
  if (row.source_url) lines.push(`- 원 출처: ${mdLink(row.source_type || row.source_url, row.source_url)}`);
  for (const item of evidence) lines.push(`- 근거 메모: ${mdEscape(compact(item, 240))}`);
  lines.push("", "### 보수적 해석", "");
  lines.push("- 검색 결과 제목·스니펫·공식 페이지 일부를 자동 수집한 것이므로, 동명 업체 가능성이 있거나 신뢰도 `중간` 이하인 항목은 영업 전 재확인을 권장한다.");
  return `${lines.join("\n")}\n`;
}

function replaceSection(text, section) {
  const pattern = /\n?## 공개 (?:조사|웹검색) 보강 \(2026-06-02\)\n[\s\S]*?(?=\n## 영업 메모|$)/;
  let next = text.replace(pattern, "\n").trimEnd() + "\n";
  const marker = "\n## 영업 메모";
  if (next.includes(marker)) {
    const [before, after] = next.split(marker);
    return `${before.trimEnd()}\n\n${section.trimEnd()}\n\n## 영업 메모${after}`;
  }
  return `${next.trimEnd()}\n\n${section}`;
}

async function outlineApi(apiKey, endpoint, body) {
  for (let attempt = 1; attempt <= 5; attempt += 1) {
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
      if ([429, 500, 502, 503, 504].includes(response.status) && attempt < 5) {
        await new Promise((resolve) => setTimeout(resolve, attempt * 1200));
        continue;
      }
      throw new Error(`${endpoint} failed ${response.status}: ${JSON.stringify(json).slice(0, 600)}`);
    } catch (error) {
      if (attempt < 5 && /fetch failed|network|timeout|ECONN|UND_ERR/i.test(String(error.message || error))) {
        await new Promise((resolve) => setTimeout(resolve, attempt * 1200));
        continue;
      }
      throw error;
    }
  }
}

function loadTargets(args) {
  const cache = JSON.parse(fs.readFileSync(DOC_CACHE, "utf8")).docs || {};
  const countryDocs = new Map();
  for (const [key, value] of Object.entries(cache)) {
    if (key.startsWith("country:")) countryDocs.set(value.id, key);
  }
  const rows = readJsonl(COMPLETE_JSONL);
  const rowByKey = new Map();
  rows.forEach((row, idx) => {
    const key = `company:${stableCompanyId(row, idx + 1)}`;
    rowByKey.set(key, { ...row, _index: idx + 1 });
  });
  const already = new Set();
  if (!args.rerun) {
    for (const row of completedJournalRows()) {
      if (row.updated) already.add(row.key);
    }
  }
  let todayKeys = null;
  if (args.todayAdded) {
    const today = JSON.parse(fs.readFileSync(TODAY_ADDED_JSON, "utf8"));
    todayKeys = new Set((today.docs || []).map((doc) => doc.key).filter(Boolean));
  }
  let targets = [];
  for (const [key, doc] of Object.entries(cache)) {
    if (!key.startsWith("company:") || key.startsWith("company:portal:")) continue;
    if (todayKeys && !todayKeys.has(key)) continue;
    if (already.has(key)) continue;
    const countryKey = countryDocs.get(doc.parent_document_id) || "";
    const parts = countryKey.split(":");
    const status = parts.length >= 4 ? parts[2] : "";
    if (!status.startsWith("잠재고객-")) continue;
    if (args.status && status !== args.status) continue;
    const row = rowByKey.get(key);
    if (!row) continue;
    targets.push({ key, doc, row, status });
  }
  targets.sort((a, b) => String(a.doc.title || "").localeCompare(String(b.doc.title || "")));
  if (args.shards > 1) {
    targets = targets.filter((_, index) => index % args.shards === args.shard);
  }
  if (args.start) targets = targets.slice(args.start);
  if (args.limit !== null && Number.isFinite(args.limit)) targets = targets.slice(0, args.limit);
  return targets;
}

async function processTarget(page, apiKey, target) {
  const search = await headlessSearch(page, target.row);
  const officialPage = await openOfficial(page, target.row, search.results);
  const classified = classifyResults(target.row, search.results, officialPage?.url || normalizeUrl(target.row.website));
  const services = inferServices(target.row, classified.relevant, officialPage);
  const trust = trustFor(target.row, classified, officialPage);
  const section = buildSection(target.row, search, officialPage, classified, services, trust);
  const info = await outlineApi(apiKey, "documents.info", { id: target.doc.id });
  const text = replaceSection(info.text || "", section);
  const updated = await outlineApi(apiKey, "documents.update", {
    id: target.doc.id,
    title: info.title || target.doc.title,
    text,
    publish: true,
    fullWidth: true,
  });
  let readbackVerified = false;
  let verifyAttempts = 0;
  for (let attempt = 1; attempt <= 3; attempt += 1) {
    verifyAttempts = attempt;
    const check = await outlineApi(apiKey, "documents.info", { id: target.doc.id });
    if (String(check.text || "").includes("현지어 치과 키워드")) {
      readbackVerified = true;
      break;
    }
    await outlineApi(apiKey, "documents.update", {
      id: target.doc.id,
      title: info.title || target.doc.title,
      text,
      publish: true,
      fullWidth: true,
    });
  }
  if (!readbackVerified) throw new Error("Outline update succeeded but readback did not contain localized web-search section");
  return {
    key: target.key,
    doc_id: target.doc.id,
    title: updated.title || target.doc.title,
    outline_url: `${OUTLINE_BASE}/doc/${updated.urlId}`,
    status: target.status,
    name: target.row.name,
    country: target.row.country,
    query: search.query,
    queries: search.queries,
    engine: search.engine,
    search_results: search.results,
    relevant_results: classified.relevant,
    official_page: officialPage,
    services,
    trust: trust[0],
    trust_reason: trust[1],
    updated: true,
    readback_verified: readbackVerified,
    verify_attempts: verifyAttempts,
    updated_at: new Date().toISOString(),
  };
}

async function main() {
  const args = parseArgs();
  const apiKey = readEnv("DOF_OUTLINE_KEY");
  fs.mkdirSync(OUT_DIR, { recursive: true });
  const targets = loadTargets(args);
  const resultJsonl = resultJsonlFor(args);
  const summaryJson = summaryJsonFor(args);
  const summary = {
    started_at: new Date().toISOString(),
    target_count: targets.length,
    concurrency: args.concurrency,
    status_filter: args.status || null,
    shard: args.shard,
    shards: args.shards,
    updated: 0,
    failed: 0,
  };
  fs.writeFileSync(summaryJson, JSON.stringify(summary, null, 2));
  console.log(JSON.stringify({ start: true, target: targets.length, concurrency: args.concurrency }, null, 0));
  if (args.verifyOnly || !targets.length) return;

  const browser = await puppeteer.launch({
    headless: true,
    args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
  });
  try {
    const pages = [];
    const workerCount = Math.max(1, Math.min(args.concurrency, targets.length));
    for (let i = 0; i < workerCount; i += 1) {
      const page = await browser.newPage();
      await page.setUserAgent(USER_AGENT);
      await page.setRequestInterception(true);
      page.on("request", (request) => {
        const type = request.resourceType();
        if (["image", "font", "media"].includes(type)) request.abort();
        else request.continue();
      });
      pages.push(page);
    }
    let cursor = 0;
    let updated = 0;
    let failed = 0;
    async function worker(page, workerId) {
      while (cursor < targets.length) {
        const index = cursor;
        cursor += 1;
        const target = targets[index];
        try {
          const result = await processTarget(page, apiKey, target);
          appendJsonl(resultJsonl, result);
          updated += 1;
        } catch (error) {
          appendJsonl(resultJsonl, {
            key: target.key,
            doc_id: target.doc.id,
            title: target.doc.title,
            status: target.status,
            updated: false,
            error: String(error.message || error).slice(0, 800),
            failed_at: new Date().toISOString(),
          });
          failed += 1;
        }
        if ((updated + failed) % 25 === 0 || updated + failed === targets.length) {
          const progress = { processed: updated + failed, target: targets.length, updated, failed, worker: workerId };
          console.log(JSON.stringify(progress));
          fs.writeFileSync(summaryJson, JSON.stringify({ ...summary, ...progress, updated_at: new Date().toISOString() }, null, 2));
        }
      }
    }
    await Promise.all(pages.map((page, idx) => worker(page, idx + 1)));
    fs.writeFileSync(
      summaryJson,
      JSON.stringify({ ...summary, processed: updated + failed, updated, failed, finished_at: new Date().toISOString() }, null, 2),
    );
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
