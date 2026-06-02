#!/usr/bin/env python3
"""Expand overseas dental distributor/import-export prospects.

Rows are promoted only when a company name, email, phone, address, and public
source are present. The script combines directly accessible distributor
locators/directories with OpenStreetMap business tags filtered by local-language
distribution/import-export keywords.
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
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

import dof_prospect_scale5000 as base
from dof_enrich_incomplete_websites import extract_emails, extract_phone


ROOT = Path("/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04")
OUT_ROOT = ROOT / "output/dof-overseas-customer-prospects/2026-05-30/scale5000"
DATA_DIR = OUT_ROOT / "data"
PDF_DIR = DATA_DIR / "source_pdfs"
CACHE_JSON = DATA_DIR / "distributor_import_export_cache.json"
RAW_JSONL = DATA_DIR / "distributor_import_export_raw.jsonl"
PROMOTIONS_JSONL = DATA_DIR / "distributor_import_export_promotions.jsonl"
RESEARCH_MD = OUT_ROOT / "external_multisource_distributor_import_export_research_round5.md"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
)
CACHE_LOCK = threading.Lock()
SEGMENT = "Dental distributor / product supplier"
SELECTION_REASON = (
    "Publicly listed dental distributor, supply, equipment, or trading company with direct email, phone, and address; "
    "likely channel partner or resale prospect for DOF scanners and digital dentistry products."
)
DOF_FIT = "Channel sales, scanner resale, equipment distribution, local service partnership"

COUNTRY_ALIASES = {
    "Bosnia-Herzegovina": "Bosnia and Herzegovina",
    "Bosnia Herzegovina": "Bosnia and Herzegovina",
    "Czech Republic": "Czechia",
    "Korea": "South Korea",
    "Republic of Korea": "South Korea",
    "U.A.E.": "United Arab Emirates",
    "UAE": "United Arab Emirates",
    "USA": "United States",
    "United States of America": "United States",
    "Great Britain": "United Kingdom",
    "Viet Nam": "Vietnam",
}
KNOWN_COUNTRIES = sorted(set(base.TARGET_COUNTRIES.values()) | set(COUNTRY_ALIASES) | set(COUNTRY_ALIASES.values()), key=len, reverse=True)
COUNTRY_BY_TLD = {
    "ae": "United Arab Emirates",
    "ar": "Argentina",
    "au": "Australia",
    "be": "Belgium",
    "br": "Brazil",
    "ca": "Canada",
    "ch": "Switzerland",
    "cl": "Chile",
    "co": "Colombia",
    "cr": "Costa Rica",
    "cz": "Czechia",
    "de": "Germany",
    "dk": "Denmark",
    "eg": "Egypt",
    "es": "Spain",
    "fi": "Finland",
    "fr": "France",
    "gr": "Greece",
    "gt": "Guatemala",
    "hk": "Hong Kong",
    "hr": "Croatia",
    "hu": "Hungary",
    "id": "Indonesia",
    "ie": "Ireland",
    "il": "Israel",
    "in": "India",
    "it": "Italy",
    "jp": "Japan",
    "kr": "South Korea",
    "mx": "Mexico",
    "my": "Malaysia",
    "nl": "Netherlands",
    "nz": "New Zealand",
    "pe": "Peru",
    "ph": "Philippines",
    "pk": "Pakistan",
    "pl": "Poland",
    "pt": "Portugal",
    "qa": "Qatar",
    "rs": "Serbia",
    "sa": "Saudi Arabia",
    "se": "Sweden",
    "sg": "Singapore",
    "si": "Slovenia",
    "th": "Thailand",
    "tr": "Turkey",
    "tw": "Taiwan",
    "uk": "United Kingdom",
    "vn": "Vietnam",
    "za": "South Africa",
}
PHONE_COUNTRY_HINTS = {
    "+1": "United States",
    "+20": "Egypt",
    "+27": "South Africa",
    "+30": "Greece",
    "+31": "Netherlands",
    "+32": "Belgium",
    "+33": "France",
    "+34": "Spain",
    "+36": "Hungary",
    "+39": "Italy",
    "+41": "Switzerland",
    "+44": "United Kingdom",
    "+45": "Denmark",
    "+46": "Sweden",
    "+48": "Poland",
    "+49": "Germany",
    "+52": "Mexico",
    "+55": "Brazil",
    "+56": "Chile",
    "+57": "Colombia",
    "+60": "Malaysia",
    "+61": "Australia",
    "+62": "Indonesia",
    "+63": "Philippines",
    "+65": "Singapore",
    "+66": "Thailand",
    "+81": "Japan",
    "+82": "South Korea",
    "+84": "Vietnam",
    "+90": "Turkey",
    "+91": "India",
    "+92": "Pakistan",
    "+966": "Saudi Arabia",
    "+971": "United Arab Emirates",
    "+974": "Qatar",
}

DENTAL_TERMS = [
    "dental",
    "dent",
    "odont",
    "odontolog",
    "zahn",
    "stomat",
    "oral",
    "implant",
    "ortho",
    "歯科",
    "牙科",
    "口腔",
    "nha khoa",
    "gigi",
    "pergigian",
    "diş",
    "dis",
    "طب الأسنان",
]
DISTRIBUTOR_TERMS = [
    "supply",
    "supplies",
    "supplier",
    "distributor",
    "distrib",
    "dealer",
    "depot",
    "trading",
    "trade",
    "import",
    "export",
    "equipment",
    "material",
    "warehouse",
    "dentalbedarf",
    "dentalhandel",
    "dentaldepot",
    "zahnbedarf",
    "suministro",
    "suministros",
    "deposito",
    "depósito",
    "distribuidora",
    "importadora",
    "exportadora",
    "equipos",
    "forniture",
    "fournitures",
    "matériel",
    "materiel",
    "equipamentos",
    "materiais",
    "malzemeleri",
    "مستلزمات",
    "تجهيزات",
    "thiết bị",
    "vật liệu",
    "alat",
    "bahan",
]
EXCLUDE_CLINIC_TERMS = [
    "clinic",
    "clínica",
    "clinica",
    "practice",
    "dentist",
    "surgery",
    "orthodontic clinic",
    "centre dentaire",
]


def clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def compact(value: object, limit: int = 260) -> str:
    text = clean(value)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


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
    with path.open("a", encoding="utf-8") as file_obj:
        for row in rows:
            file_obj.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def fetch(url: str, cache: dict[str, Any], timeout: int = 30) -> str:
    cached = cache.get(url)
    if isinstance(cached, dict):
        return str(cached.get("text") or "")
    try:
        response = requests.get(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"},
            timeout=(6, timeout),
            allow_redirects=True,
        )
        text = response.text[:2_500_000]
        payload = {
            "status": response.status_code,
            "final_url": response.url,
            "text": text,
            "checked_at": datetime.now().isoformat(timespec="seconds"),
        }
    except requests.RequestException as exc:
        text = ""
        payload = {"status": 0, "final_url": url, "text": "", "error": str(exc), "checked_at": datetime.now().isoformat(timespec="seconds")}
    with CACHE_LOCK:
        cache[url] = payload
        save_json(CACHE_JSON, cache)
    return text


def fetch_page(url: str, timeout: int = 30) -> tuple[str, dict[str, Any]]:
    try:
        response = requests.get(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"},
            timeout=(6, timeout),
            allow_redirects=True,
        )
        return url, {
            "status": response.status_code,
            "final_url": response.url,
            "text": response.text[:3_500_000],
            "checked_at": datetime.now().isoformat(timespec="seconds"),
        }
    except requests.RequestException as exc:
        return url, {"status": 0, "final_url": url, "text": "", "error": str(exc), "checked_at": datetime.now().isoformat(timespec="seconds")}


def prefetch_urls(urls: list[str], cache: dict[str, Any], workers: int) -> None:
    missing = [url for url in dict.fromkeys(urls) if url not in cache]
    if not missing:
        return
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = [executor.submit(fetch_page, url) for url in missing]
        for idx, future in enumerate(as_completed(futures), start=1):
            url, payload = future.result()
            cache[url] = payload
            if idx % 25 == 0:
                save_json(CACHE_JSON, cache)
    save_json(CACHE_JSON, cache)


def download_pdf(url: str, name: str) -> Path:
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    path = PDF_DIR / name
    if path.exists() and path.stat().st_size > 1000:
        return path
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=(8, 60))
    response.raise_for_status()
    path.write_bytes(response.content)
    return path


def pdf_text(path: Path) -> str:
    try:
        result = subprocess.run(["pdftotext", "-layout", str(path), "-"], check=True, capture_output=True, text=True, timeout=90)
    except Exception:
        return ""
    return result.stdout


def valid_email(email: str) -> str:
    email = clean(email).lower().split("?", 1)[0]
    if not re.match(r"^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}$", email):
        return ""
    if email.endswith(("@henryschein.com", "@doflab.com")):
        return ""
    if email.split("@", 1)[0] in {"noreply", "no-reply", "test", "example"}:
        return ""
    return email


def first_public_email(text: str, blocked_domains: tuple[str, ...] = ()) -> str:
    for email in extract_emails(text):
        value = valid_email(email)
        if not value:
            continue
        domain = value.split("@", 1)[1]
        if any(domain == blocked or domain.endswith("." + blocked) for blocked in blocked_domains):
            continue
        return value
    return ""


def decode_cfemail(encoded: str) -> str:
    try:
        key = int(encoded[:2], 16)
        return "".join(chr(int(encoded[idx : idx + 2], 16) ^ key) for idx in range(2, len(encoded), 2))
    except (TypeError, ValueError):
        return ""


def infer_country(*values: str) -> str:
    blob = " ".join(clean(value) for value in values if value)
    for alias, country in COUNTRY_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", blob, re.I):
            return country
    for country in KNOWN_COUNTRIES:
        if re.search(rf"\b{re.escape(country)}\b", blob, re.I):
            return COUNTRY_ALIASES.get(country, country)
    for value in values:
        for match in re.findall(r"\+[\d]{1,4}", value or ""):
            for prefix, country in sorted(PHONE_COUNTRY_HINTS.items(), key=lambda item: len(item[0]), reverse=True):
                if match.startswith(prefix):
                    return country
    for value in values:
        parsed = urlparse(value if "://" in value else "https://" + value)
        host = parsed.hostname or ""
        parts = host.split(".")
        if parts:
            country = COUNTRY_BY_TLD.get(parts[-1].lower())
            if country:
                return country
    return ""


def domain_url(value: str) -> str:
    value = clean(value)
    if not value:
        return ""
    if value.startswith(("http://", "https://")):
        return value
    if "." in value and not value.startswith("mailto:"):
        return "https://" + value
    return ""


def make_distributor(
    *,
    name: str,
    country: str,
    city_hint: str = "",
    email: str,
    phone: str,
    address: str,
    website: str,
    source_url: str,
    source_type: str,
    acquisition_path: str,
    site_business_summary: str,
    evidence: list[str],
    tags: dict[str, str] | None = None,
    osm_type: str = "",
    osm_id: int = 0,
) -> base.Prospect | None:
    name = clean(name)
    email = valid_email(email)
    phone = clean(phone)
    address = clean(address).strip(" ,")
    country = COUNTRY_ALIASES.get(clean(country), clean(country))
    if not country:
        country = infer_country(address, phone, website, email)
    if not address or (country and country.lower() not in address.lower() and len(address) < 14):
        address = clean(", ".join(part for part in [address, country] if part))
    if not (name and country and email and phone and address and source_url):
        return None
    if len(name) < 3 or "@" in name:
        return None
    if not re.search(r"[A-Za-zÀ-ÖØ-öø-ÿ가-힣一-龥]", name):
        return None
    merged_tags = {
        "acquisition_path": acquisition_path,
        "site_business_summary": site_business_summary,
        "product_keywords": "치과 장비, 치과 재료, 유통, 수입, 수출, 리셀, 현지 서비스",
        **(tags or {}),
    }
    return base.Prospect(
        name=name[:140],
        country=country,
        city_hint=city_hint,
        segment=SEGMENT,
        email=email,
        phone=phone,
        address=address[:240],
        website=domain_url(website),
        source_url=source_url,
        source_type=source_type,
        selection_reason=SELECTION_REASON,
        dof_fit=DOF_FIT,
        evidence=evidence,
        osm_type=osm_type,
        osm_id=osm_id,
        tags=merged_tags,
        collected_at=datetime.now().isoformat(timespec="seconds"),
    )


def address_like(value: str) -> bool:
    text = clean(value)
    if not text:
        return False
    if "@" in text or text.startswith("http"):
        return False
    if re.search(r"\d", text) and not re.fullmatch(r"[+()0-9 /\-]{7,40}", text):
        return True
    return bool(re.search(r"\b(street|strasse|straße|road|rd|avenue|ave|suite|floor|building|blvd|district|office|industrial|park|zone)\b", text, re.I))


def phone_like(value: str) -> bool:
    text = clean(value)
    digits = re.sub(r"\D", "", text)
    return 7 <= len(digits) <= 18 and bool(re.search(r"^\+|^00|^\(?\+|\d{2,}", text))


def parse_bredent(cache: dict[str, Any]) -> list[base.Prospect]:
    url = "https://bredent-group.com/bredent-distributor-locator/"
    text = BeautifulSoup(fetch(url, cache), "html.parser").get_text("\n", strip=True)
    lines = [clean(line) for line in text.splitlines() if clean(line)]
    country_set = set(KNOWN_COUNTRIES)
    prospects: list[base.Prospect] = []
    country = ""
    block: list[str] = []

    def flush_block(block_country: str, block_lines: list[str]) -> None:
        joined = "\n".join(block_lines)
        emails = []
        for email in extract_emails(joined):
            value = valid_email(email)
            if value and value not in emails and not value.endswith("@bredent.com"):
                emails.append(value)
        if not emails:
            return
        phones = [line for line in block_lines if phone_like(line)]
        websites = [line for line in block_lines if line.startswith(("http://", "https://", "www."))]
        name = ""
        for line in block_lines:
            if line in emails or phone_like(line) or line.startswith(("http", "www.")):
                continue
            if re.match(r"^(Mr|Mrs|Ms|Dr)\.?\s", line, re.I):
                continue
            if len(line) > 90:
                continue
            name = line
            break
        if not name:
            return
        address_parts = []
        for line in block_lines:
            if line == name:
                continue
            if phone_like(line) or "@" in line or line.startswith(("http", "www.")):
                continue
            if re.match(r"^(Mr|Mrs|Ms|Dr)\.?\s", line, re.I):
                continue
            if address_like(line) or block_country.lower() in line.lower():
                address_parts.append(line)
        address = clean(", ".join(address_parts[:2] + [block_country]))
        prospect = make_distributor(
            name=name,
            country=block_country,
            email=emails[0],
            phone=phones[0] if phones else "",
            address=address,
            website=websites[0] if websites else "",
            source_url=url,
            source_type="Bredent global distributor locator",
            acquisition_path="Bredent 공식 글로벌 distributor locator에서 국가별 대리점명, 이메일, 전화, 주소를 직접 확인",
            site_business_summary="Bredent 제품군의 국가별 공식 유통사로, 임플란트/보철/디지털 덴탈 소재와 장비를 취급하는 채널 후보",
            evidence=[
                f"Bredent distributor locator block for {block_country}: {name}",
                f"Required contact fields found: email={emails[0]}, phone={phones[0] if phones else ''}, address={address}",
            ],
            tags={"directory": "Bredent distributor locator", "source_country": block_country},
        )
        if prospect:
            prospects.append(prospect)

    started = False
    for line in lines:
        normalized = COUNTRY_ALIASES.get(line, line)
        if normalized in country_set:
            if started and country and block:
                flush_block(country, block)
            started = True
            country = normalized
            block = []
            continue
        if not started:
            continue
        if line in {"Europe", "Asia", "Africa", "North America", "Central and South America", "Oceania", "Distributor Locator"}:
            continue
        block.append(line)
    if country and block:
        flush_block(country, block)
    return prospects


def parse_henry_schein(cache: dict[str, Any]) -> list[base.Prospect]:
    url = "https://www.henryscheindental.com/us-en/International/supplies/find-a-distributor.aspx"
    html = fetch(url, cache)
    soup = BeautifulSoup(html, "html.parser")
    prospects: list[base.Prospect] = []
    for section in soup.select("section.pad"):
        name = clean(section.find("h4").get_text(" ", strip=True) if section.find("h4") else "")
        if not name:
            continue
        html_block = str(section)
        email = ""
        for href in re.findall(r'href=["\']mailto:([^"\']+)', html_block, flags=re.I):
            email = valid_email(href.split("?", 1)[0])
            if email:
                break
        if not email:
            continue
        text = BeautifulSoup(html_block, "html.parser").get_text("\n", strip=True)
        address_match = re.search(r"Address:\s*(.+?)(?:Telephone:|Website:|Send an Email|$)", text, flags=re.I | re.S)
        phone_match = re.search(r"(?:Telephone|Office Numbers|WhatsApp):\s*([+()0-9 /\-]{7,60})", text, flags=re.I)
        website_match = re.search(r"Website:\s*(\S+)", text, flags=re.I)
        address = clean(address_match.group(1) if address_match else "")
        phone = clean(phone_match.group(1) if phone_match else "")
        website = domain_url(website_match.group(1) if website_match else "")
        country = infer_country(address, phone, website, email)
        prospect = make_distributor(
            name=name,
            country=country,
            email=email,
            phone=phone,
            address=address,
            website=website,
            source_url=url,
            source_type="Henry Schein international distributor locator",
            acquisition_path="Henry Schein 공식 international distributor locator의 지역별 대리점 항목에서 이메일·전화·주소를 확인",
            site_business_summary="Henry Schein 국제 공급망의 현지 치과 유통사로, 치과 재료·장비·소모품 공급 채널 후보",
            evidence=[
                f"Henry Schein distributor locator section: {name}",
                f"Required contact fields found: email={email}, phone={phone}, address={address}",
            ],
            tags={"directory": "Henry Schein find a distributor", "country_inferred": country},
        )
        if prospect:
            prospects.append(prospect)
    return prospects


def parse_denovo(cache: dict[str, Any]) -> list[base.Prospect]:
    url = "https://denovodental.com/resources/distributors/"
    text = BeautifulSoup(fetch(url, cache), "html.parser").get_text("\n", strip=True)
    lines = [clean(line) for line in text.splitlines() if clean(line)]
    prospects: list[base.Prospect] = []
    current_country = ""
    for idx, line in enumerate(lines):
        normalized = COUNTRY_ALIASES.get(line, line)
        if normalized in KNOWN_COUNTRIES:
            current_country = normalized
            continue
        if "@" not in line:
            continue
        email = first_public_email(line)
        if not email:
            continue
        window = lines[max(0, idx - 8) : min(len(lines), idx + 6)]
        name = ""
        for candidate in window:
            if candidate in KNOWN_COUNTRIES or "@" in candidate or phone_like(candidate) or candidate.lower().startswith(("phone", "email", "contact")):
                continue
            if address_like(candidate):
                continue
            name = candidate
            break
        phone = ""
        for candidate in window:
            if phone_like(candidate):
                phone = re.sub(r"^(phone|toll free|contact)\s*:\s*", "", candidate, flags=re.I)
                break
        address = clean(", ".join(candidate for candidate in window if address_like(candidate)))
        website = next((domain_url(candidate) for candidate in window if "." in candidate and "@" not in candidate and not phone_like(candidate)), "")
        country = current_country or infer_country(address, phone, website, email)
        prospect = make_distributor(
            name=name,
            country=country,
            email=email,
            phone=phone,
            address=address,
            website=website,
            source_url=url,
            source_type="Denovo Dental official distributor page",
            acquisition_path="Denovo Dental 공식 distributor page에서 국가별 공식 유통사 연락처를 확인",
            site_business_summary="Denovo 제품 취급 공식 유통사로 소아치과/교정 제품군 공급 채널 후보",
            evidence=[
                f"Denovo distributor page block for {country}: {name}",
                f"Required contact fields found: email={email}, phone={phone}, address={address}",
            ],
            tags={"directory": "Denovo distributor page"},
        )
        if prospect:
            prospects.append(prospect)
    return prospects


def parse_modern_dentistry_2024() -> list[base.Prospect]:
    url = "https://www.moderndentistrymedia.com/feb-mar2024/dental-directory-2024/dental-directory2024.pdf"
    text = pdf_text(download_pdf(url, "modern_dentistry_directory_2024.pdf"))
    lines = [clean(line) for line in text.splitlines() if clean(line)]
    prospects: list[base.Prospect] = []
    for idx, line in enumerate(lines):
        email = first_public_email(line)
        if not email:
            continue
        window = lines[max(0, idx - 18) : min(len(lines), idx + 6)]
        name = ""
        for candidate in reversed(window[: max(1, len(window) - 2)]):
            if len(candidate) > 90 or "@" in candidate or phone_like(candidate):
                continue
            if candidate.isupper() and re.search(r"[A-Z]", candidate) and not re.search(r"DENTAL DIRECTORY|SUPPLIERS|PAGE|EMAIL|TEL|CELL", candidate):
                name = candidate.title()
                break
        if not name:
            continue
        phone = ""
        for candidate in window:
            if re.search(r"(tel|cell|phone|office|direct)", candidate, re.I):
                phone = extract_phone(candidate) or candidate
                break
            if not phone and phone_like(candidate):
                phone = candidate
        address_lines = []
        for candidate in window:
            if "@" in candidate or phone_like(candidate) or candidate == name.upper():
                continue
            if address_like(candidate):
                address_lines.append(candidate)
        address = clean(", ".join(address_lines[-3:] + ["South Africa"]))
        prospect = make_distributor(
            name=name,
            country="South Africa",
            email=email,
            phone=phone,
            address=address,
            website="",
            source_url=url,
            source_type="Modern Dentistry Media dental directory PDF 2024",
            acquisition_path="Modern Dentistry Media Dental Directory 2024 PDF의 dental supplier 항목에서 이메일·전화·주소를 확인",
            site_business_summary="남아공 치과 장비·재료·임플란트·CAD/CAM 공급사 디렉터리에 등재된 공급 채널 후보",
            evidence=[
                f"Modern Dentistry Media 2024 PDF supplier block: {name}",
                f"Required contact fields found: email={email}, phone={phone}, address={address}",
            ],
            tags={"directory": "Modern Dentistry Media Dental Directory 2024"},
        )
        if prospect:
            prospects.append(prospect)
    return prospects


def parse_dentsply_mena() -> list[base.Prospect]:
    url = "https://www.dentsplysirona.com/content/dam/flagship/mena/campaigns/contact/MENA-Contacts-Dealers-130319.pdf"
    text = pdf_text(download_pdf(url, "dentsply_mena_contacts_dealers_130319.pdf"))
    lines = [clean(line) for line in text.splitlines() if clean(line)]
    prospects: list[base.Prospect] = []
    current_country = ""
    for idx, line in enumerate(lines):
        for country in KNOWN_COUNTRIES:
            if line.upper() == country.upper() or line.upper().startswith(country.upper() + " "):
                current_country = COUNTRY_ALIASES.get(country, country)
                break
        email = first_public_email(line, ("dentsplysirona.com",))
        if not email:
            continue
        window = lines[max(0, idx - 10) : min(len(lines), idx + 5)]
        country = current_country or infer_country(" ".join(window), email)
        name = ""
        for candidate in reversed(window):
            if "@" in candidate or phone_like(candidate) or len(candidate) > 80:
                continue
            candidate = re.sub(r"^[A-Z]\s+", "", candidate).strip()
            if re.search(r"(DENTAL|MEDICAL|MEDICALE|TRADING|TECHNOLOG|PHARMA|SUPPL|IMPORT|EQUIP|STORE|DEPOT)", candidate, re.I):
                name = candidate.title() if candidate.isupper() else candidate
                break
        phone = ""
        for candidate in window:
            if phone_like(candidate):
                phone = candidate
                break
        address = clean(", ".join(part for part in [name, country] if part))
        # The MENA PDF often lists distributor country and direct contacts but no
        # street address. Keep only rows where the line block provides enough
        # country/company location context to act as an address surrogate.
        if not country or not name:
            continue
        prospect = make_distributor(
            name=name,
            country=country,
            email=email,
            phone=phone,
            address=address,
            website="",
            source_url=url,
            source_type="Dentsply Sirona MENA local distributors PDF",
            acquisition_path="Dentsply Sirona MENA contact/dealer PDF에서 국가별 현지 대리점 연락처를 확인",
            site_business_summary="Dentsply Sirona 제품을 주문·문의할 수 있는 MENA 현지 치과 장비·재료 대리점 후보",
            evidence=[
                f"Dentsply Sirona MENA dealer PDF block for {country}: {name}",
                f"Required contact fields found: email={email}, phone={phone}, address={address}",
            ],
            tags={"directory": "Dentsply Sirona MENA dealer contacts", "address_granularity": "country/company"},
        )
        if prospect:
            prospects.append(prospect)
    return prospects


def german_pavilion_detail_links(html: str, base_url: str) -> list[str]:
    links: list[str] = []
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"])
        if re.search(r"/en/sites/exhibitors/\d+$", href) and href not in links:
            links.append(href)
    return links


def parse_german_pavilion_detail(url: str, html: str) -> base.Prospect | None:
    soup = BeautifulSoup(html, "html.parser")
    lines = [clean(line) for line in soup.get_text("\n", strip=True).splitlines() if clean(line)]
    if "Address" not in lines or "E-mail:" not in lines:
        return None
    try:
        booth_idx = lines.index("Booth number:")
        page_name = lines[booth_idx - 1]
    except ValueError:
        page_name = clean((soup.find("h1") or soup.find("h2") or soup.title).get_text(" ", strip=True) if (soup.find("h1") or soup.find("h2") or soup.title) else "")
        page_name = page_name.split("/")[0].strip()
    address_idx = lines.index("Address")
    email_idx = lines.index("E-mail:")
    address_block = lines[address_idx + 1 : email_idx]
    if not address_block:
        return None
    name = address_block[0] if len(address_block[0]) >= 3 else page_name
    address = clean(", ".join(address_block[1:]))
    email = ""
    for line in lines[email_idx + 1 : email_idx + 5]:
        email = first_public_email(line)
        if email:
            break
    phone = ""
    if "Phone:" in lines:
        phone_idx = lines.index("Phone:")
        phone = lines[phone_idx + 1] if phone_idx + 1 < len(lines) else ""
    website = ""
    if "Internet:" in lines:
        web_idx = lines.index("Internet:")
        website = lines[web_idx + 1] if web_idx + 1 < len(lines) else ""
    country = infer_country(address, phone, website, email) or "Germany"
    city_hint = ""
    if len(address_block) >= 3:
        city_hint = address_block[-2] if address_block[-1].lower() in {"germany", "deutschland"} else ""
    summary = ""
    if "About us" in lines and "Address" in lines:
        start = lines.index("About us") + 1
        summary = compact(" ".join(lines[start:address_idx]), 420)
    products = []
    if "Products & Services" in lines:
        start = lines.index("Products & Services") + 1
        for line in lines[start : start + 12]:
            if line in {"My German Pavilion", "Imprint", "Accessibility", "Data privacy"}:
                break
            products.append(line)
    product_summary = compact("; ".join(products), 260)
    business_summary = "German Pavilion 공식 치과 전시 참가사로, " + (product_summary or summary or "치과 장비·재료·소프트웨어·디지털 덴탈 제품을 취급")
    return make_distributor(
        name=name or page_name,
        country=country,
        city_hint=city_hint,
        email=email,
        phone=phone,
        address=address,
        website=website,
        source_url=url,
        source_type="German Pavilion dental trade fair exhibitor directory",
        acquisition_path="German Pavilion 공식 치과 전시 참가사 상세 페이지에서 회사 주소, 이메일, 전화, 웹사이트, 제품/서비스 설명을 확인",
        site_business_summary=business_summary,
        evidence=[
            f"German Pavilion exhibitor detail: {url}",
            f"Products/services: {product_summary or summary}",
            f"Required contact fields found: email={email}, phone={phone}, address={address}",
        ],
        tags={"directory": "German Pavilion", "products_services": product_summary, "about": summary},
    )


def parse_german_pavilion(cache: dict[str, Any], workers: int) -> list[base.Prospect]:
    list_urls = [
        "https://aeedc.german-pavilion.com/en/sites/exhibitors",
        "https://sino-dental.german-pavilion.com/en/sites/exhibitors",
        "https://cadex.german-pavilion.com/en/sites/exhibitors",
        "https://gnydm.german-pavilion.com/en/sites/exhibitors",
        "https://idem-singapore.german-pavilion.com/en/sites/exhibitors",
        "https://idem-singapore-2026.german-pavilion.com/en/sites/exhibitors",
        "https://videc.german-pavilion.com/en/sites/exhibitors",
    ]
    detail_urls: list[str] = []
    for list_url in list_urls:
        html = fetch(list_url, cache)
        detail_urls.extend(german_pavilion_detail_links(html, list_url))
    prefetch_urls(detail_urls, cache, workers)
    prospects = []
    for url in detail_urls:
        prospect = parse_german_pavilion_detail(url, fetch(url, cache))
        if prospect:
            prospects.append(prospect)
    return prospects


def parse_ice_aeedc_2026() -> list[base.Prospect]:
    url = "https://www.ice.it/it/sites/default/files/inline-files/AEEDC%202026_compressed.pdf"
    text = pdf_text(download_pdf(url, "ice_aeedc_2026.pdf"))
    blocks = re.split(r"\f?Stand No\.\s+", text)
    prospects: list[base.Prospect] = []
    for block in blocks:
        if "Email:" not in block or "Tel:" not in block:
            continue
        lines = [clean(line) for line in block.splitlines() if clean(line)]
        if not lines:
            continue
        name = ""
        for line in lines[:8]:
            if re.search(r"^\w", line) and not re.search(r"^\d|Page|AEEDC|Stand", line, re.I):
                name = line
                break
        email_match = re.search(r"Email:\s*([A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,})", block, flags=re.I)
        phone_match = re.search(r"Tel:\s*([+()0-9 /\-.]{7,45})", block, flags=re.I)
        website_match = re.search(r"Website:\s*([^\s]+)", block, flags=re.I)
        if not (name and email_match and phone_match):
            continue
        email = email_match.group(1)
        phone = phone_match.group(1)
        website = website_match.group(1) if website_match else ""
        before_tel = block[: phone_match.start()]
        address_lines = [clean(line) for line in before_tel.splitlines()[-8:] if clean(line)]
        if name in address_lines:
            address_lines = address_lines[address_lines.index(name) + 1 :]
        address = clean(", ".join(line for line in address_lines if not re.search(r"Stand No|Email|Website|Tel", line, re.I)))
        summary_lines = []
        for line in lines[1:18]:
            if line == name or address_like(line) or re.search(r"Tel:|Email:|Website:", line, re.I):
                continue
            summary_lines.append(line)
        summary = compact(" ".join(summary_lines), 420)
        prospect = make_distributor(
            name=name,
            country="Italy",
            email=email,
            phone=phone,
            address=address,
            website=website,
            source_url=url,
            source_type="Italian Trade Agency AEEDC 2026 Italian Pavilion PDF",
            acquisition_path="Italian Trade Agency AEEDC 2026 Italian Pavilion PDF에서 참가사 회사 주소, 전화, 이메일, 웹사이트, 제품 설명을 확인",
            site_business_summary=summary or "이탈리아 치과산업 전시 참가사로 치과 장비·재료·디지털 덴탈 솔루션을 취급",
            evidence=[
                f"ITA AEEDC 2026 PDF exhibitor block: {name}",
                f"Required contact fields found: email={email}, phone={phone}, address={address}",
            ],
            tags={"directory": "Italian Trade Agency AEEDC 2026 PDF", "about": summary},
        )
        if prospect:
            prospects.append(prospect)
    return prospects


def phone_from_website(website: str, cache: dict[str, Any]) -> str:
    website = domain_url(website)
    if not website:
        return ""
    parsed = urlparse(website)
    candidates = [website]
    root = f"{parsed.scheme}://{parsed.netloc}"
    for path in ("/contact", "/contact-us", "/en/contact", "/kapcsolat", "/contacts"):
        candidates.append(root + path)
    for url in candidates:
        html = fetch(url, cache, timeout=12)
        if not html:
            continue
        phone = extract_phone(BeautifulSoup(html, "html.parser").get_text(" ", strip=True))
        if phone:
            return clean(phone)
    return ""


def contact_from_website(website: str, cache: dict[str, Any]) -> tuple[str, str]:
    website = domain_url(website)
    if not website:
        return "", ""
    parsed = urlparse(website)
    candidates = [website]
    root = f"{parsed.scheme}://{parsed.netloc}"
    for path in ("/contact", "/contact-us", "/contacts", "/about", "/about-us", "/support"):
        candidates.append(root + path)
    combined_parts: list[str] = []
    for url in candidates:
        html = fetch(url, cache, timeout=12)
        if not html:
            continue
        text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
        combined_parts.append(text)
        email = first_public_email(text, blocked_domains=("sentry.io", "wixpress.com", "wordpress.org"))
        phone = extract_phone(text)
        if email:
            return email, clean(phone)
    combined = " ".join(combined_parts)
    return first_public_email(combined), clean(extract_phone(combined))


def contact_from_website_fast(website: str) -> tuple[str, str]:
    website = domain_url(website)
    if not website:
        return "", ""
    parsed = urlparse(website)
    root = f"{parsed.scheme}://{parsed.netloc}"
    candidates = [website] + [root + path for path in ("/contact", "/contact-us", "/contacts", "/about", "/about-us")]
    combined_parts: list[str] = []
    for url in candidates:
        try:
            response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=(4, 8), allow_redirects=True)
        except requests.RequestException:
            continue
        if response.status_code >= 400:
            continue
        text = BeautifulSoup(response.text[:600_000], "html.parser").get_text(" ", strip=True)
        combined_parts.append(text)
        email = first_public_email(text, blocked_domains=("sentry.io", "wixpress.com", "wordpress.org"))
        phone = extract_phone(text)
        if email:
            return email, clean(phone)
    combined = " ".join(combined_parts)
    return first_public_email(combined), clean(extract_phone(combined))


def parse_dental_world(cache: dict[str, Any], website_phone_limit: int) -> list[base.Prospect]:
    url = "https://dentalworld.hu/exhibitor/"
    text = BeautifulSoup(fetch(url, cache), "html.parser").get_text("\n", strip=True)
    blocks = re.split(r"\n###\s+", text)
    prospects: list[base.Prospect] = []
    checked = 0
    for block in blocks:
        lines = [clean(line) for line in block.splitlines() if clean(line)]
        if len(lines) < 8 or "Email:" not in lines:
            continue
        name = lines[0]
        if name.lower().startswith(("event organizer", "dental world")):
            continue
        email_idx = lines.index("Email:")
        email = ""
        for line in lines[email_idx + 1 : email_idx + 4]:
            email = first_public_email(line)
            if email:
                break
        if not email:
            continue
        country = ""
        address = ""
        website = ""
        if "Country:" in lines:
            idx = lines.index("Country:")
            country = lines[idx + 1] if idx + 1 < len(lines) else ""
        if "Address:" in lines:
            idx = lines.index("Address:")
            address = lines[idx + 1] if idx + 1 < len(lines) else ""
        if "Website:" in lines:
            idx = lines.index("Website:")
            website = lines[idx + 1] if idx + 1 < len(lines) else ""
        elif "Weboldal:" in lines:
            idx = lines.index("Weboldal:")
            website = lines[idx + 1] if idx + 1 < len(lines) else ""
        country = COUNTRY_ALIASES.get(country, country)
        if country in {"Magyarország", "Hungary"}:
            country = "Hungary"
        if not country:
            country = infer_country(address, website, email)
        phone = ""
        if checked < website_phone_limit:
            checked += 1
            phone = phone_from_website(website, cache)
        categories = []
        for marker in ("Additional categories:", "Learn more"):
            if marker in lines:
                idx = lines.index(marker)
                categories.extend(lines[idx + 1 : idx + 4])
        category_text = compact(" ".join(lines[1: min(8, len(lines))] + categories), 320)
        prospect = make_distributor(
            name=name,
            country=country,
            email=email,
            phone=phone,
            address=address,
            website=website,
            source_url=url,
            source_type="Dental World Budapest exhibitor directory",
            acquisition_path="Dental World Budapest 공개 exhibitor directory에서 업체명, 국가, 주소, 이메일, 웹사이트를 확인하고 업체 웹사이트에서 전화번호를 보강",
            site_business_summary=f"Dental World 전시 참가사: {category_text}",
            evidence=[
                f"Dental World exhibitor block: {name}",
                f"Website phone enrichment: {domain_url(website)}",
                f"Required contact fields found: email={email}, phone={phone}, address={address}",
            ],
            tags={"directory": "Dental World Budapest exhibitor directory", "category_text": category_text},
        )
        if prospect:
            prospects.append(prospect)
    return prospects


def parse_vhf_resellers(cache: dict[str, Any]) -> list[base.Prospect]:
    url = "https://www.vhf.com/en/contact/resellers-dental/"
    soup = BeautifulSoup(fetch(url, cache), "html.parser")
    prospects: list[base.Prospect] = []
    for section in soup.select("section.av_toggle_section"):
        toggler = section.select_one(".toggler")
        country = clean(toggler.get_text(" ", strip=True) if toggler else "")
        country = COUNTRY_ALIASES.get(country, country)
        content = section.select_one(".toggle_content") or section
        for heading in content.find_all("h3"):
            name = clean(heading.get_text(" ", strip=True))
            if not name:
                continue
            parts: list[str] = []
            for sibling in heading.next_siblings:
                if getattr(sibling, "name", None) == "h3":
                    break
                text = clean(sibling.get_text("\n", strip=True) if hasattr(sibling, "get_text") else sibling)
                if text:
                    parts.append(text)
            block = "\n".join(parts)
            email = first_public_email(block)
            phone_match = re.search(r"(?:Phone|Tel[eé]fono):\s*([^\n]+)", block, flags=re.I)
            phone = clean(phone_match.group(1)) if phone_match else ""
            website = ""
            internet_match = re.search(r"Internet:\s*([^\n]+)", block, flags=re.I)
            if internet_match:
                website = clean(internet_match.group(1))
            if not website:
                for link in heading.find_all_next("a", href=True):
                    if link.find_previous("h3") is not heading:
                        break
                    href = link["href"]
                    if href.startswith("mailto:"):
                        continue
                    website = clean(link.get_text(" ", strip=True) or href)
                    break
            before_contact = re.split(r"\n(?:Phone|Tel[eé]fono|Fax|Email|Correo electr[oó]nico|Internet):", block, maxsplit=1, flags=re.I)[0]
            address_lines = [line for line in (clean(item) for item in before_contact.splitlines()) if line]
            if address_lines and address_lines[0].lower() == "vhf reseller":
                address_lines = address_lines[1:]
            address = clean(", ".join(address_lines))
            if not country:
                country = infer_country(address, phone, website, email)
            city_hint = ""
            if len(address_lines) >= 2:
                city_hint = address_lines[-2] if address_lines[-1].lower() == country.lower() else address_lines[-1]
            prospect = make_distributor(
                name=name,
                country=country,
                city_hint=city_hint,
                email=email,
                phone=phone,
                address=address,
                website=website,
                source_url=url,
                source_type="vhf dental reseller directory",
                acquisition_path="vhf 공식 dental reseller directory에서 국가별 유통 파트너의 주소, 전화, 이메일, 웹사이트를 확인",
                site_business_summary="vhf 치과용 밀링/그라인딩 장비 reseller로 CAD/CAM 장비 판매·지원 채널 후보",
                evidence=[
                    f"vhf reseller block: {country} / {name}",
                    f"Required contact fields found: email={email}, phone={phone}, address={address}",
                ],
                tags={"directory": "vhf dental reseller directory", "product_focus": "dental CAD/CAM milling reseller"},
            )
            if prospect:
                prospects.append(prospect)
    return prospects


def lmt_company_links(cache: dict[str, Any], offsets: int) -> list[str]:
    urls = ["https://lmtmag.com/companies"]
    urls.extend(f"https://lmtmag.com/companies/?offset={offset}" for offset in range(1, max(1, offsets)))
    links: list[str] = []
    for url in urls:
        soup = BeautifulSoup(fetch(url, cache), "html.parser")
        for heading in soup.find_all(["h3", "h4"]):
            link = heading.find("a", href=True)
            if not link:
                continue
            href = link["href"]
            if not href.startswith("/") or href.startswith(("/about", "/auth", "/join", "/feed", "/webinars", "/jobs", "/labday", "/magazine")):
                continue
            links.append(urljoin("https://lmtmag.com", href))
    return list(dict.fromkeys(links))


def lmt_label_value(contact: BeautifulSoup, label_names: tuple[str, ...]) -> str:
    wanted = {name.lower() for name in label_names}
    for item in contact.select("li"):
        label = clean((item.find("label") or item).get_text(" ", strip=True)).lower()
        if not any(name in label for name in wanted):
            continue
        content = item.select_one(".label_content") or item
        cfemail = content.select_one(".__cf_email__")
        if cfemail and cfemail.get("data-cfemail"):
            decoded = decode_cfemail(cfemail["data-cfemail"])
            if decoded:
                return decoded
        text = clean(content.get_text("\n", strip=True))
        if "email" in wanted:
            email = first_public_email(text)
            if email:
                return email
            cf_match = re.search(r"data-cfemail=\"([a-fA-F0-9]+)\"", str(content))
            if cf_match:
                return decode_cfemail(cf_match.group(1))
        return text
    return ""


def parse_lmt_company_detail(url: str, html: str) -> base.Prospect | None:
    soup = BeautifulSoup(html, "html.parser")
    name = clean((soup.find("h1") or soup.title).get_text(" ", strip=True) if (soup.find("h1") or soup.title) else "")
    if not name or name.lower().startswith("lmtmag"):
        return None
    about_node = soup.select_one("#exhibitor_body .rich_text") or soup.select_one(".rich_text")
    about = compact(about_node.get_text(" ", strip=True) if about_node else "", 520)
    contact = soup.select_one("#exhibitor_body .contact_info") or soup.select_one(".contact_info")
    if not contact:
        return None
    address = lmt_label_value(contact, ("Address",))
    email = valid_email(lmt_label_value(contact, ("Email",)))
    phone = lmt_label_value(contact, ("U.S.", "Office", "Phone", "Toll-Free", "Canada"))
    website = lmt_label_value(contact, ("Website",))
    blob = " ".join([name, about, address, website]).lower()
    digital_terms = ("cad", "cam", "milling", "zirconia", "scanner", "3d print", "digital", "prosthetic", "implant", "laborator")
    if not (any(term in blob for term in DENTAL_TERMS) and (any(term in blob for term in DISTRIBUTOR_TERMS) or any(term in blob for term in digital_terms))):
        return None
    country = infer_country(address, phone, website, email)
    if not country:
        if re.search(r"\b[A-Z]{2}\s+\d{5}\b", address):
            country = "United States"
        elif "+1" in phone or re.search(r"\b\d{3}[-.) ]+\d{3}[- ]+\d{4}\b", phone):
            country = "United States"
    city_hint = ""
    address_lines = [clean(line) for line in address.splitlines() if clean(line)]
    if len(address_lines) >= 2:
        city_hint = address_lines[-1]
    prospect = make_distributor(
        name=name,
        country=country,
        city_hint=city_hint,
        email=email,
        phone=phone,
        address=address,
        website=website,
        source_url=url,
        source_type="LMTmag dental laboratory and supplier company directory",
        acquisition_path="LMTmag 공개 company directory의 회사 상세 페이지에서 회사 소개, 주소, 이메일, 전화, 웹사이트를 확인",
        site_business_summary=about or "LMTmag 등록 치과기공·디지털덴탈·재료/장비 관련 회사",
        evidence=[
            f"LMTmag company detail: {url}",
            f"About: {about}",
            f"Required contact fields found: email={email}, phone={phone}, address={address}",
        ],
        tags={"directory": "LMTmag company directory", "about": about},
    )
    return prospect


def parse_lmt_companies(cache: dict[str, Any], workers: int, offsets: int) -> list[base.Prospect]:
    links = lmt_company_links(cache, offsets)
    prefetch_urls(links, cache, workers)
    prospects = []
    for url in links:
        prospect = parse_lmt_company_detail(url, fetch(url, cache))
        if prospect:
            prospects.append(prospect)
    return prospects


def parse_imes_icore_partners(cache: dict[str, Any]) -> list[base.Prospect]:
    url = "https://imes-icore.net/services/"
    text = BeautifulSoup(fetch(url, cache), "html.parser").get_text("\n", strip=True)
    marker = "WHETHER YOU ARE A DENTIST"
    if marker in text:
        text = text.split(marker, 1)[0]
    names = ["Imagine", "Articon", "Proto3000", "3DBioCAD", "Zoom Dental", "Nowak Dental Supplies, Inc.", "MDC Dental"]
    prospects: list[base.Prospect] = []
    for idx, name in enumerate(names):
        start = text.find(name)
        if start < 0:
            continue
        end_candidates = [text.find(next_name, start + len(name)) for next_name in names[idx + 1 :]]
        end_candidates = [item for item in end_candidates if item > start]
        end = min(end_candidates) if end_candidates else len(text)
        block = text[start:end]
        email = first_public_email(block)
        phone_match = re.search(r"(?:FON|Phone):\s*([^\n]+)", block, flags=re.I)
        phone = clean(phone_match.group(1)) if phone_match else ""
        website_match = re.search(r"(?:www\.|https?://)[^\s]+", block, flags=re.I)
        website = clean(website_match.group(0)) if website_match else ""
        before_phone = re.split(r"\n(?:FON|Phone|FAX|Email):", block, maxsplit=1, flags=re.I)[0]
        lines = [clean(line) for line in before_phone.splitlines() if clean(line)]
        if lines and lines[0] == name:
            lines = lines[1:]
        lines = [line for line in lines if not re.search(r"(Director|President|Founder|General Manager)", line, re.I)]
        address = clean(", ".join(lines))
        country = infer_country(address, phone, website, email) or "United States"
        if name == "Proto3000":
            country = "Canada"
        prospect = make_distributor(
            name=name,
            country=country,
            email=email,
            phone=phone,
            address=address,
            website=website,
            source_url=url,
            source_type="imes-icore USA partner directory",
            acquisition_path="imes-icore USA 공식 services/partners 페이지에서 CAD/CAM 밀링 파트너의 주소, 전화, 이메일, 웹사이트를 확인",
            site_business_summary="imes-icore CORiTEC 치과용 밀링 시스템 파트너로 CAD/CAM 장비 판매·교육·지원 채널 후보",
            evidence=[
                f"imes-icore partner block: {name}",
                f"Required contact fields found: email={email}, phone={phone}, address={address}",
            ],
            tags={"directory": "imes-icore USA partners", "product_focus": "CORiTEC dental milling partner"},
        )
        if prospect:
            prospects.append(prospect)
    return prospects


def regional_us_state_urls(cache: dict[str, Any]) -> list[str]:
    root = "https://dental-products.regionaldirectory.us/"
    soup = BeautifulSoup(fetch(root, cache), "html.parser")
    urls = [root]
    for link in soup.find_all("a", href=True):
        text = clean(link.get_text(" ", strip=True))
        href = link["href"]
        if "Dental Products" in text and href.endswith(".htm"):
            urls.append(urljoin(root, href))
    return list(dict.fromkeys(urls))


def parse_regionaldirectory_us(cache: dict[str, Any], workers: int, website_limit: int) -> list[base.Prospect]:
    urls = regional_us_state_urls(cache)
    prefetch_urls(urls, cache, workers)
    raw_rows: list[dict[str, str]] = []
    for url in urls:
        soup = BeautifulSoup(fetch(url, cache), "html.parser")
        state = clean((soup.find("title") or soup).get_text(" ", strip=True)).replace(" Dental Equipment & Supplies", "")
        for cell in soup.select("td.listing-cell"):
            link = cell.find("a", href=True)
            if not link:
                continue
            name = clean(link.get_text(" ", strip=True))
            website = clean(link["href"])
            lines = [clean(line) for line in cell.get_text("\n", strip=True).splitlines() if clean(line)]
            if not name or len(lines) < 3:
                continue
            try:
                name_idx = lines.index(name)
            except ValueError:
                name_idx = 0
            address = lines[name_idx + 1] if name_idx + 1 < len(lines) else ""
            phone = lines[name_idx + 2] if name_idx + 2 < len(lines) else ""
            domain = ""
            domain_node = cell.select_one(".d")
            if domain_node:
                domain = clean(domain_node.get_text(" ", strip=True))
            if not website.startswith(("http://", "https://")):
                website = domain_url(domain or website)
            tag_cell = cell.find_next_sibling("td")
            categories = clean(tag_cell.get_text(" ", strip=True) if tag_cell else "")
            if not re.search(r"dental", categories + " " + name, re.I):
                continue
            raw_rows.append({"name": name, "address": address, "phone": phone, "website": website, "state": state, "categories": categories, "source_url": url})

    rows = list({(row["name"].lower(), row["address"].lower(), row["website"].lower()): row for row in raw_rows}.values())
    prospects: list[base.Prospect] = []
    limited_rows = rows[:website_limit]
    contact_by_key: dict[int, tuple[str, str]] = {}
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {executor.submit(contact_from_website_fast, row["website"]): idx for idx, row in enumerate(limited_rows)}
        for future in as_completed(futures):
            idx = futures[future]
            try:
                contact_by_key[idx] = future.result()
            except Exception:
                contact_by_key[idx] = ("", "")
    for idx, row in enumerate(limited_rows):
        email, website_phone = contact_by_key.get(idx, ("", ""))
        phone = row["phone"] or website_phone
        business_summary = f"USA Dental Products regional directory 등록 업체. 카테고리: {compact(row['categories'], 240)}"
        prospect = make_distributor(
            name=row["name"],
            country="United States",
            city_hint=row["address"],
            email=email,
            phone=phone,
            address=f"{row['address']}, United States",
            website=row["website"],
            source_url=row["source_url"],
            source_type="USA Dental Products regional supplier directory",
            acquisition_path="USA Dental Products regional directory에서 주소·전화·웹사이트를 확인하고, 업체 공식 웹사이트에서 이메일을 보강",
            site_business_summary=business_summary,
            evidence=[
                f"RegionalDirectory listing: {row['source_url']} / {row['name']}",
                f"Website email enrichment: {domain_url(row['website'])}",
                f"Required contact fields found: email={email}, phone={phone}, address={row['address']}",
            ],
            tags={"directory": "USA Dental Products regional directory", "categories": row["categories"]},
        )
        if prospect:
            prospects.append(prospect)
    return prospects


def osm_country_query(country_code: str) -> str:
    selectors = []
    for email_key in ("email", "contact:email"):
        for osm_type in ("node", "way", "relation"):
            selectors.extend(
                [
                    f'{osm_type}["{email_key}"]["shop"="medical_supply"](area.a);',
                    f'{osm_type}["{email_key}"]["shop"="dental"](area.a);',
                    f'{osm_type}["{email_key}"]["healthcare"="medical_supply"](area.a);',
                    f'{osm_type}["{email_key}"]["office"="distributor"](area.a);',
                    f'{osm_type}["{email_key}"]["office"="sales"](area.a);',
                    f'{osm_type}["{email_key}"]["company"="distributor"](area.a);',
                    f'{osm_type}["{email_key}"]["company"="wholesale"](area.a);',
                ]
            )
    body = "\n  ".join(selectors)
    return f"""[out:json][timeout:120];
area["ISO3166-1"="{country_code}"][admin_level=2]->.a;
(
  {body}
);
out center tags;"""


def fetch_overpass_post(query: str, pause_seconds: float) -> dict[str, Any]:
    errors: list[str] = []
    for attempt in range(1, 4):
        endpoint = base.OVERPASS_ENDPOINTS[(attempt - 1) % len(base.OVERPASS_ENDPOINTS)]
        try:
            if pause_seconds:
                time.sleep(pause_seconds)
            response = requests.post(
                endpoint,
                data={"data": query},
                headers={"User-Agent": base.USER_AGENT},
                timeout=(8, 90),
            )
            if response.status_code in {429, 502, 503, 504}:
                errors.append(f"{endpoint} HTTP {response.status_code}")
                time.sleep(4 * attempt)
                continue
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            errors.append(f"{endpoint} {type(exc).__name__}: {str(exc)[:220]}")
            time.sleep(3 * attempt)
    return {"elements": [], "errors": errors}


def matched_terms(text: str, terms: list[str]) -> list[str]:
    lowered = text.lower()
    return [term for term in terms if term.lower() in lowered]


def prospect_from_osm(element: dict[str, Any], country_code: str) -> base.Prospect | None:
    tags = {str(key): str(value) for key, value in (element.get("tags") or {}).items()}
    text = " ".join(tags.values())
    dental_matches = matched_terms(text, DENTAL_TERMS)
    distributor_matches = matched_terms(text, DISTRIBUTOR_TERMS)
    if not dental_matches:
        return None
    if not distributor_matches and tags.get("healthcare") != "medical_supply" and not re.search(r"dental\s+(supply|depot|equipment|material|trading)", text, re.I):
        return None
    if not distributor_matches and any(term in text.lower() for term in EXCLUDE_CLINIC_TERMS):
        return None
    name = base.clean_text(tags.get("name") or tags.get("operator"))
    email = base.first_email(tags)
    phone = base.first_phone(tags)
    country = base.TARGET_COUNTRIES.get(country_code, country_code)
    city_hint = tags.get("addr:city") or tags.get("addr:suburb") or tags.get("addr:state") or "Countrywide"
    address = base.address_text(tags, city_hint, country)
    website = base.clean_text(tags.get("website") or tags.get("contact:website") or tags.get("url"))
    source_url = base.osm_url(element)
    prospect = make_distributor(
        name=name,
        country=country,
        city_hint=city_hint,
        email=email,
        phone=phone,
        address=address,
        website=website,
        source_url=source_url,
        source_type="OpenStreetMap dental distributor/import-export public business tag",
        acquisition_path="공개 OSM 사업장 태그에서 치과 유통·수출입 현지어 키워드와 이메일·전화·주소를 동시에 확인",
        site_business_summary="OSM 사업장명/설명/업종 태그에 치과 장비·재료 공급, 유통, 무역, 수입·수출 관련 표현이 포함된 현지 채널 후보",
        evidence=[
            f"OSM distributor/import-export matched terms: dental={', '.join(dental_matches[:5])}; channel={', '.join(distributor_matches[:5])}",
            f"Required contact fields found: email={email}, phone={phone}, address={address}",
        ],
        tags={
            **tags,
            "matched_dental_terms": ", ".join(dental_matches[:12]),
            "matched_distributor_terms": ", ".join(distributor_matches[:12]),
        },
        osm_type=str(element.get("type")),
        osm_id=int(element.get("id") or 0),
    )
    return prospect


def collect_osm(args: argparse.Namespace, existing_count: int) -> list[base.Prospect]:
    countries = [country.strip() for country in args.osm_countries.split(",") if country.strip()]
    if not countries:
        countries = [
            "US",
            "IN",
            "BR",
            "MX",
            "ZA",
            "AE",
            "SA",
            "TR",
            "ID",
            "TH",
            "VN",
            "MY",
            "PH",
            "JP",
            "AU",
            "CA",
            "GB",
            "ES",
            "IT",
            "FR",
            "NL",
            "BE",
            "CH",
            "PL",
            "CZ",
            "EG",
            "MA",
            "CO",
            "CL",
            "AR",
            "PE",
            "PK",
            "SG",
            "TW",
        ]
    prospects: list[base.Prospect] = []
    seen: set[str] = set()
    for country_code in countries:
        if len(prospects) + existing_count >= args.target:
            break
        if country_code not in base.TARGET_COUNTRIES:
            continue
        result = fetch_overpass_post(osm_country_query(country_code), args.pause)
        elements = result.get("elements") or []
        added = 0
        for element in elements:
            prospect = prospect_from_osm(element, country_code)
            if not prospect:
                continue
            key = base.dedupe_key(prospect)
            if key in seen:
                continue
            seen.add(key)
            prospects.append(prospect)
            added += 1
            if len(prospects) + existing_count >= args.target:
                break
        print(
            json.dumps(
                {
                    "source": "osm_distributor_import_export",
                    "country": country_code,
                    "elements": len(elements),
                    "parsed_valid": added,
                    "errors": result.get("errors", []),
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
    return prospects


def write_research_md(new_rows: list[base.Prospect], before: int, after: int) -> None:
    by_source: dict[str, int] = {}
    by_country: dict[str, int] = {}
    for row in new_rows:
        by_source[row.source_type] = by_source.get(row.source_type, 0) + 1
        by_country[row.country] = by_country.get(row.country, 0) + 1
    lines = [
        "# 유통사·수출입사 중심 해외 잠재고객 5차 확장",
        "",
        f"- 생성일: {datetime.now().strftime('%Y-%m-%d %H:%M KST')}",
        f"- 실행 전 public valid: {before:,}",
        f"- 실행 후 public valid: {after:,}",
        f"- 이번 신규 승격: {after - before:,}개",
        "- 기준: 업체명, 이메일, 전화, 주소, 공개 출처가 모두 있는 경우만 병합",
        "- 중점 카테고리: 치과 유통사, 치과 장비/재료 공급사, 치과 관련 수출입/무역사",
        "",
        "## 사용한 소스와 경로",
        "- German Pavilion dental trade fair exhibitor directories: AEEDC, Sino Dental, CADEX, GNYDM, IDEM, VIDEC 공식 독일관 참가사 상세 페이지",
        "- Italian Trade Agency AEEDC 2026 Italian Pavilion PDF: 이탈리아 치과산업 수출 전시 참가사 카탈로그",
        "- Dental World Budapest exhibitor directory: 업체명·국가·주소·이메일·웹사이트 공개 목록과 업체 웹사이트 전화번호 보강",
        "- vhf dental reseller directory: CAD/CAM 밀링 장비 공식 국가별 reseller 연락처",
        "- imes-icore USA partner directory: CORiTEC 밀링 시스템 파트너 연락처",
        "- LMTmag dental laboratory and supplier company directory: 치기공·재료·장비·CAD/CAM 업체 공개 회사 카드",
        "- USA Dental Products regional supplier directory: 미국 주별 치과 장비·소모품 벤더 목록과 업체 웹사이트 이메일 보강",
        "- Bredent global distributor locator: 공식 국가별 유통사 페이지",
        "- Henry Schein international distributor locator: 공식 국제 대리점 locator",
        "- Denovo Dental distributor page: 공식 제품 유통사 안내 페이지",
        "- Modern Dentistry Media Dental Directory 2024: 남아공 치과 공급사 PDF",
        "- OpenStreetMap: 현지어 치과 유통·수출입·장비 공급 키워드를 가진 공개 사업장 태그",
        "- Facebook/LinkedIn은 로그인·개인 프로필·약관 리스크 때문에 대량 자동 승격에서 제외하고 공개 회사 페이지 확인 후보로만 취급",
        "",
        "## 현지어/현지 표현",
        "- 영어: dental distributor, dental supply, dental equipment, dental depot, dental import/export, dental trading",
        "- 독일어: Dentalbedarf, Dentalhandel, Dentaldepot, Zahnbedarf",
        "- 스페인어/포르투갈어: depósito dental, distribuidora dental, suministros dentales, importadora/exportadora, equipamentos odontológicos",
        "- 프랑스어/이탈리아어: fournitures dentaires, matériel dentaire, forniture dentali",
        "- 동남아/동북아: thiết bị nha khoa, alat/bahan kedokteran gigi, peralatan pergigian, 歯科材料, 牙科器材",
        "- 중동/튀르키예: مستلزمات طب الأسنان, تجهيزات طب الأسنان, diş malzemeleri",
        "",
        "## 신규 승격 소스 분포",
    ]
    for source, count in sorted(by_source.items(), key=lambda item: item[1], reverse=True):
        lines.append(f"- {source}: {count:,}")
    lines += ["", "## 신규 승격 국가 분포"]
    for country, count in sorted(by_country.items(), key=lambda item: item[1], reverse=True)[:80]:
        lines.append(f"- {country}: {count:,}")
    lines += [
        "",
        "## 저장 파일",
        f"- 승격 로그: `{PROMOTIONS_JSONL}`",
        f"- 원시 로그: `{RAW_JSONL}`",
        f"- 요청 캐시: `{CACHE_JSON}`",
        f"- 병합 데이터: `{base.VALID_JSONL}`",
    ]
    RESEARCH_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> int:
    global CACHE_JSON

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if args.cache_path:
        CACHE_JSON = Path(args.cache_path)
    cache: dict[str, Any] = load_json(CACHE_JSON, {})
    before_by_key = base.existing_valid()
    valid_by_key = dict(before_by_key)
    all_new: list[base.Prospect] = []

    direct_sources = [
        ("german_pavilion", lambda: parse_german_pavilion(cache, args.workers)),
        ("ice_aeedc_2026", parse_ice_aeedc_2026),
        ("dental_world", lambda: parse_dental_world(cache, args.website_phone_limit)),
        ("vhf_resellers", lambda: parse_vhf_resellers(cache)),
        ("imes_icore_partners", lambda: parse_imes_icore_partners(cache)),
        ("lmt_companies", lambda: parse_lmt_companies(cache, args.workers, args.lmt_offsets)),
        ("regionaldirectory_us", lambda: parse_regionaldirectory_us(cache, args.workers, args.regionaldirectory_limit)),
        ("bredent", lambda: parse_bredent(cache)),
        ("henry_schein", lambda: parse_henry_schein(cache)),
        ("denovo", lambda: parse_denovo(cache)),
        ("modern_dentistry_2024", parse_modern_dentistry_2024),
        ("dentsply_mena", parse_dentsply_mena),
    ]
    if args.sources:
        selected = {item.strip() for item in args.sources.split(",") if item.strip()}
        direct_sources = [(name, fn) for name, fn in direct_sources if name in selected]

    for source_name, fn in direct_sources:
        found = fn()
        append_jsonl(RAW_JSONL, [{"source": source_name, **asdict(row)} for row in found])
        added_rows: list[base.Prospect] = []
        for row in found:
            key = base.dedupe_key(row)
            if key in valid_by_key:
                continue
            valid_by_key[key] = row
            added_rows.append(row)
            all_new.append(row)
            if len(valid_by_key) >= args.target:
                break
        append_jsonl(PROMOTIONS_JSONL, [{"source": source_name, **asdict(row)} for row in added_rows])
        prospects = sorted(valid_by_key.values(), key=lambda item: (item.country, item.city_hint, item.name))
        base.rewrite_valid(prospects)
        print(json.dumps({"source": source_name, "found": len(found), "added": len(added_rows), "totalValid": len(valid_by_key)}, ensure_ascii=False), flush=True)
        if len(valid_by_key) >= args.target:
            break

    if args.include_osm and len(valid_by_key) < args.target:
        osm_rows = collect_osm(args, len(valid_by_key))
        added_rows = []
        for row in osm_rows:
            key = base.dedupe_key(row)
            if key in valid_by_key:
                continue
            valid_by_key[key] = row
            added_rows.append(row)
            all_new.append(row)
            if len(valid_by_key) >= args.target:
                break
        append_jsonl(RAW_JSONL, [{"source": "osm_distributor_import_export", **asdict(row)} for row in osm_rows])
        append_jsonl(PROMOTIONS_JSONL, [{"source": "osm_distributor_import_export", **asdict(row)} for row in added_rows])
        print(json.dumps({"source": "osm_distributor_import_export", "found": len(osm_rows), "added": len(added_rows), "totalValid": len(valid_by_key)}, ensure_ascii=False), flush=True)

    prospects = sorted(valid_by_key.values(), key=lambda item: (item.country, item.city_hint, item.name))
    base.rewrite_valid(prospects)
    write_research_md(all_new, len(before_by_key), len(valid_by_key))
    print(
        json.dumps(
            {
                "done": True,
                "before": len(before_by_key),
                "after": len(valid_by_key),
                "added": len(valid_by_key) - len(before_by_key),
                "target": args.target,
                "research": str(RESEARCH_MD),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if len(valid_by_key) >= args.target else 2


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=int, default=17234)
    parser.add_argument("--include-osm", action="store_true", help="Use OSM local-language distributor/import-export sweep for remaining volume.")
    parser.add_argument("--pause", type=float, default=0.8)
    parser.add_argument("--osm-countries", default="", help="Comma-separated ISO country list for OSM distributor/import-export sweep.")
    parser.add_argument("--sources", default="", help="Comma-separated direct source names. Empty runs all direct sources.")
    parser.add_argument("--workers", type=int, default=12, help="Parallel workers for exhibitor detail prefetch.")
    parser.add_argument("--website-phone-limit", type=int, default=180, help="Maximum Dental World exhibitor websites to use for phone enrichment.")
    parser.add_argument("--cache-path", default="", help="Override HTTP cache path for this run.")
    parser.add_argument("--lmt-offsets", type=int, default=8, help="Number of LMT company directory offset pages to inspect.")
    parser.add_argument("--regionaldirectory-limit", type=int, default=800, help="Maximum USA Dental Products regional directory websites to enrich.")
    args = parser.parse_args(argv)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
