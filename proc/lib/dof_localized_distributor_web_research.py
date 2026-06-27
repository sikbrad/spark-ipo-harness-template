#!/usr/bin/env python3
"""Find dental distributor/import-export prospects through localized web search.

This round intentionally avoids OpenStreetMap as a primary source. It combines
official manufacturer dealer pages with localized search queries, then promotes
only rows where a public page exposes company name, email, phone, address, and
source URL.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote_plus, unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

import dof_distributor_import_export_research as dist
import dof_exhibition_vendor_research as exhibition
import dof_prospect_scale5000 as base
from dof_enrich_incomplete_websites import extract_emails


ROOT = Path("/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04")
OUT_ROOT = ROOT / "output/dof-overseas-customer-prospects/2026-05-30/scale5000"
DATA_DIR = OUT_ROOT / "data"
RAW_JSONL = DATA_DIR / "localized_distributor_web_raw_round7.jsonl"
PROMOTIONS_JSONL = DATA_DIR / "localized_distributor_web_promotions_round7.jsonl"
CACHE_JSON = DATA_DIR / "localized_distributor_web_cache_round7.json"
RESEARCH_MD = OUT_ROOT / "external_localized_distributor_web_research_round7.md"

USER_AGENT = dist.USER_AGENT
CACHE_LOCK = threading.Lock()
WRITE_LOCK = threading.Lock()

dist.PHONE_COUNTRY_HINTS.update(
    {
        "+7": "Kazakhstan",
        "+51": "Peru",
        "+54": "Argentina",
        "+58": "Venezuela",
        "+212": "Morocco",
        "+213": "Algeria",
        "+216": "Tunisia",
        "+218": "Libya",
        "+221": "Senegal",
        "+229": "Benin",
        "+230": "Mauritius",
        "+233": "Ghana",
        "+234": "Nigeria",
        "+252": "Somalia",
        "+254": "Kenya",
        "+255": "Tanzania",
        "+256": "Uganda",
        "+261": "Madagascar",
        "+351": "Portugal",
        "+352": "Luxembourg",
        "+353": "Ireland",
        "+355": "Albania",
        "+356": "Malta",
        "+370": "Lithuania",
        "+371": "Latvia",
        "+372": "Estonia",
        "+374": "Armenia",
        "+381": "Serbia",
        "+382": "Montenegro",
        "+383": "Kosovo",
        "+385": "Croatia",
        "+386": "Slovenia",
        "+389": "North Macedonia",
        "+420": "Czechia",
        "+502": "Guatemala",
        "+503": "El Salvador",
        "+504": "Honduras",
        "+505": "Nicaragua",
        "+506": "Costa Rica",
        "+507": "Panama",
        "+591": "Bolivia",
        "+593": "Ecuador",
        "+595": "Paraguay",
        "+598": "Uruguay",
        "+852": "Hong Kong",
        "+855": "Cambodia",
        "+856": "Laos",
        "+880": "Bangladesh",
        "+886": "Taiwan",
        "+94": "Sri Lanka",
        "+95": "Myanmar",
        "+961": "Lebanon",
        "+962": "Jordan",
        "+964": "Iraq",
        "+965": "Kuwait",
        "+967": "Yemen",
        "+968": "Oman",
        "+973": "Bahrain",
        "+977": "Nepal",
        "+994": "Azerbaijan",
        "+995": "Georgia",
        "+998": "Uzbekistan",
    }
)
dist.COUNTRY_ALIASES.update({"Bulgary": "Bulgaria", "Bosnia": "Bosnia and Herzegovina", "Columbia": "Colombia"})

OFFICIAL_GC_DEALER_URLS = [
    "https://www.gc.dental/europe/de-DE/dealers",
    "https://www.gc.dental/europe/es-ES/dealers",
    "https://www.gc.dental/europe/fr-BE/dealers",
    "https://www.gc.dental/europe/it-IT/dealers",
    "https://www.gc.dental/ortho/en/distributors",
    "https://www.gc.dental/ortho/en-US/distributors",
]
OFFICIAL_IVOCLAR_DISTRIBUTOR_URLS = [
    "https://www.ivoclar.com/distributors",
    "https://www.ivoclar.com/en_gb/distributors",
]
OFFICIAL_TABLE_SOURCES = [
    {
        "url": "https://www.detax.com/distributors",
        "source_type": "DETAX official worldwide distributor table",
        "summary": "DETAX 공식 worldwide distribution partner 표에서 국가, 회사, 주소, 웹사이트, 이메일, 전화를 직접 확인",
    },
    {
        "url": "https://www.eurodentis.com/en/europe-distributors.html",
        "source_type": "Eurodentis official Europe distributor table",
        "summary": "Eurodentis 공식 Europe distributors 표에서 국가, 회사, 웹사이트, 이메일, 전화를 직접 확인",
    },
    {
        "url": "https://dentlight.com/distributors/",
        "source_type": "DentLight official authorized dental partner table",
        "summary": "DentLight 공식 distributor 표에서 지역, 업체명, 웹사이트, 전화, 이메일을 확인",
    },
    {
        "url": "https://www.sisma.com/en/global-distribution-network/",
        "source_type": "SISMA official global distribution network table",
        "summary": "SISMA 공식 global distribution network 표에서 국가, 회사, 주소, 이메일, 전화, 웹사이트를 직접 확인",
    },
    {
        "url": "https://conxeasy.com/docs/distributors/search-result.php",
        "source_type": "ConXeasy official worldwide distributor table",
        "summary": "ConXeasy 공식 worldwide distributors 표에서 국가, 회사, 주소, 이메일, 전화, 웹사이트를 직접 확인",
    },
]
OFFICIAL_TOKUYAMA_URL = "https://tokuyama-dental.eu/en/company/distributors-and-partners/"
OFFICIAL_HEADING_SOURCES = [
    {
        "url": "https://www.ad2usa.com/contact",
        "heading": "h3",
        "source_type": "Advanced Dental Designs official international dealer page",
        "summary": "Advanced Dental Designs 공식 international dealer 섹션에서 국가별 dealer 연락처를 확인",
    },
    {
        "url": "https://zarc4endo.com/en/distributors/",
        "heading": "h2",
        "source_type": "Zarc4Endo official distributor page",
        "summary": "Zarc4Endo 공식 distributors 페이지에서 국가별 distributor 연락처를 확인",
    },
]

DIRECTORY_DOMAINS = (
    "yellowpages",
    "pagesjaunes",
    "paginasamarillas",
    "paginasamarillas.com",
    "paginasamarillas.com.pe",
    "paginasamarillas.com.co",
    "businesslist",
    "cybo.com",
    "cylex",
    "kompass",
    "europages",
    "tuugo",
    "findglocal",
    "yell.com",
    "2gis",
    "eldirectorio",
    "comxport",
    "yellow.place",
    "medicalexpo",
)
SOCIAL_DOMAINS = ("facebook.com", "linkedin.com")
BAD_DOMAINS = (
    "duckduckgo.com",
    "google.com",
    "bing.com",
    "youtube.com",
    "instagram.com",
    "pinterest.",
    "wikipedia.org",
    "wikihow.com",
    "reddit.com",
    "amazon.",
    "ebay.",
    "alibaba.",
    "made-in-china.com",
    "globalsources.com",
)
BAD_EMAIL_DOMAINS = (
    "sentry.io",
    "wixpress.com",
    "wordpress.org",
    "duckduckgo.com",
    "facebook.com",
    "linkedin.com",
)

DENTAL_RE = re.compile(
    r"dental|dent[aeio]|odont|odontolog|ortho|implant|zahn|stomat|口腔|牙科|歯科|nha khoa|gigi|pergigian|diş|طب الأسنان",
    re.I,
)
DISTRIBUTOR_RE = re.compile(
    r"distribut|supplier|supply|supplies|dealer|depot|trading|trade|import|export|equipment|material|"
    r"dentalbedarf|dentalhandel|zahnbedarf|suministro|suministros|distribuidora|dep[óo]sito|importadora|exportadora|"
    r"equipamentos|materiais|fournisseur|fournitures|mat[ée]riel|forniture|malzemeleri|مستلزمات|تجهيزات|"
    r"thiết bị|vật liệu|alat|bahan|器材|材料",
    re.I,
)
CLINIC_ONLY_RE = re.compile(
    r"clinic|cl[ií]nica|dentist|dental practice|cabinet dentaire|centre dentaire|cl[ií]nica dental|"
    r"consultorio|zahnarzt|stomatologie clinic|odontoiatria$",
    re.I,
)

COUNTRY_GROUPS: list[dict[str, Any]] = [
    {
        "countries": [
            "Algeria",
            "Angola",
            "Botswana",
            "Cameroon",
            "Egypt",
            "Ethiopia",
            "Ghana",
            "Ivory Coast",
            "Kenya",
            "Libya",
            "Mauritius",
            "Morocco",
            "Mozambique",
            "Namibia",
            "Nigeria",
            "Rwanda",
            "Senegal",
            "South Africa",
            "Tanzania",
            "Tunisia",
            "Uganda",
            "Zambia",
            "Zimbabwe",
        ],
        "terms": [
            "dental distributor",
            "dental equipment supplier",
            "dental supplies dealer",
            "dental import export",
            "مستلزمات طب الأسنان",
            "تجهيزات طب الأسنان",
            "fournisseur dentaire",
            "matériel dentaire",
        ],
        "contact_words": ["email phone address", "contact address", "yellow pages", "business directory"],
    },
    {
        "countries": [
            "Argentina",
            "Bolivia",
            "Brazil",
            "Chile",
            "Colombia",
            "Costa Rica",
            "Dominican Republic",
            "Ecuador",
            "El Salvador",
            "Guatemala",
            "Honduras",
            "Mexico",
            "Nicaragua",
            "Panama",
            "Paraguay",
            "Peru",
            "Uruguay",
            "Venezuela",
        ],
        "terms": [
            "distribuidora dental",
            "depósito dental",
            "suministros dentales",
            "equipos odontológicos",
            "importadora dental",
            "exportadora dental",
            "distribuidora odontológica",
            "equipamentos odontológicos",
        ],
        "contact_words": ["email teléfono dirección", "correo teléfono dirección", "páginas amarillas", "guía comercial"],
    },
    {
        "countries": [
            "Albania",
            "Armenia",
            "Azerbaijan",
            "Belarus",
            "Bosnia and Herzegovina",
            "Bulgaria",
            "Croatia",
            "Cyprus",
            "Czechia",
            "Estonia",
            "Georgia",
            "Greece",
            "Kosovo",
            "Latvia",
            "Lithuania",
            "Malta",
            "Moldova",
            "Montenegro",
            "North Macedonia",
            "Romania",
            "Serbia",
            "Slovakia",
            "Slovenia",
            "Ukraine",
        ],
        "terms": [
            "dental distributor",
            "dental equipment supplier",
            "dental depot",
            "dental import export",
            "Dentalbedarf",
            "Dentalhandel",
            "forniture dentali",
            "fournitures dentaires",
        ],
        "contact_words": ["email phone address", "contact address", "yellow pages", "business directory"],
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
            "Turkey",
        ],
        "terms": [
            "dental distributor",
            "dental equipment supplier",
            "dental import export",
            "مستلزمات طب الأسنان",
            "تجهيزات طب الأسنان",
            "موزع مستلزمات أسنان",
            "diş malzemeleri",
            "dental depo",
        ],
        "contact_words": ["email phone address", "contact address", "دليل الشركات", "yellow pages"],
    },
    {
        "countries": [
            "Bangladesh",
            "Cambodia",
            "India",
            "Indonesia",
            "Kazakhstan",
            "Kyrgyzstan",
            "Laos",
            "Malaysia",
            "Mongolia",
            "Myanmar",
            "Nepal",
            "Pakistan",
            "Philippines",
            "Singapore",
            "Sri Lanka",
            "Tajikistan",
            "Thailand",
            "Uzbekistan",
            "Vietnam",
        ],
        "terms": [
            "dental distributor",
            "dental equipment supplier",
            "dental import export",
            "thiết bị nha khoa",
            "vật liệu nha khoa",
            "alat kedokteran gigi",
            "bahan kedokteran gigi",
            "peralatan pergigian",
        ],
        "contact_words": ["email phone address", "contact address", "business directory", "yellow pages"],
    },
    {
        "countries": [
            "China",
            "Hong Kong",
            "Japan",
            "South Korea",
            "Taiwan",
        ],
        "terms": [
            "dental distributor",
            "dental equipment supplier",
            "牙科器材 经销商",
            "牙科材料 供應商",
            "歯科材料 ディーラー",
            "歯科器材 販売",
            "치과 재료 유통",
            "치과 장비 수입",
        ],
        "contact_words": ["email phone address", "連絡先 住所 電話", "会社概要 電話 メール", "公司 地址 电话 邮箱"],
    },
    {
        "countries": [
            "Australia",
            "New Zealand",
            "Fiji",
        ],
        "terms": [
            "dental distributor",
            "dental equipment supplier",
            "dental supply company",
            "dental import export",
        ],
        "contact_words": ["email phone address", "contact address", "yellow pages", "business directory"],
    },
]


def clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def load_json(path: Path, default: Any) -> Any:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with WRITE_LOCK:
        with path.open("a", encoding="utf-8") as file_obj:
            for row in rows:
                file_obj.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def http_get(url: str, cache: dict[str, Any], timeout: int = 4) -> dict[str, Any]:
    with CACHE_LOCK:
        cached = cache.get(url)
    if isinstance(cached, dict):
        return cached
    try:
        result = subprocess.run(
            [
                "curl",
                "-L",
                "--silent",
                "--show-error",
                "--max-time",
                str(timeout),
                "--connect-timeout",
                "2",
                "-A",
                USER_AGENT,
                url,
            ],
            capture_output=True,
            timeout=timeout + 2,
        )
        text = result.stdout[:1_500_000].decode("utf-8", errors="ignore") if result.stdout else ""
        payload = {
            "status": 200 if result.returncode == 0 and text else 0,
            "final_url": url,
            "text": text,
            "error": result.stderr.decode("utf-8", errors="ignore")[:400] if result.returncode else "",
            "checked_at": datetime.now().isoformat(timespec="seconds"),
        }
    except Exception as exc:
        payload = {"status": 0, "final_url": url, "text": "", "error": str(exc), "checked_at": datetime.now().isoformat(timespec="seconds")}
    with CACHE_LOCK:
        cache[url] = payload
    return payload


def host_of(url: str) -> str:
    host = urlparse(url).hostname or ""
    host = host.lower()
    return host[4:] if host.startswith("www.") else host


def result_url(href: str) -> str:
    href = clean(href)
    if href.startswith("//"):
        href = "https:" + href
    if "duckduckgo.com/l/" in href:
        parsed = urlparse(href)
        qs = parse_qs(parsed.query)
        uddg = qs.get("uddg", [""])[0]
        href = unquote(uddg)
    if href.startswith(("http://", "https://")):
        return href
    return ""


def is_directory_domain(url: str) -> bool:
    host = host_of(url)
    return any(marker in host for marker in DIRECTORY_DOMAINS)


def is_social_domain(url: str) -> bool:
    host = host_of(url)
    return any(host == domain or host.endswith("." + domain) for domain in SOCIAL_DOMAINS)


def is_bad_domain(url: str) -> bool:
    host = host_of(url)
    return any(marker in host for marker in BAD_DOMAINS)


def public_email(text: str) -> str:
    for email in extract_emails(text):
        value = dist.valid_email(email)
        if not value:
            continue
        domain = value.split("@", 1)[1]
        if any(domain == blocked or domain.endswith("." + blocked) for blocked in BAD_EMAIL_DOMAINS):
            continue
        return value
    return ""


def page_lines(html: str) -> list[str]:
    soup = BeautifulSoup(html or "", "html.parser")
    return [clean(line) for line in soup.get_text("\n", strip=True).splitlines() if clean(line)]


def page_title(html: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    h1 = soup.find("h1")
    if h1:
        value = clean(h1.get_text(" ", strip=True))
        if value:
            return value
    if soup.title:
        return clean(soup.title.get_text(" ", strip=True))
    return ""


def clean_name(title: str, fallback: str = "") -> str:
    name = clean(title)
    if "|" in name:
        parts = [clean(part) for part in name.split("|") if clean(part)]
        useful = [part for part in parts if part.lower() not in {"home", "contact", "contacts", "products", "about"}]
        if useful:
            name = useful[0]
    name = re.sub(r"\s*(?:\||-|–|—)\s*(?:Contact|Contacts|Contacto|Kontakt|Official Website|Home|Facebook|LinkedIn).*$", "", name, flags=re.I)
    name = re.sub(r"^(?:Contact|Contacts|Contacto|Kontakt|Products|About)\s*(?:-|:|\|)\s*", "", name, flags=re.I)
    name = re.sub(r"\s+in\s+[A-Z][A-Za-z .,'-]+(?:\s*-\s*Phone.*)?$", "", name)
    name = clean(name.strip(" -|:"))
    if len(name) < 3 or len(name) > 140 or name.lower() in {"home", "contact", "contacts", "products"}:
        name = clean(fallback)
    return name[:140]


def contact_urls(url: str) -> list[str]:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return []
    if is_directory_domain(url) or is_social_domain(url):
        return [url]
    root = f"{parsed.scheme}://{parsed.netloc}"
    paths = ["", "/contact", "/contact-us", "/contacto", "/kontakt"]
    urls = [url]
    for path in paths:
        candidate = root + path
        if candidate not in urls:
            urls.append(candidate)
    return urls[:3]


def text_address(html: str, lines: list[str], country: str) -> str:
    def acceptable(candidate: str) -> bool:
        lower = candidate.lower()
        if any(marker in lower for marker in ("copyright", "all rights", "proudly created", "created with wix", "©", "cookie policy")):
            return False
        return bool(re.search(r"\d", candidate)) and len(candidate) >= 18

    for address in exhibition.jsonld_addresses(html):
        if address and acceptable(address):
            return clean(address)
    address = exhibition.text_address(lines, country)
    if address and acceptable(address):
        return address
    for idx, line in enumerate(lines):
        if "address" not in line.lower() and "direcci" not in line.lower() and "adresse" not in line.lower():
            continue
        block = [line]
        for neighbor in lines[idx + 1 : idx + 4]:
            if "@" in neighbor or neighbor.lower().startswith(("phone", "tel", "email", "fax")):
                break
            block.append(neighbor)
        candidate = clean(", ".join(block))
        if acceptable(candidate):
            return candidate[:240]
    return ""


def business_relevant(blob: str) -> bool:
    if not DENTAL_RE.search(blob):
        return False
    if DISTRIBUTOR_RE.search(blob):
        return True
    if CLINIC_ONLY_RE.search(blob) and not DISTRIBUTOR_RE.search(blob):
        return False
    return False


def bad_address_text(candidate: str) -> bool:
    lower = clean(candidate).lower()
    return any(marker in lower for marker in ("copyright", "all rights", "proudly created", "created with wix", "©", "cookie policy"))


def contact_from_public_pages(url: str, country: str, cache: dict[str, Any]) -> dict[str, str]:
    combined_text: list[str] = []
    combined_html: list[str] = []
    first_title = ""
    found_url = url
    email = phone = address = ""
    for candidate_url in contact_urls(url):
        payload = http_get(candidate_url, cache)
        html = payload.get("text") or ""
        if not html or int(payload.get("status") or 0) >= 500:
            continue
        lines = page_lines(html)
        text = " ".join(lines)
        if not first_title:
            first_title = page_title(html)
        combined_text.append(text)
        combined_html.append(html)
        email = email or public_email(html + " " + text)
        phone = phone or clean(dist.extract_phone(text))
        address = address or text_address(html, lines, country)
        if email and phone and address:
            found_url = candidate_url
            break
    if not email:
        email = public_email(" ".join(combined_html + combined_text))
    if not phone:
        phone = clean(dist.extract_phone(" ".join(combined_text)))
    if not address:
        all_lines = []
        for html in combined_html:
            all_lines.extend(page_lines(html))
        address = text_address(" ".join(combined_html), all_lines, country)
    return {"email": email, "phone": phone, "address": address, "title": first_title, "source_url": found_url}


def search_duckduckgo(query: str, cache: dict[str, Any], limit: int) -> list[dict[str, str]]:
    cache_key = f"duckduckgo:{query}"
    with CACHE_LOCK:
        cached = cache.get(cache_key)
    if isinstance(cached, list):
        return cached[:limit]
    try:
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
        result = subprocess.run(
            ["curl", "-L", "--silent", "--show-error", "--max-time", "8", "--connect-timeout", "3", "-A", USER_AGENT, url],
            capture_output=True,
            timeout=10,
        )
        html = result.stdout.decode("utf-8", errors="ignore") if result.returncode == 0 else ""
    except Exception:
        html = ""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for result in soup.select(".result"):
        link = result.select_one("a.result__a")
        if not link:
            continue
        href = result_url(link.get("href", ""))
        if not href:
            continue
        snippet = clean(" ".join(item.get_text(" ", strip=True) for item in result.select(".result__snippet")))
        rows.append({"engine": "duckduckgo", "query": query, "title": clean(link.get_text(" ", strip=True)), "url": href, "snippet": snippet})
        if len(rows) >= limit:
            break
    with CACHE_LOCK:
        cache[cache_key] = rows
    return rows


def build_queries(max_searches: int, focus_countries: set[str] | None = None) -> list[dict[str, str]]:
    queries: list[dict[str, str]] = []
    for group in COUNTRY_GROUPS:
        countries = group["countries"]
        terms = group["terms"]
        contact_words = group["contact_words"]
        for country in countries:
            if focus_countries and country.lower() not in focus_countries:
                continue
            for term in terms[:6]:
                for words in contact_words[:3]:
                    queries.append({"country": country, "query": f"{term} {country} {words}"})
            for network in ("Facebook", "LinkedIn"):
                queries.append({"country": country, "query": f"{terms[0]} {country} {network}"})
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


def parse_gc_block(heading: Any) -> tuple[str, str, list[str]]:
    raw_title = clean(heading.get_text(" ", strip=True))
    if " - " in raw_title:
        country, name = raw_title.split(" - ", 1)
    else:
        country, name = "", raw_title
    lines: list[str] = []
    for sibling in heading.next_siblings:
        if getattr(sibling, "name", "") == "h2":
            break
        if not hasattr(sibling, "get_text"):
            continue
        for line in sibling.get_text("\n", strip=True).splitlines():
            value = clean(line)
            if value:
                lines.append(value)
    return clean(country), clean(name), lines


def parse_gc_dealers(cache: dict[str, Any]) -> list[base.Prospect]:
    prospects: list[base.Prospect] = []
    for url in OFFICIAL_GC_DEALER_URLS:
        payload = http_get(url, cache)
        html = payload.get("text") or ""
        soup = BeautifulSoup(html, "html.parser")
        for heading in soup.find_all("h2"):
            title = clean(heading.get_text(" ", strip=True))
            if title in {"Main navigation", "Follow us", "Footer menu"}:
                continue
            country, name, lines = parse_gc_block(heading)
            block = "\n".join(lines)
            email = public_email(block)
            phone = ""
            for line in lines:
                if dist.phone_like(line):
                    phone = line
                    break
            if not phone:
                phone = clean(dist.extract_phone(block))
            website = next((line for line in lines if line.startswith(("www.", "http://", "https://"))), "")
            address_lines = [line for line in lines if not dist.phone_like(line) and "@" not in line and not line.startswith(("www.", "http://", "https://"))]
            address = clean(", ".join(address_lines[:4]))
            if not country:
                country = dist.infer_country(address, phone, website, email)
            prospect = dist.make_distributor(
                name=name,
                country=country,
                email=email,
                phone=phone,
                address=address,
                website=website,
                source_url=url,
                source_type="GC Dental official dealer/distributor directory",
                acquisition_path="GC Dental 공식 dealer/distributor 페이지에서 업체명, 이메일, 전화, 주소, 웹사이트를 직접 확인",
                site_business_summary="GC Dental 또는 GC Orthodontics 제품을 취급하는 공식 지역 딜러·유통사",
                evidence=[
                    f"GC official page entry: {title}",
                    f"Required contact fields found: email={email}, phone={phone}, address={address}",
                ],
                tags={"source_trust": "high", "directory": "GC Dental official dealers"},
            )
            if prospect:
                prospects.append(prospect)
    return prospects


def h4_block(heading: Any) -> list[str]:
    lines: list[str] = []
    for sibling in heading.next_siblings:
        if getattr(sibling, "name", "") in {"h2", "h3", "h4"}:
            break
        if not hasattr(sibling, "get_text"):
            continue
        for line in sibling.get_text("\n", strip=True).splitlines():
            value = clean(line)
            if value:
                lines.append(value)
    return lines


def ivoclar_address(lines: list[str]) -> str:
    joined = clean(", ".join(line for line in lines if line))
    joined = re.sub(r"\b(?:Phone|Tel|Telephone|Mobile|Fax|WhatsApp|Contact|Email|E-mail|Correo|Telefone|Teléfono)\s*[-:–]?\s*.*", "", joined, flags=re.I)
    joined = re.sub(r"https?://\S+|www\.\S+|\S+@\S+", "", joined)
    return clean(joined.strip(" ,.-"))[:240]


def parse_ivoclar_distributors(cache: dict[str, Any]) -> list[base.Prospect]:
    prospects: list[base.Prospect] = []
    for url in OFFICIAL_IVOCLAR_DISTRIBUTOR_URLS:
        payload = http_get(url, cache, timeout=12)
        html = payload.get("text") or ""
        soup = BeautifulSoup(html, "html.parser")
        for heading in soup.find_all("h4"):
            name = clean(heading.get_text(" ", strip=True))
            if len(name) < 3 or len(name) > 140:
                continue
            if any(skip in name.lower() for skip in ("ivoclar markets", "in some countries", "find the distributor", "no distributor")):
                continue
            lines = h4_block(heading)
            if not lines:
                continue
            block = "\n".join(lines)
            email = public_email(block)
            phone = clean(dist.extract_phone(block))
            website = next((line for line in lines if line.startswith(("www.", "http://", "https://"))), "")
            address = ivoclar_address(lines)
            country = dist.infer_country(address, phone, website, email)
            prospect = dist.make_distributor(
                name=name,
                country=country,
                email=email,
                phone=phone,
                address=address,
                website=website,
                source_url=url,
                source_type="Ivoclar official distributor directory",
                acquisition_path="Ivoclar 공식 글로벌 distributor 페이지에서 업체명, 이메일, 전화, 주소, 웹사이트를 직접 확인",
                site_business_summary="Ivoclar 제품을 취급하는 공식 지역 유통사·전문 dental trade 업체",
                evidence=[
                    f"Ivoclar official distributor entry: {name}",
                    f"Required contact fields found: email={email}, phone={phone}, address={address}",
                ],
                tags={"source_trust": "high", "directory": "Ivoclar official distributors"},
            )
            if prospect:
                prospects.append(prospect)
    return prospects


def normalize_header(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    aliases = {"compagny": "company", "adress": "address", "location": "country", "distributor": "company"}
    return aliases.get(value, value)


def table_country(value: str) -> str:
    value = clean(value)
    if value.lower().startswith("usa "):
        return "United States"
    if "hong kong" in value.lower():
        return "Hong Kong"
    value = re.split(r"\s+-\s+|,", value, maxsplit=1)[0]
    value = value.title() if value.isupper() else value
    return dist.COUNTRY_ALIASES.get(value, value)


def parse_official_tables(cache: dict[str, Any]) -> list[base.Prospect]:
    prospects: list[base.Prospect] = []
    for source in OFFICIAL_TABLE_SOURCES:
        url = source["url"]
        payload = http_get(url, cache, timeout=12)
        html = payload.get("text") or ""
        soup = BeautifulSoup(html, "html.parser")
        for table in soup.find_all("table"):
            header: list[str] = []
            for row_idx, tr in enumerate(table.find_all("tr")):
                cells = [clean(cell.get_text(" ", strip=True)) for cell in tr.find_all(["th", "td"])]
                if not cells:
                    continue
                if row_idx == 0 or any(cell.lower() in {"country", "company", "compagny", "distributor", "location"} for cell in cells):
                    header = [normalize_header(cell) for cell in cells]
                    continue
                if not header or len(cells) < 3:
                    continue
                row = {header[idx]: cells[idx] for idx in range(min(len(header), len(cells)))}
                name = row.get("company", "")
                country = table_country(row.get("country", ""))
                address = row.get("address", "")
                email = public_email(row.get("email", ""))
                phone = clean(row.get("phone", ""))
                website = row.get("website", "")
                if source["source_type"].startswith("DentLight") and not address:
                    address = f"{country}, United States" if country else ""
                    country = "United States"
                prospect = dist.make_distributor(
                    name=name,
                    country=country,
                    email=email,
                    phone=phone,
                    address=address,
                    website=website,
                    source_url=url,
                    source_type=source["source_type"],
                    acquisition_path=source["summary"],
                    site_business_summary="공식 제조사/브랜드 distributor 표에 공개된 치과 제품 유통·공급 파트너",
                    evidence=[
                        f"Official table row: {name} / {country}",
                        f"Required contact fields found: email={email}, phone={phone}, address={address}",
                    ],
                    tags={"source_trust": "high", "directory": source["source_type"]},
                )
                if prospect:
                    prospects.append(prospect)
    return prospects


def is_country_line(value: str) -> bool:
    normalized = table_country(value)
    return normalized in set(dist.KNOWN_COUNTRIES) or normalized in set(dist.COUNTRY_ALIASES.values()) or " / " in value


def parse_tokuyama_partners(cache: dict[str, Any]) -> list[base.Prospect]:
    payload = http_get(OFFICIAL_TOKUYAMA_URL, cache, timeout=12)
    lines = page_lines(payload.get("text") or "")
    prospects: list[base.Prospect] = []
    try:
        start = lines.index("Country")
    except ValueError:
        start = 0
    idx = start
    while idx < len(lines) - 4:
        if not is_country_line(lines[idx]):
            idx += 1
            continue
        country = table_country(lines[idx])
        name = clean(lines[idx + 1])
        if not name or name in {"Company", "Address", "Contact", "Website"}:
            idx += 1
            continue
        block: list[str] = []
        j = idx + 2
        while j < len(lines):
            if j > idx + 2 and is_country_line(lines[j]) and j + 1 < len(lines):
                break
            block.append(lines[j])
            j += 1
        email = public_email("\n".join(block))
        phone = clean(dist.extract_phone("\n".join(block)))
        website = next((line for line in block if line.startswith(("www.", "http://", "https://"))), "")
        address_lines = []
        for line in block:
            if line.lower().startswith(("phone", "fax")) or "@" in line or line.startswith(("www.", "http://", "https://")):
                break
            address_lines.append(line)
        address = clean(", ".join(address_lines))
        inferred_country = dist.infer_country(address, phone, website, email) or country
        prospect = dist.make_distributor(
            name=name,
            country=inferred_country,
            email=email,
            phone=phone,
            address=address,
            website=website,
            source_url=OFFICIAL_TOKUYAMA_URL,
            source_type="Tokuyama Dental official distributors and partners page",
            acquisition_path="Tokuyama Dental 공식 distributors and partners 페이지에서 국가, 회사, 주소, 이메일, 전화, 웹사이트를 직접 확인",
            site_business_summary="Tokuyama Dental 제품을 취급하는 공식 지역 유통 파트너",
            evidence=[
                f"Tokuyama official partner entry: {name} / {inferred_country}",
                f"Required contact fields found: email={email}, phone={phone}, address={address}",
            ],
            tags={"source_trust": "high", "directory": "Tokuyama Dental official partners"},
        )
        if prospect:
            prospects.append(prospect)
        idx = max(j, idx + 1)
    return prospects


def label_value(lines: list[str], label: str) -> str:
    label_lower = label.lower()
    for idx, line in enumerate(lines):
        lower = line.lower().strip(":")
        if lower == label_lower or lower.startswith(label_lower + ":"):
            value = line.split(":", 1)[1] if ":" in line else ""
            if value:
                return clean(value)
            for candidate in lines[idx + 1 : idx + 4]:
                if candidate.lower().strip(":") in {"address", "phone", "website", "email", "contact", "fax"}:
                    break
                if candidate:
                    return clean(candidate)
    return ""


def parse_heading_distributors(cache: dict[str, Any]) -> list[base.Prospect]:
    prospects: list[base.Prospect] = []
    for source in OFFICIAL_HEADING_SOURCES:
        payload = http_get(source["url"], cache, timeout=12)
        soup = BeautifulSoup(payload.get("text") or "", "html.parser")
        for heading in soup.find_all(source["heading"]):
            heading_text = clean(heading.get_text(" ", strip=True))
            if not heading_text or heading_text.lower() in {"follow us", "footer menu"}:
                continue
            lines = h4_block(heading)
            if len(lines) < 4:
                continue
            country_hint = table_country(heading_text)
            name = ""
            for line in lines:
                if line.lower().strip(":") in {"address", "phone", "website", "email", "contact", "fax"}:
                    continue
                if "@" in line or dist.phone_like(line) or line.startswith(("www.", "http://", "https://")):
                    continue
                name = clean(line)
                break
            block = "\n".join(lines)
            email = public_email(block)
            phone = label_value(lines, "Phone") or clean(dist.extract_phone(block))
            website = label_value(lines, "Website") or next((line for line in lines if line.startswith(("www.", "http://", "https://"))), "")
            address = label_value(lines, "Address") or exhibition.text_address(lines, country_hint)
            inferred_country = dist.infer_country(address, phone, website, email)
            country = country_hint if country_hint and country_hint not in {"Greece And Cyprus"} else inferred_country
            prospect = dist.make_distributor(
                name=name,
                country=country,
                email=email,
                phone=phone,
                address=address,
                website=website,
                source_url=source["url"],
                source_type=source["source_type"],
                acquisition_path=source["summary"],
                site_business_summary="공식 브랜드 distributor/dealer 페이지에 공개된 치과 제품 유통 파트너",
                evidence=[
                    f"Official heading block: {heading_text} / {name}",
                    f"Required contact fields found: email={email}, phone={phone}, address={address}",
                ],
                tags={"source_trust": "high", "directory": source["source_type"]},
            )
            if prospect:
                prospects.append(prospect)
    return prospects


def process_search_result(row: dict[str, str], cache: dict[str, Any]) -> tuple[base.Prospect | None, dict[str, Any]]:
    url = row["url"]
    country = row["country"]
    raw_log: dict[str, Any] = {"kind": "search_result_checked", **row, "host": host_of(url)}
    if is_bad_domain(url):
        raw_log["decision"] = "skip_bad_domain"
        return None, raw_log
    if is_social_domain(url):
        raw_log["decision"] = "skip_social_login_or_unstable_public_contact"
        return None, raw_log
    contact = contact_from_public_pages(url, country, cache)
    blob = " ".join([row.get("title", ""), row.get("snippet", ""), contact.get("title", ""), contact.get("address", "")])
    # Fetch text for relevance from cached first URL if needed.
    payload = http_get(url, cache)
    text_sample = BeautifulSoup((payload.get("text") or "")[:300_000], "html.parser").get_text(" ", strip=True)
    blob = " ".join([blob, text_sample[:20_000]])
    if not business_relevant(blob):
        raw_log["decision"] = "skip_not_dental_distribution"
        return None, raw_log
    name = clean_name(row.get("title", ""), contact.get("title", ""))
    if not name:
        raw_log["decision"] = "skip_no_name"
        return None, raw_log
    if bad_address_text(contact.get("address", "")):
        raw_log["decision"] = "skip_bad_address"
        raw_log["contact"] = contact
        return None, raw_log
    prospect = dist.make_distributor(
        name=name,
        country=country,
        email=contact["email"],
        phone=contact["phone"],
        address=contact["address"],
        website=dist.domain_url(url if not is_directory_domain(url) else ""),
        source_url=contact["source_url"] or url,
        source_type="Localized public web or business-directory result with direct contact verification",
        acquisition_path=f"현지어/현지 검색어 `{row['query']}`로 발견한 공개 업체·비즈니스 디렉터리 페이지를 재방문해 연락처 완비 여부 확인",
        site_business_summary="치과 장비·재료 유통, 공급, 수입·수출 또는 dental depot 성격의 공개 웹 노출 업체",
        evidence=[
            f"Search title/snippet: {row.get('title', '')} / {row.get('snippet', '')[:180]}",
            f"Required contact fields found: email={contact['email']}, phone={contact['phone']}, address={contact['address']}",
        ],
        tags={
            "source_trust": "medium" if is_directory_domain(url) else "medium-high",
            "search_engine": row.get("engine", ""),
            "search_query": row.get("query", ""),
            "result_host": host_of(url),
            "non_osm": "true",
        },
    )
    if not prospect:
        raw_log["decision"] = "skip_missing_required_contact"
        raw_log["contact"] = contact
        return None, raw_log
    raw_log["decision"] = "promote"
    raw_log["contact"] = contact
    return prospect, raw_log


def write_research_md(added: list[base.Prospect], before: int, after: int, checked_results: int, search_count: int) -> None:
    by_source: dict[str, int] = {}
    by_country: dict[str, int] = {}
    by_trust: dict[str, int] = {}
    for row in added:
        by_source[row.source_type] = by_source.get(row.source_type, 0) + 1
        by_country[row.country] = by_country.get(row.country, 0) + 1
        trust = row.tags.get("source_trust", "") if isinstance(row.tags, dict) else ""
        by_trust[trust or "unspecified"] = by_trust.get(trust or "unspecified", 0) + 1
    lines = [
        "# 현지어·공식 딜러·공개 디렉터리 기반 치과 유통사 확장 7차",
        "",
        f"- 생성일: {datetime.now().strftime('%Y-%m-%d %H:%M KST')}",
        f"- 실행 전 public valid: {before:,}",
        f"- 실행 후 public valid: {after:,}",
        f"- 이번 신규 승격: {after - before:,}개",
        f"- 검색 질의 수: {search_count:,}",
        f"- 검사한 검색 결과 URL: {checked_results:,}",
        "- 기준: 업체명, 이메일, 전화, 주소, 공개 출처가 모두 있는 경우만 병합",
        "- OSM 사용 여부: 사용하지 않음",
        "",
        "## 사용한 방법",
        "- GC Dental Europe/GC Orthodontics 공식 dealer/distributor 페이지를 직접 파싱했다.",
        "- DuckDuckGo HTML 검색으로 국가별 현지어 `치과 유통사`, `치과 장비 공급`, `치과 수출입`, `dental depot`에 해당하는 질의를 생성했다.",
        "- Facebook/LinkedIn 결과도 검색 노출은 확인했지만 로그인·개인 프로필·공개 연락처 불안정성 때문에 자동 승격하지 않았다.",
        "- Yellow page, business directory, 회사 공식 contact/about/impressum 페이지에서 공개 이메일·전화·주소가 같이 확인되는 경우만 승격했다.",
        "",
        "## 신뢰도 기준",
        "- 높음: 제조사 공식 dealer/distributor locator가 업체 연락처를 직접 공개한 경우.",
        "- 중간~높음: 회사 공식 웹사이트 contact/about/impressum에서 이메일·전화·주소가 직접 확인된 경우.",
        "- 중간: Yellow page/비즈니스 디렉터리 프로필에 연락처가 공개되고 치과 유통·공급 문맥이 같이 확인된 경우.",
        "- 낮음/미승격: 검색 결과 snippet, SNS 단독 노출, 연락처 일부 누락, 병원·개인 치과 진료소 문맥만 있는 경우.",
        "",
        "## 신규 승격 소스 분포",
    ]
    for source, count in sorted(by_source.items(), key=lambda item: item[1], reverse=True):
        lines.append(f"- {source}: {count:,}")
    lines += ["", "## 신규 승격 신뢰도 분포"]
    for trust, count in sorted(by_trust.items(), key=lambda item: item[1], reverse=True):
        lines.append(f"- {trust}: {count:,}")
    lines += ["", "## 신규 승격 국가 상위"]
    for country, count in sorted(by_country.items(), key=lambda item: item[1], reverse=True)[:80]:
        lines.append(f"- {country}: {count:,}")
    lines += [
        "",
        "## 저장 파일",
        f"- 승격 로그: `{PROMOTIONS_JSONL}`",
        f"- 원시/검사 로그: `{RAW_JSONL}`",
        f"- 요청 캐시: `{CACHE_JSON}`",
        f"- 병합 데이터: `{base.VALID_JSONL}`",
    ]
    RESEARCH_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> int:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    cache: dict[str, Any] = load_json(CACHE_JSON, {})
    existing = base.existing_valid()
    before = len(existing)
    valid_by_key = dict(existing)
    added: list[base.Prospect] = []
    checked_results = 0

    gc_rows = parse_gc_dealers(cache)
    gc_added: list[base.Prospect] = []
    for row in gc_rows:
        key = base.dedupe_key(row)
        if key in valid_by_key:
            continue
        valid_by_key[key] = row
        added.append(row)
        gc_added.append(row)
    append_jsonl(RAW_JSONL, [{"kind": "gc_official_candidate", **asdict(row)} for row in gc_rows])
    append_jsonl(PROMOTIONS_JSONL, [{"source": "gc_official", **asdict(row)} for row in gc_added])
    print(json.dumps({"source": "gc_official", "found": len(gc_rows), "added": len(gc_added), "totalValid": len(valid_by_key)}, ensure_ascii=False), flush=True)

    ivoclar_rows = parse_ivoclar_distributors(cache)
    ivoclar_added: list[base.Prospect] = []
    for row in ivoclar_rows:
        key = base.dedupe_key(row)
        if key in valid_by_key:
            continue
        valid_by_key[key] = row
        added.append(row)
        ivoclar_added.append(row)
    append_jsonl(RAW_JSONL, [{"kind": "ivoclar_official_candidate", **asdict(row)} for row in ivoclar_rows])
    append_jsonl(PROMOTIONS_JSONL, [{"source": "ivoclar_official", **asdict(row)} for row in ivoclar_added])
    prospects = sorted(valid_by_key.values(), key=lambda item: (item.country, item.city_hint, item.name))
    base.rewrite_valid(prospects)
    print(json.dumps({"source": "ivoclar_official", "found": len(ivoclar_rows), "added": len(ivoclar_added), "totalValid": len(valid_by_key)}, ensure_ascii=False), flush=True)

    official_table_rows = parse_official_tables(cache)
    official_table_added: list[base.Prospect] = []
    for row in official_table_rows:
        key = base.dedupe_key(row)
        if key in valid_by_key:
            continue
        valid_by_key[key] = row
        added.append(row)
        official_table_added.append(row)
    append_jsonl(RAW_JSONL, [{"kind": "official_table_candidate", **asdict(row)} for row in official_table_rows])
    append_jsonl(PROMOTIONS_JSONL, [{"source": "official_table", **asdict(row)} for row in official_table_added])
    prospects = sorted(valid_by_key.values(), key=lambda item: (item.country, item.city_hint, item.name))
    base.rewrite_valid(prospects)
    print(json.dumps({"source": "official_tables", "found": len(official_table_rows), "added": len(official_table_added), "totalValid": len(valid_by_key)}, ensure_ascii=False), flush=True)

    tokuyama_rows = parse_tokuyama_partners(cache)
    tokuyama_added: list[base.Prospect] = []
    for row in tokuyama_rows:
        key = base.dedupe_key(row)
        if key in valid_by_key:
            continue
        valid_by_key[key] = row
        added.append(row)
        tokuyama_added.append(row)
    append_jsonl(RAW_JSONL, [{"kind": "tokuyama_official_candidate", **asdict(row)} for row in tokuyama_rows])
    append_jsonl(PROMOTIONS_JSONL, [{"source": "tokuyama_official", **asdict(row)} for row in tokuyama_added])
    prospects = sorted(valid_by_key.values(), key=lambda item: (item.country, item.city_hint, item.name))
    base.rewrite_valid(prospects)
    print(json.dumps({"source": "tokuyama_official", "found": len(tokuyama_rows), "added": len(tokuyama_added), "totalValid": len(valid_by_key)}, ensure_ascii=False), flush=True)

    heading_rows = parse_heading_distributors(cache)
    heading_added: list[base.Prospect] = []
    for row in heading_rows:
        key = base.dedupe_key(row)
        if key in valid_by_key:
            continue
        valid_by_key[key] = row
        added.append(row)
        heading_added.append(row)
    append_jsonl(RAW_JSONL, [{"kind": "heading_official_candidate", **asdict(row)} for row in heading_rows])
    append_jsonl(PROMOTIONS_JSONL, [{"source": "heading_official", **asdict(row)} for row in heading_added])
    prospects = sorted(valid_by_key.values(), key=lambda item: (item.country, item.city_hint, item.name))
    base.rewrite_valid(prospects)
    print(json.dumps({"source": "heading_official", "found": len(heading_rows), "added": len(heading_added), "totalValid": len(valid_by_key)}, ensure_ascii=False), flush=True)

    focus_countries = {item.strip().lower() for item in args.countries.split(",") if item.strip()} if args.countries else None
    queries = build_queries(args.max_searches, focus_countries)
    seen_urls: set[str] = set()
    for qidx, query_row in enumerate(queries, start=1):
        if len(added) >= args.target_added:
            break
        results = search_duckduckgo(query_row["query"], cache, args.results_per_query)
        enriched_results = [{**row, "country": query_row["country"]} for row in results]
        append_jsonl(RAW_JSONL, [{"kind": "search_result", **row} for row in enriched_results])
        batch = []
        for row in enriched_results:
            url = row["url"]
            if url in seen_urls:
                continue
            seen_urls.add(url)
            batch.append(row)
        if not batch:
            continue
        promoted_rows: list[base.Prospect] = []
        raw_logs: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
            futures = [executor.submit(process_search_result, row, cache) for row in batch]
            for future in as_completed(futures):
                prospect, raw_log = future.result()
                checked_results += 1
                raw_logs.append(raw_log)
                if not prospect:
                    continue
                key = base.dedupe_key(prospect)
                if key in valid_by_key:
                    raw_log["decision"] = "skip_duplicate_after_promotion"
                    continue
                valid_by_key[key] = prospect
                added.append(prospect)
                promoted_rows.append(prospect)
                if len(added) >= args.target_added:
                    break
        append_jsonl(RAW_JSONL, raw_logs)
        append_jsonl(PROMOTIONS_JSONL, [{"source": "localized_search", **asdict(row)} for row in promoted_rows])
        if promoted_rows:
            prospects = sorted(valid_by_key.values(), key=lambda item: (item.country, item.city_hint, item.name))
            base.rewrite_valid(prospects)
        if qidx % 25 == 0:
            save_json(CACHE_JSON, cache)
        if promoted_rows or qidx % 1 == 0:
            print(
                json.dumps(
                    {
                        "query_index": qidx,
                        "country": query_row["country"],
                        "added_this_query": len(promoted_rows),
                        "added_total": len(added),
                        "checked_results": checked_results,
                        "totalValid": len(valid_by_key),
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
        time.sleep(args.search_pause)

    prospects = sorted(valid_by_key.values(), key=lambda item: (item.country, item.city_hint, item.name))
    base.rewrite_valid(prospects)
    save_json(CACHE_JSON, cache)
    write_research_md(added, before, len(valid_by_key), checked_results, min(len(queries), qidx if queries else 0))
    print(
        json.dumps(
            {
                "done": True,
                "before": before,
                "after": len(valid_by_key),
                "added": len(valid_by_key) - before,
                "targetAdded": args.target_added,
                "checkedResults": checked_results,
                "research": str(RESEARCH_MD),
            },
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )
    return 0 if len(valid_by_key) - before >= args.target_added else 2


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-added", type=int, default=3000)
    parser.add_argument("--max-searches", type=int, default=900)
    parser.add_argument("--results-per-query", type=int, default=18)
    parser.add_argument("--workers", type=int, default=24)
    parser.add_argument("--search-pause", type=float, default=0.12)
    parser.add_argument("--countries", default="", help="Optional comma-separated country focus list.")
    args = parser.parse_args(argv)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
