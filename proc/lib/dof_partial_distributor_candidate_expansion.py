#!/usr/bin/env python3
"""Append non-OSM partial-contact dental distributor/vendor prospects.

This round deliberately differs from the earlier "complete contact" pipeline.
The user's requested target is volume expansion from non-OSM methods, so rows
from official dental exhibition directories and localized public search results
are allowed when direct email/phone/address is incomplete. Each appended row is
tagged with source trust and contact completeness so sales users can triage it.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import subprocess
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup


ROOT = Path("/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04")
OUT_ROOT = ROOT / "output/dof-overseas-customer-prospects/2026-05-30/scale5000"
DATA = OUT_ROOT / "data"
COMPLETE_JSONL = DATA / "prospects_augmented_contact_complete.jsonl"
COMPLETE_CSV = DATA / "prospects_augmented_contact_complete.csv"
EXHIBITION_RAW = DATA / "exhibition_vendor_raw_round6.jsonl"
LOCALIZED_RAW = DATA / "localized_distributor_web_raw_round7.jsonl"
BACKUP_DIR = DATA / "backups"
PROMOTIONS_JSONL = DATA / "partial_distributor_promotions_round9.jsonl"
SUMMARY_MD = OUT_ROOT / "external_partial_distributor_expansion_round9.md"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
)

GERMAN_PAVILION_AEEDC_2026 = "https://www.german-pavilion.com/en/aeedc-2026"
GERMAN_PAVILION_AEEDC_2026_SITE = "https://aeedc.german-pavilion.com"
ICE_AEEDC_2026_PDF = "https://www.ice.it/it/sites/default/files/inline-files/AEEDC%202026_compressed.pdf"
DENTAL_WORLD_2026 = "https://dentalworld.hu/exhibitor/"
BDIA_EXHIBITORS = "https://dentalshowcase.com/exhibitors"
BDIA_EXHIBITOR_LIST = "https://dentalshowcase.com/exhibitor-list"
SMALLWORLD_LIST_EVENTS = [
    ("Greater New York Dental Meeting 2025", "https://gnydm2025.smallworldlabs.com/exhibitors", "United States"),
    ("Yankee Dental Congress 2026", "https://yankee2026.smallworldlabs.com/exhibitors", "United States"),
    ("Thomas P. Hinman Dental Meeting 2025", "https://hinman25.smallworldlabs.com/exhibitors", "United States"),
    ("Thomas P. Hinman Dental Meeting 2026", "https://hinman2026.smallworldlabs.com/exhibitors", "United States"),
    ("AAO Annual Meeting 2025", "https://aaorthoannual2025.smallworldlabs.com/exhibitors", "United States"),
    ("Star of the North Meeting 2025", "https://sotn25.smallworldlabs.com/exhibitors", "United States"),
    ("Star of the North Meeting 2026", "https://sotn26.smallworldlabs.com/exhibitors", "United States"),
    ("AAO Winter Meeting 2025", "https://aaorthowintermeeting2025.smallworldlabs.com/exhibitors", "United States"),
    ("AAO Winter Meeting 2026", "https://aaorthowintermeeting2026.smallworldlabs.com/exhibitors", "United States"),
    ("ADEA Annual Session & Exhibition 2026", "https://adea2026.smallworldlabs.com/exhibitors", "Canada"),
]

OFFICIAL_EXHIBITION_SOURCES = {
    "ids_cologne_2025_detail": {
        "source_type": "IDS Cologne 2025 official exhibitor directory profile (partial contact)",
        "trust": "high",
        "family": "official_exhibition_profile",
        "priority": 10,
        "source_url_field": "url",
        "summary": "IDS Cologne 공식 전시자 프로필에 등록된 치과 장비·재료·기공·디지털 덴탈 업체",
        "acquisition": "IDS Cologne 2025 공식 exhibitor profile raw에서 업체명, 국가, 주소, 웹사이트, 제품 요약을 확인",
    },
    "gnydm_2025_profile": {
        "source_type": "Greater New York Dental Meeting 2025 official exhibitor directory profile (partial contact)",
        "trust": "medium-high",
        "family": "official_exhibition_profile",
        "priority": 20,
        "source_url_field": "profile",
        "summary": "GNYDM 공식 전시자 프로필에 등록된 치과 장비·재료·서비스 업체",
        "acquisition": "GNYDM 2025 공식 exhibitor directory profile에서 업체명, 국가, 주소, 전화, 웹사이트를 확인",
    },
    "smallworld_dental_profile": {
        "source_type": "SmallWorldLabs dental meeting official exhibitor directory profile (partial contact)",
        "trust": "medium-high",
        "family": "official_exhibition_profile",
        "priority": 30,
        "source_url_field": "profile",
        "summary": "미국 주요 치과 학회·전시회의 SmallWorldLabs 공식 exhibitor profile 등록 업체",
        "acquisition": "SmallWorldLabs 기반 공식 dental meeting exhibitor profile에서 업체명, 전시회명, 주소, 전화, 웹사이트를 확인",
    },
    "ids_preliminary_pdf_row": {
        "source_type": "IDS Cologne 2025 preliminary exhibitor list PDF (partial contact)",
        "trust": "high",
        "family": "official_exhibition_pdf",
        "priority": 40,
        "source_url_field": "source_url",
        "summary": "IDS Cologne 공식 preliminary exhibitor PDF에 등재된 글로벌 치과 전시 참가 업체",
        "acquisition": "IDS Cologne 2025 공식 preliminary exhibitor PDF에서 업체명, 국가, 웹사이트를 확인",
    },
}

SOURCE_PRIORITY = {
    "German Pavilion AEEDC 2026 official exhibitor page (partial contact)": 45,
    "ICE/ITA AEEDC 2026 official Italian Pavilion PDF (partial contact)": 46,
    "Dental World Budapest 2026 official exhibitor page (partial contact)": 47,
    "BDIA Dental Showcase official exhibitor page (partial contact)": 48,
    "SmallWorldLabs official dental exhibitor list page (source-only partial contact)": 60,
    "Localized search/yellow-page public dental distributor signal (partial contact)": 80,
    "Facebook/LinkedIn public dental distributor signal (low trust)": 90,
}

SOCIAL_HOSTS = ("facebook.com", "linkedin.com")
SKIP_HOSTS = (
    "scribd.com",
    "wikipedia.org",
    "visitorslist.com",
    "expocaptive.com",
    "exhibitorsdata.com",
    "reddit.com",
)
GENERIC_TITLE_PATTERNS = (
    "local distributors",
    "find your",
    "distributors -",
    "exhibitor list",
    "attendees list",
    "client challenge",
    "catalogue",
    "catalog",
    "pdf",
)

CSV_PREFERRED = [
    "name",
    "country",
    "city_hint",
    "segment",
    "email",
    "phone",
    "address",
    "website",
    "source_url",
    "selection_reason",
    "dof_fit",
]


@dataclass
class Candidate:
    row: dict[str, Any]
    priority: int


def clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as file_obj:
        for line in file_obj:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as file_obj:
        for row in rows:
            file_obj.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    tmp.replace(path)


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file_obj:
        for row in rows:
            file_obj.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    extra = sorted({key for row in rows for key in row if key not in CSV_PREFERRED and key not in {"tags", "evidence"}})
    fieldnames = CSV_PREFERRED + extra
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})
    tmp.replace(path)


def host(value: str) -> str:
    try:
        return (urlparse(value).hostname or "").lower().removeprefix("www.")
    except Exception:
        return ""


def domain_url(value: str) -> str:
    value = clean(value)
    if not value:
        return ""
    if value.startswith("//"):
        value = "https:" + value
    if not value.startswith(("http://", "https://")) and "." in value and " " not in value:
        value = "https://" + value
    parsed = urlparse(value)
    if not parsed.netloc:
        return ""
    return f"{parsed.scheme or 'https'}://{parsed.netloc}".rstrip("/")


def row_business_key(row: dict[str, Any]) -> str:
    email = clean(row.get("email")).lower()
    if email:
        return f"email:{email}"
    name = clean(row.get("name")).lower()
    website = domain_url(clean(row.get("website"))).lower()
    if name and website:
        return f"name_website:{name}|{website}"
    source_url = clean(row.get("source_url")).lower().rstrip("/")
    country = clean(row.get("country")).lower()
    address = clean(row.get("address")).lower()
    if name and address:
        return f"name_address:{name}|{address}"
    return f"name_country_source:{name}|{country}|{source_url}"


def publisher_dedupe_key(row: dict[str, Any]) -> str:
    email = clean(row.get("email")).lower()
    if email:
        return email
    return f"{clean(row.get('name')).lower()}|{clean(row.get('address')).lower()}"


def contact_completeness(row: dict[str, Any]) -> str:
    present = [field for field in ("email", "phone", "address", "website") if clean(row.get(field))]
    if {"email", "phone", "address"}.issubset(set(present)):
        return "complete_direct_contact"
    if "email" in present and ("phone" in present or "address" in present):
        return "email_plus_partial"
    if "phone" in present and "address" in present:
        return "phone_address"
    if "website" in present and ("address" in present or "phone" in present):
        return "website_plus_partial"
    if "website" in present:
        return "website_only"
    return "source_only"


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
    website: str = "",
    email: str = "",
    phone: str = "",
    address: str = "",
    evidence: list[str] | None = None,
    event: str = "",
    original_kind: str = "",
) -> dict[str, Any]:
    row = {
        "address": clean(address),
        "city_hint": "",
        "collected_at": datetime.now().replace(microsecond=0).isoformat(),
        "country": clean(country),
        "dof_fit": "Channel sales, scanner resale, equipment distribution, local service partnership",
        "email": clean(email),
        "evidence": [clean(item) for item in (evidence or []) if clean(item)],
        "name": clean(name),
        "osm_id": 0,
        "osm_type": "",
        "phone": clean(phone),
        "segment": "Dental distributor / product supplier",
        "selection_reason": (
            "Public non-OSM dental exhibition, distributor, supplier, importer/exporter, "
            "yellow-page, or social/public-search signal. Contact fields may be incomplete; "
            "use the trust and completeness tags before outreach."
        ),
        "source_type": source_type,
        "source_url": clean(source_url),
        "tags": {
            "acquisition_path": acquisition_path,
            "contact_completeness": "",
            "non_osm": "true",
            "partial_contact": "true",
            "product_keywords": "치과 장비, 치과 재료, 유통, 수입, 수출, 리셀, 전시회 참가, 현지 서비스",
            "site_business_summary": site_business_summary,
            "source_family": source_family,
            "source_trust": source_trust,
        },
        "validation_status": "partial_public_source",
        "website": domain_url(website) or clean(website),
    }
    if event:
        row["tags"]["event"] = event
    if original_kind:
        row["tags"]["original_source_kind"] = original_kind
    row["tags"]["contact_completeness"] = contact_completeness(row)
    if not row["evidence"]:
        row["evidence"] = [
            f"{source_type}: {row['name']}",
            f"Source trust={source_trust}; contact completeness={row['tags']['contact_completeness']}",
        ]
    else:
        row["evidence"].append(f"Source trust={source_trust}; contact completeness={row['tags']['contact_completeness']}")
    return row


def is_usable_name(name: str) -> bool:
    value = clean(name)
    lower = value.lower()
    if len(value) < 2 or len(value) > 120:
        return False
    if any(pattern in lower for pattern in GENERIC_TITLE_PATTERNS):
        return False
    if lower in {"home", "contact", "about", "website and exhibitor list", "learn more", "our sponsors"}:
        return False
    return True


def clean_title_name(title: str) -> str:
    title = re.sub(r"^\s*PDF\s+", "", clean(title), flags=re.I)
    title = re.split(r"\s+\|\s+|\s+-\s+(?:Facebook|LinkedIn|Instagram|X)\b", title, maxsplit=1)[0]
    title = re.sub(r"\s+\((?:official|home)\)$", "", title, flags=re.I)
    return clean(title)


def add_candidate(candidates: list[Candidate], row: dict[str, Any], priority: int) -> None:
    if not clean(row.get("name")) or not clean(row.get("country")) or not clean(row.get("source_url")):
        return
    if not is_usable_name(str(row.get("name"))):
        return
    candidates.append(Candidate(row=row, priority=priority))


def collect_from_exhibition_raw() -> list[Candidate]:
    candidates: list[Candidate] = []
    for raw in read_jsonl(EXHIBITION_RAW):
        source = str(raw.get("source") or "")
        meta = OFFICIAL_EXHIBITION_SOURCES.get(source)
        if not meta:
            continue
        name = clean(raw.get("name"))
        country = clean(raw.get("country"))
        source_url = clean(raw.get(meta["source_url_field"]) or raw.get("source_url") or raw.get("url") or raw.get("profile"))
        website = clean(raw.get("website"))
        address = clean(raw.get("address"))
        phone = clean(raw.get("phone"))
        summary = clean(raw.get("summary")) or str(meta["summary"])
        event = clean(raw.get("event"))
        evidence = [
            f"{source} raw entry: {name}",
            f"Public source URL: {source_url}",
        ]
        if event:
            evidence.append(f"Event: {event}")
        if summary:
            evidence.append(f"Product/profile summary: {summary[:240]}")
        row = make_row(
            name=name,
            country=country,
            source_type=str(meta["source_type"]),
            source_url=source_url,
            source_trust=str(meta["trust"]),
            source_family=str(meta["family"]),
            acquisition_path=str(meta["acquisition"]),
            site_business_summary=summary,
            website=website,
            phone=phone,
            address=address,
            evidence=evidence,
            event=event,
            original_kind=source,
        )
        add_candidate(candidates, row, int(meta["priority"]))
    return candidates


def fetch_html(url: str) -> str:
    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=(6, 24), allow_redirects=True)
    except requests.RequestException:
        return ""
    if response.status_code >= 400:
        return ""
    return response.text


def collect_german_pavilion() -> list[Candidate]:
    html = fetch_html(GERMAN_PAVILION_AEEDC_2026)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[Candidate] = []
    seen: set[str] = set()
    for link in soup.find_all("a", href=True):
        href = clean(link["href"])
        if "/sites/exhibitors/" not in href:
            continue
        name = clean(link.get_text(" ", strip=True))
        if not is_usable_name(name):
            continue
        if href.startswith("/"):
            href = GERMAN_PAVILION_AEEDC_2026_SITE + href
        key = f"{name}|{href}"
        if key in seen:
            continue
        seen.add(key)
        row = make_row(
            name=name,
            country="Germany",
            source_type="German Pavilion AEEDC 2026 official exhibitor page (partial contact)",
            source_url=href,
            source_trust="high",
            source_family="government_trade_pavilion",
            acquisition_path="독일 정부/무역전시 German Pavilion AEEDC 2026 공식 참가사 페이지에서 업체명과 전시 프로필 URL을 확인",
            site_business_summary="AEEDC Dubai 2026 German Pavilion에 참가한 독일 치과 장비·재료·디지털 덴탈 제조/유통 채널 후보",
            website="",
            evidence=[
                f"German Pavilion AEEDC 2026 exhibitor link: {name}",
                "Official German Pavilion page reports 102 exhibitors for AEEDC 2026.",
            ],
            event="AEEDC Dubai 2026 / German Pavilion",
            original_kind="german_pavilion_aeedc_2026",
        )
        add_candidate(candidates, row, SOURCE_PRIORITY[row["source_type"]])
    return candidates


def collect_bdia() -> list[Candidate]:
    candidates: list[Candidate] = []
    seen: set[str] = set()
    for url in (BDIA_EXHIBITORS, BDIA_EXHIBITOR_LIST):
        html = fetch_html(url)
        if not html:
            continue
        soup = BeautifulSoup(html, "html.parser")
        names: list[str] = []
        for heading in soup.find_all(["h2", "h3", "h4"]):
            name = clean(heading.get_text(" ", strip=True))
            if is_usable_name(name):
                names.append(name)
        text_lines = [clean(line) for line in soup.get_text("\n", strip=True).splitlines() if clean(line)]
        for idx, line in enumerate(text_lines):
            if line.lower().startswith("stand:") and idx > 0 and is_usable_name(text_lines[idx - 1]):
                names.append(text_lines[idx - 1])
        for name in names:
            lower = name.lower()
            if any(skip in lower for skip in ("opening times", "registration sponsor", "headline speaker", "official ", "exclusive ")):
                continue
            if name in seen:
                continue
            seen.add(name)
            row = make_row(
                name=name,
                country="United Kingdom",
                source_type="BDIA Dental Showcase official exhibitor page (partial contact)",
                source_url=url,
                source_trust="medium-high",
                source_family="official_exhibition_page",
                acquisition_path="BDIA Dental Showcase 공식 exhibitor page에서 업체명과 stand 정보를 확인",
                site_business_summary="영국 BDIA Dental Showcase 참가 치과 장비·재료·서비스 공급사 또는 유통 채널 후보",
                evidence=[f"BDIA Dental Showcase exhibitor listing: {name}", f"Source page: {url}"],
                event="BDIA Dental Showcase",
                original_kind="bdia_dental_showcase_exhibitor",
            )
            add_candidate(candidates, row, SOURCE_PRIORITY[row["source_type"]])
    return candidates


def collect_smallworld_list_pages() -> list[Candidate]:
    candidates: list[Candidate] = []
    global_seen: set[str] = set()
    for event, url, country in SMALLWORLD_LIST_EVENTS:
        html = fetch_html(url)
        if not html:
            continue
        soup = BeautifulSoup(html, "html.parser")
        names: list[str] = []
        for heading in soup.find_all(["h4", "h5", "h6"]):
            name = clean(heading.get_text(" ", strip=True))
            if is_usable_name(name):
                names.append(name)
        lines = [clean(line) for line in soup.get_text("\n", strip=True).splitlines() if clean(line)]
        for idx, line in enumerate(lines):
            if line.lower().startswith("booth #") and idx > 0 and is_usable_name(lines[idx - 1]):
                names.append(lines[idx - 1])
            if re.fullmatch(r"#?[A-Z0-9 ,/-]{2,18}", line) and idx > 0 and idx + 1 < len(lines) and lines[idx + 1].lower() == "explore":
                if is_usable_name(lines[idx - 1]):
                    names.append(lines[idx - 1])
        for name in names:
            lower = name.lower()
            if any(skip in lower for skip in ("foundation", "member services", "pavilion", "favorite", "filter by")):
                continue
            key = f"{event}|{name}".lower()
            if key in global_seen:
                continue
            global_seen.add(key)
            row = make_row(
                name=name,
                country=country,
                source_type="SmallWorldLabs official dental exhibitor list page (source-only partial contact)",
                source_url=url,
                source_trust="medium-high",
                source_family="official_exhibition_list_page",
                acquisition_path="SmallWorldLabs 기반 공식 dental meeting exhibitor list page에서 업체명과 booth/list 노출을 확인",
                site_business_summary=f"{event} 공식 전시자 목록에 등재된 치과 장비·재료·서비스 공급사 후보",
                evidence=[f"{event} official exhibitor list page: {name}", f"Source page: {url}"],
                event=event,
                original_kind="smallworld_official_exhibitor_list_page",
            )
            add_candidate(candidates, row, SOURCE_PRIORITY[row["source_type"]])
    return candidates


def collect_dental_world() -> list[Candidate]:
    html = fetch_html(DENTAL_WORLD_2026)
    if not html:
        return []
    text = BeautifulSoup(html, "html.parser").get_text("\n", strip=True)
    normalized = "\n".join(clean(line) for line in text.splitlines() if clean(line))
    pattern = re.compile(
        r"(?P<name>[^\n]{2,100})\nCountry:\s*(?P<country>[^\n]+)"
        r"(?:\nAddress:\s*(?P<address>[^\n]+))?"
        r"(?:\nWebsite:\s*(?P<website>[^\n]+))?"
        r"(?:\nContact person:\s*(?P<contact>[^\n]+))?"
        r"(?:\nEmail:\s*(?P<email>[^\n]+))?",
        re.I,
    )
    candidates: list[Candidate] = []
    seen: set[str] = set()
    for match in pattern.finditer(normalized):
        name = clean(match.group("name"))
        if not is_usable_name(name) or name.lower().startswith(("stand", "country", "website")):
            continue
        key = f"{name}|{match.group('country')}"
        if key in seen:
            continue
        seen.add(key)
        website = clean(match.group("website"))
        email = clean(match.group("email"))
        contact = clean(match.group("contact"))
        if not email and "@" in contact:
            email_match = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", contact)
            if email_match:
                email = email_match.group(0)
        row = make_row(
            name=name,
            country=clean(match.group("country")),
            source_type="Dental World Budapest 2026 official exhibitor page (partial contact)",
            source_url=DENTAL_WORLD_2026,
            source_trust="medium-high",
            source_family="official_exhibition_page",
            acquisition_path="Dental World Budapest 공식 exhibitor page에서 업체명, 국가, 주소, 웹사이트, 이메일이 노출된 경우 이를 확인",
            site_business_summary="Dental World Budapest 2026 참가 치과 장비·재료·디지털 덴탈 공급사 또는 현지 유통 채널 후보",
            website=website,
            email=email,
            address=clean(match.group("address")),
            evidence=[
                f"Dental World 2026 exhibitor block: {name}",
                f"Country={clean(match.group('country'))}; Website={website}; Email={email}",
            ],
            event="Dental World Budapest 2026",
            original_kind="dental_world_2026_exhibitor",
        )
        add_candidate(candidates, row, SOURCE_PRIORITY[row["source_type"]])
    return candidates


def collect_ice_pdf() -> list[Candidate]:
    pdf_path = DATA / "source_pdfs/AEEDC_2026_ICE_italian_pavilion.pdf"
    if not pdf_path.exists():
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            response = requests.get(ICE_AEEDC_2026_PDF, headers={"User-Agent": USER_AGENT}, timeout=(6, 30))
            if response.status_code < 400:
                pdf_path.write_bytes(response.content)
        except requests.RequestException:
            pass
    if not pdf_path.exists():
        return []
    try:
        result = subprocess.run(["pdftotext", "-layout", str(pdf_path), "-"], check=False, capture_output=True, timeout=30)
    except Exception:
        return []
    if result.returncode != 0:
        return []
    text = result.stdout.decode("utf-8", errors="ignore")
    candidates: list[Candidate] = []
    seen: set[str] = set()
    for raw_line in text.splitlines():
        line = clean(raw_line)
        if not line or len(line) < 3 or len(line) > 90:
            continue
        if not re.search(r"\b(SRL|S\.R\.L|SPA|S\.P\.A|GMBH|DENT|MED|IMPLANT|ORTHO|CAD|CAM)\b", line, re.I):
            continue
        name = re.sub(r"\s{2,}.*$", "", line)
        name = clean(name)
        if not is_usable_name(name):
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        row = make_row(
            name=name,
            country="Italy",
            source_type="ICE/ITA AEEDC 2026 official Italian Pavilion PDF (partial contact)",
            source_url=ICE_AEEDC_2026_PDF,
            source_trust="high",
            source_family="government_trade_pavilion_pdf",
            acquisition_path="이탈리아 무역공사 ICE/ITA의 AEEDC 2026 Italian Pavilion 공식 PDF에서 업체명을 확인",
            site_business_summary="AEEDC Dubai 2026 Italian Pavilion 참가 치과 장비·재료·임플란트·디지털 덴탈 업체",
            evidence=[f"ICE/ITA AEEDC 2026 PDF line: {line}"],
            event="AEEDC Dubai 2026 / Italian Pavilion",
            original_kind="ice_aeedc_2026_pdf",
        )
        add_candidate(candidates, row, SOURCE_PRIORITY[row["source_type"]])
    return candidates


def localized_signal_kind(raw: dict[str, Any]) -> tuple[str, str, str, int]:
    url = clean(raw.get("url") or raw.get("source_url") or (raw.get("contact") or {}).get("source_url"))
    current_host = host(url)
    if any(current_host.endswith(skip) for skip in SKIP_HOSTS):
        return "", "", "", 999
    blob = " ".join(clean(raw.get(key)) for key in ("title", "snippet", "query", "url"))
    dental = re.search(r"dental|dent|dentaire|denta|odont|zahn|stomat|nha khoa|gigi|牙|歯|طب الأسنان", blob, re.I)
    channel = re.search(
        r"distrib|supplier|supply|import|export|dealer|depot|comptoir|matériel|materiel|equip|equipment|trade|"
        r"trading|wholesale|grossiste|fournisseur|fornit|malzem|مستلزمات|器材|材料",
        blob,
        re.I,
    )
    if not dental or not channel:
        return "", "", "", 999
    if any(current_host.endswith(item) for item in SOCIAL_HOSTS):
        return "Facebook/LinkedIn public dental distributor signal (low trust)", "low", "public_social_signal", 90
    return "Localized search/yellow-page public dental distributor signal (partial contact)", "low-medium", "localized_search_or_yellow_page", 80


def collect_localized_signals() -> list[Candidate]:
    candidates: list[Candidate] = []
    for raw in read_jsonl(LOCALIZED_RAW):
        kind = raw.get("kind")
        if kind not in {"search_result", "search_result_checked"}:
            continue
        if kind == "search_result_checked" and raw.get("decision") not in {
            "skip_missing_required_contact",
            "skip_social_login_or_unstable_public_contact",
        }:
            continue
        source_type, trust, family, priority = localized_signal_kind(raw)
        if not source_type:
            continue
        contact = raw.get("contact") if isinstance(raw.get("contact"), dict) else {}
        title = clean(contact.get("title")) or clean(raw.get("title"))
        name = clean_title_name(title)
        if not is_usable_name(name):
            continue
        url = clean(raw.get("url") or contact.get("source_url"))
        row = make_row(
            name=name,
            country=clean(raw.get("country")),
            source_type=source_type,
            source_url=url,
            source_trust=trust,
            source_family=family,
            acquisition_path=(
                "현지어/영어 DuckDuckGo 검색 결과에서 치과 유통·수입·장비 공급 문맥을 확인. "
                "SNS는 로그인 없는 공개 snippet만 사용했으므로 낮은 신뢰도로 표기"
            ),
            site_business_summary=clean(raw.get("snippet"))[:420]
            or "치과 유통·공급·수출입 키워드가 검색 결과 공개 snippet에 노출된 후보",
            website=url if not any(host(url).endswith(item) for item in SOCIAL_HOSTS) else "",
            email=clean(contact.get("email")),
            phone=clean(contact.get("phone")),
            address=clean(contact.get("address")),
            evidence=[
                f"Query: {clean(raw.get('query'))}",
                f"Search title: {clean(raw.get('title'))}",
                f"Snippet: {clean(raw.get('snippet'))[:260]}",
                f"Decision before partial promotion: {clean(raw.get('decision')) or 'search_result_signal'}",
            ],
            original_kind=f"{kind}:{clean(raw.get('decision'))}",
        )
        add_candidate(candidates, row, priority)
    return candidates


def unique_candidates(candidates: list[Candidate], existing_keys: set[str], publisher_keys: set[str], limit: int) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen_keys = set(existing_keys)
    seen_publisher_keys = set(publisher_keys)
    for candidate in sorted(candidates, key=lambda item: (item.priority, clean(item.row.get("country")), clean(item.row.get("name")).lower())):
        row = candidate.row
        key = row_business_key(row)
        pub_key = publisher_dedupe_key(row)
        if not key or key in seen_keys or pub_key in seen_publisher_keys:
            continue
        selected.append(row)
        seen_keys.add(key)
        seen_publisher_keys.add(pub_key)
        if len(selected) >= limit:
            break
    return selected


def write_summary(
    *,
    backup_path: Path,
    before_count: int,
    after_count: int,
    selected: list[dict[str, Any]],
    candidates: list[Candidate],
) -> None:
    source_counts = Counter(row["source_type"] for row in selected)
    trust_counts = Counter((row.get("tags") or {}).get("source_trust", "") for row in selected)
    completeness_counts = Counter((row.get("tags") or {}).get("contact_completeness", "") for row in selected)
    country_counts = Counter(row.get("country") or "Unknown" for row in selected)
    lines = [
        "# Round 9 partial-contact non-OSM dental distributor/vendor expansion",
        "",
        "## Result",
        f"- Baseline backup: `{backup_path}`",
        f"- Complete dataset rows before: {before_count:,}",
        f"- Added rows this round: {len(selected):,}",
        f"- Complete dataset rows after: {after_count:,}",
        f"- Candidate pool before dedupe: {len(candidates):,}",
        "",
        "## Trust model",
        "- high: official exhibition PDF/profile, government or national trade pavilion page/PDF.",
        "- medium-high: official exhibition directory pages where company identity is public but direct contact may be incomplete.",
        "- low-medium: localized search/yellow-page public snippets that mention dental distribution/supply/import/export.",
        "- low: Facebook/LinkedIn public search/profile snippets only; use as a lead signal, not as verified contact data.",
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
    for country, count in country_counts.most_common(30):
        lines.append(f"- {country}: {count:,}")
    lines += [
        "",
        "## Source URLs used",
        f"- IDS Cologne preliminary exhibitor PDF: https://media.koelnmesse.io/ids/redaktionell/ids/downloads/pdf/exhibitors-of-ids/preliminary-exhibitor-list.pdf",
        f"- IDS Cologne exhibitor profiles: https://www.english.ids-cologne.de/ids-cologne-exhibitors/list-of-exhibitors/",
        f"- GNYDM / SmallWorldLabs dental exhibitor directories: https://gnydm2025.smallworldlabs.com/exhibitors",
        f"- German Pavilion AEEDC 2026: {GERMAN_PAVILION_AEEDC_2026}",
        f"- ICE/ITA AEEDC 2026 PDF: {ICE_AEEDC_2026_PDF}",
        f"- Dental World Budapest 2026 exhibitors: {DENTAL_WORLD_2026}",
        f"- BDIA Dental Showcase exhibitors: {BDIA_EXHIBITORS}",
        "",
        "## Notes",
        "- This file intentionally includes partial-contact rows. Direct outreach should prioritize complete_direct_contact and email_plus_partial first.",
        "- Existing rows were preserved. New rows were deduped against current complete rows by email, then company+website, company+address, or company+country+source URL.",
        "- OSM was not used as an acquisition source in this round.",
    ]
    SUMMARY_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-additional", type=int, default=3000)
    args = parser.parse_args()

    complete_rows = read_jsonl(COMPLETE_JSONL)
    before_count = len(complete_rows)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = BACKUP_DIR / f"prospects_augmented_contact_complete.before_partial_round9_{stamp}.jsonl"
    shutil.copy2(COMPLETE_JSONL, backup_path)

    existing_keys = {row_business_key(row) for row in complete_rows if row_business_key(row)}
    publisher_keys = {publisher_dedupe_key(row) for row in complete_rows if publisher_dedupe_key(row)}
    candidates: list[Candidate] = []
    collectors = [
        collect_from_exhibition_raw,
        collect_german_pavilion,
        collect_ice_pdf,
        collect_dental_world,
        collect_bdia,
        collect_smallworld_list_pages,
        collect_localized_signals,
    ]
    for collector in collectors:
        collected = collector()
        candidates.extend(collected)
        print(json.dumps({"collector": collector.__name__, "candidates": len(collected)}, ensure_ascii=False), flush=True)

    selected = unique_candidates(candidates, existing_keys, publisher_keys, args.target_additional)
    complete_rows.extend(selected)
    write_jsonl(COMPLETE_JSONL, complete_rows)
    write_csv(COMPLETE_CSV, complete_rows)
    append_jsonl(PROMOTIONS_JSONL, selected)
    round9_rows = read_jsonl(PROMOTIONS_JSONL)
    round9_before_count = len(complete_rows) - len(round9_rows)
    write_summary(
        backup_path=backup_path,
        before_count=round9_before_count,
        after_count=len(complete_rows),
        selected=round9_rows,
        candidates=candidates,
    )

    print(
        json.dumps(
            {
                "backup": str(backup_path),
                "beforeRows": before_count,
                "addedRows": len(selected),
                "round9CumulativeAddedRows": len(round9_rows),
                "afterRows": len(complete_rows),
                "summaryMd": str(SUMMARY_MD),
                "promotionsJsonl": str(PROMOTIONS_JSONL),
                "sourceCounts": dict(Counter(row["source_type"] for row in selected).most_common()),
                "trustCounts": dict(Counter((row.get("tags") or {}).get("source_trust", "") for row in selected).most_common()),
                "contactCompletenessCounts": dict(Counter((row.get("tags") or {}).get("contact_completeness", "") for row in selected).most_common()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
