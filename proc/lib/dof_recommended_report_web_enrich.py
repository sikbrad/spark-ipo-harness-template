#!/usr/bin/env python3
"""Enrich the 260604 recommended overseas dental distributor report.

The report is a compact sales-candidate table. This script keeps the original
recommendation columns, checks each company/source link, gathers public web
signals, appends concise enrichment columns, and writes the updated Markdown to
Outline.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote_plus, unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dof_prospect_outline_publish as publish  # noqa: E402


BASE = publish.BASE
REPORT_MD = BASE / "recommended_overseas_dental_distributors_260604.md"
RESULT_JSON = BASE / "recommended_overseas_dental_distributors_260604_result.json"
OUT_DIR = publish.PUBLISH_ROOT / "recommended_report_web_enrichment_260605"
CACHE_PATH = OUT_DIR / "cache.json"
RESEARCH_JSONL = OUT_DIR / "recommended_report_web_research.jsonl"
SUMMARY_JSON = OUT_DIR / "summary.json"

DOC_ID = "94e8e34f-731b-40fc-a3c0-8f355ba2569d"
DOC_TITLE = "리포트260604-해외"
OUTLINE_URL = "https://outline.doflab.com/doc/260604-Xma6PPNfUH"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
)
TIMEOUT = 10
SEARCH_TIMEOUT = 10
MAX_BODY = 900_000
CORE_COLS = [
    "우선순위",
    "포탈/주문 상태",
    "권역/국가",
    "업체",
    "어떤 회사인지",
    "확인된 취급품목",
    "왜 추천하는지",
    "연락/웹",
    "확인 출처",
    "신뢰도",
]
NEW_COLS = [
    "웹 링크 상태",
    "출처 링크 상태",
    "추가 확인 취급/브랜드",
    "최근 온라인 흔적",
    "링크/부가정보 신뢰도",
]

BRAND_PATTERNS = [
    ("DOF", r"\bDOF\b|freedom\s*hd|craft\s*5x|edge\s*e"),
    ("Medit", r"\bMedit\b|i700|i900"),
    ("Shining3D/Aoralscan", r"Shining\s*3D|Aoralscan"),
    ("3Shape/TRIOS", r"3Shape|TRIOS"),
    ("exocad", r"exocad|DentalCAD"),
    ("vhf", r"\bvhf\b|R5\b|E5\b|K5\b|N4\+?"),
    ("DGSHAPE/Roland", r"DGSHAPE|Roland"),
    ("imes-icore", r"imes[- ]?icore"),
    ("Amann Girrbach/Ceramill", r"Amann\s*Girrbach|Ceramill"),
    ("Zirkonzahn", r"Zirkonzahn"),
    ("Ivoclar", r"Ivoclar|Vivadent"),
    ("GC Dental", r"\bGC\s*Dental\b|GC\s+Europe|GC\s+Orthodontics"),
    ("DETAX", r"\bDETAX\b"),
    ("Bredent", r"\bbredent\b"),
    ("Dentsply Sirona", r"Dentsply|Sirona|CEREC|Primescan"),
    ("Planmeca", r"Planmeca|Emerald"),
    ("Carestream", r"Carestream|CS\s*3\d{3}"),
    ("iTero", r"iTero|Align\s+Technology"),
    ("Milling/CAD-CAM", r"CAD\s*/?\s*CAM|milling|fresadora|fresage|Fräs|zirconia|zirkon"),
    ("Intraoral scanner", r"intraoral\s+scanner|scanner\s+intraoral|escaner\s+intraoral|escáner\s+intraoral|scanner intraorale|口腔扫描|口腔スキャ"),
]
RECENT_RE = re.compile(r"\b(2026|2025|2024)\b")
MEDIA_RE = re.compile(
    r"\b(press|article|award|expo|exhibition|congress|conference|IDS|AEEDC|CAPP|webinar|seminar|event|trade fair|blog)\b|/(news|press|blog|events?)/",
    re.I,
)
SOCIAL_RE = re.compile(r"(linkedin\.com|facebook\.com|instagram\.com|youtube\.com|x\.com|twitter\.com)", re.I)
SEARCH_SKIP_DOMAINS = {
    "scamadviser.com",
    "similarweb.com",
    "webwiki.com",
    "myfonts.com",
    "doflab.com",
}
DIRECTORY_DOMAIN_MARKERS = (
    "linkedin.com",
    "facebook.com",
    "instagram.com",
    "youtube.com",
    "zoominfo.com",
    "dnb.com",
    "opencorporates.com",
    "yelp.",
    "yellowpages",
    "gelbeseiten",
    "canadiandentalsupplies.com",
    "dentistryregister.com",
    "medindexer.com",
    "lmtmag.com",
)
_cache_lock = threading.Lock()


@dataclass(frozen=True)
class ReportRow:
    index: int
    line: str
    cells: list[str]
    company: str
    website: str
    source_url: str
    country_cell: str


def load_json(path: Path, default: Any) -> Any:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def compact(value: Any, limit: int = 180) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def md_escape(value: Any) -> str:
    return compact(value, 360).replace("|", "\\|")


def normalize_url(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text.startswith("["):
        match = re.search(r"\((https?://[^)]+)\)", text)
        text = match.group(1) if match else ""
    if not text:
        return ""
    if text.startswith("www."):
        text = "https://" + text
    if text and not re.match(r"^https?://", text, re.I):
        return ""
    return text


def domain_of(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return ""
    host = host.split("@")[-1].split(":")[0]
    return host.removeprefix("www.")


def parse_link(cell: str) -> tuple[str, str]:
    match = re.search(r"\[([^\]]+)\]\((https?://[^)]+)\)", cell)
    if match:
        return html.unescape(match.group(1)).strip(), match.group(2).strip()
    url = re.search(r"https?://[^\s<)]+", cell)
    return re.sub(r"<br>.*", "", cell).strip(), url.group(0) if url else ""


def split_md_row(line: str) -> list[str]:
    raw = line.strip().strip("|")
    cells: list[str] = []
    buf: list[str] = []
    escaped = False
    for ch in raw:
        if ch == "\\" and not escaped:
            escaped = True
            buf.append(ch)
            continue
        if ch == "|" and not escaped:
            cells.append("".join(buf).strip())
            buf = []
            continue
        escaped = False
        buf.append(ch)
    cells.append("".join(buf).strip())
    return cells


def load_report_rows(markdown: str) -> tuple[list[str], list[ReportRow], list[str]]:
    lines = markdown.splitlines()
    header_idx = next(i for i, line in enumerate(lines) if line.startswith("| 우선순위 |"))
    data_start = header_idx + 2
    rows: list[ReportRow] = []
    end_idx = data_start
    for i in range(data_start, len(lines)):
        line = lines[i]
        if not (line.startswith("| A-") or line.startswith("| B-") or line.startswith("| C-")):
            end_idx = i
            break
        cells = split_md_row(line)
        core = cells[: len(CORE_COLS)]
        company, website = parse_link(core[3] if len(core) > 3 else "")
        _, source_url = parse_link(core[8] if len(core) > 8 else "")
        rows.append(
            ReportRow(
                index=len(rows) + 1,
                line=line,
                cells=core,
                company=company,
                website=website,
                source_url=source_url,
                country_cell=core[2] if len(core) > 2 else "",
            )
        )
    else:
        end_idx = len(lines)
    return lines[:header_idx], rows, lines[end_idx:]


def cache_get(cache: dict[str, Any], key: str) -> Any:
    with _cache_lock:
        return cache.get(key)


def cache_set(cache: dict[str, Any], key: str, value: Any) -> None:
    with _cache_lock:
        cache[key] = value


def soup_text(response_text: str) -> tuple[str, str, str, list[str]]:
    soup = BeautifulSoup(response_text, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "template"]):
        tag.decompose()
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    desc_tag = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
    desc = desc_tag.get("content", "") if desc_tag else ""
    text = soup.get_text(" ", strip=True)
    hrefs = []
    for tag in soup.find_all("a", href=True):
        href = tag.get("href") or ""
        if href:
            hrefs.append(href)
        if len(hrefs) >= 300:
            break
    return compact(title, 160), compact(desc, 260), compact(text, 9000), hrefs


def fetch_url(url: str, cache: dict[str, Any], *, parse: bool = True) -> dict[str, Any]:
    url = normalize_url(url)
    if not url:
        return {"url": "", "ok": False, "status": None, "status_label": "no link", "error": "no url"}
    key = f"fetch:{url}:{'parse' if parse else 'status'}"
    cached = cache_get(cache, key)
    if cached is not None:
        return cached
    result: dict[str, Any] = {
        "url": url,
        "ok": False,
        "status": None,
        "final_url": "",
        "status_label": "",
        "title": "",
        "description": "",
        "text": "",
        "hrefs": [],
        "error": "",
    }
    try:
        response = requests.get(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"},
            timeout=TIMEOUT,
            allow_redirects=True,
            stream=True,
        )
        body = response.raw.read(MAX_BODY, decode_content=True)
        result["status"] = response.status_code
        result["final_url"] = response.url
        result["ok"] = response.status_code < 400
        result["status_label"] = status_label(response.status_code, response.url, url)
        content_type = response.headers.get("content-type", "")
        if parse and body and "text/html" in content_type.lower():
            decoded = body.decode(response.encoding or "utf-8", errors="ignore")
            title, desc, text, hrefs = soup_text(decoded)
            result.update({"title": title, "description": desc, "text": text, "hrefs": hrefs})
        elif body:
            result["text"] = compact(body.decode("utf-8", errors="ignore"), 1000)
    except requests.Timeout:
        result.update({"status_label": "timeout", "error": "timeout"})
    except requests.RequestException as exc:
        result.update({"status_label": "fetch error", "error": str(exc)[:220]})
    except Exception as exc:  # noqa: BLE001
        result.update({"status_label": "parse error", "error": str(exc)[:220]})
    cache_set(cache, key, result)
    return result


def status_label(status: int | None, final_url: str, original_url: str) -> str:
    if status is None:
        return "unknown"
    base = f"{status} OK" if status < 400 else f"{status}"
    if status in {401, 403}:
        base += " blocked"
    elif status == 404:
        base += " not found"
    elif status >= 500:
        base += " server error"
    final_domain = domain_of(final_url)
    original_domain = domain_of(original_url)
    if final_domain and original_domain and final_domain != original_domain:
        base += f" -> {final_domain}"
    return base


def candidate_extra_links(base_url: str, hrefs: list[str]) -> list[str]:
    out: list[str] = []
    hints = re.compile(r"(news|blog|press|media|event|events|expo|ids|aeedc|webinar|seminar|brand|product|cad|cam|scanner|milling|digital)", re.I)
    for href in hrefs:
        if not hints.search(href):
            continue
        joined = urljoin(base_url, href)
        if domain_of(joined) != domain_of(base_url):
            continue
        if joined not in out:
            out.append(joined)
        if len(out) >= 2:
            break
    return out


def detect_brands(text: str) -> list[str]:
    found: list[str] = []
    for label, pattern in BRAND_PATTERNS:
        if re.search(pattern, text, re.I):
            found.append(label)
    return found[:7]


def recent_snippets(text: str) -> list[str]:
    snippets: list[str] = []
    for match in RECENT_RE.finditer(text):
        start = max(0, match.start() - 55)
        end = min(len(text), match.end() + 90)
        snippet = compact(text[start:end], 170)
        if snippet and snippet not in snippets:
            snippets.append(snippet)
        if len(snippets) >= 2:
            break
    return snippets


def ddg_url(raw: str) -> str:
    if raw.startswith("//duckduckgo.com/l/"):
        raw = "https:" + raw
    parsed = urlparse(raw)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        target = parse_qs(parsed.query).get("uddg", [""])[0]
        return unquote(target) if target else raw
    return raw


def search_web(query: str, cache: dict[str, Any]) -> list[dict[str, str]]:
    query = re.sub(r"\s+", " ", query).strip()
    if not query:
        return []
    key = f"search:{query}"
    cached = cache_get(cache, key)
    if cached is not None:
        return cached
    results: list[dict[str, str]] = []
    try:
        response = requests.get(
            "https://duckduckgo.com/html/",
            params={"q": query},
            headers={"User-Agent": USER_AGENT},
            timeout=SEARCH_TIMEOUT,
        )
        soup = BeautifulSoup(response.text, "html.parser")
        for item in soup.select(".result"):
            title_tag = item.select_one(".result__a, .result__title a")
            if not title_tag:
                continue
            title = compact(title_tag.get_text(" ", strip=True), 140)
            url = ddg_url(title_tag.get("href") or "")
            host = domain_of(url)
            if not title or not url or host in SEARCH_SKIP_DOMAINS or host.endswith(".doflab.com"):
                continue
            snippet_tag = item.select_one(".result__snippet")
            snippet = compact(snippet_tag.get_text(" ", strip=True), 260) if snippet_tag else ""
            results.append({"title": title, "url": url, "domain": host, "snippet": snippet})
            if len(results) >= 5:
                break
    except Exception as exc:  # noqa: BLE001
        results = [{"title": "검색 실패", "url": "", "domain": "", "snippet": str(exc)[:180]}]
    cache_set(cache, key, results)
    time.sleep(0.05)
    return results


def search_query(row: ReportRow) -> str:
    country = row.country_cell.split("/")[-1].strip()
    clean_name = re.sub(
        r"\b(gmbh|inc|ltd|limited|srl|s\.r\.l|spa|s\.p\.a|llc|bv|b\.v|s\.a|sas|ag|pte|plc|co)\b",
        "",
        row.company,
        flags=re.I,
    )
    clean_name = re.sub(r"\s+", " ", clean_name).strip()
    return f'"{clean_name}" {country} dental news distributor'


def result_is_relevant(row: ReportRow, result: dict[str, str], official_domain: str) -> bool:
    host = result.get("domain") or ""
    if official_domain and host == official_domain:
        return True
    hay = " ".join([result.get("title", ""), result.get("snippet", ""), result.get("url", "")]).lower()
    tokens = [t for t in re.findall(r"[a-z0-9]{3,}", row.company.lower()) if t not in {"dental", "group", "company", "gmbh", "ltd", "inc"}]
    if not tokens:
        return False
    return any(token in hay for token in tokens[:4]) and bool(re.search(r"dental|dent|scanner|cad|cam|milling|clinic|lab|orthodont", hay, re.I))


def is_directory_result(result: dict[str, str]) -> bool:
    url = (result.get("url") or "").lower()
    domain = (result.get("domain") or "").lower()
    return any(marker in domain or marker in url for marker in DIRECTORY_DOMAIN_MARKERS)


def social_labels(text: str, hrefs: list[str]) -> list[str]:
    labels: list[str] = []
    combined = " ".join([text, " ".join(hrefs)])
    for label, pattern in [
        ("LinkedIn", r"linkedin\.com"),
        ("Facebook", r"facebook\.com"),
        ("Instagram", r"instagram\.com"),
        ("YouTube", r"youtube\.com"),
        ("X/Twitter", r"(x\.com|twitter\.com)"),
    ]:
        if re.search(pattern, combined, re.I):
            labels.append(label)
    return labels[:4]


def research_row(row: ReportRow, cache: dict[str, Any]) -> dict[str, Any]:
    website = normalize_url(row.website)
    source_url = normalize_url(row.source_url)
    web = fetch_url(website, cache, parse=True) if website else {"status_label": "no link", "ok": False}
    source = fetch_url(source_url, cache, parse=False) if source_url else {"status_label": "no link", "ok": False}
    extra_pages: list[dict[str, Any]] = []
    if web.get("ok") and web.get("hrefs"):
        for link in candidate_extra_links(web.get("final_url") or website, web.get("hrefs") or []):
            extra_pages.append(fetch_url(link, cache, parse=True))
    query = search_query(row)
    search_results = [r for r in search_web(query, cache) if result_is_relevant(row, r, domain_of(web.get("final_url") or website))]
    evidence_text = " ".join(
        [
            row.cells[4] if len(row.cells) > 4 else "",
            row.cells[5] if len(row.cells) > 5 else "",
            row.cells[6] if len(row.cells) > 6 else "",
            web.get("title", ""),
            web.get("description", ""),
            web.get("text", ""),
            source.get("text", ""),
            " ".join(page.get("title", "") + " " + page.get("description", "") + " " + page.get("text", "") for page in extra_pages),
            " ".join(item.get("title", "") + " " + item.get("snippet", "") for item in search_results),
        ]
    )
    brands = detect_brands(evidence_text)
    recent = recent_snippets(evidence_text)
    social = social_labels(evidence_text, web.get("hrefs") or [])
    media = [
        item
        for item in search_results
        if not is_directory_result(item)
        and MEDIA_RE.search(" ".join([item.get("title", ""), item.get("snippet", ""), item.get("url", "")]))
    ]
    if web.get("ok") and source.get("ok") and brands:
        confidence = "높음"
    elif (web.get("ok") or source.get("ok")) and (brands or search_results or recent):
        confidence = "중간"
    else:
        confidence = "낮음"
    return {
        "index": row.index,
        "company": row.company,
        "country_cell": row.country_cell,
        "website": website,
        "source_url": source_url,
        "website_status": web.get("status_label") or "unknown",
        "website_final_url": web.get("final_url") or "",
        "website_title": web.get("title") or "",
        "source_status": source.get("status_label") or "unknown",
        "source_final_url": source.get("final_url") or "",
        "brands": brands,
        "recent_snippets": recent,
        "social": social,
        "media_results": media[:2],
        "search_results": search_results[:3],
        "query": query,
        "confidence": confidence,
        "extra_pages": [{"url": p.get("url"), "status": p.get("status_label"), "title": p.get("title")} for p in extra_pages[:2]],
        "checked_at": datetime.now().isoformat(timespec="seconds"),
    }


def link_cell(status: str, final_url: str, original_url: str) -> str:
    label = compact(status or "unknown", 48)
    if final_url or original_url:
        return f"[{md_escape(label)}]({final_url or original_url})"
    return md_escape(label)


def brands_cell(research: dict[str, Any]) -> str:
    brands = research.get("brands") or []
    if brands:
        return md_escape(", ".join(brands[:6]))
    title = research.get("website_title") or ""
    if title:
        return "브랜드 직접 검출 없음<br>" + md_escape(title, )
    return "브랜드 직접 검출 없음"


def online_cell(research: dict[str, Any]) -> str:
    parts: list[str] = []
    if research.get("recent_snippets"):
        years = sorted(set(re.findall(r"20(?:24|25|26)", " ".join(research["recent_snippets"]))), reverse=True)
        parts.append("최근연도 " + ", ".join(years))
    if research.get("social"):
        parts.append("SNS " + "/".join(research["social"]))
    media = research.get("media_results") or []
    if media:
        first = media[0]
        parts.append(f"[미디어/행사 후보]({first.get('url')})")
    elif research.get("search_results"):
        first = research["search_results"][0]
        parts.append(f"[검색근거]({first.get('url')})")
    if research.get("extra_pages"):
        parts.append("뉴스/제품 페이지 확인")
    if not parts:
        return "최근 공개 흔적 미확인"
    return md_escape("<br>".join(parts))


def confidence_cell(research: dict[str, Any]) -> str:
    confidence = research.get("confidence") or "낮음"
    if confidence == "높음":
        reason = "웹/출처 링크 정상 + 브랜드/품목 신호"
    elif confidence == "중간":
        reason = "일부 링크 또는 검색 신호 확인"
    else:
        reason = "링크 차단/검색 근거 제한"
    return f"{confidence}<br>{md_escape(reason)}"


def render_report(prefix: list[str], rows: list[ReportRow], suffix: list[str], research_by_index: dict[int, dict[str, Any]]) -> str:
    out = list(prefix)
    out.append("| " + " | ".join(CORE_COLS + NEW_COLS) + " |")
    out.append("| " + " | ".join(["---"] * (len(CORE_COLS) + len(NEW_COLS))) + " |")
    for row in rows:
        research = research_by_index[row.index]
        cells = list(row.cells[: len(CORE_COLS)])
        cells.extend(
            [
                link_cell(research.get("website_status", ""), research.get("website_final_url", ""), research.get("website", "")),
                link_cell(research.get("source_status", ""), research.get("source_final_url", ""), research.get("source_url", "")),
                brands_cell(research),
                online_cell(research),
                confidence_cell(research),
            ]
        )
        out.append("| " + " | ".join(cells) + " |")
    out.extend(suffix)
    text = "\n".join(out).strip() + "\n"
    text = re.sub(r"- 추천 업체 수:\s*\d+개", f"- 추천 업체 수: {len(rows)}개", text)
    text = re.sub(
        r"(- 제외: OSM 단독, 일반 병원/학교/학회/미디어, parser 잡음\(`Phone:`, 이미지 파일명 이메일 등\), 공식 출처 없이 검색 snippet만 있는 후보, 포탈 주문/등록 업체\.)",
        r"\1\n- 웹 부가정보: 2026-06-05 기준 회사 웹사이트/원출처 링크 상태, 홈페이지·제품·뉴스 페이지, 공개 검색 결과에서 브랜드·최근 온라인 흔적·미디어/행사성 후보를 자동 검증해 추가 컬럼으로 반영했다.",
        text,
        count=1,
    )
    return text


def run(args: argparse.Namespace) -> dict[str, Any]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    markdown = REPORT_MD.read_text(encoding="utf-8")
    prefix, rows, suffix = load_report_rows(markdown)
    if args.limit:
        rows = rows[: args.limit]
    cache = load_json(CACHE_PATH, {})
    research_rows: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_map = {executor.submit(research_row, row, cache): row for row in rows}
        for idx, future in enumerate(as_completed(future_map), start=1):
            row = future_map[future]
            try:
                research_rows.append(future.result())
            except Exception as exc:  # noqa: BLE001
                research_rows.append(
                    {
                        "index": row.index,
                        "company": row.company,
                        "country_cell": row.country_cell,
                        "website": row.website,
                        "source_url": row.source_url,
                        "website_status": "error",
                        "source_status": "error",
                        "brands": [],
                        "recent_snippets": [],
                        "social": [],
                        "media_results": [],
                        "search_results": [],
                        "confidence": "낮음",
                        "error": str(exc)[:240],
                        "checked_at": datetime.now().isoformat(timespec="seconds"),
                    }
                )
            if idx % 25 == 0 or idx == len(rows):
                print(json.dumps({"researched": idx, "target": len(rows)}, ensure_ascii=False), flush=True)
                save_json(CACHE_PATH, cache)
    research_rows.sort(key=lambda item: int(item["index"]))
    write_jsonl(RESEARCH_JSONL, research_rows)
    save_json(CACHE_PATH, cache)
    research_by_index = {int(row["index"]): row for row in research_rows}
    next_text = render_report(prefix, rows, suffix, research_by_index)
    REPORT_MD.write_text(next_text, encoding="utf-8")
    client = publish.OutlineClient(publish.read_env_key("DOF_OUTLINE_KEY"))
    updated = client.update_document(DOC_ID, DOC_TITLE, next_text)
    check = client.document_info(DOC_ID)
    check_text = check.get("text") or ""
    row_count = sum(1 for line in check_text.splitlines() if line.startswith("| A-") or line.startswith("| B-") or line.startswith("| C-"))
    trust_counts = Counter(row.get("confidence") for row in research_rows)
    website_status_counts = Counter((row.get("website_status") or "").split()[0] for row in research_rows)
    source_status_counts = Counter((row.get("source_status") or "").split()[0] for row in research_rows)
    with_brands = sum(1 for row in research_rows if row.get("brands"))
    with_recent = sum(1 for row in research_rows if row.get("recent_snippets") or row.get("media_results") or row.get("social"))
    with_media = sum(1 for row in research_rows if row.get("media_results"))
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "url": OUTLINE_URL,
        "outline_url_returned": f"https://outline.doflab.com/doc/{updated.get('urlId') or check.get('urlId')}",
        "title": check.get("title"),
        "row_count": row_count,
        "expected_rows": len(rows),
        "has_new_columns": all(col in check_text for col in NEW_COLS),
        "text_len": len(check_text),
        "trust_counts": dict(trust_counts),
        "website_status_counts": dict(website_status_counts),
        "source_status_counts": dict(source_status_counts),
        "with_brands": with_brands,
        "with_recent_or_social_or_media": with_recent,
        "with_media_candidates": with_media,
        "research_jsonl": str(RESEARCH_JSONL),
        "cache": str(CACHE_PATH),
        "local_md": str(REPORT_MD),
    }
    save_json(SUMMARY_JSON, summary)
    existing = load_json(RESULT_JSON, {})
    existing.update(
        {
            "web_enrichment": summary,
            "row_count": row_count,
            "has_table": "## 추천 업체 테이블" in check_text,
            "has_portal_exclusion": "포탈 제외 기준" in check_text,
            "text_len": len(check_text),
            "updated_at_epoch": int(time.time()),
        }
    )
    save_json(RESULT_JSON, existing)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=10)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    print(json.dumps(run(args), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
