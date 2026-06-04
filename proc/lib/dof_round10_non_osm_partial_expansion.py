#!/usr/bin/env python3
"""Round 10 non-OSM partial lead expansion for dental distributors/vendors.

This round keeps the round9 artifacts intact. It adds a fresh set of public
non-OSM leads from official exhibitor pages and broad localized search/yellow
page/social snippets, with explicit trust and contact-completeness tags.
"""

from __future__ import annotations

import argparse
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
from urllib.parse import quote_plus, unquote, urlparse, parse_qs

from bs4 import BeautifulSoup

import dof_partial_distributor_candidate_expansion as partial


ROOT = Path("/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04")
OUT_ROOT = ROOT / "output/dof-overseas-customer-prospects/2026-05-30/scale5000"
DATA = OUT_ROOT / "data"
BACKUP_DIR = DATA / "backups"
COMPLETE_JSONL = DATA / "prospects_augmented_contact_complete.jsonl"
COMPLETE_CSV = DATA / "prospects_augmented_contact_complete.csv"
PROMOTIONS_JSONL = DATA / "partial_distributor_promotions_round10.jsonl"
SEARCH_RAW_JSONL = DATA / "partial_distributor_search_raw_round10.jsonl"
SEARCH_CACHE_JSON = DATA / "partial_distributor_search_cache_round10.json"
SUMMARY_MD = OUT_ROOT / "external_partial_distributor_expansion_round10.md"

CEDE_2026 = "https://www.cede.pl/en/exhibition/exhibitors-list/"
SWDC_2026 = "https://swdentalconf.org/exhibit-hall-2/exhibitor-listing/"
BDIA_2026 = "https://dentalshowcase.com/exhibitor-list"
LMT_COMPANIES = "https://lmtmag.com/companies/"
LMT_SHOWS = [
    ("LMT LAB DAY Chicago 2026", "https://lmtmag.com/shows/lmt-lab-day-chicago-2026/exhibitors"),
    ("LMT LAB DAY West 2026", "https://lmtmag.com/shows/lmt-lab-day-west-2026/exhibitors"),
    ("LMT LAB DAY Chicago 2025", "https://lmtmag.com/shows/lmt-lab-day-chicago-2025/exhibitors"),
]
BDIA_MEMBER_API = "https://members.bdia.org.uk/wp-json/members/v1/companies"
ADIA_MEMBERS = "https://www.adia.org.au/adia-members.html"
SADTO_COMPANIES = "https://sadto.org.za/company/"
GERMAN_PAVILION_PAGES = [
    ("Sino Dental 2026 German Pavilion", "https://www.german-pavilion.com/en/sino-dental-2026", "Germany"),
    ("IDEM Singapore 2026 German Pavilion", "https://www.german-pavilion.com/en/idem-singapore-2026", "Germany"),
    ("CIOSP 2026 German Pavilion", "https://www.german-pavilion.com/en/ciosp-2026", "Germany"),
]
SCOTTISH_DENTAL_SHOW = "https://sdshow.co.uk/exhibitors/"
WESTERN_REGIONAL_2026 = "https://westernregional.org/2026/Exhibitors/Register.asp"
AO_2026 = "https://s6.goeshow.com/AO/Annual/2026/exhibitor_list.cfm"
AAO_A2Z_PAGES = [
    ("AAO Annual Session 2026", "https://s36.a2zinc.net/clients/aaortho/annual2026/public/EventMap.aspx?shMode=E&ID=618", "United States"),
    ("AAO Winter Meeting 2026", "https://s36.a2zinc.net/clients/aaortho/wintermeeting2026/Public/eventmap.aspx?shmode=E", "United States"),
    ("Star of the North Meeting 2026 A2Z", "https://s23.a2zinc.net/clients/MNDA/sotn26/Public/EventMap.aspx", "United States"),
]
DENTAL_EXPO_NL = "https://www.dentalexpo.nl/en/exhibitors/"
VDA_SHOWCASE = "https://www.vadental.org/showcase/exhibits"
NDDA_NEPAL = "https://nepaldda.org.np/member-directory/"
DENTISTRYREGISTER_SUPPLIERS = "https://www.dentistryregister.com/list/suppliers.asp"
REGIONAL_DIRECTORY_DENTAL_PRODUCTS = "https://dental-products.regionaldirectory.us/"
MEDINDEXER_CATEGORIES = [
    ("Dental Imaging", "https://www.medindexer.com/c/dental-imaging"),
    ("Dental Instruments", "https://www.medindexer.com/c/dental-instruments"),
    ("Dental Lab Equipment", "https://www.medindexer.com/c/dental-lab-equipment"),
    ("Dental Units", "https://www.medindexer.com/c/dental-units"),
]
DENTSPLY_DISTRIBUTOR_PDF = "https://www.dentalcity.com/PDF/Dentsply-Authorized-Distributor-Network.pdf"
HENRY_SCHEIN_VENDOR_PDF = "https://www.henryschein.com/us-es/images/dental/Authorized-Equipment-Vendor-List-v5.3.2023-23BS1029.pdf"
MODERN_DENTISTRY_SA_DIRECTORY_PDF = "https://www.moderndentistrymedia.com/feb-mar2025/dental-directory2025/dental-directory2025.pdf"
LANG_DENTAL_DEALERS = "https://www.langdental.com/index.php/domestic/dealers/"
HANDLER_DISTRIBUTORS = "https://www.handlermfg.com/dealers/"
EXPORTERSINDIA_PAGES = [
    "https://www.exportersindia.com/indian-suppliers/dental-equipment.htm",
    "https://www.exportersindia.com/indian-suppliers/dental-implants.htm",
    "https://www.exportersindia.com/indian-suppliers/dental-x-ray-machine.htm",
    "https://www.exportersindia.com/indian-suppliers/dental-scaler.htm",
    "https://www.exportersindia.com/indian-suppliers/dental-curing-light.htm",
    "https://www.exportersindia.com/indian-suppliers/dental-camera.htm",
    "https://www.exportersindia.com/indian-suppliers/dental-files.htm",
    "https://www.exportersindia.com/indian-suppliers/dental-kit.htm",
    "https://www.exportersindia.com/indian-suppliers/dental-implant-kit.htm",
    "https://www.exportersindia.com/indian-suppliers/dental-accessories.htm",
    "https://www.exportersindia.com/indian-suppliers/electric-toothbrush.htm",
    "https://www.exportersindia.com/indian-suppliers/dental-handpieces.htm",
    "https://www.exportersindia.com/indian-suppliers/dental-air-compressors.htm",
    "https://www.exportersindia.com/indian-suppliers/dental-microscope.htm",
    "https://www.exportersindia.com/indian-suppliers/dental-milling-machine.htm",
    "https://www.exportersindia.com/indian-suppliers/dental-disposables.htm",
    "https://www.exportersindia.com/indian-suppliers/dental-burs.htm",
    "https://www.exportersindia.com/indian-suppliers/dental-probes.htm",
    "https://www.exportersindia.com/indian-suppliers/dental-floss.htm",
    "https://www.exportersindia.com/indian-suppliers/dental-crowns.htm",
    "https://www.exportersindia.com/indian-suppliers/dental-cements.htm",
    "https://www.exportersindia.com/indian-suppliers/orthodontic-instruments.htm",
    "https://www.exportersindia.com/indian-suppliers/ultrasonic-scaler.htm",
    "https://www.exportersindia.com/indian-suppliers/dental-chairs.htm",
    "https://www.exportersindia.com/indian-suppliers/dental-x-ray-film.htm",
    "https://www.exportersindia.com/indian-suppliers/dental-autoclave.htm",
    "https://www.exportersindia.com/indian-suppliers/dental-syringe.htm",
    "https://www.exportersindia.com/indian-suppliers/dental-explorer.htm",
    "https://www.exportersindia.com/indian-suppliers/dental-products.htm",
    "https://www.exportersindia.com/indian-suppliers/dental-polisher.htm",
    "https://www.exportersindia.com/indian-suppliers/dental-brush.htm",
    "https://www.exportersindia.com/indian-suppliers/dental-impression-tray.htm",
    "https://www.exportersindia.com/indian-suppliers/dental-plaster.htm",
    *[
        f"https://www.exportersindia.com/{city}/dental-equipment.htm"
        for city in [
            "gujarat",
            "mumbai",
            "delhi",
            "bangalore",
            "chennai",
            "hyderabad",
            "kolkata",
            "pune",
            "jaipur",
            "noida",
            "ahmedabad",
            "rajkot",
            "vadodara",
            "surat",
            "coimbatore",
            "kerala",
            "lucknow",
            "indore",
            "nagpur",
            "ludhiana",
            "chandigarh",
            "faridabad",
            "ghaziabad",
            "thane",
            "navi-mumbai",
            "gurgaon",
            "meerut",
            "kanpur",
            "patna",
            "bhopal",
            "bhubaneswar",
            "visakhapatnam",
            "vijayawada",
            "ernakulam",
            "kochi",
            "madurai",
            "mangalore",
            "mysore",
            "raipur",
            "ranchi",
            "jalandhar",
            "amritsar",
            "agra",
            "dehradun",
            "haridwar",
            "roorkee",
            "ambala",
            "secunderabad",
            "mohali",
            "baddi",
            "sonipat",
            "panipat",
            "nasik",
            "aurangabad",
            "goa",
            "pondicherry",
            "maharashtra",
            "rajasthan",
            "punjab",
            "haryana",
            "west-bengal",
            "telangana",
            "chhattisgarh",
            "jammu-kashmir",
        ]
    ],
]
INDIAMART_PAGES = [
    ("Dental Equipment", "https://dir.indiamart.com/impcat/dental-equipment.html"),
    ("Dental Instruments", "https://dir.indiamart.com/impcat/dental-instruments.html"),
    ("Dental Implants", "https://dir.indiamart.com/impcat/dental-implants.html"),
    ("Dental X Ray Machine", "https://dir.indiamart.com/impcat/dental-x-ray-machine.html"),
    ("Dental Burs", "https://dir.indiamart.com/impcat/dental-burs.html"),
    ("Dental Air Compressor", "https://dir.indiamart.com/impcat/dental-air-compressor.html"),
]

USER_AGENT = partial.USER_AGENT
CACHE_LOCK = threading.Lock()

SOCIAL_HOSTS = ("facebook.com", "linkedin.com")
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
    "medicalexpo",
    "exportersindia",
    "tradeindia",
    "go4worldbusiness",
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
)

DENTAL_RE = re.compile(
    r"dental|dent[aeio]|odont|odontolog|orthodont|ortho|implant|zahn|stomat|口腔|牙科|歯科|nha khoa|gigi|pergigian|diş|طب الأسنان",
    re.I,
)
CHANNEL_RE = re.compile(
    r"distribut|supplier|supply|supplies|dealer|depot|trading|trade|import|export|equipment|material|"
    r"laborator|lab |dentalbedarf|dentalhandel|zahnbedarf|suministro|suministros|distribuidora|"
    r"dep[óo]sito|importadora|exportadora|equipamentos|materiais|fournisseur|fournitures|mat[ée]riel|"
    r"forniture|fornitore|malzemeleri|مستلزمات|تجهيزات|thiết bị|vật liệu|alat|bahan|器材|材料",
    re.I,
)
GENERIC_RE = re.compile(
    r"\b(top|best|list of|directory|yellow pages|category|near me|jobs?|market report|attendees?|visitor list|"
    r"exhibitor list|companies in|suppliers in|distributors in|importers and buyers|database|catalogue|catalog|"
    r"events?|conference|course|training|news|blog|article|pdf)\b",
    re.I,
)

FOOTER_OR_NAV_RE = re.compile(
    r"^(openingstijden|adres|nieuwsletter|newsletter|contact|home|directory|view profile|filters|categories|countries|"
    r"stay connected|about us|privacy policy|terms of use|copyright|for buyers|for vendors|indexer|submit an rfp|"
    r"industry news|knowledge|sign in|cart|checkout|product usage|safety data sheets|marketing center|certificates|"
    r"my exhibitors|pre-configured lab packages|opening times)$",
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
            "fournisseur dentaire",
            "matériel dentaire distributeur",
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
        ],
        "terms": [
            "dental distributor",
            "dental equipment supplier",
            "dental depot",
            "dental import export",
            "Dentalbedarf Händler",
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
            "مستلزمات طب الأسنان موزع",
            "تجهيزات طب الأسنان",
            "diş malzemeleri distribütör",
            "dental depo",
        ],
    },
    {
        "countries": [
            "Bangladesh",
            "Cambodia",
            "India",
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
            "thiết bị nha khoa nhà phân phối",
            "alat kedokteran gigi distributor",
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
        uddg = parse_qs(parsed.query).get("uddg", [""])[0]
        href = unquote(uddg)
    if href.startswith("//"):
        href = "https:" + href
    return href if href.startswith(("http://", "https://")) else ""


def source_trust_for_url(url: str) -> tuple[str, str, str, int]:
    current_host = host(url)
    if any(item in current_host for item in SOCIAL_HOSTS):
        return "Facebook/LinkedIn public dental distributor signal (low trust)", "low", "public_social_signal", 90
    if any(item in current_host for item in DIRECTORY_HOST_HINTS):
        return "Localized yellow-page/business-directory dental distributor signal (partial contact)", "low-medium", "localized_yellow_page_or_business_directory", 82
    return "Localized web-search public dental distributor signal (partial contact)", "low-medium", "localized_search_public_web", 84


def usable_search_name(title: str) -> str:
    value = clean(title)
    value = re.sub(r"\s+[-|–]\s+(Facebook|LinkedIn|Instagram|X|Kompass|Cybo|Cylex|Europages|Yellow Pages|BusinessList).*$", "", value, flags=re.I)
    value = re.sub(r"\s+\|\s+.*$", "", value)
    value = re.sub(r"^(Company Profile\s*[-:]\s*)", "", value, flags=re.I)
    value = clean(value.strip(" -:;,."))
    lower = value.lower()
    if not partial.is_usable_name(value):
        return ""
    if GENERIC_RE.search(lower):
        return ""
    if re.search(r"\b(dental supplies?|dental equipment|dentists?|clinics?|yellow pages|search results)\b\s+(in|near)\b", lower):
        return ""
    if len(value.split()) > 12:
        return ""
    return value


def add_candidate(candidates: list[partial.Candidate], row: dict[str, Any], priority: int) -> None:
    partial.add_candidate(candidates, row, priority)


def make_public_row(
    *,
    name: str,
    country: str,
    source_type: str,
    source_url: str,
    source_trust: str,
    source_family: str,
    acquisition_path: str,
    site_business_summary: str,
    website: str = "",
    email: str = "",
    phone: str = "",
    address: str = "",
    evidence: list[str] | None = None,
    event: str = "",
    original_kind: str = "",
) -> dict[str, Any]:
    return partial.make_row(
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


def name_country_key(row: dict[str, Any]) -> str:
    name = clean(row.get("name")).lower()
    country = clean(row.get("country")).lower()
    return f"{name}|{country}" if name and country else ""


def unique_round10_candidates(
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
        source_only = (row.get("tags") or {}).get("contact_completeness") == "source_only"
        row_name_country = name_country_key(row)
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


def table_names(url: str, country: str, source_type: str, event: str, trust: str = "medium-high") -> list[partial.Candidate]:
    html = partial.fetch_html(url)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[partial.Candidate] = []
    seen: set[str] = set()
    for row in soup.select("table tr"):
        cells = [clean(cell.get_text(" ", strip=True)) for cell in row.find_all(["td", "th"])]
        if not cells or cells[0].lower() in {"company", "company booth number", "exhibitor"}:
            continue
        name = cells[0]
        if len(cells) == 1:
            name = re.sub(r"\s+(PCC\.?\S+|\d{2,5}|[A-Z]\d{1,4})$", "", name).strip()
        if not partial.is_usable_name(name) or GENERIC_RE.search(name):
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        row_obj = make_public_row(
            name=name,
            country=country,
            source_type=source_type,
            source_url=url,
            source_trust=trust,
            source_family="official_exhibition_list_page",
            acquisition_path=f"{event} 공식 exhibitor list/table에서 업체명과 booth/list 노출을 확인",
            site_business_summary=f"{event} 공식 전시자 목록에 등재된 치과 장비·재료·서비스 공급사 또는 유통 채널 후보",
            evidence=[f"{event} official exhibitor table/list: {name}", f"Source page: {url}"],
            event=event,
            original_kind="round10_official_exhibitor_table",
        )
        add_candidate(candidates, row_obj, 30)
    return candidates


def heading_names(url: str, country: str, source_type: str, event: str, selector: str = "h2") -> list[partial.Candidate]:
    html = partial.fetch_html(url)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[partial.Candidate] = []
    seen: set[str] = set()
    for heading in soup.select(selector):
        name = clean(heading.get_text(" ", strip=True))
        if not partial.is_usable_name(name) or GENERIC_RE.search(name):
            continue
        if any(skip in name.lower() for skip in ("sponsor", "opening times", "legal information", "quick links", "members lounge")):
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        row_obj = make_public_row(
            name=name,
            country=country,
            source_type=source_type,
            source_url=url,
            source_trust="medium-high",
            source_family="official_exhibition_list_page",
            acquisition_path=f"{event} 공식 exhibitor heading/list에서 업체명을 확인",
            site_business_summary=f"{event} 공식 전시자 목록에 등재된 치과 장비·재료·서비스 공급사 또는 유통 채널 후보",
            evidence=[f"{event} official exhibitor heading/list: {name}", f"Source page: {url}"],
            event=event,
            original_kind="round10_official_exhibitor_heading",
        )
        add_candidate(candidates, row_obj, 35)
    return candidates


def collect_official_event_pages() -> list[partial.Candidate]:
    candidates: list[partial.Candidate] = []
    candidates.extend(table_names(CEDE_2026, "Poland", "CEDE 2026 official dental expo exhibitor list (partial contact)", "Dental Expo CEDE 2026"))
    candidates.extend(table_names(SWDC_2026, "United States", "Southwest Dental Conference 2026 official exhibitor list (partial contact)", "Southwest Dental Conference 2026"))
    candidates.extend(heading_names(BDIA_2026, "United Kingdom", "BDIA Dental Showcase 2026 official exhibitor list (partial contact)", "BDIA Dental Showcase 2026"))
    for event, url, country in GERMAN_PAVILION_PAGES:
        candidates.extend(table_names(url, country, f"{event} official German Pavilion exhibitor list (partial contact)", event, trust="high"))
    return candidates


def collect_lmt_h4(url: str, event: str, source_type: str, country: str = "United States", offsets: range | None = None) -> list[partial.Candidate]:
    candidates: list[partial.Candidate] = []
    seen: set[str] = set()
    pages = [url]
    if offsets is not None:
        pages = [url if int(offset) == 0 else f"{url}?offset={offset}" for offset in offsets]
    for page_url in pages:
        html = partial.fetch_html(page_url)
        if not html:
            continue
        soup = BeautifulSoup(html, "html.parser")
        for heading in soup.select("h4"):
            name = clean(heading.get_text(" ", strip=True))
            if not partial.is_usable_name(name) or GENERIC_RE.search(name):
                continue
            if name in {"LMT Magazine", "LMTmag.com", "LMT LAB DAY®"}:
                continue
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            row_obj = make_public_row(
                name=name,
                country=country,
                source_type=source_type,
                source_url=page_url,
                source_trust="medium-high",
                source_family="official_dental_lab_industry_directory",
                acquisition_path=f"{event} 공개 업체/전시자 목록에서 업체명을 확인",
                site_business_summary=f"{event}에 노출된 치과기공·랩 장비·디지털 덴탈 공급사 또는 서비스 업체 후보",
                evidence=[f"{event} public h4 listing: {name}", f"Source page: {page_url}"],
                event=event,
                original_kind="round10_lmt_public_listing",
            )
            add_candidate(candidates, row_obj, 32)
    return candidates


def collect_bdia_member_api() -> list[partial.Candidate]:
    candidates: list[partial.Candidate] = []
    seen: set[str] = set()
    for page in range(1, 10):
        try:
            import requests

            response = requests.get(
                BDIA_MEMBER_API,
                params={"page": page},
                headers={"User-Agent": USER_AGENT, "Referer": "https://bdia.org.uk/member-directory/"},
                timeout=(6, 24),
            )
            data = response.json() if response.status_code < 400 else {}
        except Exception:
            break
        items = data.get("items") if isinstance(data, dict) else None
        if not items:
            break
        for item in items:
            name = clean(item.get("trading_name"))
            if not partial.is_usable_name(name) or name.lower() in seen:
                continue
            seen.add(name.lower())
            categories = ", ".join(item.get("business_categories") or [])
            slug = clean(item.get("slug"))
            url = f"https://bdia.org.uk/member-directory/{slug}" if slug else "https://bdia.org.uk/member-directory/"
            row_obj = make_public_row(
                name=name,
                country="United Kingdom",
                source_type="BDIA official member directory API (partial contact)",
                source_url=url,
                source_trust="medium-high",
                source_family="official_dental_industry_association_directory",
                acquisition_path="BDIA member directory 공개 REST endpoint에서 member trading name과 business category를 확인",
                site_business_summary=f"BDIA approved member supplier. Categories: {categories or 'not shown'}",
                evidence=[f"BDIA member API item: {name}", f"Business categories: {categories or 'not shown'}"],
                event="BDIA Member Directory",
                original_kind="round10_bdia_member_api",
            )
            add_candidate(candidates, row_obj, 28)
        if len(seen) >= int(data.get("total") or 0):
            break
    return candidates


def collect_association_headings(url: str, country: str, source_type: str, event: str, selector: str = "h3") -> list[partial.Candidate]:
    html = partial.fetch_html(url)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[partial.Candidate] = []
    seen: set[str] = set()
    for heading in soup.select(selector):
        name = clean(heading.get_text(" ", strip=True))
        if not partial.is_usable_name(name) or GENERIC_RE.search(name):
            continue
        if any(skip in name.lower() for skip in ("follow us", "quick links", "contact", "resources", "discover")):
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        row_obj = make_public_row(
            name=name,
            country=country,
            source_type=source_type,
            source_url=url,
            source_trust="medium-high",
            source_family="official_dental_industry_association_directory",
            acquisition_path=f"{event} 공개 member/trader directory heading에서 업체명을 확인",
            site_business_summary=f"{event}에 등재된 치과 산업 회원사·trader·공급사 후보",
            evidence=[f"{event} public directory listing: {name}", f"Source page: {url}"],
            event=event,
            original_kind="round10_association_member_directory",
        )
        add_candidate(candidates, row_obj, 33)
    return candidates


def collect_direct_association_pages() -> list[partial.Candidate]:
    candidates: list[partial.Candidate] = []
    candidates.extend(collect_lmt_h4(LMT_COMPANIES, "LMT company directory", "LMT public dental laboratory industry company directory (partial contact)", offsets=range(0, 4)))
    for event, url in LMT_SHOWS:
        candidates.extend(collect_lmt_h4(url, event, f"{event} official exhibitor list (partial contact)"))
    candidates.extend(collect_bdia_member_api())
    candidates.extend(collect_association_headings(ADIA_MEMBERS, "Australia", "ADIA Australia official member directory (partial contact)", "Australian Dental Industry Association Member Directory", selector="h3"))
    candidates.extend(collect_association_headings(SADTO_COMPANIES, "South Africa", "SADTO South Africa dental trader directory (partial contact)", "Southern African Dental Traders Organisation Member Directory", selector="h2"))
    return candidates


def is_booth_label(value: str) -> bool:
    text = clean(value)
    return bool(re.fullmatch(r"(?:\*?\d{1,5}[A-Z]?|[A-Z]{1,3}-?\d{1,5}|Hallway|Booth)", text, flags=re.I))


def non_generic_listing_name(value: str) -> str:
    name = clean(value).strip(" -*•:")
    if not partial.is_usable_name(name):
        return ""
    if GENERIC_RE.search(name) or FOOTER_OR_NAV_RE.search(name):
        return ""
    if re.search(r"^(education\s+)?programme:", name, re.I):
        return ""
    if re.fullmatch(r"[A-Z#]", name):
        return ""
    if len(name.split()) > 14:
        return ""
    return name


def collect_named_heading_page(
    *,
    url: str,
    country: str,
    source_type: str,
    event: str,
    selector: str,
    trust: str = "medium-high",
    family: str = "official_exhibition_list_page",
    priority: int = 34,
) -> list[partial.Candidate]:
    html = partial.fetch_html(url)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[partial.Candidate] = []
    seen: set[str] = set()
    for heading in soup.select(selector):
        name = non_generic_listing_name(heading.get_text(" ", strip=True))
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        row_obj = make_public_row(
            name=name,
            country=country,
            source_type=source_type,
            source_url=url,
            source_trust=trust,
            source_family=family,
            acquisition_path=f"{event} 공개 exhibitor/member list에서 업체명을 확인",
            site_business_summary=f"{event}에 노출된 치과 장비·재료·서비스 공급사, 유통사, 또는 치과 산업 벤더 후보",
            evidence=[f"{event} public listing: {name}", f"Source page: {url}"],
            event=event,
            original_kind="round10_public_heading_listing",
        )
        add_candidate(candidates, row_obj, priority)
    return candidates


def collect_dental_expo_nl() -> list[partial.Candidate]:
    candidates: list[partial.Candidate] = []
    for page in range(1, 7):
        url = DENTAL_EXPO_NL if page == 1 else f"{DENTAL_EXPO_NL}?stands%5Bpage%5D={page}"
        candidates.extend(
            collect_named_heading_page(
                url=url,
                country="Netherlands",
                source_type="Dental Expo Netherlands official exhibitor list (partial contact)",
                event="Dental Expo Netherlands",
                selector="h2",
                trust="medium-high",
                priority=31,
            )
        )
    return candidates


def collect_a2z_or_goeshow_table(url: str, event: str, country: str) -> list[partial.Candidate]:
    html = partial.fetch_html(url)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    cells = [clean(cell.get_text(" ", strip=True)) for cell in soup.select("td") if clean(cell.get_text(" ", strip=True))]
    candidates: list[partial.Candidate] = []
    seen: set[str] = set()
    for index, value in enumerate(cells):
        nearby = cells[index + 1] if index + 1 < len(cells) else ""
        previous = cells[index - 1] if index > 0 else ""
        name = ""
        if is_booth_label(nearby):
            name = non_generic_listing_name(value)
        elif is_booth_label(previous):
            name = non_generic_listing_name(value)
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        row_obj = make_public_row(
            name=name,
            country=country,
            source_type=f"{event} official A2Z/Goeshow exhibitor list (partial contact)",
            source_url=url,
            source_trust="medium-high",
            source_family="official_exhibition_floorplan_or_exhibitor_table",
            acquisition_path=f"{event} 공식 A2Z/Goeshow exhibitor/floorplan table에서 업체명과 booth 노출을 확인",
            site_business_summary=f"{event} 공식 전시자/플로어플랜에 등재된 치과 장비·재료·서비스 공급사 또는 유통 채널 후보",
            evidence=[f"{event} official table/floorplan listing: {name}", f"Source page: {url}"],
            event=event,
            original_kind="round10_a2z_goeshow_public_table",
        )
        add_candidate(candidates, row_obj, 29)
    return candidates


def collect_vda_showcase() -> list[partial.Candidate]:
    html = partial.fetch_html(VDA_SHOWCASE)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    lines = [clean(line) for line in soup.get_text("\n").splitlines() if clean(line)]
    candidates: list[partial.Candidate] = []
    seen: set[str] = set()
    active = False
    states_or_letters = {
        "A",
        "B",
        "C",
        "D",
        "F",
        "G",
        "L",
        "M",
        "N",
        "P",
        "R",
        "S",
        "T",
        "U",
    }
    for line in lines:
        if line == "2026 Exhibitors":
            active = True
            continue
        if active and line == "Stay Connected":
            break
        if not active or line in states_or_letters:
            continue
        name = non_generic_listing_name(line)
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        row_obj = make_public_row(
            name=name,
            country="United States",
            source_type="Virginia Dental Showcase 2026 official exhibitor list (partial contact)",
            source_url=VDA_SHOWCASE,
            source_trust="medium-high",
            source_family="official_exhibition_list_page",
            acquisition_path="Virginia Dental Showcase 공식 2026 exhibitors 섹션에서 업체명을 확인",
            site_business_summary="Virginia Dental Showcase 2026 공식 전시자 목록에 등재된 치과 장비·서비스·유통 채널 후보",
            evidence=[f"Virginia Dental Showcase 2026 exhibitor section: {name}", f"Source page: {VDA_SHOWCASE}"],
            event="Virginia Dental Showcase 2026",
            original_kind="round10_vda_public_exhibitor_section",
        )
        add_candidate(candidates, row_obj, 32)
    return candidates


def first_href_url(node: Any) -> str:
    if not node:
        return ""
    hrefs: list[str] = []
    for link in node.find_all("a", href=True):
        href = clean(link.get("href"))
        if href.startswith("mailto:") or href.startswith("tel:"):
            continue
        if href.startswith("//"):
            href = "https:" + href
        if href.startswith(("http://", "https://")):
            hrefs.append(href)
    return hrefs[0] if hrefs else ""


def extract_email(text: str) -> str:
    match = re.search(r"[\w.+%-]+@[\w.-]+\.[A-Za-z]{2,}", text)
    return match.group(0) if match else ""


def extract_phone(text: str) -> str:
    match = re.search(r"(?:\+?\d[\d\s()./-]{6,}\d)", text)
    return clean(match.group(0)) if match else ""


def collect_ndda_nepal() -> list[partial.Candidate]:
    html = partial.fetch_html(NDDA_NEPAL)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[partial.Candidate] = []
    for heading in soup.select("h4"):
        name = non_generic_listing_name(heading.get_text(" ", strip=True))
        if not name:
            continue
        detail_node = heading.find_next("p")
        detail_text = clean(detail_node.get_text(" ", strip=True)) if detail_node else ""
        website = first_href_url(detail_node)
        row_obj = make_public_row(
            name=name,
            country="Nepal",
            source_type="Nepal Dental Distributor's Association official member directory (partial contact)",
            source_url=NDDA_NEPAL,
            source_trust="high",
            source_family="official_dental_distributor_association_directory",
            acquisition_path="NDDA 공식 member directory에서 치과 유통사 회원명과 일부 연락처를 확인",
            site_business_summary="Nepal Dental Distributor's Association 공식 회원 디렉터리에 등재된 치과 유통사 후보",
            website=website,
            email=extract_email(detail_text),
            phone=extract_phone(detail_text),
            address=re.split(r"\b(?:Tel|Mobile|Email|Website|Co-Ordinator)\b", detail_text, maxsplit=1, flags=re.I)[0],
            evidence=[f"NDDA member directory listing: {name}", f"Details: {detail_text[:240]}", f"Source page: {NDDA_NEPAL}"],
            event="Nepal Dental Distributor's Association Member Directory",
            original_kind="round10_ndda_official_member_directory",
        )
        add_candidate(candidates, row_obj, 18)
    return candidates


def collect_dentistryregister_suppliers() -> list[partial.Candidate]:
    candidates: list[partial.Candidate] = []
    seen: set[str] = set()
    paths = ["/list/suppliers.asp"] + [f"/Manufacturers/Suppliers/Page{page}/cid.htm" for page in range(2, 11)]
    for path in paths:
        url = "https://www.dentistryregister.com" + path
        html = partial.fetch_html(url)
        if not html:
            continue
        soup = BeautifulSoup(html, "html.parser")
        for link in soup.find_all("a", href=True):
            href = clean(link.get("href"))
            if "/Supplier/" not in href:
                continue
            name = non_generic_listing_name(link.get_text(" ", strip=True))
            if not name or name.lower() == "more...":
                continue
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            profile_url = href if href.startswith("http") else "https://www.dentistryregister.com" + href
            row_obj = make_public_row(
                name=name,
                country="United States",
                source_type="DentistryRegister public dental supplier directory (partial contact)",
                source_url=profile_url,
                source_trust="low-medium",
                source_family="public_dental_supplier_directory",
                acquisition_path="DentistryRegister supplier list/profile URL에서 치과 supplier 명칭을 확인",
                site_business_summary="DentistryRegister 공개 supplier directory에 등록된 치과 공급사 또는 관련 벤더 후보",
                evidence=[f"DentistryRegister supplier link: {name}", f"Source page: {url}", f"Profile: {profile_url}"],
                event="DentistryRegister Supplier Directory",
                original_kind="round10_dentistryregister_supplier_directory",
            )
            add_candidate(candidates, row_obj, 78)
    return candidates


def collect_regional_directory() -> list[partial.Candidate]:
    html = partial.fetch_html(REGIONAL_DIRECTORY_DENTAL_PRODUCTS)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[partial.Candidate] = []
    seen: set[str] = set()
    skip_names = {"Dental Products", "Government Contractors", "Medical Equipment & Supplies", "Hospital Supplies", "Surgical Instruments"}
    for link in soup.find_all("a", href=True):
        href = clean(link.get("href"))
        name = non_generic_listing_name(link.get_text(" ", strip=True))
        if not name or name in skip_names or " Map" in name:
            continue
        if not href.startswith(("http://", "https://")) or "regionaldirectory.us" in href:
            continue
        key = f"{name.lower()}|{host(href)}"
        if key in seen:
            continue
        seen.add(key)
        row_obj = make_public_row(
            name=name,
            country="United States",
            source_type="RegionalDirectory dental equipment and supplies directory (partial contact)",
            source_url=REGIONAL_DIRECTORY_DENTAL_PRODUCTS,
            source_trust="low-medium",
            source_family="localized_yellow_page_or_business_directory",
            acquisition_path="RegionalDirectory Dental Equipment & Supplies category에서 업체명과 웹사이트 링크를 확인",
            site_business_summary="Dental Equipment & Supplies 카테고리에 등재된 미국 치과 장비·공급 업체 후보",
            website=href,
            evidence=[f"RegionalDirectory dental products listing: {name}", f"Website link: {href}", f"Source page: {REGIONAL_DIRECTORY_DENTAL_PRODUCTS}"],
            event="RegionalDirectory Dental Products Directory",
            original_kind="round10_regionaldirectory_dental_products",
        )
        add_candidate(candidates, row_obj, 79)
    return candidates


def collect_medindexer() -> list[partial.Candidate]:
    candidates: list[partial.Candidate] = []
    seen_pages: set[str] = set()
    for category, url in MEDINDEXER_CATEGORIES:
        pages = [url]
        html = partial.fetch_html(url)
        if html:
            soup = BeautifulSoup(html, "html.parser")
            for link in soup.find_all("a", href=True):
                href = clean(link.get("href"))
                if href.startswith("/c/") and href.count("/") >= 3:
                    pages.append("https://www.medindexer.com" + href)
        for page_url in pages:
            if page_url in seen_pages:
                continue
            seen_pages.add(page_url)
            page_html = partial.fetch_html(page_url)
            if not page_html:
                continue
            soup = BeautifulSoup(page_html, "html.parser")
            for heading in soup.select("h3"):
                name = non_generic_listing_name(heading.get_text(" ", strip=True))
                if not name:
                    continue
                row_obj = make_public_row(
                    name=name,
                    country="United States",
                    source_type=f"MedIndexer {category} dental vendor directory (partial contact)",
                    source_url=page_url,
                    source_trust="low-medium",
                    source_family="public_dental_supplier_directory",
                    acquisition_path=f"MedIndexer {category} category/state page에서 vendor name을 확인",
                    site_business_summary=f"MedIndexer {category} 치과 장비·기공·이미징·기구 공급사 후보",
                    evidence=[f"MedIndexer {category} listing: {name}", f"Source page: {page_url}"],
                    event=f"MedIndexer {category}",
                    original_kind="round10_medindexer_dental_vendor_directory",
                )
                add_candidate(candidates, row_obj, 76)
    return candidates


def fetch_pdf_text(url: str) -> str:
    try:
        import os
        import tempfile
        import requests

        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=(8, 30))
        if response.status_code >= 400 or not response.content.startswith(b"%PDF"):
            return ""
        fd, path = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        Path(path).write_bytes(response.content)
        try:
            result = subprocess.run(["pdftotext", path, "-"], capture_output=True, timeout=35)
            return result.stdout.decode("utf-8", errors="ignore") if result.returncode == 0 else ""
        finally:
            Path(path).unlink(missing_ok=True)
    except Exception:
        return ""


def collect_dentsply_pdf() -> list[partial.Candidate]:
    text = fetch_pdf_text(DENTSPLY_DISTRIBUTOR_PDF)
    candidates: list[partial.Candidate] = []
    if not text:
        return candidates
    lines = [clean(line) for line in text.splitlines() if clean(line)]
    for index, line in enumerate(lines):
        if not re.fullmatch(r"[A-Z0-9&.,' -]{4,}", line) or line in {"DENTSPLY Authorized Distributor Network1"}:
            continue
        nearby = " ".join(lines[index + 1 : index + 5])
        website_match = re.search(r"(?:www\.|https?://)[\w.-]+\.[A-Za-z]{2,}(?:/\S*)?", nearby)
        if not website_match:
            continue
        website = website_match.group(0)
        row_obj = make_public_row(
            name=line.title().replace(" Co.", " Co.").replace(" Inc.", " Inc."),
            country="United States",
            source_type="DENTSPLY authorized distributor network PDF (partial contact)",
            source_url=DENTSPLY_DISTRIBUTOR_PDF,
            source_trust="high",
            source_family="manufacturer_authorized_distributor_list_pdf",
            acquisition_path="DENTSPLY authorized distributor network PDF에서 유통사명, 전화, 웹사이트를 확인",
            site_business_summary="DENTSPLY 공식 authorized distributor network에 등재된 미국 치과 유통사",
            website=website,
            phone=extract_phone(nearby),
            evidence=[f"DENTSPLY PDF distributor row: {line}", f"Details: {nearby[:180]}", f"Source PDF: {DENTSPLY_DISTRIBUTOR_PDF}"],
            event="DENTSPLY Authorized Distributor Network",
            original_kind="round10_dentsply_authorized_distributor_pdf",
        )
        add_candidate(candidates, row_obj, 17)
    return candidates


def collect_henry_schein_vendor_pdf() -> list[partial.Candidate]:
    text = fetch_pdf_text(HENRY_SCHEIN_VENDOR_PDF)
    if not text:
        return []
    lines = [clean(line) for line in text.splitlines() if clean(line)]
    candidates: list[partial.Candidate] = []
    vendor_started = False
    for line in lines:
        if line == "3Shape":
            vendor_started = True
        if not vendor_started:
            continue
        if line.startswith("Henry Schein is authorized") or line in {"Vendor Code", "Vendor", "v. 5.3.2023"}:
            continue
        if re.fullmatch(r"[A-Z0-9]{2,8}", line):
            continue
        name = non_generic_listing_name(line)
        if not name:
            continue
        row_obj = make_public_row(
            name=name,
            country="United States",
            source_type="Henry Schein authorized equipment vendor PDF (partial contact)",
            source_url=HENRY_SCHEIN_VENDOR_PDF,
            source_trust="medium-high",
            source_family="authorized_equipment_vendor_list_pdf",
            acquisition_path="Henry Schein authorized equipment vendor list PDF에서 벤더명을 확인",
            site_business_summary="Henry Schein이 service/support authorized vendor로 표시한 치과 장비 공급 벤더 후보",
            evidence=[f"Henry Schein authorized equipment vendor PDF: {name}", f"Source PDF: {HENRY_SCHEIN_VENDOR_PDF}"],
            event="Henry Schein Authorized Equipment Vendor List",
            original_kind="round10_henry_schein_authorized_equipment_vendor_pdf",
        )
        add_candidate(candidates, row_obj, 40)
    return candidates


def collect_modern_dentistry_sa_pdf() -> list[partial.Candidate]:
    text = fetch_pdf_text(MODERN_DENTISTRY_SA_DIRECTORY_PDF)
    if not text:
        return []
    before_body = text.split("Dental Suppliers", 1)[0]
    candidates: list[partial.Candidate] = []
    for line in before_body.splitlines():
        name = non_generic_listing_name(line)
        if not name:
            continue
        if re.fullmatch(r"\d{2}", name) or name == "DIRECTORY 2025":
            continue
        row_obj = make_public_row(
            name=name,
            country="South Africa",
            source_type="Modern Dentistry South Africa Dental Directory 2025 PDF (partial contact)",
            source_url=MODERN_DENTISTRY_SA_DIRECTORY_PDF,
            source_trust="medium-high",
            source_family="published_dental_supplier_directory_pdf",
            acquisition_path="Modern Dentistry South Africa Dental Directory PDF 목차/업체 섹션에서 supplier 명칭을 확인",
            site_business_summary="남아공 dental supplier directory에 등재된 치과 유통사·수입사·장비/재료 공급사 후보",
            evidence=[f"Modern Dentistry SA Dental Directory listing: {name}", f"Source PDF: {MODERN_DENTISTRY_SA_DIRECTORY_PDF}"],
            event="Modern Dentistry South Africa Dental Directory 2025",
            original_kind="round10_modern_dentistry_sa_directory_pdf",
        )
        add_candidate(candidates, row_obj, 36)
    return candidates


def collect_lang_dealers() -> list[partial.Candidate]:
    html = partial.fetch_html(LANG_DENTAL_DEALERS)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    lines = [clean(line) for line in soup.get_text("\n").splitlines() if clean(line)]
    candidates: list[partial.Candidate] = []
    active = False
    country = "United States"
    states = {
        "Arizona",
        "California",
        "Florida",
        "Georgia",
        "Illinois",
        "Indiana",
        "Maryland",
        "Massachusetts",
        "Minnesota",
        "Mississippi",
        "Missouri",
        "New Jersey",
        "New York",
        "North Carolina",
        "Ohio",
        "Oklahoma",
        "Pennsylvania",
        "Puerto Rico",
        "Tennessee",
        "Texas",
        "Washington",
        "Wisconsin",
    }
    for line in lines:
        if line == "National Distributors":
            active = True
            continue
        if active and line.startswith("For international orders"):
            break
        if not active or line in states or re.search(r"^\d|^(T:|F:|Search by State|Home|US Distributors|NATIONAL DISTRIBUTORS)$", line):
            continue
        if line == "Puerto Rico":
            country = "Puerto Rico"
            continue
        name = non_generic_listing_name(line)
        if not name:
            continue
        row_obj = make_public_row(
            name=name,
            country=country,
            source_type="Lang Dental manufacturer dealer list (partial contact)",
            source_url=LANG_DENTAL_DEALERS,
            source_trust="medium-high",
            source_family="manufacturer_dealer_distributor_list",
            acquisition_path="Lang Dental US distributors/dealers 페이지에서 dealer/distributor 명칭을 확인",
            site_business_summary="Lang Dental dealer list에 등재된 치과 재료·기공 유통 채널 후보",
            evidence=[f"Lang Dental dealer list: {name}", f"Source page: {LANG_DENTAL_DEALERS}"],
            event="Lang Dental US Distributors",
            original_kind="round10_lang_dental_dealer_list",
        )
        add_candidate(candidates, row_obj, 34)
    return candidates


def collect_handler_distributors() -> list[partial.Candidate]:
    html = partial.fetch_html(HANDLER_DISTRIBUTORS)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[partial.Candidate] = []
    for item in soup.select("li"):
        text = clean(item.get_text(" ", strip=True))
        if "–" not in text and "-" not in text:
            continue
        website = first_href_url(item)
        if not website:
            continue
        name = non_generic_listing_name(re.split(r"\s+[–-]\s+", text, maxsplit=1)[0])
        if not name:
            continue
        row_obj = make_public_row(
            name=name,
            country="United States",
            source_type="Handler manufacturer dental distributor list (partial contact)",
            source_url=HANDLER_DISTRIBUTORS,
            source_trust="medium-high",
            source_family="manufacturer_dealer_distributor_list",
            acquisition_path="Handler MFG Dental Distributors 페이지에서 distributor 명칭과 웹사이트를 확인",
            site_business_summary="Handler MFG distributor list에 등재된 치과기공 장비·재료 유통 채널 후보",
            website=website,
            evidence=[f"Handler distributor list: {name}", f"Website link: {website}", f"Source page: {HANDLER_DISTRIBUTORS}"],
            event="Handler Dental Distributors",
            original_kind="round10_handler_manufacturer_distributor_list",
        )
        add_candidate(candidates, row_obj, 33)
    return candidates


def absolute_url(base_url: str, href: str) -> str:
    href = clean(href)
    if href.startswith(("http://", "https://")):
        return href
    parsed = urlparse(base_url)
    if href.startswith("/"):
        return f"{parsed.scheme}://{parsed.netloc}{href}"
    return f"{parsed.scheme}://{parsed.netloc}/{href}"


def collect_exportersindia() -> list[partial.Candidate]:
    candidates: list[partial.Candidate] = []
    seen: set[str] = set()
    for url in EXPORTERSINDIA_PAGES:
        html = partial.fetch_html(url)
        if not html:
            continue
        soup = BeautifulSoup(html, "html.parser")
        if "Dental Equipment" not in soup.get_text(" ", strip=True) and "Dental" not in url:
            continue
        for link in soup.select("h3._company a.com_nam"):
            name = non_generic_listing_name(link.get_text(" ", strip=True))
            if not name:
                continue
            profile_url = absolute_url(url, clean(link.get("href")))
            key = f"{name.lower()}|{profile_url.lower()}"
            if key in seen:
                continue
            seen.add(key)
            block = link.find_parent("div", class_="com_addOth") or link.find_parent("div", class_="com_address")
            address_node = block.select_one("._fAdre") if block else None
            address = clean(address_node.get_text(" ", strip=True)) if address_node else ""
            row_obj = make_public_row(
                name=name,
                country="India",
                source_type="ExportersIndia dental equipment supplier marketplace listing (partial contact)",
                source_url=profile_url,
                source_trust="low-medium",
                source_family="b2b_marketplace_dental_supplier_directory",
                acquisition_path="ExportersIndia dental equipment 지역/제품 페이지에서 supplier profile 명칭과 일부 지역 정보를 확인",
                site_business_summary="ExportersIndia dental equipment/products marketplace에 노출된 인도 치과 장비·재료 공급사 후보",
                address=address,
                evidence=[f"ExportersIndia dental supplier listing: {name}", f"Address snippet: {address or 'not shown'}", f"Source page: {url}", f"Profile: {profile_url}"],
                event="ExportersIndia Dental Supplier Marketplace",
                original_kind="round10_exportersindia_dental_marketplace",
            )
            add_candidate(candidates, row_obj, 74)
    return candidates


def indiamart_seller_name(text: str) -> str:
    text = clean(text)
    if len(text) > 160 or "•" not in text or "yrs" not in text:
        return ""
    match = re.match(r"(.{2,90}?)\s+[A-Z][A-Za-z .'-]+(?:,\s*[A-Za-z .'-]+)?\s+•\s+\d+\s+yrs\b", text)
    if not match:
        return ""
    name = non_generic_listing_name(match.group(1))
    if not name or re.search(r"^(TrustSEAL|Exporter|Manufacturer|Supplier)\b", name, re.I):
        return ""
    return name


def collect_indiamart() -> list[partial.Candidate]:
    candidates: list[partial.Candidate] = []
    seen: set[str] = set()
    for category, url in INDIAMART_PAGES:
        html = partial.fetch_html(url)
        if not html:
            continue
        soup = BeautifulSoup(html, "html.parser")
        title = clean(" ".join(node.get_text(" ", strip=True) for node in soup.select("h1")[:1]))
        if "Dental" not in title:
            continue
        for node in soup.select("div"):
            text = clean(node.get_text(" ", strip=True))
            name = indiamart_seller_name(text)
            if not name:
                continue
            key = f"{name.lower()}|{category.lower()}"
            if key in seen:
                continue
            seen.add(key)
            row_obj = make_public_row(
                name=name,
                country="India",
                source_type=f"IndiaMART {category} supplier marketplace listing (partial contact)",
                source_url=url,
                source_trust="low-medium",
                source_family="b2b_marketplace_dental_supplier_directory",
                acquisition_path=f"IndiaMART {category} category result에서 seller명과 지역/활동연수 노출을 확인",
                site_business_summary=f"IndiaMART {category} 카테고리에 노출된 인도 치과 장비·재료 공급사 후보",
                evidence=[f"IndiaMART seller listing: {name}", f"Listing text: {text[:220]}", f"Source page: {url}"],
                event=f"IndiaMART {category}",
                original_kind="round10_indiamart_dental_marketplace",
            )
            add_candidate(candidates, row_obj, 75)
    return candidates


def collect_round10_expanded_sources() -> list[partial.Candidate]:
    candidates: list[partial.Candidate] = []
    candidates.extend(collect_named_heading_page(url=SCOTTISH_DENTAL_SHOW, country="United Kingdom", source_type="Scottish Dental Show official exhibitor list (partial contact)", event="Scottish Dental Show", selector="h4", priority=31))
    candidates.extend(collect_named_heading_page(url=WESTERN_REGIONAL_2026, country="United States", source_type="Western Regional Dental Convention 2026 official exhibitor list (partial contact)", event="Western Regional Dental Convention 2026", selector="h4", priority=31))
    candidates.extend(collect_a2z_or_goeshow_table(AO_2026, "Academy of Osseointegration 2026", "United States"))
    for event, url, country in AAO_A2Z_PAGES:
        candidates.extend(collect_a2z_or_goeshow_table(url, event, country))
    candidates.extend(collect_dental_expo_nl())
    candidates.extend(collect_vda_showcase())
    candidates.extend(collect_ndda_nepal())
    candidates.extend(collect_dentsply_pdf())
    candidates.extend(collect_henry_schein_vendor_pdf())
    candidates.extend(collect_modern_dentistry_sa_pdf())
    candidates.extend(collect_lang_dealers())
    candidates.extend(collect_handler_distributors())
    candidates.extend(collect_dentistryregister_suppliers())
    candidates.extend(collect_regional_directory())
    candidates.extend(collect_medindexer())
    candidates.extend(collect_exportersindia())
    candidates.extend(collect_indiamart())
    return candidates


def search_duckduckgo(query: str, cache: dict[str, Any], limit: int) -> list[dict[str, str]]:
    cache_key = f"duckduckgo:{query}"
    with CACHE_LOCK:
        cached = cache.get(cache_key)
    if isinstance(cached, list):
        return cached[:limit]
    try:
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
        result = subprocess.run(
            ["curl", "-L", "--silent", "--show-error", "--max-time", "10", "--connect-timeout", "4", "-A", USER_AGENT, url],
            capture_output=True,
            timeout=12,
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


def build_queries(max_searches: int) -> list[dict[str, str]]:
    if max_searches <= 0:
        return []
    queries: list[dict[str, str]] = []
    site_patterns = [
        "",
        "site:kompass.com",
        "site:cybo.com",
        "site:europages.co.uk",
        "site:cylex",
        "site:yellow.place",
        "site:businesslist",
        "site:facebook.com",
        "site:linkedin.com/company",
    ]
    suffixes = ["", "company", "contact", "email", "yellow pages", "business directory"]
    for group in COUNTRY_GROUPS:
        for country in group["countries"]:
            for term in group["terms"]:
                for suffix in suffixes[:4]:
                    queries.append({"country": country, "query": clean(f"{term} {country} {suffix}")})
                for site in site_patterns[1:]:
                    queries.append({"country": country, "query": clean(f"{site} {term} {country}")})
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


def result_to_candidate(row: dict[str, str]) -> partial.Candidate | None:
    url = clean(row.get("url"))
    current_host = host(url)
    if not current_host or any(item in current_host for item in SKIP_HOST_HINTS):
        return None
    signal_blob = " ".join([clean(row.get("title")), clean(row.get("snippet")), url])
    if not DENTAL_RE.search(signal_blob):
        return None
    if not CHANNEL_RE.search(signal_blob) and not any(item in current_host for item in DIRECTORY_HOST_HINTS + SOCIAL_HOSTS):
        return None
    name = usable_search_name(clean(row.get("title")))
    if not name:
        return None
    source_type, trust, family, priority = source_trust_for_url(url)
    snippet = clean(row.get("snippet"))
    candidate = make_public_row(
        name=name,
        country=clean(row.get("country")),
        source_type=source_type,
        source_url=url,
        source_trust=trust,
        source_family=family,
        acquisition_path=(
            "현지어/영어 DuckDuckGo HTML 검색 결과에서 치과 유통·수입·수출·장비 공급 문맥을 확인. "
            "Facebook/LinkedIn은 로그인 없는 공개 title/snippet만 쓰므로 낮은 신뢰도로 표기"
        ),
        site_business_summary=snippet[:420] or "치과 유통·공급·수출입 키워드가 공개 검색 결과에 노출된 후보",
        website="" if any(item in current_host for item in SOCIAL_HOSTS) else url,
        evidence=[
            f"Query: {clean(row.get('query'))}",
            f"Search title: {clean(row.get('title'))}",
            f"Snippet: {snippet[:260]}",
            f"Host: {current_host}",
        ],
        original_kind="round10_duckduckgo_public_search_result",
    )
    return partial.Candidate(row=candidate, priority=priority)


def collect_search_candidates(max_searches: int, results_per_query: int, target_candidates: int, pause: float) -> tuple[list[partial.Candidate], int]:
    cache = load_json(SEARCH_CACHE_JSON, {})
    candidates: list[partial.Candidate] = []
    raw_rows: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    queries = build_queries(max_searches)
    for index, query_row in enumerate(queries, start=1):
        results = search_duckduckgo(query_row["query"], cache, results_per_query)
        enriched = [{**row, "country": query_row["country"]} for row in results]
        raw_rows.extend({"kind": "round10_search_result", **row} for row in enriched)
        for row in enriched:
            url = clean(row.get("url"))
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            candidate = result_to_candidate(row)
            if candidate:
                candidates.append(candidate)
                raw_rows.append({"kind": "round10_search_candidate", **candidate.row})
        if index % 25 == 0:
            append_jsonl(SEARCH_RAW_JSONL, raw_rows)
            raw_rows = []
            save_json(SEARCH_CACHE_JSON, cache)
            print(json.dumps({"search_index": index, "queries": len(queries), "candidates": len(candidates), "seen_urls": len(seen_urls)}, ensure_ascii=False), flush=True)
        if len(candidates) >= target_candidates:
            break
        time.sleep(pause)
    append_jsonl(SEARCH_RAW_JSONL, raw_rows)
    save_json(SEARCH_CACHE_JSON, cache)
    return candidates, min(index if queries else 0, len(queries))


def write_summary(
    *,
    backup_path: Path,
    before_count: int,
    after_count: int,
    selected: list[dict[str, Any]],
    candidates: list[partial.Candidate],
    query_count: int,
) -> None:
    source_counts = Counter(row["source_type"] for row in selected)
    trust_counts = Counter((row.get("tags") or {}).get("source_trust", "") for row in selected)
    completeness_counts = Counter((row.get("tags") or {}).get("contact_completeness", "") for row in selected)
    country_counts = Counter(row.get("country") or "Unknown" for row in selected)
    lines = [
        "# Round 10 non-OSM partial dental distributor/vendor expansion",
        "",
        "## Result",
        f"- Baseline backup: `{backup_path}`",
        f"- Complete dataset rows before: {before_count:,}",
        f"- Added rows this round: {len(selected):,}",
        f"- Complete dataset rows after: {after_count:,}",
        f"- Candidate pool before dedupe: {len(candidates):,}",
        f"- DuckDuckGo HTML queries executed/read from cache: {query_count:,}",
        "",
        "## Trust model",
        "- medium-high: official exhibition list/table/heading pages where the exhibitor identity is directly exposed.",
        "- low-medium: localized yellow-page/business-directory/search snippets mentioning dental distribution, supply, import/export, or equipment.",
        "- low: Facebook/LinkedIn public title/snippet only; use as a lead signal, not verified contact data.",
        "",
        "## Added by source",
    ]
    for source, count in source_counts.most_common():
        lines.append(f"- {source}: {count:,}")
    lines += ["", "## Added by source trust"]
    for trust, count in trust_counts.most_common():
        lines.append(f"- {trust}: {count:,}")
    lines += ["", "## Added by contact completeness"]
    for completeness, count in completeness_counts.most_common():
        lines.append(f"- {completeness}: {count:,}")
    lines += ["", "## Top countries"]
    for country, count in country_counts.most_common(40):
        lines.append(f"- {country}: {count:,}")
    lines += [
        "",
        "## Source URLs used directly",
        f"- Dental Expo CEDE 2026 exhibitors: {CEDE_2026}",
        f"- Southwest Dental Conference 2026 exhibitors: {SWDC_2026}",
        f"- BDIA Dental Showcase 2026 exhibitors: {BDIA_2026}",
        f"- LMT company directory: {LMT_COMPANIES}",
        *[f"- {event}: {url}" for event, url in LMT_SHOWS],
        f"- BDIA member directory API: {BDIA_MEMBER_API}",
        f"- ADIA Australia member directory: {ADIA_MEMBERS}",
        f"- SADTO South Africa company directory: {SADTO_COMPANIES}",
        *[f"- {event}: {url}" for event, url, _country in GERMAN_PAVILION_PAGES],
        f"- Scottish Dental Show exhibitors: {SCOTTISH_DENTAL_SHOW}",
        f"- Western Regional Dental Convention 2026 exhibitors: {WESTERN_REGIONAL_2026}",
        f"- Academy of Osseointegration 2026 exhibitor list: {AO_2026}",
        *[f"- {event}: {url}" for event, url, _country in AAO_A2Z_PAGES],
        f"- Dental Expo Netherlands exhibitors: {DENTAL_EXPO_NL}",
        f"- Virginia Dental Showcase exhibitors: {VDA_SHOWCASE}",
        f"- Nepal Dental Distributor's Association member directory: {NDDA_NEPAL}",
        f"- DentistryRegister supplier directory: {DENTISTRYREGISTER_SUPPLIERS}",
        f"- RegionalDirectory Dental Products directory: {REGIONAL_DIRECTORY_DENTAL_PRODUCTS}",
        *[f"- MedIndexer {category}: {url}" for category, url in MEDINDEXER_CATEGORIES],
        f"- DENTSPLY authorized distributor PDF: {DENTSPLY_DISTRIBUTOR_PDF}",
        f"- Henry Schein authorized equipment vendor PDF: {HENRY_SCHEIN_VENDOR_PDF}",
        f"- Modern Dentistry South Africa Dental Directory PDF: {MODERN_DENTISTRY_SA_DIRECTORY_PDF}",
        f"- Lang Dental dealer list: {LANG_DENTAL_DEALERS}",
        f"- Handler Dental Distributors: {HANDLER_DISTRIBUTORS}",
        "- ExportersIndia dental supplier marketplace pages:",
        *[f"  - {url}" for url in EXPORTERSINDIA_PAGES],
        "- IndiaMART dental supplier marketplace pages:",
        *[f"  - {category}: {url}" for category, url in INDIAMART_PAGES],
        "- Localized search sources: DuckDuckGo HTML result pages for country-language dental distributor/import/export queries, including yellow-page, business-directory, Facebook, and LinkedIn public snippets.",
        "",
        "## Notes",
        "- This file intentionally includes partial-contact/source-only rows. Direct outreach should prioritize medium-high and low-medium rows before low-trust social snippets.",
        "- Existing rows were preserved. New rows were deduped against the current complete dataset by email, company+website, company+address, or company+country+source URL.",
        "- OSM was not used as an acquisition source in this round.",
    ]
    SUMMARY_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-additional", type=int, default=3000)
    parser.add_argument("--max-searches", type=int, default=1400)
    parser.add_argument("--results-per-query", type=int, default=12)
    parser.add_argument("--search-pause", type=float, default=0.05)
    args = parser.parse_args()

    complete_rows = partial.read_jsonl(COMPLETE_JSONL)
    before_count = len(complete_rows)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = BACKUP_DIR / f"prospects_augmented_contact_complete.before_partial_round10_{stamp}.jsonl"
    shutil.copy2(COMPLETE_JSONL, backup_path)

    existing_keys = {partial.row_business_key(row) for row in complete_rows if partial.row_business_key(row)}
    publisher_keys = {partial.publisher_dedupe_key(row) for row in complete_rows if partial.publisher_dedupe_key(row)}

    candidates: list[partial.Candidate] = []
    official_candidates = collect_official_event_pages()
    candidates.extend(official_candidates)
    print(json.dumps({"collector": "official_event_pages", "candidates": len(official_candidates)}, ensure_ascii=False), flush=True)

    direct_candidates = collect_direct_association_pages()
    candidates.extend(direct_candidates)
    print(json.dumps({"collector": "direct_association_pages", "candidates": len(direct_candidates)}, ensure_ascii=False), flush=True)

    expanded_candidates = collect_round10_expanded_sources()
    candidates.extend(expanded_candidates)
    print(json.dumps({"collector": "expanded_direct_sources", "candidates": len(expanded_candidates)}, ensure_ascii=False), flush=True)

    search_candidates, query_count = collect_search_candidates(
        max_searches=args.max_searches,
        results_per_query=args.results_per_query,
        target_candidates=args.target_additional * 3,
        pause=args.search_pause,
    )
    candidates.extend(search_candidates)
    print(json.dumps({"collector": "localized_public_search", "candidates": len(search_candidates), "query_count": query_count}, ensure_ascii=False), flush=True)

    selected = unique_round10_candidates(candidates, complete_rows, existing_keys, publisher_keys, args.target_additional)
    complete_rows.extend(selected)
    partial.write_jsonl(COMPLETE_JSONL, complete_rows)
    partial.write_csv(COMPLETE_CSV, complete_rows)
    partial.write_jsonl(PROMOTIONS_JSONL, selected)
    write_summary(
        backup_path=backup_path,
        before_count=before_count,
        after_count=len(complete_rows),
        selected=selected,
        candidates=candidates,
        query_count=query_count,
    )
    result = {
        "backup": str(backup_path),
        "beforeRows": before_count,
        "addedRows": len(selected),
        "afterRows": len(complete_rows),
        "summaryMd": str(SUMMARY_MD),
        "promotionsJsonl": str(PROMOTIONS_JSONL),
        "searchRawJsonl": str(SEARCH_RAW_JSONL),
        "queryCount": query_count,
        "candidatePool": len(candidates),
        "sourceCounts": dict(Counter(row["source_type"] for row in selected).most_common()),
        "trustCounts": dict(Counter((row.get("tags") or {}).get("source_trust", "") for row in selected).most_common()),
        "contactCompletenessCounts": dict(Counter((row.get("tags") or {}).get("contact_completeness", "") for row in selected).most_common()),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
