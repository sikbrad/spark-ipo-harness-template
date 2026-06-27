#!/usr/bin/env python3
"""Collect prospect contacts from directly accessible public directories."""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, unquote, urljoin

import requests
from bs4 import BeautifulSoup

import dof_prospect_scale5000 as base
from dof_enrich_incomplete_websites import extract_emails, extract_phone


ROOT = Path("/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04")
OUT_ROOT = ROOT / "output/dof-overseas-customer-prospects/2026-05-30/scale5000"
DATA_DIR = OUT_ROOT / "data"
RESEARCH_MD = OUT_ROOT / "direct_directory_prospect_research.md"
RAW_JSONL = DATA_DIR / "direct_directory_raw.jsonl"
PROMOTIONS_JSONL = DATA_DIR / "direct_directory_promotions.jsonl"
CACHE_JSON = DATA_DIR / "direct_directory_cache.json"
SOURCE_PDF_DIR = DATA_DIR / "source_pdfs"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
)

GERMAN_CITIES = [
    "berlin",
    "hamburg",
    "m%C3%BCnchen",
    "k%C3%B6ln",
    "frankfurt-am-main",
    "stuttgart",
    "d%C3%BCsseldorf",
    "dortmund",
    "essen",
    "leipzig",
    "dresden",
    "hannover",
    "bremen",
    "n%C3%BCrnberg",
    "duisburg",
    "bochum",
    "wuppertal",
    "bielefeld",
    "bonn",
    "m%C3%BCnster",
    "karlsruhe",
    "mannheim",
    "augsburg",
    "wiesbaden",
    "gelsenkirchen",
    "m%C3%B6nchengladbach",
    "braunschweig",
    "kiel",
    "aachen",
    "chemnitz",
    "halle-saale",
    "magdeburg",
    "freiburg-im-breisgau",
    "krefeld",
    "l%C3%BCbeck",
    "oberhausen",
    "erfurt",
    "mainz",
    "rostock",
    "kassel",
    "hagen",
    "saarbr%C3%BCcken",
    "hamm",
    "potsdam",
    "ludwigshafen-am-rhein",
    "oldenburg",
    "leverkusen",
    "heidelberg",
    "solingen",
    "herne",
    "neuss",
    "darmstadt",
    "regensburg",
    "ingolstadt",
    "w%C3%BCrzburg",
    "f%C3%BCrth",
    "wolfsburg",
    "ulm",
    "heilbronn",
    "pforzheim",
]

GELBE_CATEGORIES = [
    ("dentallabor", "Dental laboratory / dental technician"),
    ("zahntechnik", "Dental laboratory / dental technician"),
    ("zahntechnische-laboratorien", "Dental laboratory / dental technician"),
    ("dentalbedarf", "Dental distributor / product supplier"),
]


def clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def load_json(path: Path, default: object) -> object:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def save_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def append_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def fetch(url: str, cache: dict[str, object], timeout: int = 25) -> str:
    if url in cache:
        return str(cache[url].get("text", "")) if isinstance(cache[url], dict) else str(cache[url])
    try:
        response = requests.get(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"},
            timeout=timeout,
            allow_redirects=True,
        )
        text = response.text[:1_200_000]
        cache[url] = {"status": response.status_code, "final_url": response.url, "text": text, "checked_at": datetime.now().isoformat(timespec="seconds")}
    except requests.RequestException as exc:
        text = ""
        cache[url] = {"status": 0, "final_url": url, "text": "", "error": str(exc), "checked_at": datetime.now().isoformat(timespec="seconds")}
    save_json(CACHE_JSON, cache)
    return text


def fetch_page(url: str, timeout: int = 25) -> tuple[str, dict[str, object]]:
    try:
        response = requests.get(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"},
            timeout=timeout,
            allow_redirects=True,
        )
        return url, {
            "status": response.status_code,
            "final_url": response.url,
            "text": response.text[:1_200_000],
            "checked_at": datetime.now().isoformat(timespec="seconds"),
        }
    except requests.RequestException as exc:
        return url, {"status": 0, "final_url": url, "text": "", "error": str(exc), "checked_at": datetime.now().isoformat(timespec="seconds")}


def prefetch_urls(urls: list[str], cache: dict[str, object], workers: int = 12) -> None:
    missing = [url for url in urls if url not in cache]
    if not missing:
        return
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = [executor.submit(fetch_page, url) for url in missing]
        for idx, future in enumerate(as_completed(futures), start=1):
            url, payload = future.result()
            cache[url] = payload
            if idx % 50 == 0:
                save_json(CACHE_JSON, cache)
    save_json(CACHE_JSON, cache)


def cf_email(hex_string: str) -> str:
    data = bytes.fromhex(hex_string)
    key = data[0]
    return "".join(chr(b ^ key) for b in data[1:])


def cf_emails(html: str) -> list[str]:
    emails: list[str] = []
    for value in re.findall(r"(?:data-cfemail=|/cdn-cgi/l/email-protection#)[\"']?([a-fA-F0-9]+)", html):
        try:
            email = cf_email(value)
        except Exception:  # noqa: BLE001
            continue
        if "@" in email and email not in emails:
            emails.append(email)
    return emails


def reason_for(segment: str) -> tuple[str, str]:
    if segment == "Dental distributor / product supplier":
        return (
            "Publicly listed dental distributor, supply, equipment, or trading company with direct email, phone, and address; likely channel partner or resale prospect for DOF scanners and digital dentistry products.",
            "Channel sales, scanner resale, equipment distribution, local service partnership",
        )
    if segment == "Dental clinic / orthodontics":
        return (
            "Publicly listed orthodontic dental practice with direct email, phone, and address; orthodontic clinics are prospective buyers of intraoral scanners and digital model workflows.",
            "Intraoral scanner, orthodontic digital impression, aligner and model workflow",
        )
    if segment == "Dental clinic / practice":
        return (
            "Publicly listed dental practice with direct email, phone, and address; dental clinics are prospective buyers of intraoral scanners and digital impression workflows.",
            "Intraoral scanner, digital impression, clinic-to-lab workflow",
        )
    return (
        "Publicly listed dental lab or dental technician with direct email, phone, and address; likely buyer of lab scanners, model scanning workflow, and CAD/CAM production tools.",
        "Lab scanner, CAD/CAM workflow, production digitization",
    )


def source_pdf_path(name: str) -> Path:
    SOURCE_PDF_DIR.mkdir(parents=True, exist_ok=True)
    return SOURCE_PDF_DIR / name


def pdf_text(path: Path) -> str:
    try:
        result = subprocess.run(["pdftotext", "-layout", str(path), "-"], check=True, capture_output=True, text=True, timeout=60)
    except Exception:  # noqa: BLE001
        return ""
    return result.stdout


def city_slug(city: str) -> str:
    city = clean(city).lower().replace("ß", "ss")
    city = re.sub(r"[^a-z0-9äöü]+", "-", city, flags=re.I).strip("-")
    return quote(city)


def german_city_slugs(limit: int) -> list[str]:
    slugs = list(dict.fromkeys(GERMAN_CITIES))
    if limit <= len(slugs):
        return slugs[:limit]
    try:
        base.download_geonames()
        cities = []
        with base.GEONAMES_TXT.open("r", encoding="utf-8") as f:
            reader = csv.reader(f, delimiter="\t")
            for row in reader:
                if row[8] != "DE" or row[6] != "P":
                    continue
                population = int(row[14] or 0)
                if population < 10_000:
                    continue
                cities.append((population, row[1]))
        cities.sort(reverse=True)
    except Exception:  # noqa: BLE001
        return slugs
    for _, name in cities:
        slug = city_slug(name)
        if slug and slug not in slugs:
            slugs.append(slug)
        if len(slugs) >= limit:
            break
    return slugs


def make_prospect(
    *,
    name: str,
    country: str,
    city_hint: str,
    segment: str,
    email: str,
    phone: str,
    address: str,
    website: str,
    source_url: str,
    source_type: str,
    evidence: list[str],
    tags: dict[str, str],
) -> base.Prospect | None:
    name = clean(name)
    email = clean(email).lower()
    phone = clean(phone)
    address = clean(address)
    if not (name and email and phone and address):
        return None
    if len(name) < 3 or "@" in name:
        return None
    if len(re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ]", name)) < 2:
        return None
    reason, dof_fit = reason_for(segment)
    return base.Prospect(
        name=name[:140],
        country=country,
        city_hint=city_hint,
        segment=segment,
        email=email,
        phone=phone,
        address=address[:240],
        website=website,
        source_url=source_url,
        source_type=source_type,
        selection_reason=reason,
        dof_fit=dof_fit,
        evidence=evidence,
        osm_type="",
        osm_id=0,
        tags=tags,
        collected_at=datetime.now().isoformat(timespec="seconds"),
    )


def public_emails(html: str, blocked_domains: tuple[str, ...] = ()) -> list[str]:
    emails: list[str] = []
    for email in [*cf_emails(html), *extract_emails(html)]:
        value = clean(email).lower()
        if not value or value in emails:
            continue
        domain = value.split("@")[-1]
        if any(domain == blocked or domain.endswith("." + blocked) for blocked in blocked_domains):
            continue
        emails.append(value)
    return emails


def first_external_website(html: str, blocked_domains: tuple[str, ...]) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        href = clean(a["href"])
        if not href.startswith(("http://", "https://")):
            continue
        lowered = href.lower()
        if any(blocked in lowered for blocked in blocked_domains):
            continue
        if any(blocked in lowered for blocked in ("google.", "schema.org", "gstatic.", "facebook.com/sharer", "twitter.com/share")):
            continue
        return href
    return ""


def local_ch_search_urls(max_pages: int) -> list[str]:
    terms = [
        ("de", "schweiz", "dentallabor"),
        ("de", "schweiz", "zahntechnisches labor"),
        ("de", "schweiz", "zahntechnik"),
        ("de", "schweiz", "zahnprothetiker"),
        ("de", "schweiz", "dentalbedarf"),
        ("fr", "suisse", "laboratoire dentaire"),
        ("fr", "suisse", "prothésiste dentaire"),
        ("fr", "suisse", "fournitures dentaires"),
        ("it", "svizzera", "laboratorio dentale"),
        ("it", "svizzera", "odontotecnico"),
        ("en", "switzerland", "dental laboratory"),
        ("en", "switzerland", "dental technician"),
    ]
    urls: list[str] = []
    for lang, place, term in terms:
        for page in range(1, max_pages + 1):
            suffix = "" if page == 1 else f"?page={page}"
            urls.append(f"https://www.local.ch/{lang}/q/{quote(place)}/{quote(term)}{suffix}")
    return urls


def local_ch_detail_links(html: str) -> list[str]:
    links: list[str] = []
    for href in re.findall(r'href="([^"]+/d/[^"]+)"', html):
        url = urljoin("https://www.local.ch", href.replace("&amp;", "&"))
        if url not in links:
            links.append(url)
    return links


def jsonld_businesses(html: str) -> list[dict[str, object]]:
    businesses: list[dict[str, object]] = []
    soup = BeautifulSoup(html, "html.parser")
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.get_text())
        except Exception:  # noqa: BLE001
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if isinstance(item, dict) and item.get("@type") in {"LocalBusiness", "Dentist", "MedicalBusiness"}:
                businesses.append(item)
    return businesses


def segment_from_local_ch(url: str, text: str) -> str:
    lowered = f"{url} {text}".lower()
    if re.search(r"dentalbedarf|bedarfsartikel|fournitures|forniture|supply|supplies", lowered):
        return "Dental distributor / product supplier"
    if re.search(r"orthodont|kieferorthop|orthodontie|ortodonz", lowered):
        return "Dental clinic / orthodontics"
    if re.search(r"dentallabor|zahntechnik|zahntechnisches|zahnprothet|laboratoire|proth[èe]s|laboratorio|odontotecn", lowered):
        return "Dental laboratory / dental technician"
    return "Dental clinic / practice"


def parse_local_ch(cache: dict[str, object], max_pages: int, workers: int) -> list[base.Prospect]:
    list_urls = local_ch_search_urls(max_pages)
    prefetch_urls(list_urls, cache, workers)
    detail_urls: list[str] = []
    for url in list_urls:
        for detail_url in local_ch_detail_links(fetch(url, cache)):
            if detail_url not in detail_urls:
                detail_urls.append(detail_url)
    prefetch_urls(detail_urls, cache, workers)

    prospects: list[base.Prospect] = []
    for url in detail_urls:
        detail = fetch(url, cache)
        if not detail.strip():
            continue
        businesses = jsonld_businesses(detail)
        business = businesses[0] if businesses else {}
        soup = BeautifulSoup(detail, "html.parser")
        title = clean(soup.title.get_text(" ", strip=True) if soup.title else "")
        name = clean(business.get("name") or title.split(" - ")[0])
        address_obj = business.get("address") if isinstance(business.get("address"), dict) else {}
        street = clean(address_obj.get("streetAddress") if isinstance(address_obj, dict) else "")
        city = clean(address_obj.get("addressLocality") if isinstance(address_obj, dict) else "")
        postal_code = clean(address_obj.get("postalCode") if isinstance(address_obj, dict) else "")
        address = clean(", ".join(part for part in [street, f"{postal_code} {city}".strip(), "Switzerland"] if part))
        emails = public_emails(detail, ("local.ch", "localsearch.ch"))
        phone = ""
        phone_match = re.search(r'href="tel:[^"]+">([^<]+)</a>', detail)
        if phone_match:
            phone = clean(BeautifulSoup(phone_match.group(1), "html.parser").get_text(" ", strip=True))
        if not phone:
            tel_match = re.search(r'href="tel:([^"]+)"', detail)
            phone = clean(tel_match.group(1)) if tel_match else ""
        if not phone:
            phone = extract_phone(soup.get_text(" ", strip=True))
        website = first_external_website(detail, ("local.ch", "localsearch.ch"))
        segment = segment_from_local_ch(url, title)
        prospect = make_prospect(
            name=name,
            country="Switzerland",
            city_hint=city,
            segment=segment,
            email=emails[0] if emails else "",
            phone=phone,
            address=address,
            website=website,
            source_url=url,
            source_type="local.ch Switzerland public yellow pages directory",
            evidence=[f"local.ch profile: {url}", f"Required contact fields found: email={emails[0] if emails else ''}, phone={phone}, address={address}"],
            tags={"directory": "local.ch", "category_hint": title},
        )
        if prospect:
            prospects.append(prospect)
    return prospects


def parse_lmtmag(cache: dict[str, object], workers: int) -> list[base.Prospect]:
    list_url = "https://lmtmag.com/labs"
    html = fetch(list_url, cache)
    soup = BeautifulSoup(html, "html.parser")
    profile_urls: list[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith(("/labs", "/events", "/groups", "/articles", "/products", "/jobs", "/vendors", "/people")):
            continue
        url = urljoin("https://lmtmag.com", href.split("#", 1)[0])
        if re.fullmatch(r"https://lmtmag\.com/[A-Za-z0-9_-]+", url) and url not in profile_urls:
            profile_urls.append(url)
    prefetch_urls(profile_urls, cache, workers)

    prospects: list[base.Prospect] = []
    for url in profile_urls:
        detail = fetch(url, cache)
        if "contact_info" not in detail and "data-cfemail" not in detail:
            continue
        soup = BeautifulSoup(detail, "html.parser")
        title = clean(soup.title.get_text(" ", strip=True) if soup.title else "")
        name = clean(title.replace("LMTmag |", ""))
        emails = public_emails(detail)
        phone = ""
        phone_match = re.search(r'href="tel:([^"]+)"[^>]*>(.*?)</a>', detail, flags=re.S)
        if phone_match:
            phone = clean(BeautifulSoup(phone_match.group(2), "html.parser").get_text(" ", strip=True) or phone_match.group(1))
        address = ""
        map_match = re.search(r"https://maps\.google\.com\?q=([^\"']+)", detail)
        if map_match:
            address = clean(unquote(map_match.group(1)).replace("+", " "))
        website = first_external_website(detail, ("lmtmag.com", "google.com"))
        prospect = make_prospect(
            name=name,
            country="United States",
            city_hint="",
            segment="Dental laboratory / dental technician",
            email=emails[0] if emails else "",
            phone=phone,
            address=address,
            website=website,
            source_url=url,
            source_type="LMTmag public dental laboratory profile directory",
            evidence=[f"LMTmag lab profile: {url}", f"Required contact fields found: email={emails[0] if emails else ''}, phone={phone}, address={address}"],
            tags={"directory": "LMTmag", "source_list": list_url},
        )
        if prospect:
            prospects.append(prospect)
    return prospects


def vzls_emails(html: str) -> list[str]:
    emails: list[str] = []
    for raw in re.findall(r"mailto:<ma>(.*?)</ma>", html, flags=re.S):
        without_noise = re.sub(r"<b>.*?</b>", "", raw, flags=re.S)
        value = BeautifulSoup(without_noise, "html.parser").get_text("", strip=True).replace(" ", "").lower()
        domain = value.split("@")[-1]
        if domain == "vzls.ch" or domain.endswith(".vzls.ch"):
            continue
        if "@" in value and value not in emails:
            emails.append(value)
    for value in public_emails(html, ("vzls.ch",)):
        if value not in emails:
            emails.append(value)
    return emails


def first_vzls_address(html: str) -> tuple[str, str]:
    match = re.search(r"<h3[^>]*>\s*Hauptstandort\s*</h3>\s*<p>(.*?)</p>", html, flags=re.S)
    if not match:
        return "", ""
    lines = [clean(line) for line in BeautifulSoup(match.group(1).replace("<br>", "\n"), "html.parser").get_text("\n", strip=True).splitlines() if clean(line)]
    address = clean(", ".join([*lines, "Switzerland"]))
    city = ""
    if lines:
        city_match = re.search(r"\b\d{4}\s+(.+)$", lines[-1])
        city = clean(city_match.group(1)) if city_match else ""
    return address, city


def vzls_product_categories(html: str) -> str:
    match = re.search(r"<dt[^>]*>\s*Produktkategorien\s*</dt>\s*<dd>(.*?)</dd>", html, flags=re.S)
    if not match:
        return ""
    return clean(BeautifulSoup(match.group(1), "html.parser").get_text(", ", strip=True))


def parse_vzls(cache: dict[str, object], workers: int) -> list[base.Prospect]:
    list_url = "https://www.vzls.ch/de/lab-finder"
    html = fetch(list_url, cache)
    links: list[str] = []
    for href in re.findall(r'href="([^"]*/de/lab-finder/[^"]+)"', html):
        url = urljoin("https://www.vzls.ch", clean(href))
        if url.rstrip("/") == list_url:
            continue
        if url not in links:
            links.append(url)
    prefetch_urls(links, cache, workers)

    prospects: list[base.Prospect] = []
    for url in links:
        detail = fetch(url, cache)
        if not detail.strip():
            continue
        soup = BeautifulSoup(detail, "html.parser")
        heading = soup.find("h1")
        name = clean(heading.get_text(" ", strip=True) if heading else "")
        emails = vzls_emails(detail)
        phone = ""
        phone_match = re.search(r"Telefon:\s*<a[^>]+href=\"tel:[^\"]+\"[^>]*>\s*([^<]+)", detail, flags=re.S)
        if phone_match:
            phone = clean(phone_match.group(1))
        if not phone:
            tel_match = re.search(r'href="tel:([^"]+)"', detail)
            phone = clean(tel_match.group(1)) if tel_match else ""
        address, city = first_vzls_address(detail)
        website = first_external_website(detail, ("vzls.ch",))
        product_categories = vzls_product_categories(detail)
        prospect = make_prospect(
            name=name,
            country="Switzerland",
            city_hint=city,
            segment="Dental laboratory / dental technician",
            email=emails[0] if emails else "",
            phone=phone,
            address=address,
            website=website,
            source_url=url,
            source_type="Swiss Dental Laboratories VZLS public lab finder",
            evidence=[
                f"VZLS lab finder profile: {url}",
                f"Product categories: {product_categories}" if product_categories else "VZLS profile lists laboratory service categories.",
                f"Required contact fields found: email={emails[0] if emails else ''}, phone={phone}, address={address}",
            ],
            tags={"directory": "VZLS Swiss Dental Laboratories", "product_categories": product_categories},
        )
        if prospect:
            prospects.append(prospect)
    return prospects


MEDITRADER_BASE = "https://mail.meditrader.co.za"


def meditrader_list_urls(max_start: int) -> list[str]:
    starts = list(range(0, max_start + 1, 20))
    urls = [
        f"{MEDITRADER_BASE}/dental-laboratories?controller=search&categoryId=85&orderBy=packageOrder%20desc&start={start}"
        for start in starts
    ]
    urls += [
        f"{MEDITRADER_BASE}/dental-laboratories?controller=search&categoryId=127&orderBy=companyName%20asc&start={start}"
        for start in starts
    ]
    return urls


def meditrader_detail_links(html: str) -> list[str]:
    links: list[str] = []
    blocked = ("/category/", "/members/", "/for-", "/about-", "/medical-trader-home", "/media/", "/component/")
    for a in BeautifulSoup(html, "html.parser").find_all("a", href=True):
        href = a["href"]
        if href.startswith("/"):
            href = urljoin(MEDITRADER_BASE, href)
        if not href.startswith(MEDITRADER_BASE + "/"):
            continue
        if href.rstrip("/") == MEDITRADER_BASE:
            continue
        if any(part in href for part in blocked):
            continue
        if href not in links:
            links.append(href)
    return links


def meditrader_category(lines: list[str]) -> str:
    for idx, line in enumerate(lines):
        if line == "DENTISTRY" and idx + 1 < len(lines):
            return lines[idx + 1]
    for value in ("Dental Laboratory", "Orthodontist", "Prosthodontist", "Dentist/Dental Surgeon", "Dental Supplier"):
        if value in lines:
            return value
    return ""


def meditrader_segment(category: str, title: str, text: str) -> str:
    haystack = f"{category} {title} {text[:1200]}".lower()
    if "laboratory" in haystack or "laboratorium" in haystack or "lab " in haystack or " lab" in haystack:
        return "Dental laboratory / dental technician"
    if "supplier" in haystack or "supply" in haystack or "distributor" in haystack or "trading" in haystack:
        return "Dental distributor / product supplier"
    if "orthodont" in haystack:
        return "Dental clinic / orthodontics"
    if "prosthodont" in haystack or "periodont" in haystack or "oral medicine" in haystack:
        return "Dental clinic / implant and surgery"
    return "Dental clinic / practice"


def meditrader_name(lines: list[str], category: str) -> str:
    for idx, line in enumerate(lines):
        if line == category and idx + 1 < len(lines):
            return clean(lines[idx + 1])
    for line in lines[:80]:
        if category and category in line and "Meditrader" not in line:
            return clean(line.split(" - Meditrader", 1)[0])
    return ""


def meditrader_address(lines: list[str]) -> str:
    start = 0
    end = len(lines)
    if "Business Info" in lines:
        start = lines.index("Business Info") + 1
    for marker in ("Contact business", "Request info", "Quote Request", "Map Location"):
        if marker in lines and lines.index(marker) > start:
            end = min(end, lines.index(marker))
    for idx, line in enumerate(lines[start:end], start=start):
        if "South Africa" in line:
            if re.search(r"\b(throughout|entire|all over|category|description)\b", line, flags=re.I):
                continue
            parts = [line]
            if idx + 1 < len(lines) and re.search(r"Municipality|Metropolitan|District", lines[idx + 1]):
                parts.append(lines[idx + 1])
            return clean(", ".join(parts))
    return ""


def parse_meditrader(cache: dict[str, object], max_start: int, workers: int) -> list[base.Prospect]:
    list_urls = meditrader_list_urls(max_start)
    prefetch_urls(list_urls, cache, workers)
    detail_urls: list[str] = []
    for url in list_urls:
        for detail_url in meditrader_detail_links(fetch(url, cache)):
            if detail_url not in detail_urls:
                detail_urls.append(detail_url)
    prefetch_urls(detail_urls, cache, workers)

    prospects: list[base.Prospect] = []
    for url in detail_urls:
        html = fetch(url, cache)
        if not html.strip():
            continue
        soup = BeautifulSoup(html, "html.parser")
        lines = [clean(line) for line in soup.get_text("\n", strip=True).splitlines() if clean(line)]
        text = "\n".join(lines)
        emails = [email for email in public_emails(html, ("meditrader.co.za",)) if not email.endswith("@example.com")]
        phones = [clean(phone) for phone in re.findall(r'href="tel:([^"]+)"', html)]
        phone = next((value for value in phones if 7 <= len(re.sub(r"\D", "", value)) <= 16), "")
        if not phone:
            phone = extract_phone(text)
        address = meditrader_address(lines)
        category = meditrader_category(lines)
        name = meditrader_name(lines, category)
        website = first_external_website(html, ("meditrader.co.za", "google.com"))
        segment = meditrader_segment(category, name, text)
        prospect = make_prospect(
            name=name,
            country="South Africa",
            city_hint="",
            segment=segment,
            email=emails[0] if emails else "",
            phone=phone,
            address=address,
            website=website,
            source_url=url,
            source_type="Meditrader South Africa public dental business directory",
            evidence=[
                f"Meditrader profile: {url}",
                f"Category: {category}" if category else "Meditrader dentistry profile.",
                f"Required contact fields found: email={emails[0] if emails else ''}, phone={phone}, address={address}",
            ],
            tags={"directory": "Meditrader South Africa", "category": category},
        )
        if prospect:
            prospects.append(prospect)
    return prospects


def parse_nbc_certified_labs(cache: dict[str, object]) -> list[base.Prospect]:
    url = "https://nbccert.org/directories/nbc-whos-who-cdl/"
    html = fetch(url, cache)
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", id="NBCdirectory")
    prospects: list[base.Prospect] = []
    if not table:
        return prospects
    for tr in table.find_all("tr")[1:]:
        cells = tr.find_all("td")
        if len(cells) < 5:
            continue
        company_lines = [clean(part) for part in cells[2].get_text("\n", strip=True).splitlines() if clean(part)]
        if not company_lines:
            continue
        name = company_lines[0]
        address = clean(", ".join([*company_lines[1:], "United States"]))
        emails: list[str] = []
        for a in cells[4].find_all("a", href=True):
            href = a["href"]
            if href.startswith("mailto:"):
                raw = href.removeprefix("mailto:").split("?", 1)[0]
                for part in re.split(r"[;,]", raw):
                    email = clean(part).lower()
                    if "@" in email and email not in emails and not email.endswith("@nbccert.org"):
                        emails.append(email)
        phone = ""
        phone_match = re.search(r"phone:\s*([^'\";)]+)", str(cells[4]), flags=re.I)
        if phone_match:
            phone = clean(phone_match.group(1))
        website = ""
        for a in cells[4].find_all("a", href=True):
            href = clean(a["href"])
            if href.startswith(("http://", "https://")) and "nbccert.org" not in href:
                website = href
                break
        prospect = make_prospect(
            name=name,
            country="United States",
            city_hint="",
            segment="Dental laboratory / dental technician",
            email=emails[0] if emails else "",
            phone=phone,
            address=address,
            website=website,
            source_url=url,
            source_type="NBC Certified Dental Laboratories public directory",
            evidence=[
                "NBC Certified Dental Laboratories directory lists certified lab company, city/state/ZIP, specialties, phone, email, and website.",
                f"Required contact fields found: email={emails[0] if emails else ''}, phone={phone}, address={address}",
            ],
            tags={"directory": "NBC Certified Dental Laboratories", "specialties": clean(cells[3].get_text(" ", strip=True))},
        )
        if prospect:
            prospects.append(prospect)
    return prospects


def parse_healthspace(cache: dict[str, object], max_pages: int = 30) -> list[base.Prospect]:
    prospects: list[base.Prospect] = []
    seen_links: set[str] = set()
    for page in range(1, max_pages + 1):
        list_url = f"https://healthspace.ph/search/nationwide/Dental-Clinics/page-{page}?facility_type_id=FCT003"
        html = fetch(list_url, cache)
        if not html.strip():
            continue
        soup = BeautifulSoup(html, "html.parser")
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("/facility/"):
                url = urljoin("https://healthspace.ph", href)
                if url not in seen_links:
                    seen_links.add(url)
                    links.append(url)
        if not links:
            break
        for url in links:
            detail = fetch(url, cache)
            if not detail.strip():
                continue
            text = BeautifulSoup(detail, "html.parser").get_text("\n", strip=True)
            lines = [clean(line) for line in text.splitlines() if clean(line)]
            if not lines:
                continue
            title = lines[0].replace(" - Dental Clinics | HealthSpace Philippines", "")
            if "Back" in lines:
                idx = lines.index("Back")
                if idx + 1 < len(lines):
                    title = lines[idx + 1]
            email = (cf_emails(detail) or extract_emails(detail) or [""])[0]
            phone = ""
            address = ""
            if "Phone" in lines:
                i = lines.index("Phone")
                for line in lines[i + 1 : i + 5]:
                    if re.search(r"\d", line):
                        phone = line
                        break
            if "Address" in lines and "Phone" in lines:
                ai = lines.index("Address")
                pi = lines.index("Phone")
                address = clean(", ".join(line.strip(" ,") for line in lines[ai + 1 : pi] if line not in {","}))
            segment = "Dental laboratory / dental technician" if re.search(r"laboratory|lab|studio|supply", title, re.I) else "Dental clinic / practice"
            if "supply" in title.lower():
                segment = "Dental distributor / product supplier"
            prospect = make_prospect(
                name=title,
                country="Philippines",
                city_hint="",
                segment=segment,
                email=email,
                phone=phone,
                address=address,
                website=url,
                source_url=url,
                source_type="HealthSpace Philippines public healthcare directory",
                evidence=[f"HealthSpace profile: {url}", f"Required contact fields found: email={email}, phone={phone}, address={address}"],
                tags={"directory": "HealthSpace", "facility_type": "Dental Clinics"},
            )
            if prospect:
                prospects.append(prospect)
        time.sleep(0.2)
    return prospects


def parse_gelbeseiten(cache: dict[str, object], include_zahnarzt: bool, city_limit: int, workers: int, delay: float) -> list[base.Prospect]:
    prospects: list[base.Prospect] = []
    categories = list(GELBE_CATEGORIES)
    if include_zahnarzt:
        categories.append(("zahnarzt", "Dental clinic / practice"))
    cities = german_city_slugs(city_limit)
    prefetch_urls([f"https://www.gelbeseiten.de/branchen/{category}/{city}" for city in cities for category, _ in categories], cache, workers)
    for city in cities:
        for category, segment in categories:
            url = f"https://www.gelbeseiten.de/branchen/{category}/{city}"
            html = fetch(url, cache)
            soup = BeautifulSoup(html, "html.parser")
            for item in soup.select("article.mod-Treffer"):
                item_html = str(item)
                emails = extract_emails(item_html)
                if not emails:
                    continue
                lines = [clean(line) for line in item.get_text("\n", strip=True).splitlines() if clean(line)]
                if not lines:
                    continue
                name = lines[0]
                phone = ""
                for line in reversed(lines):
                    digits = re.sub(r"\D", "", line)
                    if 7 <= len(digits) <= 16:
                        phone = line
                        break
                address = ""
                for i, line in enumerate(lines):
                    if re.search(r"\b\d{5}\b", line):
                        previous = lines[i - 1] if i else ""
                        address = clean(", ".join(part for part in [previous, line] if part))
                        break
                website = ""
                detail_url = url
                for a in item.find_all("a", href=True):
                    href = a["href"]
                    if "gelbeseiten.de/gsbiz/" in href:
                        detail_url = href
                    elif href.startswith("http") and "gelbeseiten.de" not in href:
                        website = href
                prospect = make_prospect(
                    name=name,
                    country="Germany",
                    city_hint=unquote(city).replace("-", " ").title(),
                    segment=segment,
                    email=emails[0],
                    phone=phone,
                    address=address,
                    website=website,
                    source_url=detail_url,
                    source_type="Gelbe Seiten Germany public business directory",
                    evidence=[f"Gelbe Seiten listing: {detail_url}", f"Required contact fields found: email={emails[0]}, phone={phone}, address={address}"],
                    tags={"directory": "Gelbe Seiten", "category": category},
                )
                if prospect:
                    prospects.append(prospect)
            if delay:
                time.sleep(delay)
    return prospects


def parse_compedent(cache: dict[str, object]) -> list[base.Prospect]:
    url = "https://www.compedent.de/standorte/"
    text = BeautifulSoup(fetch(url, cache), "html.parser").get_text("\n", strip=True)
    lines = [clean(line) for line in text.splitlines() if clean(line)]
    prospects: list[base.Prospect] = []
    for idx, line in enumerate(lines):
        if "@" not in line:
            continue
        email = extract_emails(line)[0] if extract_emails(line) else ""
        if not email:
            continue
        name = ""
        street = ""
        zip_city = ""
        phone = ""
        for back in range(idx - 1, max(-1, idx - 8), -1):
            if re.search(r"\b\d{5}\b", lines[back]):
                zip_city = lines[back]
                street = lines[back - 1] if back - 1 >= 0 else ""
            if not name and back - 2 >= 0 and re.search(r"\b\d{5}\b", lines[back]):
                name = lines[back - 2]
        for forward in range(idx - 1, max(-1, idx - 5), -1):
            if re.search(r"\d{3,}", lines[forward]):
                phone = lines[forward]
                break
        if not name:
            name = lines[idx - 4] if idx >= 4 else ""
        prospect = make_prospect(
            name=name,
            country="Germany",
            city_hint="",
            segment="Dental laboratory / dental technician",
            email=email,
            phone=phone,
            address=clean(", ".join(part for part in [street, zip_city, "Germany"] if part)),
            website=lines[idx + 1] if idx + 1 < len(lines) and lines[idx + 1].startswith("www.") else "",
            source_url=url,
            source_type="CompeDent dental laboratory network directory",
            evidence=[f"CompeDent location directory: {url}", f"Required contact fields found: email={email}, phone={phone}"],
            tags={"directory": "CompeDent"},
        )
        if prospect:
            prospects.append(prospect)
    return prospects


def parse_ivoclar_bps(cache: dict[str, object]) -> list[base.Prospect]:
    sources = [
        ("New Zealand", "https://www.ivoclar.com/en_nz/shop/company/bps-laboratories"),
        ("Australia", "https://www.ivoclar.com/en_au/shop/company/bps-laboratories"),
    ]
    prospects: list[base.Prospect] = []
    for country, url in sources:
        text = BeautifulSoup(fetch(url, cache), "html.parser").get_text("\n", strip=True)
        lines = [clean(line) for line in text.splitlines() if clean(line)]
        for idx, line in enumerate(lines):
            emails = extract_emails(line)
            if not emails:
                continue
            email = emails[0]
            phone = ""
            name = ""
            address_parts: list[str] = []
            for back in range(idx - 1, max(-1, idx - 9), -1):
                if not phone and "phone:" in lines[back].lower():
                    phone = clean(re.sub(r"phone:\s*", "", lines[back], flags=re.I))
                elif not name and not re.search(r"phone|email", lines[back], flags=re.I) and len(lines[back]) < 80:
                    name = lines[back]
                if re.search(r"\d", lines[back]) and "phone" not in lines[back].lower():
                    address_parts.insert(0, lines[back])
            if not phone:
                for back in range(idx - 1, max(-1, idx - 8), -1):
                    value = extract_phone(lines[back])
                    if value:
                        phone = value
                        break
            address = clean(", ".join(address_parts[-3:] + [country]))
            prospect = make_prospect(
                name=name,
                country=country,
                city_hint="",
                segment="Dental laboratory / dental technician",
                email=email,
                phone=phone,
                address=address,
                website="",
                source_url=url,
                source_type="Ivoclar BPS public dental laboratory directory",
                evidence=[f"Ivoclar BPS directory: {url}", f"Required contact fields found: email={email}, phone={phone}, address={address}"],
                tags={"directory": "Ivoclar BPS"},
            )
            if prospect:
                prospects.append(prospect)
    return prospects


def parse_vddi(cache: dict[str, object]) -> list[base.Prospect]:
    api_url = "https://www.vddi.de/?type=1000"
    text = fetch(api_url, cache)
    try:
        companies = json.loads(text).get("companies", [])
    except Exception:  # noqa: BLE001
        companies = []
    prospects: list[base.Prospect] = []
    for company in companies:
        name = clean(company.get("name"))
        email = clean(company.get("mail")).lower()
        phone_prefix = clean(company.get("phone_prefix"))
        phone = clean(company.get("phone"))
        full_phone = clean(f"+49 {phone_prefix} {phone}") if phone else ""
        street = clean(company.get("street"))
        city = clean(company.get("city"))
        zipcode = clean(company.get("zip"))
        address = clean(", ".join(part for part in [street, f"{zipcode} {city}".strip(), "Germany"] if part))
        website = clean(company.get("www"))
        if website and not website.startswith(("http://", "https://")):
            website = "https://" + website
        prospect = make_prospect(
            name=name,
            country="Germany",
            city_hint=city,
            segment="Dental distributor / product supplier",
            email=email,
            phone=full_phone,
            address=address,
            website=website,
            source_url="https://www.vddi.de/en/member-directory",
            source_type="VDDI German dental industry member directory API",
            evidence=[
                "VDDI member directory exposes company/manufacturer records through its public member search endpoint.",
                f"Required contact fields found: email={email}, phone={full_phone}, address={address}",
            ],
            tags={"directory": "VDDI", "uid": str(company.get("uid", ""))},
        )
        if prospect:
            prospects.append(prospect)
    return prospects


def parse_myerson_ema_pdf(cache: dict[str, object]) -> list[base.Prospect]:
    url = "https://www.myersontooth.com/wp-content/uploads/2025/11/authorized-ema-labs_11_4_2025.pdf"
    path = source_pdf_path("myerson_ema_2025.pdf")
    if not path.exists():
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=60)
        if response.ok:
            path.write_bytes(response.content)
    text = pdf_text(path)
    prospects: list[base.Prospect] = []
    for raw_line in text.splitlines():
        line = clean(raw_line)
        if not line or line.startswith(("United States", "Lab Name", "Canada", "Australia")):
            continue
        emails = extract_emails(line)
        if not emails:
            continue
        parts = [clean(part) for part in re.split(r"\s{2,}", raw_line.strip()) if clean(part)]
        if len(parts) < 5:
            continue
        name, city, state, phone = parts[:4]
        email = emails[0]
        address = clean(", ".join(part for part in [city, state, "United States"] if part))
        prospect = make_prospect(
            name=name,
            country="United States",
            city_hint=city,
            segment="Dental laboratory / dental technician",
            email=email,
            phone=phone,
            address=address,
            website="",
            source_url=url,
            source_type="Myerson authorized EMA dental laboratory PDF list",
            evidence=[
                "Myerson authorized EMA lab PDF lists lab name, city/state, phone, and website/email.",
                f"Required contact fields found: email={email}, phone={phone}, address={address}",
            ],
            tags={"directory": "Myerson EMA authorized labs", "state": state},
        )
        if prospect:
            prospects.append(prospect)
    return prospects


def parse_modern_dentistry_pdf(cache: dict[str, object]) -> list[base.Prospect]:
    url = "https://www.moderndentistrymedia.com/moderndentistrymedia/wp-content/uploads/2020/02/DentalDirectory2020.pdf"
    path = source_pdf_path("modern_dentistry_directory_2020.pdf")
    if not path.exists():
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=60)
        if response.ok:
            path.write_bytes(response.content)
    text = pdf_text(path)
    prospects: list[base.Prospect] = []
    lines = text.splitlines()
    for idx, raw_line in enumerate(lines):
        emails = extract_emails(raw_line)
        if not emails:
            continue
        window = lines[max(0, idx - 14) : idx + 5]
        candidate_names: list[str] = []
        for lookback in window:
            chunks = [clean(part) for part in re.split(r"\s{3,}", lookback) if clean(part)]
            for chunk in chunks:
                if 3 <= len(chunk) <= 70 and chunk.upper() == chunk and not re.search(r"EMAIL|TEL|FAX|WWW|DIRECTORY|SUPPLIERS", chunk):
                    candidate_names.append(chunk.title())
        name = candidate_names[-1] if candidate_names else ""
        text_window = clean(" ".join(window))
        phone_match = re.search(r"(?:Tel|Cell|Office|Mobile|Phone)\s*:\s*([+()0-9 /\-]{7,35})", text_window, flags=re.I)
        phone = clean(phone_match.group(1)) if phone_match else ""
        address = ""
        for line in reversed(window):
            if re.search(r"\d", line) and not extract_emails(line) and not re.search(r"Tel|Cell|Fax|Email|www", line, flags=re.I):
                address = clean(line)
                break
        if address:
            address = clean(f"{address}, South Africa")
        prospect = make_prospect(
            name=name,
            country="South Africa",
            city_hint="",
            segment="Dental distributor / product supplier",
            email=emails[0],
            phone=phone,
            address=address,
            website="",
            source_url=url,
            source_type="Modern Dentistry Media dental and laboratory supplier PDF directory",
            evidence=[
                "Modern Dentistry Media PDF directory lists dental/laboratory suppliers with contact details.",
                f"Required contact fields found: email={emails[0]}, phone={phone}, address={address}",
            ],
            tags={"directory": "Modern Dentistry Media Directory 2020"},
        )
        if prospect:
            prospects.append(prospect)
    return prospects


def write_research_md(rows: list[base.Prospect], before: int, after: int) -> None:
    by_source: dict[str, int] = {}
    by_country: dict[str, int] = {}
    by_segment: dict[str, int] = {}
    for row in rows:
        by_source[row.source_type] = by_source.get(row.source_type, 0) + 1
        by_country[row.country] = by_country.get(row.country, 0) + 1
        by_segment[row.segment] = by_segment.get(row.segment, 0) + 1
    lines = [
        "# 직접 접근 공개 디렉터리 기반 해외 잠재고객 확장",
        "",
        f"- 생성일: {datetime.now().strftime('%Y-%m-%d %H:%M KST')}",
        f"- 실행 전 public valid: {before:,}",
        f"- 실행 후 public valid: {after:,}",
        f"- 이번 스크립트 신규 승격: {after - before:,}개",
        "- 기준: 업체명, 이메일, 전화, 주소, 공개 출처가 모두 있는 경우만 병합",
        "",
        "## 사용한 비 OSM 소스",
        "- HealthSpace Philippines: 필리핀 의료/치과 시설 공개 디렉터리",
        "- Gelbe Seiten Germany: 독일 Yellow Pages 계열 공개 사업자 디렉터리",
        "- CompeDent: 독일 치과기공소 네트워크 공개 위치 목록",
        "- Ivoclar BPS: 뉴질랜드/호주 BPS 치과기공소 공개 목록",
        "- VDDI: 독일 치과산업 협회 회원사 공개 검색 API",
        "- Myerson authorized EMA labs: 미국 EMA 장치 승인 기공소 PDF",
        "- local.ch: 스위스 공개 Yellow Pages 사업자 디렉터리",
        "- LMTmag: 미국 치과기공소 공개 프로필 디렉터리",
        "- VZLS Swiss Dental Laboratories: 스위스 치과기공소 협회 Lab-Finder",
        "- Meditrader South Africa: 남아공 치과·치기공·공급사 공개 사업자 디렉터리",
        "- NBC Certified Dental Laboratories: 미국 인증 치과기공소 공개 디렉터리",
        "",
        "## 이번 승격 소스 분포",
    ]
    for key, count in sorted(by_source.items(), key=lambda kv: kv[1], reverse=True):
        lines.append(f"- {key}: {count:,}")
    lines += ["", "## 이번 승격 국가 분포"]
    for key, count in sorted(by_country.items(), key=lambda kv: kv[1], reverse=True):
        lines.append(f"- {key}: {count:,}")
    lines += ["", "## 이번 승격 세그먼트 분포"]
    for key, count in sorted(by_segment.items(), key=lambda kv: kv[1], reverse=True):
        lines.append(f"- {key}: {count:,}")
    lines += [
        "",
        "## 저장 파일",
        f"- 원시 후보 로그: `{RAW_JSONL}`",
        f"- 승격 로그: `{PROMOTIONS_JSONL}`",
        f"- 요청 캐시: `{CACHE_JSON}`",
        f"- 병합 데이터: `{base.VALID_JSONL}`",
    ]
    RESEARCH_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> int:
    global CACHE_JSON
    if args.cache_path:
        CACHE_JSON = Path(args.cache_path)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    cache: dict[str, object] = load_json(CACHE_JSON, {})  # type: ignore[assignment]
    before_by_key = base.existing_valid()
    sources = [
        ("healthspace", lambda: parse_healthspace(cache, args.healthspace_pages)),
        ("compedent", lambda: parse_compedent(cache)),
        ("ivoclar_bps", lambda: parse_ivoclar_bps(cache)),
        ("vddi", lambda: parse_vddi(cache)),
        ("myerson_ema_pdf", lambda: parse_myerson_ema_pdf(cache)),
        ("local_ch", lambda: parse_local_ch(cache, args.local_ch_pages, args.workers)),
        ("lmtmag", lambda: parse_lmtmag(cache, args.workers)),
        ("vzls", lambda: parse_vzls(cache, args.workers)),
        ("meditrader", lambda: parse_meditrader(cache, args.meditrader_max_start, args.workers)),
        ("nbc_certified_labs", lambda: parse_nbc_certified_labs(cache)),
        ("gelbeseiten", lambda: parse_gelbeseiten(cache, args.include_zahnarzt, args.german_city_limit, args.workers, args.gelbe_delay)),
    ]
    if args.sources:
        selected_sources = {source.strip() for source in args.sources.split(",") if source.strip()}
        unknown_sources = selected_sources - {source_name for source_name, _ in sources}
        if unknown_sources:
            raise ValueError(f"Unknown source(s): {', '.join(sorted(unknown_sources))}")
        sources = [(source_name, fn) for source_name, fn in sources if source_name in selected_sources]
    all_new: list[base.Prospect] = []
    valid_by_key = dict(before_by_key)
    for source_name, fn in sources:
        found = fn()
        append_jsonl(RAW_JSONL, [{"source": source_name, **asdict(row)} for row in found])
        added = 0
        for prospect in found:
            key = base.dedupe_key(prospect)
            if key in valid_by_key:
                continue
            valid_by_key[key] = prospect
            all_new.append(prospect)
            added += 1
            if len(valid_by_key) >= args.target:
                break
        append_jsonl(PROMOTIONS_JSONL, [{"source": source_name, **asdict(row)} for row in all_new[-added:]])
        prospects = sorted(valid_by_key.values(), key=lambda p: (p.country, p.city_hint, p.name))
        base.rewrite_valid(prospects)
        print(json.dumps({"source": source_name, "found": len(found), "added": added, "totalValid": len(valid_by_key)}, ensure_ascii=False), flush=True)
        if len(valid_by_key) >= args.target:
            break
    prospects = sorted(valid_by_key.values(), key=lambda p: (p.country, p.city_hint, p.name))
    base.rewrite_valid(prospects)
    write_research_md(all_new, len(before_by_key), len(valid_by_key))
    print(json.dumps({"done": True, "before": len(before_by_key), "after": len(valid_by_key), "added": len(valid_by_key) - len(before_by_key), "target": args.target, "research": str(RESEARCH_MD)}, ensure_ascii=False, indent=2))
    return 0 if len(valid_by_key) >= args.target else 2


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=int, default=11183)
    parser.add_argument("--healthspace-pages", type=int, default=25)
    parser.add_argument("--include-zahnarzt", action="store_true", help="Fill remaining volume with German dental clinics from Gelbe Seiten.")
    parser.add_argument("--german-city-limit", type=int, default=len(GERMAN_CITIES), help="Number of German GeoNames cities to query in Gelbe Seiten.")
    parser.add_argument("--local-ch-pages", type=int, default=4, help="Pages per local.ch Switzerland local-language query.")
    parser.add_argument("--gelbe-delay", type=float, default=0.0, help="Optional delay between Gelbe Seiten category parse loops.")
    parser.add_argument("--meditrader-max-start", type=int, default=0, help="Maximum Meditrader search start offset, in steps of 20.")
    parser.add_argument("--workers", type=int, default=12, help="Parallel workers for direct directory page prefetch.")
    parser.add_argument("--sources", default="", help="Comma-separated source names to run. Empty runs all sources.")
    parser.add_argument("--cache-path", default="", help="Optional alternate cache JSON path for source-specific runs.")
    args = parser.parse_args(argv)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
