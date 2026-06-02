#!/usr/bin/env python3
"""Enrich existing customer Outline pages with public company research."""

from __future__ import annotations

import argparse
import html
import json
import re
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import requests
from bs4 import BeautifulSoup

import dof_prospect_outline_publish as publish


BASE = publish.BASE
DATA = publish.DATA
OUT_DIR = publish.PUBLISH_ROOT / "existing_customer_enrichment"
CACHE_PATH = OUT_DIR / "public_research_cache.json"
RESEARCH_JSONL = OUT_DIR / "existing_customer_research.jsonl"
SUMMARY_JSON = OUT_DIR / "existing_customer_enrichment_summary.json"

TODAY_LABEL = "2026-06-02"
SECTION_TITLE = f"## 공개 조사 보강 ({TODAY_LABEL})"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
)
REQUEST_TIMEOUT = 8
SEARCH_TIMEOUT = 8
DEFAULT_WORKERS = 12
MAX_SEARCH_RESULTS = 6

NO_WEBSITE_VALUES = {
    "",
    "-",
    "n/a",
    "none",
    "null",
    "메모에 입력요청",
    "메모 입력요청",
}

SERVICE_KEYWORDS = [
    ("치기공/보철 제작", r"\b(dental\s*lab|laborator|dentallabor|zahntechnik|prothes|prosthetic|prosthodontic|技工|치기공|랩)\b"),
    ("CAD/CAM·밀링", r"\b(cad\s*/?\s*cam|milling|mill|zirconia|zirkon|crown|bridge|implant bar|abutment|imes|roland|dgshape)\b"),
    ("디지털 치과 워크플로우", r"\b(digital dentistry|intraoral|scanner|scan|3d\s*print|printing|exocad|model creator|digital workflow)\b"),
    ("치과 병·의원 진료", r"\b(dental clinic|dental practice|dentist|orthodont|implantology|endodont|periodont|clinic)\b"),
    ("치과 유통/장비 공급", r"\b(distributor|dealer|supply|supplies|equipment|trading|medical device|authorized|reseller|import|export)\b"),
    ("교육·세미나·행사", r"\b(training|course|seminar|webinar|conference|congress|expo|exhibition|ids|aeedc|capp)\b"),
]

MEDIA_KEYWORDS = re.compile(
    r"\b(news|press|article|interview|award|awards|expo|exhibition|congress|conference|ids|aeedc|capp|sidex|event|trade fair)\b",
    re.I,
)
DIRECTORY_DOMAINS = {
    "linkedin.com",
    "facebook.com",
    "instagram.com",
    "youtube.com",
    "zoominfo.com",
    "dnb.com",
    "crunchbase.com",
    "opencorporates.com",
    "lmtmag.com",
    "dentistrytoday.com",
    "dental-tribune.com",
    "yellowpages",
    "gelbeseiten",
    "google.com",
    "maps.apple.com",
}
BLOCKED_RESULT_DOMAINS = {
    "scamadviser.com",
    "similarweb.com",
}
DENTAL_RESULT_TERMS = re.compile(
    r"\b(dental|dentist|dentistry|orthodont|clinic|laborator|lab|milling|cad\s*/?\s*cam|zahnarzt|zahntechnik|odont|stomatolog|prosthetic|implant)\b",
    re.I,
)

_cache_lock = threading.Lock()


@dataclass(frozen=True)
class ExistingCustomer:
    key: str
    portal_company_id: int | None
    doc_id: str
    title: str
    url: str
    row: dict[str, Any]


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def normalize_space(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def compact(value: Any, limit: int = 260) -> str:
    text = normalize_space(value)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def clean_company_name(name: str) -> str:
    name = normalize_space(name)
    name = re.sub(r"^\d{1,4}\.\s*", "", name)
    name = re.sub(r"\s*\([^)]*\)\s*$", "", name)
    name = re.sub(
        r"\b(co\.?\s*ltd\.?|ltd\.?|inc\.?|corp\.?|corporation|gmbh|srl|s\.r\.l\.|llc|pte\.?\s*ltd\.?|limited|ag|sas|s\.a\.|a/s|doo|d\.o\.o\.)\b",
        "",
        name,
        flags=re.I,
    )
    return normalize_space(name)


def normalize_url(value: Any) -> str:
    text = normalize_space(value)
    if text.lower() in NO_WEBSITE_VALUES:
        return ""
    if "@" in text and not text.startswith(("http://", "https://")):
        return ""
    if text.startswith("www."):
        text = "https://" + text
    elif text and not re.match(r"^https?://", text, re.I):
        text = "https://" + text
    parsed = urlparse(text)
    if not parsed.netloc or "." not in parsed.netloc:
        return ""
    return text


def domain_of(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return ""
    host = host.split("@")[-1].split(":")[0]
    return host.removeprefix("www.")


def is_dof_url(url: str) -> bool:
    host = domain_of(url)
    return host == "doflab.com" or host.endswith(".doflab.com")


def email_domain(email: Any) -> str:
    text = normalize_space(email).lower()
    if "@" not in text:
        return ""
    domain = text.rsplit("@", 1)[-1]
    if "." not in domain:
        return ""
    return domain


def cache_get(cache: dict[str, Any], key: str) -> Any:
    with _cache_lock:
        return cache.get(key)


def cache_set(cache: dict[str, Any], key: str, value: Any) -> None:
    with _cache_lock:
        cache[key] = value


def fetch_url(url: str, cache: dict[str, Any]) -> dict[str, Any]:
    key = f"url:{url}"
    cached = cache_get(cache, key)
    if cached is not None:
        return cached
    result: dict[str, Any] = {"url": url, "ok": False, "status": None, "title": "", "description": "", "text": "", "error": ""}
    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        result["status"] = response.status_code
        result["final_url"] = response.url
        ctype = response.headers.get("content-type", "")
        if response.status_code < 400 and "text/html" in ctype:
            soup = BeautifulSoup(response.text, "html.parser")
            for tag in soup(["script", "style", "noscript", "svg"]):
                tag.decompose()
            title = soup.title.get_text(" ", strip=True) if soup.title else ""
            desc_tag = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
            desc = desc_tag.get("content", "") if desc_tag else ""
            text = soup.get_text(" ", strip=True)
            result.update({"ok": True, "title": compact(title, 180), "description": compact(desc, 360), "text": compact(text, 6000)})
        elif response.status_code < 400:
            result.update({"ok": True, "text": compact(response.text, 1000)})
    except Exception as exc:  # noqa: BLE001 - external websites fail in many non-actionable ways.
        result["error"] = str(exc)[:220]
    cache_set(cache, key, result)
    return result


def ddg_url(raw: str) -> str:
    if raw.startswith("//duckduckgo.com/l/"):
        raw = "https:" + raw
    parsed = urlparse(raw)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        target = parse_qs(parsed.query).get("uddg", [""])[0]
        return unquote(target) if target else raw
    return raw


def search_web(query: str, cache: dict[str, Any]) -> list[dict[str, str]]:
    query = normalize_space(query)
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
            title = normalize_space(title_tag.get_text(" ", strip=True))
            url = ddg_url(title_tag.get("href") or "")
            snippet_tag = item.select_one(".result__snippet")
            snippet = normalize_space(snippet_tag.get_text(" ", strip=True)) if snippet_tag else ""
            if not title or not url:
                continue
            host = domain_of(url)
            if host in BLOCKED_RESULT_DOMAINS:
                continue
            if "doflab.com" in host or "outline.doflab.com" in host:
                continue
            results.append({"title": compact(title, 180), "url": url, "domain": host, "snippet": compact(snippet, 360)})
            if len(results) >= MAX_SEARCH_RESULTS:
                break
    except Exception as exc:  # noqa: BLE001 - search fallback should not fail the whole batch.
        results = [{"title": "검색 실패", "url": "", "domain": "", "snippet": str(exc)[:220]}]
    cache_set(cache, key, results)
    time.sleep(0.08)
    return results


def infer_services(text: str) -> list[str]:
    found: list[str] = []
    for label, pattern in SERVICE_KEYWORDS:
        if re.search(pattern, text, re.I):
            found.append(label)
    return found[:5]


def is_directory_result(result: dict[str, str]) -> bool:
    domain = result.get("domain", "")
    url = result.get("url", "").lower()
    return any(marker in domain or marker in url for marker in DIRECTORY_DOMAINS)


def is_media_result(result: dict[str, str]) -> bool:
    text = " ".join([result.get("title", ""), result.get("snippet", ""), result.get("url", "")])
    return bool(MEDIA_KEYWORDS.search(text)) and not is_directory_result(result)


def result_line(result: dict[str, str]) -> str:
    title = result.get("title") or result.get("domain") or "출처"
    url = result.get("url") or ""
    snippet = result.get("snippet") or ""
    if url:
        return f"- [{publish.md_escape(title)}]({url})" + (f" — {publish.md_escape(snippet)}" if snippet else "")
    return f"- {publish.md_escape(title)}" + (f" — {publish.md_escape(snippet)}" if snippet else "")


def trust_label(has_official: bool, has_fetched_official: bool, search_results: list[dict[str, str]], media_results: list[dict[str, str]]) -> tuple[str, str]:
    if has_fetched_official and search_results:
        return ("높음", "공식 웹사이트 본문과 공개 검색 결과를 함께 확인했고, DOF 포탈 주문/등록 근거가 있다.")
    if has_fetched_official:
        return ("높음", "공식 웹사이트 본문과 DOF 포탈 주문/등록 근거가 있다. 다만 외부 언론 노출은 제한적으로만 확인됐다.")
    if has_official or search_results or media_results:
        return ("중간", "DOF 포탈 등록 근거와 공개 검색 결과는 있으나, 공식 웹사이트 본문까지 안정적으로 읽지는 못했다.")
    return ("낮음", "DOF 포탈 등록/주문 근거 외에 동일 업체로 확정 가능한 공개 웹 근거가 부족하다.")


def build_queries(row: dict[str, Any]) -> list[str]:
    name = normalize_space(row.get("name"))
    cleaned = clean_company_name(name)
    country = normalize_space(row.get("country"))
    website = normalize_url(row.get("website")) or normalize_url(row.get("source_url"))
    if is_dof_url(website):
        website = ""
    website_domain = domain_of(website)
    mail_domain = email_domain(row.get("email"))
    pieces = []
    if cleaned:
        pieces.extend(
            [
                f"{cleaned} {country} dental",
                f"{cleaned} dental lab OR dental clinic OR distributor",
                f"{cleaned} news dental",
            ]
        )
    if website_domain:
        pieces.append(f"site:{website_domain} dental")
    elif mail_domain:
        pieces.append(f"{mail_domain} dental")
    dedup: list[str] = []
    for item in pieces:
        item = normalize_space(item)
        if item and item not in dedup:
            dedup.append(item)
    return dedup[:2]


def meaningful_name_tokens(name: str) -> list[str]:
    stop = {
        "dental",
        "dent",
        "clinic",
        "lab",
        "laboratory",
        "company",
        "group",
        "medical",
        "service",
        "services",
        "international",
    }
    tokens = re.findall(r"[a-z0-9][a-z0-9-]{2,}", clean_company_name(name).lower())
    return [token for token in tokens if token not in stop][:6]


def relevant_result(row: dict[str, Any], result: dict[str, str], official_domain: str, mail_domain: str) -> bool:
    domain = result.get("domain", "")
    if domain and (domain == official_domain or domain == mail_domain):
        return True
    text = " ".join([result.get("title", ""), result.get("snippet", ""), result.get("url", "")]).lower()
    tokens = meaningful_name_tokens(str(row.get("name") or ""))
    has_name = any(token in text for token in tokens)
    has_dental = bool(DENTAL_RESULT_TERMS.search(text))
    if len(clean_company_name(str(row.get("name") or ""))) <= 4:
        return has_dental and has_name
    return has_name and has_dental


def research_customer(customer: ExistingCustomer, cache: dict[str, Any]) -> dict[str, Any]:
    row = customer.row
    name = normalize_space(row.get("name")) or clean_company_name(customer.title)
    website = normalize_url(row.get("website"))
    if not website:
        website = normalize_url(row.get("source_url"))
    if is_dof_url(website):
        website = ""
    official = fetch_url(website, cache) if website else {}
    queries = build_queries(row)
    all_results: list[dict[str, str]] = []
    for query in queries:
        for result in search_web(query, cache):
            if result.get("url") and result["url"] not in {item.get("url") for item in all_results}:
                all_results.append(result)

    official_domain = domain_of(website)
    email_dom = email_domain(row.get("email"))
    all_results = [result for result in all_results if relevant_result(row, result, official_domain, email_dom)]
    official_results = [
        result
        for result in all_results
        if result.get("domain") and (result["domain"] == official_domain or result["domain"] == email_dom)
    ]
    media_results = [result for result in all_results if is_media_result(result)]
    directory_results = [result for result in all_results if is_directory_result(result)]
    other_results = [
        result
        for result in all_results
        if result not in official_results and result not in media_results and result not in directory_results
    ]
    evidence_text = " ".join(
        [
            normalize_space(row.get("segment")),
            normalize_space(row.get("selection_reason")),
            official.get("title", ""),
            official.get("description", ""),
            official.get("text", ""),
            " ".join(result.get("title", "") + " " + result.get("snippet", "") for result in all_results[:8]),
        ]
    )
    services = infer_services(evidence_text)
    trust, trust_reason = trust_label(bool(website or official_results), bool(official.get("ok") and official.get("text")), all_results, media_results)
    return {
        "key": customer.key,
        "portal_company_id": customer.portal_company_id,
        "doc_id": customer.doc_id,
        "title": customer.title,
        "outline_url": customer.url,
        "name": name,
        "country": row.get("country"),
        "orders": row.get("portal_orders_count"),
        "website": website,
        "official": {k: official.get(k) for k in ["ok", "status", "final_url", "title", "description", "error"]} if official else {},
        "queries": queries,
        "services": services,
        "official_results": official_results[:3],
        "media_results": media_results[:3],
        "directory_results": directory_results[:3],
        "other_results": other_results[:3],
        "trust": trust,
        "trust_reason": trust_reason,
        "searched_at": datetime.now().isoformat(timespec="seconds"),
    }


def build_section(row: dict[str, Any], research: dict[str, Any]) -> str:
    services = research.get("services") or []
    services_text = ", ".join(services) if services else "공개 웹 텍스트만으로 구체 업역을 확정하기 어려움"
    media = research.get("media_results") or []
    if media:
        media_text = f"{len(media)}건의 행사/언론성 검색 결과가 확인됨. 동일성은 아래 링크별로 재확인 필요."
    else:
        media_text = "명확한 언론 기사/행사 노출은 이번 공개 검색에서 확인하지 못함."
    orders = row.get("portal_orders_count")
    portal_line = f"DOF 포탈 회사 ID {row.get('portal_company_id')}, 포탈 주문 {orders}건" if orders is not None else "DOF 포탈 등록 기존고객"
    lines = [
        SECTION_TITLE,
        "",
        "### 요약",
        "",
        f"- 확인 방법: DOF 포탈 등록/주문 근거, 공식 웹사이트/이메일 도메인, 공개 검색 결과, 업계 디렉터리·언론성 키워드 검색.",
        f"- 치과 관련 활동: {publish.md_escape(services_text)}.",
        f"- 언론·외부 노출: {publish.md_escape(media_text)}",
        f"- 신뢰도: **{publish.md_escape(research.get('trust'))}** — {publish.md_escape(research.get('trust_reason'))}",
        "",
        "### 확인 근거",
        "",
        f"- 포탈 근거: {publish.md_escape(portal_line)}.",
    ]
    official = research.get("official") or {}
    website = research.get("website") or ""
    if website:
        official_title = official.get("title") or official.get("description") or domain_of(website) or website
        status = official.get("status")
        status_text = f", HTTP {status}" if status else ""
        lines.append(f"- 공식/자체 채널: [{publish.md_escape(compact(official_title, 120))}]({website}){publish.md_escape(status_text)}.")
    if research.get("official_results"):
        lines += ["", "### 공식/자체 채널 검색 결과", ""]
        lines.extend(result_line(item) for item in research["official_results"][:3])
    if research.get("media_results"):
        lines += ["", "### 언론·행사성 노출 후보", ""]
        lines.extend(result_line(item) for item in research["media_results"][:3])
    if research.get("directory_results") or research.get("other_results"):
        lines += ["", "### 기타 공개 검색 근거", ""]
        for item in (research.get("directory_results") or [])[:2] + (research.get("other_results") or [])[:2]:
            lines.append(result_line(item))
    lines += [
        "",
        "### 보수적 해석",
        "",
        "- 위 내용은 공개 웹에서 자동 수집한 제목/스니펫/공식 페이지 본문 기반이다. 동명이인·동명 업체 가능성이 있으면 신뢰도를 중간 이하로 낮춰 해석한다.",
    ]
    return "\n".join(lines).strip() + "\n"


def replace_section(text: str, section: str) -> str:
    pattern = re.compile(r"\n?## 공개 조사 보강 \(2026-06-02\)\n.*?(?=\n## 영업 메모|\Z)", re.S)
    text = pattern.sub("\n", text).rstrip() + "\n"
    marker = "\n## 영업 메모"
    if marker in text:
        before, after = text.split(marker, 1)
        return before.rstrip() + "\n\n" + section.rstrip() + "\n\n## 영업 메모" + after
    return text.rstrip() + "\n\n" + section


def parse_current_body_fields(text: str) -> dict[str, Any]:
    row: dict[str, Any] = {}
    title = re.search(r"^#\s+(.+)$", text, re.M)
    if title:
        row["name"] = title.group(1).strip()
    for label, key in [
        ("국가", "country"),
        ("고객군", "segment"),
        ("DOF 적합성", "dof_fit"),
        ("선정 이유", "selection_reason"),
        ("이메일", "email"),
        ("전화", "phone"),
        ("주소", "address"),
    ]:
        match = re.search(rf"^- {label}:\s*(.+)$", text, re.M)
        if match:
            row[key] = match.group(1).strip()
    orders = re.search(r"포탈 주문 수:\s*(\d+)", text)
    if orders:
        row["portal_orders_count"] = int(orders.group(1))
    return row


def load_portal_rows() -> dict[int, dict[str, Any]]:
    rows = read_jsonl(DATA / "prospects_augmented_with_portal.jsonl")
    result: dict[int, dict[str, Any]] = {}
    for row in rows:
        if row.get("portal_company_id"):
            result[int(row["portal_company_id"])] = row
    raw_path = DATA / "portal_active_companies_raw.json"
    if raw_path.exists():
        raw_rows = json.loads(raw_path.read_text(encoding="utf-8"))
        for item in raw_rows:
            company_id = item.get("id")
            if not company_id or int(company_id) in result:
                continue
            result[int(company_id)] = {
                "name": item.get("name"),
                "country": item.get("country"),
                "email": item.get("email"),
                "phone": item.get("phone") or item.get("telephone"),
                "address": item.get("address"),
                "website": item.get("website"),
                "source_url": f"https://portal.doflab.com/companies/{company_id}",
                "source_type": "DOF portal Company",
                "segment": "Portal customer / overseas account",
                "selection_reason": "DOF portal에 등록된 기존고객.",
                "portal_company_id": company_id,
                "portal_orders_count": item.get("orders_count"),
            }
    return result


def load_customers(limit: int | None = None) -> list[ExistingCustomer]:
    cache = load_json(publish.DOC_CACHE, {"docs": {}}).get("docs", {})
    portal_rows = load_portal_rows()
    customers: list[ExistingCustomer] = []
    for key, doc in sorted(cache.items(), key=lambda item: item[1].get("title", "")):
        if not key.startswith("company:portal:"):
            continue
        company_id_text = key.rsplit(":", 1)[-1]
        company_id = int(company_id_text) if company_id_text.isdigit() else None
        row = dict(portal_rows.get(company_id or -1, {}))
        row.setdefault("portal_company_id", company_id)
        row.setdefault("name", clean_company_name(doc.get("title", "")))
        customers.append(
            ExistingCustomer(
                key=key,
                portal_company_id=company_id,
                doc_id=doc["id"],
                title=doc.get("title") or row["name"],
                url=doc.get("url") or "",
                row=row,
            )
        )
        if limit and len(customers) >= limit:
            break
    return customers


def update_one(api_key: str, customer: ExistingCustomer, research: dict[str, Any], dry_run: bool = False) -> dict[str, Any]:
    client = publish.OutlineClient(api_key)
    last_error: Exception | None = None
    for attempt in range(1, 6):
        try:
            info = client.document_info(customer.doc_id)
            current_text = info.get("text") or ""
            row = dict(customer.row)
            for key, value in parse_current_body_fields(current_text).items():
                row.setdefault(key, value)
            section = build_section(row, research)
            new_text = replace_section(current_text, section)
            if dry_run:
                return {"updated": False, "changed": new_text != current_text, "text_len": len(new_text)}
            if new_text == current_text:
                return {"updated": False, "changed": False, "text_len": len(new_text)}
            updated = client.update_document(customer.doc_id, info.get("title") or customer.title, new_text)
            return {"updated": True, "changed": True, "text_len": len(new_text), "url": publish.doc_url(updated)}
        except Exception as exc:  # noqa: BLE001 - retry transient Outline/network failures.
            last_error = exc
            if attempt < 5:
                time.sleep(min(20, attempt * 2))
                continue
    raise RuntimeError(str(last_error) if last_error else "unknown Outline update error")


def run(limit: int | None, workers: int, dry_run: bool, research_only: bool, update_only: bool) -> dict[str, Any]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    customers = load_customers(limit)
    cache = load_json(CACHE_PATH, {})
    research_rows: list[dict[str, Any]] = []
    update_results: list[dict[str, Any]] = []
    api_key = publish.read_env_key("DOF_OUTLINE_KEY")

    if update_only:
        existing = read_jsonl(RESEARCH_JSONL)
        existing_by_key = {row["key"]: row for row in existing}
        research_rows = [existing_by_key[customer.key] for customer in customers if customer.key in existing_by_key]
    else:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_map = {executor.submit(research_customer, customer, cache): customer for customer in customers}
            for index, future in enumerate(as_completed(future_map), start=1):
                customer = future_map[future]
                try:
                    research = future.result()
                    research_rows.append(research)
                except Exception as exc:  # noqa: BLE001
                    research = {
                        "key": customer.key,
                        "portal_company_id": customer.portal_company_id,
                        "doc_id": customer.doc_id,
                        "title": customer.title,
                        "outline_url": customer.url,
                        "trust": "낮음",
                        "trust_reason": f"조사 중 오류: {str(exc)[:220]}",
                        "services": [],
                        "official_results": [],
                        "media_results": [],
                        "directory_results": [],
                        "other_results": [],
                        "queries": [],
                    }
                    research_rows.append(research)
                if index % 25 == 0 or index == len(customers):
                    print(json.dumps({"researched": index, "target": len(customers)}, ensure_ascii=False), flush=True)
                    save_json(CACHE_PATH, cache)

        research_rows.sort(key=lambda row: row.get("title", ""))
        write_jsonl(RESEARCH_JSONL, research_rows)
        save_json(CACHE_PATH, cache)

    if not research_only:
        research_by_key = {row["key"]: row for row in research_rows}
        for index, customer in enumerate(customers, start=1):
            research = research_by_key[customer.key]
            try:
                result = update_one(api_key, customer, research, dry_run=dry_run)
                result.update({"key": customer.key, "title": customer.title, "doc_id": customer.doc_id, "outline_url": customer.url})
            except Exception as exc:  # noqa: BLE001
                result = {
                    "key": customer.key,
                    "title": customer.title,
                    "doc_id": customer.doc_id,
                    "outline_url": customer.url,
                    "updated": False,
                    "changed": False,
                    "error": str(exc)[:500],
                }
            update_results.append(result)
            if index % 25 == 0 or index == len(customers):
                print(json.dumps({"updated_checked": index, "target": len(customers)}, ensure_ascii=False), flush=True)

    trust_counts = Counter(row.get("trust") for row in research_rows)
    service_counts = Counter(service for row in research_rows for service in row.get("services", []))
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "target_customers": len(customers),
        "research_rows": len(research_rows),
        "trust_counts": dict(trust_counts),
        "service_counts": dict(service_counts),
        "with_website": sum(1 for row in research_rows if row.get("website")),
        "with_media_or_event_candidates": sum(1 for row in research_rows if row.get("media_results")),
        "dry_run": dry_run,
        "research_only": research_only,
        "update_only": update_only,
        "updated": sum(1 for row in update_results if row.get("updated")),
        "changed": sum(1 for row in update_results if row.get("changed")),
        "failed": [row for row in update_results if row.get("error")],
        "research_jsonl": str(RESEARCH_JSONL),
    }
    save_json(SUMMARY_JSON, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int)
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--research-only", action="store_true")
    parser.add_argument("--update-only", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(args.limit, args.workers, args.dry_run, args.research_only, args.update_only), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
