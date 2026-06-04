#!/usr/bin/env python3
"""Round 11 non-OSM dental prospect expansion.

This round adds sources the earlier OSM-heavy and exhibition-heavy passes did
not emphasize enough: official dental-lab registry/API data, certification or
association style directories, country-language yellow pages, public social
signals, and dental press/blog snippets. Rows remain explicitly tagged by trust
and contact completeness because many sources expose only partial outreach data.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import shutil
import subprocess
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
import threading
from typing import Any
from urllib.parse import parse_qs, quote_plus, unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

import dof_partial_distributor_candidate_expansion as partial


ROOT = Path("/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04")
OUT_ROOT = ROOT / "output/dof-overseas-customer-prospects/2026-05-30/scale5000"
DATA = OUT_ROOT / "data"
BACKUP_DIR = DATA / "backups"
COMPLETE_JSONL = DATA / "prospects_augmented_contact_complete.jsonl"
COMPLETE_CSV = DATA / "prospects_augmented_contact_complete.csv"
PROMOTIONS_JSONL = DATA / "partial_distributor_promotions_round11.jsonl"
SEARCH_RAW_JSONL = DATA / "partial_distributor_search_raw_round11.jsonl"
SEARCH_CACHE_JSON = DATA / "partial_distributor_search_cache_round11.json"
SUMMARY_MD = OUT_ROOT / "external_partial_distributor_expansion_round11.md"
RESULT_JSON = OUT_ROOT / "external_partial_distributor_expansion_round11_result.json"

USER_AGENT = partial.USER_AGENT
CMS_NPI_API = "https://npiregistry.cms.hhs.gov/api/"
CACHE_LOCK = threading.Lock()

SEED_A2Z_EVENT_PAGES = [
    (
        "AAO Annual Meeting 2024",
        "https://s36.a2zinc.net/clients/aaortho/annual2024/public/EventMap.aspx",
        "United States",
    ),
    (
        "AAO Annual Meeting 2025",
        "https://s36.a2zinc.net/clients/aaortho/annual2025/Public/eventmap.aspx?MapID=10&MapItBooth=3202&MapItBoothID=114335",
        "United States",
    ),
    (
        "AAO Annual Meeting 2026",
        "https://s36.a2zinc.net/clients/aaortho/annual2026/Public/EventMap.aspx",
        "United States",
    ),
    (
        "AAO Winter Meeting 2025",
        "https://s36.a2zinc.net/clients/aaortho/wintermeeting2025/Public/eventmap.aspx?shmode=E",
        "United States",
    ),
    (
        "AAO Winter Meeting 2026",
        "https://s36.a2zinc.net/clients/aaortho/wintermeeting2026/Public/eventmap.aspx?shmode=E",
        "United States",
    ),
    (
        "Star of the North Meeting 2026",
        "https://s23.a2zinc.net/clients/MNDA/sotn26/Public/EventMap.aspx",
        "United States",
    ),
    (
        "Star of the North Meeting 2025",
        "https://s23.a2zinc.net/clients/mnda/sotn25/Public/eventmap.aspx",
        "United States",
    ),
    (
        "Thomas P. Hinman Dental Meeting 2024",
        "https://s36.a2zinc.net/clients/hdsa/hinman24/Public/EventMap.aspx?ID=1006",
        "United States",
    ),
    (
        "Thomas P. Hinman Dental Meeting 2025",
        "https://s36.a2zinc.net/clients/hdsa/hinman2025/public/EventMap.aspx",
        "United States",
    ),
    (
        "ADEA Annual Session & Exhibition 2024",
        "https://s36.a2zinc.net/clients/adea/adea2024/Public/EventMap.aspx",
        "United States",
    ),
    (
        "ADEA Annual Session & Exhibition 2025",
        "https://s36.a2zinc.net/clients/adea/adea2025/public/eventmap.aspx?shmode=E",
        "United States",
    ),
    (
        "SmileCon 2024",
        "https://s23.a2zinc.net/clients/corcexpo/SmileCon2024/Public/EventMap.aspx",
        "United States",
    ),
    (
        "Greater New York Dental Meeting 2024",
        "https://s19.a2zinc.net/clients/gnydm/gnydm/Public/EventMap.aspx?shMode=E",
        "United States",
    ),
]

DIRECT_PROBE_SOURCES = [
    "https://expositores.apcd.org.br/",
    "https://www.ciosp.com.br/expositores",
    "https://cda26.mapyourshow.com/8_0/explore/exhibitor-gallery.cfm?featured=false",
    "https://www.dentallabprofile.com/dental-lab-network.php",
]

SOCIAL_HOST_HINTS = ("facebook.com", "linkedin.com")
DIRECTORY_HOST_HINTS = (
    "yellowpages",
    "pagesjaunes",
    "paginasamarillas",
    "cylex",
    "cybo.com",
    "kompass",
    "europages",
    "businesslist",
    "yellow.place",
    "tuugo",
    "yell.com",
    "2gis",
    "findglocal",
    "hotfrog",
    "brownbook",
    "local.infobel",
)
MEDIA_HOST_HINTS = (
    "dental-tribune",
    "dentistry",
    "dentalnews",
    "dentalreview",
    "dentalworld",
    "dentaljournal",
    "magazine",
    "news",
)
OFFICIAL_HOST_HINTS = (
    ".gov",
    ".gob",
    ".gouv",
    ".go.",
    "cms.hhs.gov",
    "npiregistry.cms.hhs.gov",
    "german-pavilion.com",
    "ice.it",
    "trade.gov",
    "export.gov",
    "a2zinc.net",
    "mapyourshow.com",
    "smallworldlabs.com",
    "apcd.org.br",
)
SKIP_HOST_HINTS = (
    "duckduckgo.com",
    "google.",
    "bing.com",
    "openstreetmap.org",
    "wikipedia.org",
    "youtube.com",
    "instagram.com",
    "pinterest.",
    "reddit.com",
    "amazon.",
    "ebay.",
    "alibaba.",
    "made-in-china.com",
    "globalsources.com",
    "scribd.com",
    "visitorslist.com",
    "exhibitorsdata.com",
    "expocaptive.com",
    "marketresearch",
    "salary",
    "jobs.",
    "indeed.",
    "deltadental",
    "ada.org",
    "webmd.com",
    "medlineplus.gov",
    "ensun.io",
    "tradeford.com",
)

DENTAL_RE = re.compile(
    r"dental|dent[aeio]|odont|odontolog|orthodont|ortho|implant|zahn|stomat|口腔|牙科|歯科|"
    r"nha khoa|gigi|pergigian|diş|طب الأسنان|laboratorio dental|laboratório dent|laboratoire dentaire",
    re.I,
)
CHANNEL_RE = re.compile(
    r"distribut|supplier|supply|supplies|dealer|depot|trading|trade|import|export|equipment|material|"
    r"laborator|lab |dentalbedarf|dentalhandel|zahnbedarf|suministro|suministros|distribuidora|"
    r"dep[óo]sito|importadora|exportadora|equipamentos|materiais|fournisseur|fournitures|mat[ée]riel|"
    r"forniture|fornitore|malzemeleri|مستلزمات|تجهيزات|thiết bị|vật liệu|alat|bahan|器材|材料|"
    r"registry|register|certif|association|member|exhibitor",
    re.I,
)
GENERIC_RE = re.compile(
    r"\b(top|best|buy|find a dentist|insurance plans?|plans for individuals|provider directory|list of|directory|yellow pages|category|near me|jobs?|market report|attendees?|visitor list|"
    r"exhibitor list|companies in|suppliers in|distributors in|importers and buyers|database|catalogue|catalog|"
    r"events?|conference|course|training|agenda|program|programme|news list|blog list|article list|pdf)\b",
    re.I,
)
FOOTER_RE = re.compile(
    r"^(home|contact|about|privacy|terms|login|sign in|register|my exhibitors|floorplan|legend|print|help|"
    r"opening times|newsletter|events|sessions|products and services)$",
    re.I,
)


COUNTRY_GROUPS: list[dict[str, Any]] = [
    {
        "countries": [
            "Angola",
            "Benin",
            "Botswana",
            "Burkina Faso",
            "Cameroon",
            "Cote d'Ivoire",
            "Ethiopia",
            "Ghana",
            "Kenya",
            "Madagascar",
            "Mauritius",
            "Mozambique",
            "Namibia",
            "Nigeria",
            "Rwanda",
            "Senegal",
            "Somalia",
            "Tanzania",
            "Uganda",
            "Zambia",
            "Zimbabwe",
            "Morocco",
            "Algeria",
            "Tunisia",
            "Libya",
            "Egypt",
        ],
        "terms": [
            "dental equipment supplier",
            "dental supplies distributor",
            "dental import export",
            "dental laboratory supplier",
            "fournisseur dentaire",
            "matériel dentaire distributeur",
            "laboratoire dentaire fournisseur",
            "مستلزمات طب الأسنان موزع",
        ],
    },
    {
        "countries": [
            "Bolivia",
            "Costa Rica",
            "Dominican Republic",
            "Ecuador",
            "El Salvador",
            "Guatemala",
            "Honduras",
            "Nicaragua",
            "Panama",
            "Paraguay",
            "Uruguay",
            "Venezuela",
            "Colombia",
            "Peru",
            "Chile",
            "Argentina",
            "Brazil",
        ],
        "terms": [
            "distribuidora dental",
            "depósito dental",
            "suministros dentales",
            "equipos odontológicos",
            "importadora dental",
            "distribuidora odontológica",
            "laboratorio dental",
            "laboratório de prótese dentária",
            "equipamentos odontológicos distribuidor",
        ],
    },
    {
        "countries": [
            "Albania",
            "Bosnia and Herzegovina",
            "Bulgaria",
            "Croatia",
            "Kosovo",
            "Latvia",
            "Lithuania",
            "Malta",
            "Montenegro",
            "North Macedonia",
            "Romania",
            "Serbia",
            "Slovakia",
            "Slovenia",
            "Ukraine",
            "Georgia",
            "Azerbaijan",
            "Armenia",
            "Moldova",
            "Greece",
            "Cyprus",
        ],
        "terms": [
            "dental distributor",
            "dental equipment supplier",
            "dental depot",
            "dental import export",
            "dental laboratory",
            "Dentalbedarf Händler",
            "Dentalhandel",
            "forniture dentali distributore",
            "fournitures dentaires distributeur",
        ],
    },
    {
        "countries": [
            "Bahrain",
            "Iraq",
            "Jordan",
            "Kuwait",
            "Lebanon",
            "Oman",
            "Qatar",
            "Saudi Arabia",
            "United Arab Emirates",
            "Yemen",
            "Palestine",
            "Turkey",
            "Iran",
        ],
        "terms": [
            "dental distributor",
            "dental equipment supplier",
            "dental import export",
            "dental laboratory supplier",
            "مستلزمات طب الأسنان موزع",
            "تجهيزات طب الأسنان",
            "مختبر أسنان",
            "diş malzemeleri distribütör",
            "dental depo",
        ],
    },
    {
        "countries": [
            "Bangladesh",
            "Cambodia",
            "Laos",
            "Malaysia",
            "Myanmar",
            "Nepal",
            "Pakistan",
            "Philippines",
            "Singapore",
            "Sri Lanka",
            "Thailand",
            "Timor-Leste",
            "Vietnam",
            "Indonesia",
        ],
        "terms": [
            "dental distributor",
            "dental equipment supplier",
            "dental import export",
            "dental laboratory",
            "thiết bị nha khoa nhà phân phối",
            "phòng lab nha khoa",
            "alat kedokteran gigi distributor",
            "laboratorium gigi",
            "bahan pergigian pembekal",
            "牙科器材 代理商",
        ],
    },
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


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as file_obj:
        for row in rows:
            file_obj.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    tmp.replace(path)


def host(value: str) -> str:
    try:
        return (urlparse(value).hostname or "").lower().removeprefix("www.")
    except Exception:
        return ""


def result_url(href: str) -> str:
    href = clean(href)
    if not href:
        return ""
    if "duckduckgo.com/l/" in href:
        parsed = urlparse(href)
        href = unquote(parse_qs(parsed.query).get("uddg", [""])[0])
    if "bing.com/ck/" in href:
        parsed = urlparse(href)
        encoded = parse_qs(parsed.query).get("u", [""])[0]
        if encoded.startswith("a1"):
            try:
                import base64

                href = base64.urlsafe_b64decode(encoded[2:] + "==").decode("utf-8", errors="ignore")
            except Exception:
                href = ""
    if "r.search.yahoo.com" in href:
        match = re.search(r"/RU=([^/]+)/", href)
        href = unquote(match.group(1)) if match else ""
    if href.startswith("//"):
        href = "https:" + href
    return href if href.startswith(("http://", "https://")) else ""


def fetch_html(url: str, *, verify: bool = True, timeout: tuple[int, int] = (5, 18)) -> str:
    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout, allow_redirects=True, verify=verify)
    except requests.RequestException:
        return ""
    if response.status_code >= 400:
        return ""
    return response.text


def is_usable_listing_name(value: str) -> bool:
    name = clean(value).strip(" -*•:")
    if not partial.is_usable_name(name):
        return False
    if GENERIC_RE.search(name) or FOOTER_RE.search(name):
        return False
    if re.fullmatch(r"[A-Z#]|\d{1,5}|[A-Z]{1,3}-?\d{1,5}", name):
        return False
    if len(name.split()) > 14:
        return False
    return True


def clean_listing_name(value: str) -> str:
    name = clean(value)
    name = re.sub(r"\s+[-|–]\s+(Facebook|LinkedIn|Instagram|X|Kompass|Cybo|Cylex|Europages|Yellow Pages|BusinessList).*$", "", name, flags=re.I)
    if "|" in name:
        parts = [clean(part) for part in name.split("|") if clean(part)]
        if parts and re.search(r"\b(top|best|buy|directory|suppliers?|exporters?|equipment in|plans?)\b", parts[0], re.I):
            name = parts[-1]
        elif parts:
            name = parts[0]
    name = re.sub(r"^[a-z0-9][\w.-]*\.[a-z]{2,}\s+(?:https?://\S+(?:\s+›\s+\S+)*\s+)?", "", name, flags=re.I)
    name = re.sub(r"\s+[-–]\s+(?:Dental Equipment|Dental Supplies|Dental Products|Dental Laboratory|Home|Official Site).*$", "", name, flags=re.I)
    name = re.sub(r"^(Company Profile\s*[-:]\s*)", "", name, flags=re.I)
    name = clean(name.strip(" -:;,."))
    return name if is_usable_listing_name(name) else ""


def add_candidate(candidates: list[partial.Candidate], row: dict[str, Any], priority: int) -> None:
    partial.add_candidate(candidates, row, priority)


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
    return row


def name_country_key(row: dict[str, Any]) -> str:
    name = clean(row.get("name")).lower()
    country = clean(row.get("country")).lower()
    return f"{name}|{country}" if name and country else ""


def unique_round11_candidates(
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
    for candidate in sorted(candidates, key=lambda item: (item.priority, clean(item.row.get("country")), clean(item.row.get("name")).lower())):
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


def format_npi_address(address: dict[str, Any]) -> str:
    parts = [
        clean(address.get("address_1")),
        clean(address.get("address_2")),
        clean(address.get("city")),
        clean(address.get("state")),
        clean(address.get("postal_code")),
    ]
    return clean(", ".join(part for part in parts if part))


def collect_cms_npi_dental_labs(max_rows: int) -> list[partial.Candidate]:
    candidates: list[partial.Candidate] = []
    seen_npi: set[str] = set()
    for skip in range(0, max_rows + 200, 200):
        params = {
            "version": "2.1",
            "taxonomy_description": "Dental Laboratory",
            "enumeration_type": "NPI-2",
            "limit": 200,
            "skip": skip,
        }
        try:
            response = requests.get(CMS_NPI_API, params=params, headers={"User-Agent": USER_AGENT}, timeout=(5, 30))
            data = response.json() if response.status_code < 400 else {}
        except Exception:
            break
        results = data.get("results") if isinstance(data, dict) else None
        if not results:
            break
        for item in results:
            npi = clean(item.get("number"))
            if not npi or npi in seen_npi:
                continue
            seen_npi.add(npi)
            basic = item.get("basic") or {}
            name = clean(basic.get("organization_name"))
            if not is_usable_listing_name(name):
                continue
            addresses = item.get("addresses") or []
            location = next((address for address in addresses if address.get("address_purpose") == "LOCATION"), addresses[0] if addresses else {})
            country = clean(location.get("country_name")) or "United States"
            phone = clean(location.get("telephone_number")) or clean(basic.get("authorized_official_telephone_number"))
            address = format_npi_address(location)
            source_url = f"https://npiregistry.cms.hhs.gov/provider-view/{npi}"
            taxonomy_desc = "; ".join(clean(tax.get("desc")) for tax in item.get("taxonomies") or [] if clean(tax.get("desc")))
            row = make_row(
                name=name,
                country=country,
                source_type="CMS NPI Registry official Dental Laboratory organization API",
                source_url=source_url,
                source_trust="high",
                source_family="government_health_provider_registry_api",
                acquisition_path="미국 CMS NPI Registry API에서 Dental Laboratory taxonomy의 organization NPI, 위치 주소, 전화, 등록일을 확인",
                site_business_summary=f"CMS NPI 공식 등록 조직. Taxonomy: {taxonomy_desc or 'Dental Laboratory'}",
                segment="Dental laboratory / certified lab prospect",
                dof_fit="Dental lab prospect for scanner, CAD/CAM, model design, and lab-service partnership",
                selection_reason="Official registry row for a dental laboratory organization. Treat as high-confidence identity/contact, but validate commercial fit before distributor outreach.",
                phone=phone,
                address=address,
                evidence=[
                    f"NPI: {npi}",
                    f"Enumeration date: {clean(basic.get('enumeration_date')) or 'not shown'}",
                    f"Last updated: {clean(basic.get('last_updated')) or 'not shown'}",
                    f"Taxonomy: {taxonomy_desc or 'Dental Laboratory'}",
                ],
                event="CMS NPI Registry Dental Laboratory taxonomy",
                original_kind="round11_cms_npi_dental_laboratory_api",
            )
            add_candidate(candidates, row, 12)
            if len(candidates) >= max_rows:
                return candidates
        if len(results) < 200:
            break
        time.sleep(0.05)
    return candidates


def collect_cms_npi_taxonomy_organizations(max_rows: int, taxonomy_description: str, source_label: str, original_kind: str, priority: int) -> list[partial.Candidate]:
    candidates: list[partial.Candidate] = []
    seen_npi: set[str] = set()
    for skip in range(0, max_rows + 200, 200):
        params = {
            "version": "2.1",
            "taxonomy_description": taxonomy_description,
            "enumeration_type": "NPI-2",
            "limit": 200,
            "skip": skip,
        }
        try:
            response = requests.get(CMS_NPI_API, params=params, headers={"User-Agent": USER_AGENT}, timeout=(5, 30))
            data = response.json() if response.status_code < 400 else {}
        except Exception:
            break
        results = data.get("results") if isinstance(data, dict) else None
        if not results:
            break
        for item in results:
            npi = clean(item.get("number"))
            if not npi or npi in seen_npi:
                continue
            seen_npi.add(npi)
            basic = item.get("basic") or {}
            name = clean(basic.get("organization_name"))
            if not is_usable_listing_name(name):
                continue
            taxonomies = item.get("taxonomies") or []
            taxonomy_desc = "; ".join(clean(tax.get("desc")) for tax in taxonomies if clean(tax.get("desc")))
            if not re.search(r"dental|dentist|orthodont|oral|clinic/center", taxonomy_desc, re.I):
                continue
            addresses = item.get("addresses") or []
            location = next((address for address in addresses if address.get("address_purpose") == "LOCATION"), addresses[0] if addresses else {})
            country = clean(location.get("country_name")) or "United States"
            phone = clean(location.get("telephone_number")) or clean(basic.get("authorized_official_telephone_number"))
            address = format_npi_address(location)
            source_url = f"https://npiregistry.cms.hhs.gov/provider-view/{npi}"
            row = make_row(
                name=name,
                country=country,
                source_type=f"CMS NPI Registry official {source_label} organization API",
                source_url=source_url,
                source_trust="high",
                source_family="government_health_provider_registry_api",
                acquisition_path=f"미국 CMS NPI Registry API에서 {taxonomy_description} taxonomy의 organization NPI, 위치 주소, 전화, 등록일을 확인",
                site_business_summary=f"CMS NPI 공식 등록 치과 관련 조직. Taxonomy: {taxonomy_desc or taxonomy_description}",
                segment="Dental clinic / official registry prospect",
                dof_fit="Dental clinic prospect for scanner, CAD/CAM workflow, and digital dentistry outreach",
                selection_reason="Official registry row for a dental-related organization. It is categorized separately from distributors/labs and should be triaged for clinic outreach.",
                phone=phone,
                address=address,
                evidence=[
                    f"NPI: {npi}",
                    f"Enumeration date: {clean(basic.get('enumeration_date')) or 'not shown'}",
                    f"Last updated: {clean(basic.get('last_updated')) or 'not shown'}",
                    f"Taxonomy: {taxonomy_desc or 'Dental'}",
                ],
                event=f"CMS NPI Registry {taxonomy_description} organization taxonomy",
                original_kind=original_kind,
            )
            add_candidate(candidates, row, priority)
            if len(candidates) >= max_rows:
                return candidates
        if len(results) < 200:
            break
        time.sleep(0.05)
    return candidates


def collect_cms_npi_dental_organizations(max_rows: int) -> list[partial.Candidate]:
    return collect_cms_npi_taxonomy_organizations(
        max_rows=max_rows,
        taxonomy_description="Dental",
        source_label="Dental",
        original_kind="round11_cms_npi_dental_organization_api",
        priority=42,
    )


def collect_cms_npi_dentist_organizations(max_rows: int) -> list[partial.Candidate]:
    return collect_cms_npi_taxonomy_organizations(
        max_rows=max_rows,
        taxonomy_description="Dentist",
        source_label="Dentist",
        original_kind="round11_cms_npi_dentist_organization_api",
        priority=44,
    )


def search_duckduckgo(query: str, cache: dict[str, Any], limit: int) -> list[dict[str, str]]:
    yahoo_rows = search_yahoo(query, cache, limit)
    if yahoo_rows:
        return yahoo_rows[:limit]
    bing_rows = search_bing(query, cache, limit)
    if bing_rows:
        return bing_rows[:limit]
    cache_key = f"duckduckgo:{query}"
    with CACHE_LOCK:
        cached = cache.get(cache_key)
    if isinstance(cached, list) and cached:
        return cached[:limit]
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    try:
        result = subprocess.run(
            ["curl", "-L", "--silent", "--show-error", "--max-time", "12", "--connect-timeout", "4", "-A", USER_AGENT, url],
            capture_output=True,
            timeout=15,
        )
        html = result.stdout.decode("utf-8", errors="ignore") if result.returncode == 0 else ""
    except Exception:
        html = ""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for item in soup.select(".result"):
        link = item.select_one("a.result__a")
        if not link:
            continue
        href = result_url(link.get("href", ""))
        if not href:
            continue
        snippet = clean(" ".join(node.get_text(" ", strip=True) for node in item.select(".result__snippet")))
        rows.append({"engine": "duckduckgo", "query": query, "title": clean(link.get_text(" ", strip=True)), "url": href, "snippet": snippet})
        if len(rows) >= limit:
            break
    with CACHE_LOCK:
        cache[cache_key] = rows
    return rows


def search_yahoo(query: str, cache: dict[str, Any], limit: int) -> list[dict[str, str]]:
    cache_key = f"yahoo:{query}"
    with CACHE_LOCK:
        cached = cache.get(cache_key)
    if isinstance(cached, list):
        return cached[:limit]
    url = f"https://search.yahoo.com/search?p={quote_plus(query)}"
    try:
        response = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en;q=0.9"},
            timeout=(4, 14),
        )
        html = response.text if response.status_code < 400 else ""
    except requests.RequestException:
        html = ""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for item in soup.select("div.algo"):
        link = item.select_one("a[href]")
        if not link:
            continue
        href = result_url(link.get("href", ""))
        if not href:
            continue
        snippet_node = item.select_one(".compText") or item.select_one("p")
        snippet = clean(snippet_node.get_text(" ", strip=True) if snippet_node else "")
        title = clean(link.get_text(" ", strip=True))
        rows.append({"engine": "yahoo", "query": query, "title": title, "url": href, "snippet": snippet})
        if len(rows) >= limit:
            break
    with CACHE_LOCK:
        cache[cache_key] = rows
    return rows[:limit]


def search_bing(query: str, cache: dict[str, Any], limit: int) -> list[dict[str, str]]:
    cache_key = f"bing:{query}"
    with CACHE_LOCK:
        cached = cache.get(cache_key)
    if isinstance(cached, list):
        return cached[:limit]
    url = f"https://www.bing.com/search?cc=us&setlang=en-US&q={quote_plus(query)}"
    try:
        response = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en;q=0.9"},
            timeout=(4, 14),
        )
        html = response.text if response.status_code < 400 else ""
    except requests.RequestException:
        html = ""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for item in soup.select("li.b_algo"):
        link = item.select_one("h2 a[href]") or item.select_one("a[href]")
        if not link:
            continue
        href = result_url(link.get("href", ""))
        if not href:
            continue
        snippet_node = item.select_one("p")
        snippet = clean(snippet_node.get_text(" ", strip=True) if snippet_node else "")
        rows.append({"engine": "bing", "query": query, "title": clean(link.get_text(" ", strip=True)), "url": href, "snippet": snippet})
        if len(rows) >= limit:
            break
    with CACHE_LOCK:
        cache[cache_key] = rows
    return rows[:limit]


def discover_a2z_pages(cache: dict[str, Any], max_pages: int) -> list[tuple[str, str, str]]:
    discovered = list(SEED_A2Z_EVENT_PAGES)
    queries = [
        'site:a2zinc.net/clients dental 2026 "Event Map"',
        'site:a2zinc.net/clients "Dental" "EventMap.aspx"',
        'site:a2zinc.net/clients "orthodontic" "EventMap.aspx"',
        'site:a2zinc.net/clients "dental" "Public/EventMap.aspx"',
    ]
    seen_urls = {url.lower().split("#", 1)[0] for _event, url, _country in discovered}
    for query in queries:
        for result in search_duckduckgo(query, cache, 20):
            url = clean(result.get("url")).split("#", 1)[0]
            if "a2zinc.net" not in url or "eventmap" not in url.lower():
                continue
            key = url.lower()
            if key in seen_urls:
                continue
            title = clean_listing_name(result.get("title")) or "A2Z dental event"
            discovered.append((title, url, "United States"))
            seen_urls.add(key)
            if len(discovered) >= max_pages:
                return discovered
    return discovered[:max_pages]


def collect_a2z_event_page(event: str, url: str, country: str) -> list[partial.Candidate]:
    html = fetch_html(url)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    page_title = clean(soup.title.get_text(" ", strip=True) if soup.title else "") or event
    event_check = page_title if event == "A2Z dental event" else f"{event} {page_title}"
    if not re.search(r"dental|orthodont|dentistry|AAO|ADEA|Hinman|SmileCon|GNYDM|Yankee|Star of the North", event_check, re.I):
        return []
    candidates: list[partial.Candidate] = []
    seen: set[str] = set()
    for row in soup.select("table tr"):
        cells = [clean(cell.get_text(" ", strip=True)) for cell in row.find_all(["td", "th"])]
        cells = [cell for cell in cells if cell]
        if len(cells) < 2:
            continue
        name = clean_listing_name(cells[0])
        booth = clean(cells[1])
        if not name or not re.fullmatch(r"\*?[A-Z]{0,4}-?\d{1,5}[A-Z]?|\d{1,5}[A-Z]?", booth):
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        row_obj = make_row(
            name=name.lstrip("*"),
            country=country,
            source_type=f"{page_title} official A2Z exhibitor/event map table",
            source_url=url,
            source_trust="medium-high",
            source_family="official_exhibition_floorplan_or_exhibitor_table",
            acquisition_path=f"{page_title} 공식 A2Z event map의 EXHIBITOR NAME/Booth table에서 업체명과 booth를 확인",
            site_business_summary=f"{page_title} 공식 전시자/플로어플랜에 등재된 치과·교정·장비·서비스 벤더 후보",
            segment="Dental exhibition vendor / distributor prospect",
            dof_fit="Channel sales, scanner resale, orthodontic/dental equipment distribution, and event-based partner outreach",
            selection_reason="Official dental/orthodontic event exhibitor identity. Contact details may be incomplete; use source URL and event booth as verification evidence.",
            evidence=[f"Official A2Z table row: {name} / booth {booth}", f"Source page: {url}"],
            event=page_title,
            original_kind="round11_a2z_official_event_map_table",
        )
        add_candidate(candidates, row_obj, 28)
    return candidates


def discover_german_pavilion_pages(cache: dict[str, Any], max_pages: int) -> list[tuple[str, str]]:
    queries = [
        'site:german-pavilion.com/en dental 2026 German Pavilion exhibitor',
        'site:german-pavilion.com/en "Sino-Dental" "German Pavilion"',
        'site:german-pavilion.com/en "IDEM" "German Pavilion" dental',
        'site:german-pavilion.com/en "CIOSP" "German Pavilion" dental',
        'site:german-pavilion.com/en "AEEDC" "German Pavilion"',
    ]
    pages: list[tuple[str, str]] = []
    seen: set[str] = set()
    for query in queries:
        for result in search_duckduckgo(query, cache, 12):
            url = clean(result.get("url")).split("#", 1)[0]
            if "german-pavilion.com" not in url or "/en/" not in url:
                continue
            if any(skip in url for skip in ("/sites/exhibitors/", "/imprint", "/privacy")):
                continue
            key = url.lower().rstrip("/")
            if key in seen:
                continue
            title = clean_listing_name(result.get("title")) or clean(url.rsplit("/", 1)[-1]).replace("-", " ").title()
            pages.append((title, url))
            seen.add(key)
            if len(pages) >= max_pages:
                return pages
    return pages


def collect_german_pavilion_page(event: str, url: str) -> list[partial.Candidate]:
    html = fetch_html(url)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[partial.Candidate] = []
    seen: set[str] = set()
    for link in soup.find_all("a", href=True):
        href = clean(link.get("href"))
        if "/sites/exhibitors/" not in href:
            continue
        name = clean_listing_name(link.get_text(" ", strip=True))
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        profile_url = urljoin(url, href)
        row = make_row(
            name=name,
            country="Germany",
            source_type=f"{event} official German Pavilion exhibitor profile link",
            source_url=profile_url,
            source_trust="high",
            source_family="government_trade_pavilion_exhibitor_page",
            acquisition_path=f"German Pavilion 공식 페이지에서 독일 치과/의료 장비 참가사 profile link를 확인",
            site_business_summary=f"{event} German Pavilion에 등재된 독일 치과 장비·재료·디지털 덴탈 수출/전시 참가사",
            segment="Dental exhibition vendor / exporter prospect",
            dof_fit="Export partner, channel sales, scanner resale, and international distributor research",
            selection_reason="Government-backed trade pavilion exhibitor signal. Treat as high-confidence identity, then validate dental category on the profile before outreach.",
            website=profile_url,
            evidence=[f"German Pavilion exhibitor profile link: {name}", f"Source page: {url}"],
            event=event,
            original_kind="round11_german_pavilion_discovered_profile",
        )
        add_candidate(candidates, row, 18)
    return candidates


def source_trust_for_search_url(url: str) -> tuple[str, str, str, int]:
    current_host = host(url)
    if any(item in current_host for item in SOCIAL_HOST_HINTS):
        return "Facebook/LinkedIn public dental company signal", "low", "public_social_signal", 90
    if any(item in current_host for item in OFFICIAL_HOST_HINTS):
        return "Official/association/exhibition public dental registry or exhibitor signal", "medium-high", "official_or_association_public_page", 38
    if any(item in current_host for item in DIRECTORY_HOST_HINTS):
        return "Localized yellow-page/business-directory dental distributor or lab signal", "low-medium", "localized_yellow_page_or_business_directory", 74
    if any(item in current_host for item in MEDIA_HOST_HINTS):
        return "Dental press/blog public company mention", "low-medium", "dental_press_or_blog_company_signal", 82
    return "Localized public web dental distributor/lab/import-export signal", "low-medium", "localized_search_public_web", 84


def build_localized_queries(max_searches: int) -> list[dict[str, str]]:
    if max_searches <= 0:
        return []
    general_queries: list[dict[str, str]] = []
    site_queries: list[dict[str, str]] = []
    site_patterns = [
        "",
        "site:kompass.com",
        "site:cybo.com",
        "site:europages",
        "site:cylex",
        "site:businesslist",
        "site:yellow.place",
        "site:facebook.com",
        "site:linkedin.com/company",
        "site:dental-tribune.com",
    ]
    suffixes = ["", "contact", "email", "company", "yellow pages", "business directory", "association", "registry"]
    for group in COUNTRY_GROUPS:
        for country in group["countries"]:
            for term in group["terms"]:
                for suffix in suffixes[:5]:
                    general_queries.append({"country": country, "query": clean(f"{term} {country} {suffix}")})
                for site in site_patterns[1:]:
                    site_queries.append({"country": country, "query": clean(f"{site} {term} {country}")})
    queries = general_queries + site_queries
    seen: set[str] = set()
    unique: list[dict[str, str]] = []
    for row in queries:
        key = row["query"].lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
        if len(unique) >= max_searches:
            break
    return unique


def search_result_to_candidate(row: dict[str, str]) -> partial.Candidate | None:
    url = clean(row.get("url"))
    current_host = host(url)
    if not current_host or any(item in current_host for item in SKIP_HOST_HINTS):
        return None
    title = clean(row.get("title"))
    snippet = clean(row.get("snippet"))
    blob = " ".join([title, snippet, url])
    if not DENTAL_RE.search(blob):
        return None
    commercial_equipment_signal = bool(
        re.search(r"equipment|supplies|materials?|products?|loja|produtos|instrument|lab(?:oratory)?|cad.?cam|scanner|implant|orthodontic", blob, re.I)
    )
    if not CHANNEL_RE.search(blob) and not commercial_equipment_signal:
        return None
    if re.search(r"dentist near me|find a dentist|dental insurance|dental plans|patient portal|appointment|clinic reviews?", blob, re.I):
        return None
    name = clean_listing_name(title)
    if not name:
        return None
    source_type, trust, family, priority = source_trust_for_search_url(url)
    is_lab = bool(re.search(r"laborator|lab |laboratorio|laboratório|laboratoire|registry|register|certif", blob, re.I))
    segment = "Dental laboratory / certified lab prospect" if is_lab else "Dental distributor / product supplier"
    row_obj = make_row(
        name=name,
        country=clean(row.get("country")),
        source_type=source_type,
        source_url=url,
        source_trust=trust,
        source_family=family,
        acquisition_path=(
            "현지어/영어 DuckDuckGo HTML 검색 결과에서 치과 유통·수출입·치기공소·인증/협회·언론 노출 문맥을 확인. "
            "SNS와 언론 snippet은 회사 신호로만 사용하고 낮은 신뢰도로 표기"
        ),
        site_business_summary=snippet[:420] or "치과 유통·공급·수출입·치기공소 키워드가 공개 웹 결과에 노출된 후보",
        segment=segment,
        dof_fit=(
            "Dental lab prospect for scanner/CAD-CAM/lab workflow outreach"
            if is_lab
            else "Channel sales, scanner resale, equipment distribution, local service partnership"
        ),
        selection_reason=(
            "Public search signal. Use as low/medium-confidence lead seed until official site/contact page is manually verified."
        ),
        website="" if any(item in current_host for item in SOCIAL_HOST_HINTS) else url,
        evidence=[
            f"Query: {clean(row.get('query'))}",
            f"Search title: {title}",
            f"Snippet: {snippet[:260]}",
            f"Host: {current_host}",
        ],
        original_kind="round11_duckduckgo_localized_public_search_result",
    )
    return partial.Candidate(row=row_obj, priority=priority)


def collect_localized_search_candidates(
    *,
    cache: dict[str, Any],
    max_searches: int,
    results_per_query: int,
    target_candidates: int,
    pause: float,
    workers: int,
) -> tuple[list[partial.Candidate], int]:
    candidates: list[partial.Candidate] = []
    raw_rows: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    queries = build_localized_queries(max_searches)
    executed = 0

    def run_query(query_row: dict[str, str]) -> list[dict[str, str]]:
        if pause > 0:
            time.sleep(pause)
        results = search_duckduckgo(query_row["query"], cache, results_per_query)
        return [{**result, "country": query_row["country"]} for result in results]

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        future_to_query = {executor.submit(run_query, query_row): query_row for query_row in queries}
        for future in concurrent.futures.as_completed(future_to_query):
            executed += 1
            try:
                enriched = future.result()
            except Exception:
                enriched = []
            raw_rows.extend({"kind": "round11_search_result", **result} for result in enriched)
            for result in enriched:
                url = clean(result.get("url"))
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                candidate = search_result_to_candidate(result)
                if candidate:
                    candidates.append(candidate)
                    raw_rows.append({"kind": "round11_search_candidate", **candidate.row})
            if executed % 50 == 0:
                append_jsonl(SEARCH_RAW_JSONL, raw_rows)
                raw_rows = []
                save_json(SEARCH_CACHE_JSON, cache)
                print(json.dumps({"search_completed": executed, "queries": len(queries), "candidates": len(candidates), "seen_urls": len(seen_urls)}, ensure_ascii=False), flush=True)
            if len(candidates) >= target_candidates:
                for pending in future_to_query:
                    pending.cancel()
                break
    append_jsonl(SEARCH_RAW_JSONL, raw_rows)
    save_json(SEARCH_CACHE_JSON, cache)
    return candidates, executed


def probe_direct_sources() -> list[dict[str, Any]]:
    probes: list[dict[str, Any]] = []
    for url in DIRECT_PROBE_SOURCES:
        started = time.time()
        verify = "ciosp.com.br" not in url and "apcd.org.br" not in url
        html = fetch_html(url, verify=verify, timeout=(4, 12))
        status = "ok" if html else "unusable"
        note = ""
        if "expositores.apcd.org.br" in url and html:
            note = "Public Vue app opened, but exhibitor area is restricted/login-oriented; no public company list endpoint used."
        elif "ciosp.com.br" in url and html:
            note = "CIOSP page opened with TLS verification disabled; public page points to exhibitor area/login rather than a public vendor list."
        elif "mapyourshow.com" in url and html:
            note = "MapYourShow gallery page opened, but JSON remote-proxy returns 403 without browser session; not used as direct source."
        elif "dentallabprofile.com" in url:
            note = "Connection timed out during live probe; use only search snippets if encountered."
        probes.append({"url": url, "status": status, "elapsedSeconds": round(time.time() - started, 2), "note": note})
    return probes


def write_summary(
    *,
    backup_path: Path | None,
    before_count: int,
    after_count: int,
    selected: list[dict[str, Any]],
    candidates: list[partial.Candidate],
    query_count: int,
    direct_probes: list[dict[str, Any]],
    dry_run: bool,
) -> None:
    source_counts = Counter(row["source_type"] for row in selected)
    trust_counts = Counter((row.get("tags") or {}).get("source_trust", "") for row in selected)
    completeness_counts = Counter((row.get("tags") or {}).get("contact_completeness", "") for row in selected)
    country_counts = Counter(row.get("country") or "Unknown" for row in selected)
    segment_counts = Counter(row.get("segment") or "Unknown" for row in selected)
    lines = [
        "# Round 11 non-OSM dental lab registry, exhibition, directory, media expansion",
        "",
        "## Result",
        f"- Mode: {'dry-run' if dry_run else 'applied'}",
        f"- Baseline backup: `{backup_path}`" if backup_path else "- Baseline backup: not created in dry-run",
        f"- Complete dataset rows before: {before_count:,}",
        f"- Added rows this round: {len(selected):,}",
        f"- Complete dataset rows after: {after_count:,}",
        f"- Candidate pool before dedupe: {len(candidates):,}",
        f"- DuckDuckGo HTML queries executed/read from cache: {query_count:,}",
        "",
        "## Trust model",
        "- high: official government/health provider registry API or government-backed trade pavilion profile.",
        "- medium-high: official exhibition/event map table, association or certification-style public page.",
        "- low-medium: localized yellow-page/business-directory/search snippet, dental media/blog mention, or public supplier profile with incomplete contact data.",
        "- low: Facebook/LinkedIn public title/snippet only. Use as a lead signal, not verified contact data.",
        "",
        "## Added by segment",
    ]
    for segment, count in segment_counts.most_common():
        lines.append(f"- {segment}: {count:,}")
    lines += ["", "## Added by source"]
    for source, count in source_counts.most_common():
        lines.append(f"- {source}: {count:,}")
    lines += ["", "## Added by source trust"]
    for trust, count in trust_counts.most_common():
        lines.append(f"- {trust}: {count:,}")
    lines += ["", "## Added by contact completeness"]
    for completeness, count in completeness_counts.most_common():
        lines.append(f"- {completeness}: {count:,}")
    lines += ["", "## Top countries"]
    for country, count in country_counts.most_common(50):
        lines.append(f"- {country}: {count:,}")
    lines += [
        "",
        "## Direct source families used",
        f"- CMS NPI Registry API: {CMS_NPI_API} with `taxonomy_description=Dental Laboratory`, `Dental`, and `Dentist`, all limited to `enumeration_type=NPI-2` organizations.",
        "- A2Z official dental/orthodontic event maps discovered from public pages and DuckDuckGo search.",
        "- German Pavilion public pages discovered from search; profile links treated as government-backed trade pavilion evidence.",
        "- Localized country-language public search: dental distributor/import/export/lab/registry/certification/media/SNS queries.",
        "",
        "## Direct probes not promoted",
    ]
    for probe in direct_probes:
        lines.append(f"- {probe['url']}: {probe['status']} ({probe['elapsedSeconds']}s). {probe.get('note') or ''}".rstrip())
    lines += [
        "",
        "## Notes",
        "- OSM was not used as an acquisition source in this round.",
        "- Existing rows were preserved. New rows were deduped against the current complete dataset by email, company+website, company+address, or company+country+source URL.",
        "- Dental-lab registry rows are not dental distributors by default; they are intentionally categorized as lab prospects for scanner/CAD-CAM/lab workflow outreach.",
        "- Dental organization registry rows are not distributor leads by default; they are categorized separately as official-registry clinic/dental-organization prospects.",
        "- Search, SNS, and media rows should be revisited before outreach because they may reflect public mentions rather than verified contact ownership.",
    ]
    SUMMARY_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-additional", type=int, default=3000)
    parser.add_argument("--max-searches", type=int, default=2200)
    parser.add_argument("--results-per-query", type=int, default=12)
    parser.add_argument("--search-pause", type=float, default=0.04)
    parser.add_argument("--max-npi", type=int, default=1200)
    parser.add_argument("--max-npi-dental-orgs", type=int, default=3500)
    parser.add_argument("--max-npi-dentist-orgs", type=int, default=2500)
    parser.add_argument("--max-a2z-pages", type=int, default=30)
    parser.add_argument("--max-german-pages", type=int, default=20)
    parser.add_argument("--search-workers", type=int, default=8)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    complete_rows = partial.read_jsonl(COMPLETE_JSONL)
    before_count = len(complete_rows)
    existing_keys = {partial.row_business_key(row) for row in complete_rows if partial.row_business_key(row)}
    publisher_keys = {partial.publisher_dedupe_key(row) for row in complete_rows if partial.publisher_dedupe_key(row)}
    cache = load_json(SEARCH_CACHE_JSON, {})
    candidates: list[partial.Candidate] = []

    direct_probes = probe_direct_sources()
    print(json.dumps({"collector": "direct_source_probes", "probes": direct_probes}, ensure_ascii=False), flush=True)

    npi_candidates = collect_cms_npi_dental_labs(args.max_npi)
    candidates.extend(npi_candidates)
    print(json.dumps({"collector": "cms_npi_dental_labs", "candidates": len(npi_candidates)}, ensure_ascii=False), flush=True)

    npi_dental_org_candidates = collect_cms_npi_dental_organizations(args.max_npi_dental_orgs)
    candidates.extend(npi_dental_org_candidates)
    print(json.dumps({"collector": "cms_npi_dental_organizations", "candidates": len(npi_dental_org_candidates)}, ensure_ascii=False), flush=True)

    npi_dentist_org_candidates = collect_cms_npi_dentist_organizations(args.max_npi_dentist_orgs)
    candidates.extend(npi_dentist_org_candidates)
    print(json.dumps({"collector": "cms_npi_dentist_organizations", "candidates": len(npi_dentist_org_candidates)}, ensure_ascii=False), flush=True)

    a2z_pages = discover_a2z_pages(cache, args.max_a2z_pages)
    a2z_candidates: list[partial.Candidate] = []
    for event, url, country in a2z_pages:
        collected = collect_a2z_event_page(event, url, country)
        a2z_candidates.extend(collected)
    candidates.extend(a2z_candidates)
    print(json.dumps({"collector": "a2z_official_event_maps", "pages": len(a2z_pages), "candidates": len(a2z_candidates)}, ensure_ascii=False), flush=True)

    german_pages = discover_german_pavilion_pages(cache, args.max_german_pages)
    german_candidates: list[partial.Candidate] = []
    for event, url in german_pages:
        german_candidates.extend(collect_german_pavilion_page(event, url))
    candidates.extend(german_candidates)
    print(json.dumps({"collector": "german_pavilion_discovered", "pages": len(german_pages), "candidates": len(german_candidates)}, ensure_ascii=False), flush=True)

    search_candidates, query_count = collect_localized_search_candidates(
        cache=cache,
        max_searches=args.max_searches,
        results_per_query=args.results_per_query,
        target_candidates=max(args.target_additional * 4, 4000),
        pause=args.search_pause,
        workers=args.search_workers,
    )
    candidates.extend(search_candidates)
    print(json.dumps({"collector": "localized_public_search_social_media_directory", "candidates": len(search_candidates), "query_count": query_count}, ensure_ascii=False), flush=True)

    selected = unique_round11_candidates(candidates, complete_rows, existing_keys, publisher_keys, args.target_additional)
    after_count = before_count + len(selected)
    backup_path: Path | None = None
    if not args.dry_run:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        backup_path = BACKUP_DIR / f"prospects_augmented_contact_complete.before_partial_round11_{stamp}.jsonl"
        shutil.copy2(COMPLETE_JSONL, backup_path)
        complete_rows.extend(selected)
        partial.write_jsonl(COMPLETE_JSONL, complete_rows)
        partial.write_csv(COMPLETE_CSV, complete_rows)
        write_jsonl(PROMOTIONS_JSONL, selected)

    write_summary(
        backup_path=backup_path,
        before_count=before_count,
        after_count=after_count,
        selected=selected,
        candidates=candidates,
        query_count=query_count,
        direct_probes=direct_probes,
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
        "directProbes": direct_probes,
        "sourceCounts": dict(Counter(row["source_type"] for row in selected).most_common()),
        "trustCounts": dict(Counter((row.get("tags") or {}).get("source_trust", "") for row in selected).most_common()),
        "contactCompletenessCounts": dict(Counter((row.get("tags") or {}).get("contact_completeness", "") for row in selected).most_common()),
        "segmentCounts": dict(Counter(row.get("segment") or "" for row in selected).most_common()),
    }
    save_json(RESULT_JSON, result)
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
