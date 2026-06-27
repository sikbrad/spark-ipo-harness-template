#!/usr/bin/env python3
"""Expand DOF overseas prospects from major dental exhibition exhibitors.

Rows are promoted only when the public exhibitor profile provides a company
identity/address/source and the company's own website exposes both email and
phone. The main source in this round is the official IDS Cologne 2025 exhibitor
search because it is large, public, and stable enough to provide address and
website data for global dental equipment vendors.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

import dof_prospect_scale5000 as base
import dof_distributor_import_export_research as dist


ROOT = Path("/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04")
OUT_ROOT = ROOT / "output/dof-overseas-customer-prospects/2026-05-30/scale5000"
DATA_DIR = OUT_ROOT / "data"
PDF_DIR = DATA_DIR / "source_pdfs"
RAW_JSONL = DATA_DIR / "exhibition_vendor_raw_round6.jsonl"
PROMOTIONS_JSONL = DATA_DIR / "exhibition_vendor_promotions_round6.jsonl"
CACHE_JSON = DATA_DIR / "exhibition_vendor_cache_round6.json"
RESEARCH_MD = OUT_ROOT / "external_exhibition_vendor_research_round6.md"

USER_AGENT = dist.USER_AGENT
IDS_LIST_URL = "https://www.english.ids-cologne.de/ids-cologne-exhibitors/list-of-exhibitors/"
IDS_BASE_URL = "https://www.english.ids-cologne.de"
IDS_SOURCE_TYPE = "IDS Cologne 2025 official exhibitor search"
IDS_PRELIMINARY_PDF_URL = "https://media.koelnmesse.io/ids/redaktionell/ids/downloads/pdf/exhibitors-of-ids/preliminary-exhibitor-list.pdf"
IDS_PRELIMINARY_SOURCE_TYPE = "IDS Cologne 2025 preliminary exhibitor list PDF and official website contact"
GNYDM_2025_URL = "https://gnydm2025.smallworldlabs.com/exhibitors"
GNYDM_2025_BASE = "https://gnydm2025.smallworldlabs.com"
GNYDM_SOURCE_TYPE = "Greater New York Dental Meeting 2025 official exhibitor directory"
SMALLWORLD_DENTAL_SOURCE_TYPE = "SmallWorldLabs official dental exhibition exhibitor directory"
SMALLWORLD_DENTAL_EVENTS = [
    {
        "key": "hinman25",
        "event": "Thomas P. Hinman Dental Meeting 2025",
        "url": "https://hinman25.smallworldlabs.com/exhibitors",
        "base": "https://hinman25.smallworldlabs.com",
    },
    {
        "key": "hinman2026",
        "event": "Thomas P. Hinman Dental Meeting 2026",
        "url": "https://hinman2026.smallworldlabs.com/exhibitors",
        "base": "https://hinman2026.smallworldlabs.com",
    },
    {
        "key": "aaorthoannual2025",
        "event": "AAO Annual Meeting 2025",
        "url": "https://aaorthoannual2025.smallworldlabs.com/exhibitors",
        "base": "https://aaorthoannual2025.smallworldlabs.com",
    },
    {
        "key": "sotn25",
        "event": "Star of the North Meeting 2025",
        "url": "https://sotn25.smallworldlabs.com/exhibitors",
        "base": "https://sotn25.smallworldlabs.com",
    },
    {
        "key": "yankee2026",
        "event": "Yankee Dental Congress 2026",
        "url": "https://yankee2026.smallworldlabs.com/exhibitors",
        "base": "https://yankee2026.smallworldlabs.com",
    },
    {
        "key": "aaorthowintermeeting2025",
        "event": "AAO Winter Meeting 2025",
        "url": "https://aaorthowintermeeting2025.smallworldlabs.com/exhibitors",
        "base": "https://aaorthowintermeeting2025.smallworldlabs.com",
    },
    {
        "key": "aaorthowintermeeting2026",
        "event": "AAO Winter Meeting 2026",
        "url": "https://aaorthowintermeeting2026.smallworldlabs.com/exhibitors",
        "base": "https://aaorthowintermeeting2026.smallworldlabs.com",
    },
    {
        "key": "sotn26",
        "event": "Star of the North Meeting 2026",
        "url": "https://sotn26.smallworldlabs.com/exhibitors",
        "base": "https://sotn26.smallworldlabs.com",
    },
    {
        "key": "adea2026",
        "event": "ADEA Annual Session & Exhibition 2026",
        "url": "https://adea2026.smallworldlabs.com/exhibitors",
        "base": "https://adea2026.smallworldlabs.com",
    },
]

CACHE_LOCK = threading.Lock()
NOISE_LINES = {
    "",
    "share",
    "Facebook Twitter LinkedIn copy link",
    "print version add to favorites",
    "Log-In for favorites functionality",
    "Log in for contact details",
    "more information",
    "back",
    "To the search overview back",
    "Favorites",
}


def clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def load_json(path: Path, default: Any) -> Any:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def save_json(path: Path, data: Any) -> None:
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


def cached_get(url: str, cache: dict[str, Any], timeout: int = 24) -> str:
    with CACHE_LOCK:
        cached = cache.get(url)
    if cached is not None:
        return str(cached)
    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=(5, timeout), allow_redirects=True)
        if response.status_code >= 400:
            text = ""
        else:
            text = response.text
    except requests.RequestException:
        text = ""
    with CACHE_LOCK:
        cache[url] = text
        if len(cache) % 100 == 0:
            save_json(CACHE_JSON, cache)
    return text


def public_external_url(href: str) -> str:
    href = clean(href)
    if not href or href.startswith(("mailto:", "tel:", "#")):
        return ""
    if href.startswith("//"):
        href = "https:" + href
    if not href.startswith(("http://", "https://")):
        return ""
    host = urlparse(href).hostname or ""
    if host.endswith("ids-cologne.de") or host.endswith("koelnmesse.de") or host.endswith("linkedin.com"):
        return ""
    return href


def ids_paginated_url(start: int) -> str:
    paginatevalues = json.dumps({"stichwort": "", "suchart": "alle", "start": start}, separators=(",", ":"))
    return (
        f"{IDS_LIST_URL}?route=aussteller%2Fblaettern&fw_goto=aussteller%2Fblaettern"
        f"&paginatevalues={requests.utils.quote(paginatevalues)}&tab=2&sortAby="
    )


def collect_ids_links(cache: dict[str, Any], max_offsets: int) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for start in range(0, max_offsets, 20):
        url = IDS_LIST_URL if start == 0 else ids_paginated_url(start)
        html = cached_get(url, cache)
        if not html:
            continue
        soup = BeautifulSoup(html, "html.parser")
        page_links: list[dict[str, str]] = []
        for link in soup.find_all("a", href=True):
            href = link["href"]
            name = clean(link.get_text(" ", strip=True))
            if not href.startswith("/exhibitor/") or not name:
                continue
            full_url = urljoin(IDS_BASE_URL, href)
            if full_url in seen:
                continue
            seen.add(full_url)
            page_links.append({"name": name, "url": full_url})
        rows.extend(page_links)
        if len(page_links) < 10:
            break
    return rows


def text_lines(soup: BeautifulSoup) -> list[str]:
    lines: list[str] = []
    for raw in soup.get_text("\n", strip=True).splitlines():
        line = clean(raw)
        if not line:
            continue
        lines.append(line)
    return lines


def detail_address(lines: list[str], name: str) -> str:
    indexes = [idx for idx, line in enumerate(lines) if line == name]
    for idx in reversed(indexes):
        chunk: list[str] = []
        for line in lines[idx + 1 : idx + 9]:
            if line in NOISE_LINES or line.startswith("Hall ") or line.startswith("Represented at"):
                if chunk:
                    break
                continue
            if line.startswith(("www.", "http://", "https://")):
                break
            if line == "/" or line == name:
                continue
            if line.lower().startswith("log in"):
                break
            chunk.append(line)
        address = clean(", ".join(chunk))
        if address and re.search(r"\d", address) and len(address) > 12:
            return address
    return ""


def detail_website(soup: BeautifulSoup) -> str:
    candidates: list[str] = []
    for link in soup.find_all("a", href=True):
        href = public_external_url(link["href"])
        label = clean(link.get_text(" ", strip=True))
        if not href:
            continue
        if "." in label or re.search(r"\.(com|net|org|de|it|cn|co|io|fr|es|us|kr|jp|ch|nl|uk|au)($|/)", href, re.I):
            candidates.append(dist.domain_url(href))
    for candidate in candidates:
        if candidate:
            return candidate
    return ""


def detail_product_summary(soup: BeautifulSoup) -> str:
    lines = text_lines(soup)
    interesting: list[str] = []
    for marker in ("Product sector", "Product emphasis"):
        if marker in lines:
            idx = lines.index(marker)
            for line in lines[idx + 1 : idx + 8]:
                if line in NOISE_LINES or line.startswith(("Favorites", "Subscribe")):
                    break
                if len(line) > 2 and line not in interesting:
                    interesting.append(line)
    product_json = re.findall(r'"text":"([^"]+)"', soup.decode()[:260_000])
    for item in product_json:
        label = clean(item.replace("\\/", "/"))
        if label and label not in interesting and len(interesting) < 10:
            interesting.append(label)
    return clean(", ".join(interesting[:10]))


def parse_ids_detail(item: dict[str, str], cache: dict[str, Any]) -> dict[str, str]:
    html = cached_get(item["url"], cache)
    if not html:
        return {**item, "address": "", "website": "", "country": "", "summary": ""}
    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.find("h1")
    name = clean(h1.get_text(" ", strip=True) if h1 else item["name"])
    lines = text_lines(soup)
    address = detail_address(lines, name)
    website = detail_website(soup)
    country = dist.infer_country(address, website, "")
    summary = detail_product_summary(soup)
    return {
        "name": name or item["name"],
        "url": item["url"],
        "address": address,
        "website": website,
        "country": country,
        "summary": summary,
    }


def cached_contact(website: str, cache: dict[str, Any]) -> tuple[str, str]:
    website = dist.domain_url(website)
    if not website:
        return "", ""
    key = f"contact::{website}"
    with CACHE_LOCK:
        cached = cache.get(key)
    if isinstance(cached, dict):
        cached_email = clean(cached.get("email"))
        cached_phone = clean(cached.get("phone"))
        if cached_email or cached_phone:
            return cached_email, cached_phone
    email, phone = contact_from_company_website(website)
    with CACHE_LOCK:
        cache[key] = {"email": email, "phone": phone}
        if len(cache) % 100 == 0:
            save_json(CACHE_JSON, cache)
    return clean(email), clean(phone)


def html_emails(html: str) -> list[str]:
    emails: list[str] = []
    soup = BeautifulSoup(html[:900_000], "html.parser")
    for link in soup.find_all("a", href=True):
        href = clean(link["href"])
        if href.lower().startswith("mailto:"):
            emails.append(href.split(":", 1)[1].split("?", 1)[0])
    for node in soup.select("[data-cfemail]"):
        decoded = dist.decode_cfemail(node.get("data-cfemail", ""))
        if decoded:
            emails.append(decoded)
    text = soup.get_text(" ", strip=True)
    html_blob = html[:900_000].replace("\\u0040", "@")
    for candidate in [dist.first_public_email(html_blob), dist.first_public_email(text)]:
        if candidate:
            emails.append(candidate)
    valid: list[str] = []
    for item in emails:
        value = dist.valid_email(item)
        if not value:
            continue
        local = value.split("@", 1)[0]
        if local in {"privacy", "datenschutz", "webmaster", "postmaster"}:
            continue
        if value not in valid:
            valid.append(value)
    return valid


def jsonld_addresses(html: str) -> list[str]:
    soup = BeautifulSoup(html[:900_000], "html.parser")
    addresses: list[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, list):
            for item in value:
                walk(item)
            return
        if not isinstance(value, dict):
            return
        value_type = str(value.get("@type") or "").lower()
        if "postaladdress" in value_type:
            parts = [
                value.get("streetAddress"),
                value.get("addressLocality"),
                value.get("addressRegion"),
                value.get("postalCode"),
                value.get("addressCountry"),
            ]
            address = clean(", ".join(str(part) for part in parts if part))
            if address:
                addresses.append(address)
        address = value.get("address")
        if isinstance(address, (dict, list)):
            walk(address)
        elif isinstance(address, str) and re.search(r"\d", address):
            addresses.append(clean(address))
        for item in value.values():
            if isinstance(item, (dict, list)):
                walk(item)

    for script in soup.find_all("script", type=lambda item: item and "ld+json" in item):
        raw = script.string or script.get_text("", strip=True)
        if not raw:
            continue
        try:
            walk(json.loads(raw))
        except json.JSONDecodeError:
            continue
    return [address for address in addresses if 12 <= len(address) <= 260]


def likely_address_line(line: str, country: str) -> bool:
    text = clean(line)
    if len(text) < 12 or len(text) > 220 or "@" in text:
        return False
    lower = text.lower()
    if any(skip in lower for skip in ("cookie", "privacy", "newsletter", "copyright", "all rights reserved", "menu")):
        return False
    markers = (
        "address",
        "head office",
        "headquarters",
        "street",
        "str.",
        "strasse",
        "straße",
        "road",
        "rd.",
        "avenue",
        "ave",
        "boulevard",
        "blvd",
        "industrial",
        "park",
        "zone",
        "via ",
        "viale",
        "piazza",
        "rue ",
        "unit ",
        "suite",
        "floor",
        "building",
        "gmbh",
        "srl",
        "inc.",
        "ltd",
        "co.,",
    )
    if country and country.lower() in lower and re.search(r"\d", text):
        return True
    return bool(re.search(r"\d", text) and any(marker in lower for marker in markers))


def text_address(lines: list[str], country: str) -> str:
    candidates: list[str] = []
    for idx, line in enumerate(lines):
        if not likely_address_line(line, country):
            continue
        block = [line]
        for neighbor in lines[idx + 1 : idx + 4]:
            if len(" ".join(block + [neighbor])) > 230:
                break
            if "@" in neighbor or neighbor.lower().startswith(("tel", "phone", "fax", "email")):
                break
            if country and country.lower() in neighbor.lower() or re.search(r"\d", neighbor):
                block.append(neighbor)
        candidate = clean(", ".join(block))
        if re.search(r"\d", candidate) and len(candidate) >= 18:
            candidates.append(candidate)
    if not candidates:
        return ""
    candidates.sort(key=lambda item: (country.lower() not in item.lower() if country else True, len(item)))
    return candidates[0][:240]


def fetch_contact_html(url: str) -> str:
    try:
        result = subprocess.run(
            [
                "curl",
                "-L",
                "--silent",
                "--show-error",
                "--max-time",
                "5",
                "--connect-timeout",
                "2",
                "-A",
                USER_AGENT,
                url,
            ],
            capture_output=True,
            timeout=7,
        )
    except Exception:
        return ""
    if result.returncode != 0 or not result.stdout:
        return ""
    return result.stdout[:900_000].decode("utf-8", errors="ignore")


def contact_from_company_website_full(website: str, country: str = "") -> tuple[str, str, str]:
    website = dist.domain_url(website)
    if not website:
        return "", "", ""
    parsed = urlparse(website)
    root = f"{parsed.scheme}://{parsed.netloc}"
    paths = (
        "",
        "/contact",
        "/contact-us",
        "/about",
        "/en/contact",
        "/kontakt",
        "/impressum",
        "/contacto",
    )
    candidates = [website if not path else root + path for path in paths]
    all_emails: list[str] = []
    all_text: list[str] = []
    all_addresses: list[str] = []
    for url in candidates:
        html = fetch_contact_html(url)
        if not html:
            continue
        soup = BeautifulSoup(html, "html.parser")
        lines = [clean(line) for line in soup.get_text("\n", strip=True).splitlines() if clean(line)]
        text = " ".join(lines)
        all_text.append(text)
        for email in html_emails(html):
            if email not in all_emails:
                all_emails.append(email)
        for address in jsonld_addresses(html):
            if address not in all_addresses:
                all_addresses.append(address)
        address = text_address(lines, country)
        if address and address not in all_addresses:
            all_addresses.append(address)
        phone = clean(dist.extract_phone(text))
        if all_emails and phone and all_addresses:
            return all_emails[0], phone, all_addresses[0]
    return (
        all_emails[0] if all_emails else "",
        clean(dist.extract_phone(" ".join(all_text))),
        all_addresses[0] if all_addresses else "",
    )


def contact_from_company_website(website: str) -> tuple[str, str]:
    email, phone, _address = contact_from_company_website_full(website)
    return email, phone


def email_from_company_website(website: str) -> str:
    website = dist.domain_url(website)
    if not website:
        return ""
    parsed = urlparse(website)
    root = f"{parsed.scheme}://{parsed.netloc}"
    paths = ("", "/contact", "/contact-us", "/en/contact", "/kontakt", "/impressum", "/contacto")
    candidates = [website if not path else root + path for path in paths]
    for url in candidates:
        html = fetch_contact_html(url)
        if not html:
            continue
        emails = html_emails(html)
        if emails:
            return emails[0]
    return ""


def cached_email(website: str, cache: dict[str, Any]) -> str:
    website = dist.domain_url(website)
    if not website:
        return ""
    key = f"email::{website}"
    with CACHE_LOCK:
        cached = cache.get(key)
    if isinstance(cached, str) and cached:
        return clean(cached)
    email = email_from_company_website(website)
    with CACHE_LOCK:
        cache[key] = email
        if len(cache) % 100 == 0:
            save_json(CACHE_JSON, cache)
    return clean(email)


def cached_contact_full(website: str, country: str, cache: dict[str, Any]) -> tuple[str, str, str]:
    website = dist.domain_url(website)
    if not website:
        return "", "", ""
    key = f"contact_full::{website}"
    with CACHE_LOCK:
        cached = cache.get(key)
    if isinstance(cached, dict):
        cached_email = clean(cached.get("email"))
        cached_phone = clean(cached.get("phone"))
        cached_address = clean(cached.get("address"))
        if cached_email or cached_phone or cached_address:
            return cached_email, cached_phone, cached_address
    email, phone, address = contact_from_company_website_full(website, country)
    with CACHE_LOCK:
        cache[key] = {"email": email, "phone": phone, "address": address}
        if len(cache) % 100 == 0:
            save_json(CACHE_JSON, cache)
    return clean(email), clean(phone), clean(address)


def pdf_text(url: str, filename: str) -> str:
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    path = PDF_DIR / filename
    if not path.exists():
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=60)
        response.raise_for_status()
        path.write_bytes(response.content)
    try:
        result = subprocess.run(["pdftotext", "-layout", str(path), "-"], check=True, capture_output=True, text=True, timeout=90)
    except Exception:
        return ""
    return result.stdout


def parse_ids_preliminary_pdf() -> list[dict[str, str]]:
    text = pdf_text(IDS_PRELIMINARY_PDF_URL, "ids_2025_preliminary_exhibitor_list.pdf")
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    countries = sorted(set(dist.KNOWN_COUNTRIES) | {"Republic of Korea", "Great Britain", "USA", "Türkiye"}, key=len, reverse=True)
    for raw in text.splitlines():
        line = clean(raw)
        if not line or "Exhibitor Country Website" in line or line.startswith("Status:"):
            continue
        match = re.search(r"\s((?:https?://|www\.)\S+|[A-Za-z0-9][A-Za-z0-9.\-]+\.[A-Za-z]{2,}(?:/\S*)?)$", line)
        if not match:
            continue
        website = match.group(1)
        if website.lower() == "specified" or "not specified" in line.lower():
            continue
        prefix = line[: match.start()].strip()
        country = ""
        name = ""
        for candidate in countries:
            token = " " + candidate
            if prefix.endswith(token):
                country = candidate
                name = prefix[: -len(token)].strip()
                break
            idx = prefix.rfind(token + " ")
            if idx > 0:
                country = candidate
                name = prefix[:idx].strip()
                break
        if not name or not country:
            continue
        country = dist.COUNTRY_ALIASES.get(country, country)
        if country == "Republic of Korea":
            country = "South Korea"
        if country == "Great Britain":
            country = "United Kingdom"
        if country == "USA":
            country = "United States"
        key = (name.lower(), dist.domain_url(website).lower())
        if key in seen:
            continue
        seen.add(key)
        rows.append({"name": name, "country": country, "website": dist.domain_url(website), "source_url": IDS_PRELIMINARY_PDF_URL})
    return rows


def extract_label_block(lines: list[str], label: str) -> str:
    if label not in lines:
        return ""
    idx = lines.index(label)
    values: list[str] = []
    stop_labels = {"Name", "What We Do", "Website", "Categories (3)", "Phone", "Address", "Contacts", "Share:", "[Cancel]"}
    for line in lines[idx + 1 : idx + 8]:
        if line in stop_labels:
            break
        values.append(line)
    return clean(", ".join(values))


def smallworld_tokens(session: requests.Session, cache: dict[str, Any], url: str) -> tuple[str, str, str]:
    html = cached_get(url, cache)
    if not html:
        response = session.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        html = response.text
    tk_match = re.search(r"var tk='([^']+)'", html)
    tm_match = re.search(r"var tm='([^']+)'", html)
    if not (tk_match and tm_match):
        raise RuntimeError(f"SmallWorldLabs tokens not found for {url}")
    return tk_match.group(1), tm_match.group(1), html


def gnydm_tokens(session: requests.Session, cache: dict[str, Any]) -> tuple[str, str, str]:
    return smallworld_tokens(session, cache, GNYDM_2025_URL)


def parse_smallworld_cards(html: str, base_url: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for button in soup.select("[data-option-url]"):
        profile = clean(button.get("data-option-url"))
        if not profile.startswith("/co/"):
            continue
        container = button.find_parent("tr") or button.find_parent(class_="card") or button.find_parent(class_="row") or button.parent
        label = clean(button.get_text(" ", strip=True))
        if label.lower() in {"explore", "view", "details"}:
            label = ""
        heading = container.find(["h5", "h4", "h3"]) if container else None
        text = clean(container.get_text(" ", strip=True) if container else "")
        name = clean(heading.get_text(" ", strip=True) if heading else label)
        if not name and text:
            name = re.split(r"\s+(?:Booth|#\d+|Explore)\b", text, maxsplit=1)[0]
        name = clean(name)
        if not name:
            continue
        website = ""
        for link in (container.find_all("a", href=True) if container else []):
            href = clean(link.get("href"))
            if href.startswith(("http://", "https://")) and "smallworldlabs.com" not in href and "a2zinc.net" not in href:
                website = href
                break
        rows.append({"name": name, "profile": urljoin(base_url, profile), "website": dist.domain_url(website)})
    return rows


def smallworld_modules(html: str) -> list[dict[str, str]]:
    modules: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for block in re.findall(r"var ajaxParams = \{([\s\S]{0,1500}?)\};", html):
        if "'paginationHandler'" not in block and '"paginationHandler"' not in block:
            continue
        params: dict[str, str] = {}
        for key in ("module", "site_page_id", "method", "template", "mCell", "mId", "limit", "offset"):
            match = re.search(rf"['\"]{key}['\"]\s*:\s*['\"]([^'\"]*)['\"]", block)
            if match:
                params[key] = match.group(1)
        if params.get("module") != "organizations_organization_list":
            continue
        key = (params.get("site_page_id", ""), params.get("mCell", ""), params.get("mId", ""), params.get("limit", ""))
        if key in seen:
            continue
        seen.add(key)
        modules.append(params)
    if not modules:
        modules.append({"site_page_id": "3000", "mCell": "0", "mId": "0", "limit": "40", "offset": "40", "template": "generic_items"})
    return modules


def parse_gnydm_cards(html: str) -> list[dict[str, str]]:
    return parse_smallworld_cards(html, GNYDM_2025_BASE)


def collect_smallworld_links(cache: dict[str, Any], event: dict[str, str]) -> list[dict[str, str]]:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Referer": event["url"]})
    tk, tm, html = smallworld_tokens(session, cache, event["url"])
    rows = parse_smallworld_cards(html, event["base"])
    seen = {row["profile"] for row in rows}
    for module in smallworld_modules(html):
        limit = int(module.get("limit") or "40")
        start_offset = int(module.get("offset") or str(limit))
        total = 2000
        empty_pages = 0
        for offset in range(start_offset, total + limit, limit):
            data = {
                "module": "organizations_organization_list",
                "site_page_id": module.get("site_page_id", "3000"),
                "method": "paginationHandler",
                "template": module.get("template", "generic_items"),
                "mCell": module.get("mCell", "0"),
                "mId": module.get("mId", "0"),
                "limit": str(limit),
                "offset": str(offset),
                "page_id": "openAjax",
                "tk": tk,
                "tm": tm,
                "ajaxType": "paginate",
            }
            try:
                response = session.post(f"{event['base']}/index.php", data=data, timeout=30)
                payload = response.json()
            except Exception:
                empty_pages += 1
                if empty_pages >= 3:
                    break
                continue
            tk = payload.get("formToken") or tk
            tm = payload.get("formTime") or tm
            try:
                total = int(payload.get("total") or total)
            except (TypeError, ValueError):
                pass
            html_page = requests.utils.unquote(str(payload.get("data") or ""))
            new_rows = 0
            for row in parse_smallworld_cards(html_page, event["base"]):
                if row["profile"] in seen:
                    continue
                seen.add(row["profile"])
                rows.append(row)
                new_rows += 1
            empty_pages = 0 if new_rows else empty_pages + 1
            if offset >= total or empty_pages >= 3:
                break
    for row in rows:
        row["event"] = event["event"]
        row["event_key"] = event["key"]
    return rows


def collect_gnydm_links(cache: dict[str, Any]) -> list[dict[str, str]]:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Referer": GNYDM_2025_URL})
    tk, tm, html = gnydm_tokens(session, cache)
    rows = parse_gnydm_cards(html)
    seen = {row["profile"] for row in rows}
    total = 506
    for offset in range(40, total + 40, 40):
        data = {
            "module": "organizations_organization_list",
            "site_page_id": "3000",
            "method": "paginationHandler",
            "template": "generic_items",
            "mCell": "0",
            "mId": "0",
            "limit": "40",
            "offset": str(offset),
            "page_id": "openAjax",
            "tk": tk,
            "tm": tm,
            "ajaxType": "paginate",
        }
        try:
            response = session.post(f"{GNYDM_2025_BASE}/index.php", data=data, timeout=30)
            payload = response.json()
        except Exception:
            continue
        tk = payload.get("formToken") or tk
        tm = payload.get("formTime") or tm
        html_page = requests.utils.unquote(str(payload.get("data") or ""))
        for row in parse_gnydm_cards(html_page):
            if row["profile"] in seen:
                continue
            seen.add(row["profile"])
            rows.append(row)
        total = int(payload.get("total") or total)
        if offset >= total:
            break
    return rows


def parse_smallworld_profile(row: dict[str, str], cache: dict[str, Any]) -> dict[str, str]:
    detail = parse_gnydm_profile(row, cache)
    detail["event"] = row.get("event", "")
    detail["event_key"] = row.get("event_key", "")
    return detail


def parse_gnydm_profile(row: dict[str, str], cache: dict[str, Any]) -> dict[str, str]:
    html = cached_get(row["profile"], cache)
    if not html:
        return {**row, "phone": "", "address": "", "country": "", "summary": ""}
    soup = BeautifulSoup(html, "html.parser")
    lines = [clean(line) for line in soup.get_text("\n", strip=True).splitlines() if clean(line)]
    name = extract_label_block(lines, "Name") or row["name"]
    summary = extract_label_block(lines, "What We Do")
    website = extract_label_block(lines, "Website") or row.get("website", "")
    phone = extract_label_block(lines, "Phone")
    address = extract_label_block(lines, "Address")
    country = dist.infer_country(address, website, phone) or "United States"
    return {
        "name": name,
        "profile": row["profile"],
        "website": dist.domain_url(website),
        "phone": phone,
        "address": address,
        "country": country,
        "summary": summary,
    }


def collect_ids_prospects(args: argparse.Namespace, cache: dict[str, Any], existing: dict[str, base.Prospect]) -> list[base.Prospect]:
    links = collect_ids_links(cache, args.ids_offsets)
    print(json.dumps({"source": "ids_links", "links": len(links)}, ensure_ascii=False), flush=True)

    details: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(parse_ids_detail, item, cache): item for item in links}
        for idx, future in enumerate(as_completed(futures), start=1):
            detail = future.result()
            if detail.get("address") and detail.get("website"):
                details.append(detail)
            if idx % 250 == 0:
                print(json.dumps({"source": "ids_details", "processed": idx, "usable": len(details)}, ensure_ascii=False), flush=True)
    save_json(CACHE_JSON, cache)
    append_jsonl(RAW_JSONL, [{"source": "ids_cologne_2025_detail", **row} for row in details])

    added: list[base.Prospect] = []
    candidate_details = [row for row in details if row.get("website")]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(cached_contact, row["website"], cache): row for row in candidate_details}
        for idx, future in enumerate(as_completed(futures), start=1):
            row = futures[future]
            email, phone = future.result()
            if not email or not phone:
                continue
            prospect = dist.make_distributor(
                name=row["name"],
                country=row.get("country") or "",
                email=email,
                phone=phone,
                address=row["address"],
                website=row["website"],
                source_url=row["url"],
                source_type=IDS_SOURCE_TYPE,
                acquisition_path="IDS Cologne 2025 공식 exhibitor search에서 회사 주소와 웹사이트를 확인하고, 업체 공식 웹사이트 contact/about 페이지에서 이메일·전화번호를 보강",
                site_business_summary="IDS Cologne 2025 참가 치과 장비·재료·디지털 덴탈 벤더: " + (row.get("summary") or "전시 제품군 공개"),
                evidence=[
                    f"IDS Cologne 2025 exhibitor profile: {row['url']}",
                    f"Official website contact enrichment: {dist.domain_url(row['website'])}",
                ],
                tags={
                    "directory": "IDS Cologne 2025 official exhibitor search",
                    "event": "IDS Cologne 2025",
                    "products_services": row.get("summary", ""),
                },
            )
            if not prospect:
                continue
            key = base.dedupe_key(prospect)
            if key in existing:
                continue
            existing[key] = prospect
            added.append(prospect)
            if len(added) % 100 == 0:
                print(json.dumps({"source": "ids_contacts", "processed": idx, "added": len(added)}, ensure_ascii=False), flush=True)
            if len(added) >= args.limit:
                break
    save_json(CACHE_JSON, cache)
    append_jsonl(PROMOTIONS_JSONL, [{"source": "ids_cologne_2025", **asdict(row)} for row in added])
    return added


def collect_ids_preliminary_pdf_prospects(
    args: argparse.Namespace,
    cache: dict[str, Any],
    existing: dict[str, base.Prospect],
    remaining: int,
) -> list[base.Prospect]:
    rows = parse_ids_preliminary_pdf()
    print(json.dumps({"source": "ids_preliminary_pdf", "rows": len(rows)}, ensure_ascii=False), flush=True)
    append_jsonl(RAW_JSONL, [{"source": "ids_preliminary_pdf_row", **row} for row in rows])

    added: list[base.Prospect] = []
    processed = 0
    candidates = [row for row in rows if row.get("website")]
    for start in range(0, len(candidates), args.batch_size):
        if len(added) >= remaining:
            break
        batch = candidates[start : start + args.batch_size]
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(cached_contact_full, row["website"], row["country"], cache): row for row in batch}
            for future in as_completed(futures):
                processed += 1
                row = futures[future]
                if processed % 100 == 0:
                    print(json.dumps({"source": "ids_preliminary_contacts", "processed": processed, "added": len(added)}, ensure_ascii=False), flush=True)
                try:
                    email, phone, address = future.result()
                except Exception:
                    continue
                if not (email and phone and address):
                    continue
                prospect = dist.make_distributor(
                    name=row["name"],
                    country=row["country"],
                    email=email,
                    phone=phone,
                    address=address,
                    website=row["website"],
                    source_url=row["source_url"],
                    source_type=IDS_PRELIMINARY_SOURCE_TYPE,
                    acquisition_path="Koelnmesse IDS 2025 preliminary exhibitor list PDF에서 업체명·국가·웹사이트를 확인하고, 업체 공식 웹사이트 contact/about/impressum 페이지에서 이메일·전화·주소를 확인",
                    site_business_summary="IDS Cologne 2025 preliminary exhibitor list에 등재된 국제 치과 장비·재료·디지털 덴탈 벤더",
                    evidence=[
                        "IDS Cologne 2025 preliminary exhibitor list PDF",
                        f"Official website contact/address enrichment: {dist.domain_url(row['website'])}",
                    ],
                    tags={
                        "directory": "IDS Cologne 2025 preliminary exhibitor list PDF",
                        "event": "IDS Cologne 2025",
                        "products_services": "치과 장비·재료·디지털 덴탈 전시 참가사",
                    },
                )
                if not prospect:
                    continue
                key = base.dedupe_key(prospect)
                if key in existing:
                    continue
                existing[key] = prospect
                added.append(prospect)
                if len(added) % 25 == 0:
                    print(json.dumps({"source": "ids_preliminary_contacts", "processed": processed, "added": len(added)}, ensure_ascii=False), flush=True)
                if len(added) >= remaining:
                    break
        save_json(CACHE_JSON, cache)
    append_jsonl(PROMOTIONS_JSONL, [{"source": "ids_preliminary_pdf", **asdict(row)} for row in added])
    return added


def collect_gnydm_prospects(args: argparse.Namespace, cache: dict[str, Any], existing: dict[str, base.Prospect], remaining: int) -> list[base.Prospect]:
    links = collect_gnydm_links(cache)
    print(json.dumps({"source": "gnydm_2025_links", "links": len(links)}, ensure_ascii=False), flush=True)
    details: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(parse_gnydm_profile, row, cache): row for row in links}
        for idx, future in enumerate(as_completed(futures), start=1):
            detail = future.result()
            if detail.get("address") and detail.get("phone") and detail.get("website"):
                details.append(detail)
            if idx % 100 == 0:
                print(json.dumps({"source": "gnydm_2025_profiles", "processed": idx, "usable": len(details)}, ensure_ascii=False), flush=True)
    save_json(CACHE_JSON, cache)
    append_jsonl(RAW_JSONL, [{"source": "gnydm_2025_profile", **row} for row in details])

    added: list[base.Prospect] = []
    processed = 0
    for start in range(0, len(details), args.batch_size):
        if len(added) >= remaining:
            break
        batch = details[start : start + args.batch_size]
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(cached_email, row["website"], cache): row for row in batch}
            for future in as_completed(futures):
                processed += 1
                row = futures[future]
                if processed % 100 == 0:
                    print(json.dumps({"source": "gnydm_2025_contacts", "processed": processed, "added": len(added)}, ensure_ascii=False), flush=True)
                try:
                    email = future.result()
                except Exception:
                    continue
                if not email:
                    continue
                prospect = dist.make_distributor(
                    name=row["name"],
                    country=row["country"],
                    email=email,
                    phone=row["phone"],
                    address=row["address"],
                    website=row["website"],
                    source_url=row["profile"],
                    source_type=GNYDM_SOURCE_TYPE,
                    acquisition_path="GNYDM 2025 공식 exhibitor directory에서 업체명·전화·주소·웹사이트를 확인하고, 업체 공식 웹사이트에서 이메일을 보강",
                    site_business_summary="Greater New York Dental Meeting 2025 참가 치과 장비·재료·서비스 벤더: " + (row.get("summary") or "전시 제품/서비스 공개"),
                    evidence=[
                        f"GNYDM 2025 exhibitor profile: {row['profile']}",
                        f"Official website email enrichment: {dist.domain_url(row['website'])}",
                    ],
                    tags={
                        "directory": "Greater New York Dental Meeting 2025 official exhibitor directory",
                        "event": "Greater New York Dental Meeting 2025",
                        "products_services": row.get("summary", ""),
                    },
                )
                if not prospect:
                    continue
                key = base.dedupe_key(prospect)
                if key in existing:
                    continue
                existing[key] = prospect
                added.append(prospect)
                if len(added) % 25 == 0:
                    print(json.dumps({"source": "gnydm_2025_contacts", "processed": processed, "added": len(added)}, ensure_ascii=False), flush=True)
                if len(added) >= remaining:
                    break
        save_json(CACHE_JSON, cache)
    append_jsonl(PROMOTIONS_JSONL, [{"source": "gnydm_2025", **asdict(row)} for row in added])
    return added


def collect_smallworld_dental_prospects(
    args: argparse.Namespace,
    cache: dict[str, Any],
    existing: dict[str, base.Prospect],
    remaining: int,
) -> list[base.Prospect]:
    added: list[base.Prospect] = []
    for event in SMALLWORLD_DENTAL_EVENTS:
        if len(added) >= remaining:
            break
        links = collect_smallworld_links(cache, event)
        print(json.dumps({"source": "smallworld_dental_links", "event": event["event"], "links": len(links)}, ensure_ascii=False), flush=True)
        details: list[dict[str, str]] = []
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(parse_smallworld_profile, row, cache): row for row in links}
            for idx, future in enumerate(as_completed(futures), start=1):
                detail = future.result()
                if detail.get("address") and detail.get("phone") and detail.get("website"):
                    details.append(detail)
                if idx % 100 == 0:
                    print(
                        json.dumps(
                            {"source": "smallworld_dental_profiles", "event": event["event"], "processed": idx, "usable": len(details)},
                            ensure_ascii=False,
                        ),
                        flush=True,
                    )
        save_json(CACHE_JSON, cache)
        append_jsonl(RAW_JSONL, [{"source": "smallworld_dental_profile", **row} for row in details])

        event_added: list[base.Prospect] = []
        processed = 0
        for start in range(0, len(details), args.batch_size):
            if len(added) >= remaining:
                break
            batch = details[start : start + args.batch_size]
            with ThreadPoolExecutor(max_workers=args.workers) as pool:
                futures = {pool.submit(cached_email, row["website"], cache): row for row in batch}
                for future in as_completed(futures):
                    processed += 1
                    row = futures[future]
                    if processed % 100 == 0:
                        print(
                            json.dumps(
                                {
                                    "source": "smallworld_dental_contacts",
                                    "event": event["event"],
                                    "processed": processed,
                                    "added": len(event_added),
                                    "total_added": len(added),
                                },
                                ensure_ascii=False,
                            ),
                            flush=True,
                        )
                    try:
                        email = future.result()
                    except Exception:
                        continue
                    if not email:
                        continue
                    prospect = dist.make_distributor(
                        name=row["name"],
                        country=row["country"],
                        email=email,
                        phone=row["phone"],
                        address=row["address"],
                        website=row["website"],
                        source_url=row["profile"],
                        source_type=SMALLWORLD_DENTAL_SOURCE_TYPE,
                        acquisition_path=f"{event['event']} 공식 exhibitor directory에서 업체명·전화·주소·웹사이트를 확인하고, 업체 공식 웹사이트에서 이메일을 보강",
                        site_business_summary=f"{event['event']} 참가 치과 장비·재료·서비스 벤더: " + (row.get("summary") or "전시 제품/서비스 공개"),
                        evidence=[
                            f"{event['event']} exhibitor profile: {row['profile']}",
                            f"Official website email enrichment: {dist.domain_url(row['website'])}",
                        ],
                        tags={
                            "directory": f"{event['event']} official exhibitor directory",
                            "event": event["event"],
                            "products_services": row.get("summary", ""),
                        },
                    )
                    if not prospect:
                        continue
                    key = base.dedupe_key(prospect)
                    if key in existing:
                        continue
                    existing[key] = prospect
                    added.append(prospect)
                    event_added.append(prospect)
                    if len(event_added) % 25 == 0:
                        print(
                            json.dumps(
                                {
                                    "source": "smallworld_dental_contacts",
                                    "event": event["event"],
                                    "processed": processed,
                                    "added": len(event_added),
                                    "total_added": len(added),
                                },
                                ensure_ascii=False,
                            ),
                            flush=True,
                        )
                    if len(added) >= remaining:
                        break
            save_json(CACHE_JSON, cache)
        append_jsonl(PROMOTIONS_JSONL, [{"source": "smallworld_dental", "event": event["event"], **asdict(row)} for row in event_added])
    return added


def write_research_md(added: list[base.Prospect], before: int, after: int) -> None:
    by_country: dict[str, int] = {}
    for row in added:
        by_country[row.country] = by_country.get(row.country, 0) + 1
    country_lines = [f"- {country}: {count}" for country, count in sorted(by_country.items(), key=lambda item: (-item[1], item[0]))[:40]]
    lines = [
        "# 국제 치과 장비 전시회 기반 해외 잠재고객 6차 확장",
        "",
        f"- 생성일: {datetime.now().strftime('%Y-%m-%d %H:%M KST')}",
        f"- 실행 전 public valid: {before:,}",
        f"- 실행 후 public valid: {after:,}",
        f"- 이번 신규 승격: {len(added):,}개",
        "- 기준: 업체명, 이메일, 전화, 주소, 공개 전시회 출처가 모두 있는 경우만 병합",
        "- 중점 카테고리: 국제 치과 장비 전시회 참가 벤더·제조사·유통사",
        "- 품질 기준 미달 후보는 수량 확보 목적으로 승격하지 않음",
        "",
        "## 사용한 전시회 소스",
        "- Greater New York Dental Meeting 2025 official exhibitor directory: 공개 SmallWorldLabs exhibitor 프로필에서 업체명·전화·주소·웹사이트를 확인하고 업체 공식 웹사이트에서 이메일을 보강했다.",
        "- SmallWorldLabs official dental exhibition exhibitor directory: Hinman Dental Meeting, AAO Annual/Winter, Star of the North, Yankee Dental Congress 등 공개 치과 전시회 프로필에서 업체명·전화·주소·웹사이트를 확인하고 업체 공식 웹사이트에서 이메일을 보강했다.",
        "- IDS Cologne 2025 official exhibitor search: IDS는 VDDI/GFDI와 Koelnmesse가 주관하는 대표 국제 치과 산업 전시회이며, 2025 리뷰 exhibitor 상세에서 회사 주소와 웹사이트를 공개한다.",
        "- IDS Cologne 2025 preliminary exhibitor list PDF: Koelnmesse 공개 PDF의 업체명·국가·웹사이트를 기준으로 업체 공식 웹사이트 contact/about/impressum에서 이메일·전화·주소를 보강했다.",
        "- AEEDC Dubai German Pavilion 및 Italian Pavilion은 5차에서 이미 반영되어 있어 이번에는 중복을 피하고 IDS 중심으로 확장했다.",
        "- Expodental Meeting, GNYDM, Chicago Midwinter 등은 공개 exhibitor 또는 참가 후기 페이지를 조사 후보로 두되, 이 반복에서는 연락처 완비 대량 승격 가능성이 가장 높은 IDS를 우선 사용했다.",
        "",
        "## 신규 승격 국가 상위",
        *(country_lines or ["- 신규 승격 없음"]),
        "",
        "## 저장 파일",
        f"- 승격 로그: `{PROMOTIONS_JSONL}`",
        f"- 원시 로그: `{RAW_JSONL}`",
        f"- 요청 캐시: `{CACHE_JSON}`",
        f"- 병합 데이터: `{base.VALID_JSONL}`",
    ]
    RESEARCH_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> int:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    cache: dict[str, Any] = load_json(CACHE_JSON, {})
    existing = base.existing_valid()
    before = len(existing)
    added: list[base.Prospect] = []
    if len(added) < args.limit and "gnydm_2025" in args.sources:
        added.extend(collect_gnydm_prospects(args, cache, existing, args.limit - len(added)))
    if len(added) < args.limit and "smallworld_dental" in args.sources:
        added.extend(collect_smallworld_dental_prospects(args, cache, existing, args.limit - len(added)))
    if len(added) < args.limit and "ids_detail" in args.sources:
        added.extend(collect_ids_prospects(args, cache, existing))
    if len(added) < args.limit and "ids_pdf" in args.sources:
        added.extend(collect_ids_preliminary_pdf_prospects(args, cache, existing, args.limit - len(added)))
    prospects = sorted(existing.values(), key=lambda item: (item.country, item.city_hint, item.name))
    base.rewrite_valid(prospects)
    write_research_md(added, before, len(existing))
    print(
        json.dumps(
            {
                "done": True,
                "before": before,
                "after": len(existing),
                "added": len(added),
                "targetAdded": args.limit,
                "research": str(RESEARCH_MD),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if len(added) >= args.limit else 2


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--workers", type=int, default=24)
    parser.add_argument("--batch-size", type=int, default=160)
    parser.add_argument("--ids-offsets", type=int, default=2040, help="Maximum IDS list offset to scan; pages are 20 exhibitors each.")
    parser.add_argument("--sources", default="gnydm_2025,smallworld_dental,ids_pdf,ids_detail", help="Comma-separated source keys: gnydm_2025,smallworld_dental,ids_pdf,ids_detail.")
    args = parser.parse_args(argv)
    args.sources = {item.strip() for item in args.sources.split(",") if item.strip()}
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
