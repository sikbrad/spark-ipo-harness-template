#!/usr/bin/env python3
"""Round 12 scanner/milling/CAD-CAM focused non-OSM prospect expansion."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import shutil
import subprocess
import threading
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

import dof_partial_distributor_candidate_expansion as partial
import dof_round11_non_osm_lab_registry_expansion as round11


ROOT = Path("/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04")
OUT_ROOT = ROOT / "output/dof-overseas-customer-prospects/2026-05-30/scale5000"
DATA = OUT_ROOT / "data"
BACKUP_DIR = DATA / "backups"
COMPLETE_JSONL = DATA / "prospects_augmented_contact_complete.jsonl"
COMPLETE_CSV = DATA / "prospects_augmented_contact_complete.csv"
PROMOTIONS_JSONL = DATA / "partial_distributor_promotions_round12.jsonl"
SEARCH_RAW_JSONL = DATA / "partial_distributor_search_raw_round12.jsonl"
SEARCH_CACHE_JSON = DATA / "partial_distributor_search_cache_round12.json"
PAGE_CACHE_JSON = DATA / "partial_distributor_page_cache_round12.json"
SUMMARY_MD = OUT_ROOT / "scanner_milling_cadcam_expansion_round12.md"
RESULT_JSON = OUT_ROOT / "scanner_milling_cadcam_expansion_round12_result.json"

USER_AGENT = partial.USER_AGENT
VHF_RESELLERS = "https://www.vhf.com/en/contact/resellers-dental/"
EXOCAD_IDS_RESELLER_PDF = "https://bcontent.exocad.com/fileadmin/content/Events/IDS_2025/exocad_IDS_Reseller_List_EN_web.pdf"
CACHE_LOCK = threading.Lock()

TARGET_RE = re.compile(
    r"medit|shining\s*3d|aoralscan|3shape|trios|exocad|vhf|dgshape|roland\s*dg|dwx|imes[-\s]?icore|coritec|"
    r"amann\s+girrbach|ceramill|zirkonzahn|planmeca|cerec|dentsply\s+sirona|carestream|itero|"
    r"intra.?oral\s+scanner|oral\s+scanner|lab\s+scanner|dental\s+scanner|cad.?cam|milling\s+machine|fresadora|fraiseuse|"
    r"fräsmaschine|fräsgerät|fresatrice|ミリング|口腔扫描|口腔掃描|구강\s*스캐너",
    re.I,
)
CHANNEL_RE = re.compile(
    r"distribut|dealer|reseller|revendeur|fournisseur|händler|vertrieb|authorized|authorised|official\s+partner|"
    r"partner|vendor|supplier|depot|import|export|suministro|distribuidor|distribuidora|rivenditore|代理商|经销商|販売代理店|대리점|유통",
    re.I,
)
GENERIC_RE = re.compile(
    r"\b(news|blog|article|manual|brochure|catalog|catalogue|training|course|webinar|forum|reddit|review|"
    r"price|prices|used|second hand|job|jobs|careers|download|support only|market report|study|research)\b",
    re.I,
)
SKIP_HOST_HINTS = (
    "reddit.com",
    "wikipedia.org",
    "youtube.com",
    "instagram.com",
    "pinterest.",
    "amazon.",
    "ebay.",
    "alibaba.",
    "made-in-china.com",
    "globalsources.com",
    "researchgate.net",
    "arxiv.org",
    "ncbi.nlm.nih.gov",
    "pubmed.ncbi.nlm.nih.gov",
    "facebook.com/events",
    "facebook.com/groups",
)
SOCIAL_HOST_HINTS = ("facebook.com", "linkedin.com")
DIRECTORY_HOST_HINTS = (
    "kompass",
    "europages",
    "medicalexpo",
    "directindustry",
    "cylex",
    "cybo.com",
    "yellowpages",
    "pagesjaunes",
    "paginasamarillas",
    "businesslist",
    "tuugo",
    "hotfrog",
    "brownbook",
)
OFFICIAL_HOST_HINTS = (
    "vhf.com",
    "exocad.com",
    "bcontent.exocad.com",
    "medit.com",
    "shining3ddental.com",
    "shining3d.com",
    "3shape.com",
    "rolanddg.",
    "dgshape.com",
    "imes-icore.com",
    "amanngirrbach.com",
    "zirkonzahn.com",
    "planmeca.com",
    "dentsplysirona.com",
    "carestreamdental.com",
)

COUNTRIES = [
    "United States",
    "Canada",
    "Mexico",
    "Brazil",
    "Argentina",
    "Chile",
    "Colombia",
    "Peru",
    "Costa Rica",
    "Panama",
    "Germany",
    "France",
    "Italy",
    "Spain",
    "Portugal",
    "Netherlands",
    "Belgium",
    "Switzerland",
    "Austria",
    "United Kingdom",
    "Ireland",
    "Norway",
    "Sweden",
    "Denmark",
    "Finland",
    "Poland",
    "Czech Republic",
    "Slovakia",
    "Hungary",
    "Romania",
    "Bulgaria",
    "Croatia",
    "Serbia",
    "Greece",
    "Turkey",
    "United Arab Emirates",
    "Saudi Arabia",
    "Qatar",
    "Kuwait",
    "Jordan",
    "Israel",
    "Egypt",
    "Morocco",
    "South Africa",
    "Nigeria",
    "Kenya",
    "India",
    "Pakistan",
    "Bangladesh",
    "Sri Lanka",
    "Nepal",
    "Thailand",
    "Vietnam",
    "Indonesia",
    "Malaysia",
    "Singapore",
    "Philippines",
    "Japan",
    "South Korea",
    "China",
    "Taiwan",
    "Hong Kong",
    "Australia",
    "New Zealand",
]

TERMS = [
    '"Medit" "authorized distributor" dental scanner',
    '"Medit" "reseller" "intraoral scanner"',
    '"Medit i700" reseller dental',
    '"Medit i900" distributor dental',
    '"Shining 3D" dental distributor',
    '"Aoralscan" reseller',
    '"Shining 3D" "authorized reseller" dental',
    '"3Shape TRIOS" reseller',
    '"3Shape" "distributor" "TRIOS"',
    '"exocad" reseller dental',
    '"exocad" "authorized reseller"',
    '"vhf" "dental milling" reseller',
    '"DGSHAPE" distributor dental',
    '"Roland DG" "dental milling" reseller',
    '"imes-icore" distributor dental',
    '"Amann Girrbach" distributor dental',
    '"Ceramill" reseller dental',
    '"Zirkonzahn" distributor dental',
    '"intraoral scanner" distributor dental',
    '"dental scanner" dealer',
    '"dental CAD CAM" distributor',
    '"dental milling machine" distributor',
    'distribuidor escáner intraoral dental',
    'distribuidor fresadora dental CAD CAM',
    'revendeur scanner intra-oral dentaire',
    'fournisseur CAD CAM dentaire',
    'Dental CAD CAM Händler',
    'Intraoralscanner Händler Dental',
    'scanner intraorale rivenditore dentale',
    'fresatrice dentale distributore',
    '歯科用 ミリングマシン 販売代理店',
    '口腔扫描仪 经销商 牙科',
    '치과 구강스캐너 대리점',
]

SITE_PATTERNS = [
    "",
    "site:kompass.com",
    "site:europages.com",
    "site:medicalexpo.com",
    "site:linkedin.com/company",
    "site:facebook.com",
]


def clean(value: object) -> str:
    return partial.clean(value)


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path: Path, value: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file_obj:
        for row in rows:
            file_obj.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def host(value: str) -> str:
    try:
        return (urlparse(value).hostname or "").lower().removeprefix("www.")
    except Exception:
        return ""


def root_domain_label(url: str) -> str:
    current_host = host(url)
    if not current_host:
        return ""
    label = current_host.split(".")[0]
    return " ".join(part.capitalize() for part in re.split(r"[-_]+", label) if part)


def strong_target_text(text: str) -> bool:
    return bool(TARGET_RE.search(text) and (CHANNEL_RE.search(text) or re.search(r"scanner|milling|cad.?cam|fresadora|fräs|fraiseuse", text, re.I)))


def infer_search_name(title: str, url: str) -> str:
    title = clean(title)
    parts = [clean(part) for part in re.split(r"\s+[|–-]\s+|::|»", title) if clean(part)]
    generic = re.compile(r"medit|shining|aoralscan|3shape|trios|exocad|vhf|dgshape|roland|imes|amann|ceramill|zirkonzahn|scanner|cad.?cam|milling|fresadora|distributor|reseller|dealer|official|partner", re.I)
    non_generic = [part for part in parts if not generic.search(part) and partial.is_usable_name(part)]
    if non_generic:
        return non_generic[-1] if len(non_generic[-1]) > 2 else non_generic[0]
    cleaned = round11.clean_listing_name(title)
    if cleaned and not GENERIC_RE.search(cleaned):
        return cleaned
    return root_domain_label(url)


def source_meta_for_url(url: str, blob: str) -> tuple[str, str, str, int]:
    current_host = host(url)
    if any(item in current_host for item in OFFICIAL_HOST_HINTS):
        return "Official scanner/milling/CAD-CAM vendor or partner page signal", "medium-high", "official_vendor_partner_or_product_page", 35
    if any(item in current_host for item in DIRECTORY_HOST_HINTS):
        return "CAD-CAM/scanner distributor business-directory signal", "low-medium", "cadcam_scanner_business_directory", 75
    if any(item in current_host for item in SOCIAL_HOST_HINTS):
        return "CAD-CAM/scanner public social company signal", "low", "public_social_signal", 92
    if re.search(r"authorized|authorised|official\s+partner|distributor|reseller|dealer", blob, re.I):
        return "Fetched public CAD-CAM/scanner reseller page", "low-medium", "fetched_public_reseller_page", 70
    return "Localized public CAD-CAM/scanner/milling search signal", "low-medium", "localized_public_search_cadcam_scanner", 84


def make_row(
    *,
    name: str,
    country: str,
    source_type: str,
    source_url: str,
    source_trust: str,
    source_family: str,
    acquisition_path: str,
    site_business_summary: str,
    segment: str,
    dof_fit: str,
    selection_reason: str,
    website: str = "",
    email: str = "",
    phone: str = "",
    address: str = "",
    evidence: list[str] | None = None,
    event: str = "",
    original_kind: str = "",
    product_context: str = "",
) -> dict[str, Any]:
    row = partial.make_row(
        name=name,
        country=country,
        source_type=source_type,
        source_url=source_url,
        source_trust=source_trust,
        source_family=source_family,
        acquisition_path=acquisition_path,
        site_business_summary=site_business_summary,
        website=website,
        email=email,
        phone=phone,
        address=address,
        evidence=evidence,
        event=event,
        original_kind=original_kind,
    )
    row["segment"] = segment
    row["dof_fit"] = dof_fit
    row["selection_reason"] = selection_reason
    row["tags"]["product_keywords"] = "구강스캐너, 랩스캐너, 덴탈 스캐너, 덴탈 밀링기, CAD/CAM, exocad, 3Shape TRIOS, Medit, Shining3D, vhf, DGSHAPE, imes-icore, Ceramill"
    if product_context:
        row["tags"]["product_context"] = clean(product_context)[:500]
    row["tags"]["contact_completeness"] = partial.contact_completeness(row)
    return row


def collect_vhf_resellers() -> list[partial.Candidate]:
    html = round11.fetch_html(VHF_RESELLERS, timeout=(5, 30))
    soup = BeautifulSoup(html, "html.parser")
    tags = soup.find_all(["h2", "h3", "p"])
    countries = set(COUNTRIES + ["Bolivia", "Ecuador", "Venezuela", "Dominican Republic", "El Salvador", "Guatemala", "Honduras", "Uruguay"])
    candidates: list[partial.Candidate] = []
    current_country = ""
    i = 0
    while i < len(tags):
        tag = tags[i]
        text = clean(tag.get_text(" ", strip=True))
        next_text = clean(tags[i + 1].get_text(" ", strip=True)) if i + 1 < len(tags) else ""
        if tag.name == "p" and text in countries and re.search(r"vhf reseller", next_text, re.I):
            current_country = text
            i += 2
            continue
        if tag.name == "h3" and current_country and text and text not in {"North and South America", "Europe and Russia", "Africa and Middle East", "Asia", "Australia and Oceania"}:
            name = text
            fields: list[str] = []
            j = i + 1
            while j < len(tags):
                if tags[j].name == "h3":
                    break
                value = clean(tags[j].get_text(" ", strip=True))
                next_value = clean(tags[j + 1].get_text(" ", strip=True)) if j + 1 < len(tags) else ""
                if value in countries and re.search(r"vhf reseller", next_value, re.I):
                    break
                if value:
                    fields.append(value)
                j += 1
            block = "\n".join(fields)
            email = (re.findall(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", block) or [""])[0]
            phone_match = re.search(r"(?:Phone|Tel[eé]fono|電話|電話番号|Tel|T)\s*:\s*([+()0-9 .\\/-]{7,40})", block, re.I)
            phone = clean(phone_match.group(1)) if phone_match else ""
            internet_match = re.search(r"(?:Internet|Website|Web)\s*:\s*([^\n ]+)", block, re.I)
            website = internet_match.group(1) if internet_match else ""
            address_lines = [line for line in fields if not re.search(r"^(Phone|Fax|Email|Internet|Tel|Correo electrónico)", line, re.I)]
            address = ", ".join(address_lines[:3])
            row = make_row(
                name=name,
                country=current_country,
                source_type="vhf official global dental milling reseller page",
                source_url=VHF_RESELLERS,
                source_trust="high",
                source_family="official_milling_machine_reseller_locator",
                acquisition_path="vhf 공식 dental reseller 페이지에서 국가별 밀링기 리셀러 이름, 주소, 전화, 이메일/웹사이트를 확인",
                site_business_summary="vhf dental milling and grinding machines 공식 sales partner/reseller",
                segment="Dental milling machine distributor / CAD-CAM reseller",
                dof_fit="Direct milling-machine distributor target for scanner/milling/CAD-CAM channel outreach",
                selection_reason="Vendor official reseller locator with contact fields; high-confidence milling-machine channel lead.",
                website=website,
                email=email,
                phone=phone,
                address=address,
                evidence=[f"vhf reseller country: {current_country}", f"Contact block: {clean(block)[:420]}"],
                event="vhf dental reseller locator",
                original_kind="round12_vhf_official_reseller_page",
                product_context="vhf dental milling and grinding machines",
            )
            partial.add_candidate(candidates, row, 8)
            i = j
            continue
        i += 1
    return candidates


def collect_exocad_ids_reseller_pdf() -> list[partial.Candidate]:
    pdf_path = DATA / "round12_exocad_IDS_Reseller_List_EN_web.pdf"
    if not pdf_path.exists():
        response = requests.get(EXOCAD_IDS_RESELLER_PDF, headers={"User-Agent": USER_AGENT}, timeout=(5, 30))
        response.raise_for_status()
        pdf_path.write_bytes(response.content)
    result = subprocess.run(["pdftotext", "-layout", str(pdf_path), "-"], check=True, capture_output=True, text=True, timeout=60)
    candidates: list[partial.Candidate] = []
    for raw_line in result.stdout.splitlines():
        line = clean(raw_line)
        if not line or line.startswith(("OUR RESELLERS", "NAME ", "View our")):
            continue
        match = re.match(r"(.+?)\s{2,}([A-Za-z0-9][A-Za-z0-9./_-]+\.[A-Za-z]{2,}[^\s]*)\s{2,}(.+)$", raw_line.rstrip())
        if not match:
            continue
        name, website, booth = [clean(part) for part in match.groups()]
        if not partial.is_usable_name(name):
            continue
        row = make_row(
            name=name,
            country="Germany",
            source_type="exocad official IDS 2025 reseller PDF",
            source_url=EXOCAD_IDS_RESELLER_PDF,
            source_trust="high",
            source_family="official_cadcam_reseller_pdf",
            acquisition_path="exocad 공식 IDS 2025 reseller PDF에서 파트너명, 웹사이트, 부스를 확인",
            site_business_summary="exocad가 IDS 2025 현장에서 공개한 CAD/CAM reseller/distribution partner",
            segment="Dental CAD-CAM software reseller / scanner workflow partner",
            dof_fit="exocad/CAD-CAM reseller lead for scanner and milling workflow channel outreach",
            selection_reason="Vendor official reseller PDF; high-confidence CAD/CAM channel lead.",
            website=website,
            evidence=[f"PDF row: {name} / {website} / {booth}"],
            event="exocad IDS 2025 reseller list",
            original_kind="round12_exocad_official_ids_reseller_pdf",
            product_context="exocad DentalCAD / ChairsideCAD reseller",
        )
        partial.add_candidate(candidates, row, 9)
    return candidates


def build_queries(max_searches: int) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for country in COUNTRIES:
        for term in TERMS:
            rows.append({"country": country, "query": f"{term} {country}"})
    for country in COUNTRIES[:45]:
        for site in SITE_PATTERNS[1:]:
            for term in TERMS[:18]:
                rows.append({"country": country, "query": f"{site} {term} {country}"})
    seen: set[str] = set()
    unique: list[dict[str, str]] = []
    for row in rows:
        key = row["query"].lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
        if len(unique) >= max_searches:
            break
    return unique


def fetch_page_detail(url: str, page_cache: dict[str, Any], timeout: int = 10) -> dict[str, str]:
    current_host = host(url)
    if not current_host or any(item in current_host for item in SOCIAL_HOST_HINTS):
        return {}
    with CACHE_LOCK:
        cached = page_cache.get(url)
    if isinstance(cached, dict):
        return cached
    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}, timeout=(4, timeout), allow_redirects=True)
        html = response.text[:900_000] if response.status_code < 400 and "text" in response.headers.get("content-type", "text/html") else ""
    except requests.RequestException as error:
        detail = {"ok": "false", "error": str(error)[:180]}
        with CACHE_LOCK:
            page_cache[url] = detail
        return detail
    soup = BeautifulSoup(html, "html.parser")
    title = clean(soup.title.get_text(" ", strip=True) if soup.title else "")
    meta = ""
    node = soup.select_one('meta[name="description"], meta[property="og:description"]')
    if node:
        meta = clean(node.get("content", ""))
    text = clean(soup.get_text(" ", strip=True))[:8000]
    email = (re.findall(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", html) or [""])[0]
    phone = ""
    phone_match = re.search(r"(?:Phone|Tel|T[eé]l|전화|電話|Contact)\s*[:.]?\s*([+()0-9 .\\/-]{8,35})", text, re.I)
    if phone_match:
        phone = clean(phone_match.group(1))
    detail = {"ok": "true", "title": title, "meta": meta, "text": text[:1800], "email": email, "phone": phone, "final_url": response.url}
    with CACHE_LOCK:
        page_cache[url] = detail
    return detail


def search_result_to_candidate(result: dict[str, str], page_cache: dict[str, Any], fetch_detail: bool) -> partial.Candidate | None:
    url = clean(result.get("url"))
    current_host = host(url)
    if not current_host or any(item in current_host for item in SKIP_HOST_HINTS):
        return None
    title = clean(result.get("title"))
    snippet = clean(result.get("snippet"))
    query = clean(result.get("query"))
    blob = " ".join([query, title, snippet, url])
    if not strong_target_text(blob) or GENERIC_RE.search(blob):
        return None
    detail: dict[str, str] = {}
    if fetch_detail:
        detail = fetch_page_detail(url, page_cache)
        detail_blob = " ".join([detail.get("title", ""), detail.get("meta", ""), detail.get("text", "")])
        if detail.get("ok") == "true" and TARGET_RE.search(detail_blob):
            blob = " ".join([blob, detail_blob[:1600]])
    name = infer_search_name(detail.get("title") or title, url)
    if not name or not partial.is_usable_name(name):
        return None
    source_type, trust, family, priority = source_meta_for_url(url, blob)
    segment = "Dental scanner / CAD-CAM / milling distributor lead"
    if re.search(r"lab|laboratory|milling center|dentallabor|laboratorio", blob, re.I):
        segment = "Dental lab / milling center scanner-CADCAM prospect"
    website = "" if any(item in current_host for item in SOCIAL_HOST_HINTS) else (detail.get("final_url") or url)
    row = make_row(
        name=name,
        country=clean(result.get("country")),
        source_type=source_type,
        source_url=url,
        source_trust=trust,
        source_family=family,
        acquisition_path="제조사명/제품군/현지어 CAD-CAM·구강스캐너·밀링기 검색 후 공개 페이지를 열어 제품/리셀러 문맥을 확인",
        site_business_summary=(detail.get("meta") or snippet or detail.get("text") or "CAD-CAM/scanner/milling product or reseller signal")[:500],
        segment=segment,
        dof_fit="Scanner, milling machine, CAD-CAM software/equipment channel or partner prospect",
        selection_reason="Targeted scanner/milling/CAD-CAM public web signal. Prioritize higher trust official/vendor pages before broad search snippets.",
        website=website,
        email=detail.get("email", ""),
        phone=detail.get("phone", ""),
        evidence=[
            f"Query: {query}",
            f"Search title: {title}",
            f"Snippet: {snippet[:260]}",
            f"Fetched title: {detail.get('title', '')[:180]}",
            f"Host: {current_host}",
        ],
        original_kind="round12_targeted_scanner_milling_cadcam_search",
        product_context=blob[:500],
    )
    return partial.Candidate(row=row, priority=priority)


def collect_search_candidates(
    *,
    search_cache: dict[str, Any],
    page_cache: dict[str, Any],
    max_searches: int,
    results_per_query: int,
    target_candidates: int,
    workers: int,
    fetch_details: int,
) -> tuple[list[partial.Candidate], int]:
    candidates: list[partial.Candidate] = []
    raw_rows: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    detail_budget = {"remaining": fetch_details}
    queries = build_queries(max_searches)
    executed = 0

    def run_query(query_row: dict[str, str]) -> list[dict[str, str]]:
        rows = round11.search_duckduckgo(query_row["query"], search_cache, results_per_query)
        return [{**row, "country": query_row["country"]} for row in rows]

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {executor.submit(run_query, row): row for row in queries}
        for future in concurrent.futures.as_completed(futures):
            executed += 1
            try:
                results = future.result()
            except Exception:
                results = []
            raw_rows.extend({"kind": "round12_search_result", **row} for row in results)
            for result in results:
                url = clean(result.get("url"))
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                fetch_detail = False
                if detail_budget["remaining"] > 0 and not any(item in host(url) for item in SOCIAL_HOST_HINTS):
                    fetch_detail = True
                    detail_budget["remaining"] -= 1
                candidate = search_result_to_candidate(result, page_cache, fetch_detail)
                if candidate:
                    candidates.append(candidate)
                    raw_rows.append({"kind": "round12_search_candidate", **candidate.row})
            if executed % 50 == 0:
                append_jsonl(SEARCH_RAW_JSONL, raw_rows)
                raw_rows = []
                save_json(SEARCH_CACHE_JSON, search_cache)
                save_json(PAGE_CACHE_JSON, page_cache)
                print(json.dumps({"search_completed": executed, "queries": len(queries), "candidates": len(candidates), "seen_urls": len(seen_urls)}, ensure_ascii=False), flush=True)
            if len(candidates) >= target_candidates:
                for pending in futures:
                    pending.cancel()
                break
    append_jsonl(SEARCH_RAW_JSONL, raw_rows)
    save_json(SEARCH_CACHE_JSON, search_cache)
    save_json(PAGE_CACHE_JSON, page_cache)
    return candidates, executed


def enrich_selected_details(rows: list[dict[str, Any]], page_cache: dict[str, Any], limit: int, workers: int) -> int:
    targets = [row for row in rows if clean(row.get("website")) and not any(item in host(clean(row.get("website"))) for item in SOCIAL_HOST_HINTS)]
    targets = targets[: max(0, limit)]
    if not targets:
        return 0

    def enrich(row: dict[str, Any]) -> bool:
        detail = fetch_page_detail(clean(row.get("website")), page_cache, timeout=10)
        if detail.get("ok") != "true":
            return False
        changed = False
        if detail.get("email") and not clean(row.get("email")):
            row["email"] = detail["email"]
            changed = True
        if detail.get("phone") and not clean(row.get("phone")):
            row["phone"] = detail["phone"]
            changed = True
        blob = " ".join([detail.get("title", ""), detail.get("meta", ""), detail.get("text", "")])
        if TARGET_RE.search(blob):
            evidence = row.setdefault("evidence", [])
            evidence.append(f"Fetched page confirms scanner/CAD-CAM/milling context: {clean(detail.get('title') or detail.get('meta'))[:240]}")
            row.setdefault("tags", {})["fetched_page_target_context"] = "true"
            changed = True
        row.setdefault("tags", {})["contact_completeness"] = partial.contact_completeness(row)
        return changed

    changed_count = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, min(workers, len(targets)))) as executor:
        futures = [executor.submit(enrich, row) for row in targets]
        for future in concurrent.futures.as_completed(futures):
            try:
                if future.result():
                    changed_count += 1
            except Exception:
                pass
    save_json(PAGE_CACHE_JSON, page_cache)
    return changed_count


def name_country_key(row: dict[str, Any]) -> str:
    name = clean(row.get("name")).lower()
    country = clean(row.get("country")).lower()
    return f"{name}|{country}" if name and country else ""


def unique_candidates(
    candidates: list[partial.Candidate],
    complete_rows: list[dict[str, Any]],
    existing_keys: set[str],
    publisher_keys: set[str],
    limit: int,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen_keys = set(existing_keys)
    seen_publisher_keys = set(publisher_keys)
    seen_name_country = {key for row in complete_rows if (key := name_country_key(row))}
    for candidate in sorted(candidates, key=lambda item: (item.priority, clean(item.row.get("country")), clean(item.row.get("name")).lower(), clean(item.row.get("source_url")))):
        row = candidate.row
        key = partial.row_business_key(row)
        pub_key = partial.publisher_dedupe_key(row)
        row_name_country = name_country_key(row)
        source_only = (row.get("tags") or {}).get("contact_completeness") == "source_only"
        if not key or key in seen_keys or pub_key in seen_publisher_keys:
            continue
        if source_only and row_name_country in seen_name_country:
            continue
        selected.append(row)
        seen_keys.add(key)
        seen_publisher_keys.add(pub_key)
        if row_name_country:
            seen_name_country.add(row_name_country)
        if len(selected) >= limit:
            break
    return selected


def write_summary(*, backup_path: Path | None, before_count: int, after_count: int, selected: list[dict[str, Any]], candidates: list[partial.Candidate], query_count: int, dry_run: bool) -> None:
    source_counts = Counter(row["source_type"] for row in selected)
    trust_counts = Counter((row.get("tags") or {}).get("source_trust", "") for row in selected)
    completeness_counts = Counter((row.get("tags") or {}).get("contact_completeness", "") for row in selected)
    country_counts = Counter(row.get("country") or "Unknown" for row in selected)
    segment_counts = Counter(row.get("segment") or "Unknown" for row in selected)
    lines = [
        "# Round 12 scanner/milling/CAD-CAM focused prospect expansion",
        "",
        "## Result",
        f"- Mode: {'dry-run' if dry_run else 'applied'}",
        f"- Baseline backup: `{backup_path}`" if backup_path else "- Baseline backup: not created in dry-run",
        f"- Complete dataset rows before: {before_count:,}",
        f"- Added rows this round: {len(selected):,}",
        f"- Complete dataset rows after: {after_count:,}",
        f"- Candidate pool before dedupe: {len(candidates):,}",
        f"- Targeted search queries executed/read from cache: {query_count:,}",
        "",
        "## Trust model",
        "- high: official vendor reseller locator/PDF with explicit scanner, milling, or CAD-CAM reseller context.",
        "- medium-high: official vendor/product/partner page, official exhibitor context, or fetched public page with direct authorized reseller language.",
        "- low-medium: localized public web/business-directory/search result with scanner, milling, CAD-CAM and channel terms.",
        "- low: Facebook/LinkedIn public company snippet only; use as lead seed, not verified contact ownership.",
        "",
        "## Added by segment",
    ]
    for label, count in segment_counts.most_common():
        lines.append(f"- {label}: {count:,}")
    lines += ["", "## Added by source"]
    for label, count in source_counts.most_common():
        lines.append(f"- {label}: {count:,}")
    lines += ["", "## Added by source trust"]
    for label, count in trust_counts.most_common():
        lines.append(f"- {label}: {count:,}")
    lines += ["", "## Added by contact completeness"]
    for label, count in completeness_counts.most_common():
        lines.append(f"- {label}: {count:,}")
    lines += ["", "## Top countries"]
    for label, count in country_counts.most_common(60):
        lines.append(f"- {label}: {count:,}")
    lines += [
        "",
        "## Direct source families used",
        f"- vhf official dental reseller locator: {VHF_RESELLERS}",
        f"- exocad official IDS 2025 reseller PDF: {EXOCAD_IDS_RESELLER_PDF}",
        "- Targeted localized search for Medit, Shining3D/Aoralscan, 3Shape/TRIOS, exocad, vhf, DGSHAPE/Roland, imes-icore/CORiTEC, Amann Girrbach/Ceramill, Zirkonzahn, Planmeca/CEREC/Carestream/iTero plus local distributor/dealer terms.",
        "",
        "## Notes",
        "- OSM was not used as an acquisition source in this round.",
        "- Existing rows were preserved. New rows were deduped against the current complete dataset by email, company+website, company+address, or company+country+source URL.",
        "- Search-derived rows are intentionally tagged lower trust than official locator/PDF rows. They should be filtered by `source_trust` and `contact_completeness` before outreach.",
        "- This round is intentionally more relevant to DOF scanner/CAD-CAM/milling channels than generic dental clinics.",
    ]
    SUMMARY_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-additional", type=int, default=3000)
    parser.add_argument("--max-searches", type=int, default=2200)
    parser.add_argument("--results-per-query", type=int, default=12)
    parser.add_argument("--search-workers", type=int, default=10)
    parser.add_argument("--fetch-details", type=int, default=900)
    parser.add_argument("--enrich-selected-details", type=int, default=500)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    complete_rows = partial.read_jsonl(COMPLETE_JSONL)
    before_count = len(complete_rows)
    if not args.dry_run and SEARCH_RAW_JSONL.exists():
        SEARCH_RAW_JSONL.unlink()
    existing_keys = {partial.row_business_key(row) for row in complete_rows if partial.row_business_key(row)}
    publisher_keys = {partial.publisher_dedupe_key(row) for row in complete_rows if partial.publisher_dedupe_key(row)}
    search_cache = load_json(SEARCH_CACHE_JSON, {})
    page_cache = load_json(PAGE_CACHE_JSON, {})
    candidates: list[partial.Candidate] = []

    for collector in (collect_vhf_resellers, collect_exocad_ids_reseller_pdf):
        try:
            collected = collector()
        except Exception as error:
            collected = []
            print(json.dumps({"collector": collector.__name__, "error": str(error)[:300]}, ensure_ascii=False), flush=True)
        candidates.extend(collected)
        print(json.dumps({"collector": collector.__name__, "candidates": len(collected)}, ensure_ascii=False), flush=True)

    search_candidates, query_count = collect_search_candidates(
        search_cache=search_cache,
        page_cache=page_cache,
        max_searches=args.max_searches,
        results_per_query=args.results_per_query,
        target_candidates=max(args.target_additional * 5, 4500),
        workers=args.search_workers,
        fetch_details=args.fetch_details,
    )
    candidates.extend(search_candidates)
    print(json.dumps({"collector": "targeted_scanner_milling_cadcam_search", "candidates": len(search_candidates), "query_count": query_count}, ensure_ascii=False), flush=True)

    selected = unique_candidates(candidates, complete_rows, existing_keys, publisher_keys, args.target_additional)
    detail_enriched = enrich_selected_details(selected, page_cache, args.enrich_selected_details, args.search_workers)
    after_count = before_count + len(selected)
    backup_path: Path | None = None
    if not args.dry_run:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        backup_path = BACKUP_DIR / f"prospects_augmented_contact_complete.before_partial_round12_{stamp}.jsonl"
        shutil.copy2(COMPLETE_JSONL, backup_path)
        complete_rows.extend(selected)
        partial.write_jsonl(COMPLETE_JSONL, complete_rows)
        partial.write_csv(COMPLETE_CSV, complete_rows)
        partial.write_jsonl(PROMOTIONS_JSONL, selected)

    write_summary(
        backup_path=backup_path,
        before_count=before_count,
        after_count=after_count,
        selected=selected,
        candidates=candidates,
        query_count=query_count,
        dry_run=args.dry_run,
    )
    result = {
        "dryRun": args.dry_run,
        "backup": str(backup_path) if backup_path else "",
        "beforeRows": before_count,
        "addedRows": len(selected),
        "afterRows": after_count,
        "summaryMd": str(SUMMARY_MD),
        "promotionsJsonl": str(PROMOTIONS_JSONL),
        "searchRawJsonl": str(SEARCH_RAW_JSONL),
        "queryCount": query_count,
        "candidatePool": len(candidates),
        "detailEnrichedRows": detail_enriched,
        "sourceCounts": dict(Counter(row["source_type"] for row in selected).most_common()),
        "trustCounts": dict(Counter((row.get("tags") or {}).get("source_trust", "") for row in selected).most_common()),
        "contactCompletenessCounts": dict(Counter((row.get("tags") or {}).get("contact_completeness", "") for row in selected).most_common()),
        "segmentCounts": dict(Counter(row.get("segment") or "" for row in selected).most_common()),
    }
    save_json(RESULT_JSON, result)
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
