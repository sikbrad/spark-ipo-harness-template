#!/usr/bin/env python3
"""Collect overseas DOF prospect cards with required contact fields.

This pipeline is intentionally strict: a prospect is considered valid only when
email, phone/contact number, address, and a DOF selection reason are present.
It uses public OpenStreetMap business tags as the high-volume contact source and
GeoNames city coordinates to query dense overseas markets in manageable chunks.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import re
import sys
import time
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import requests


ROOT = Path("/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04")
OUT_ROOT = ROOT / "output/dof-overseas-customer-prospects/2026-05-30/scale5000"
DATA_DIR = OUT_ROOT / "data"
CARDS_DIR = OUT_ROOT / "cards"
CACHE_DIR = OUT_ROOT / "cache"
LOG_DIR = OUT_ROOT / "logs"

GEONAMES_URL = "https://download.geonames.org/export/dump/cities15000.zip"
GEONAMES_ZIP = CACHE_DIR / "cities15000.zip"
GEONAMES_TXT = CACHE_DIR / "cities15000.txt"

VALID_JSONL = DATA_DIR / "prospects_valid.jsonl"
VALID_CSV = DATA_DIR / "prospects_valid.csv"
INCOMPLETE_JSONL = DATA_DIR / "prospects_incomplete.jsonl"
RAW_SOURCES_JSON = DATA_DIR / "raw_sources.json"
RUN_LOG = LOG_DIR / "collection_run.log"
README = OUT_ROOT / "README.md"
SCHEMA = OUT_ROOT / "schema.md"

USER_AGENT = "DOF overseas prospect research contact validation (local agent; public OSM/GeoNames data)"
OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

US_STATE_AREAS = [
    "US-AL",
    "US-AK",
    "US-AZ",
    "US-AR",
    "US-CA",
    "US-CO",
    "US-CT",
    "US-DE",
    "US-DC",
    "US-FL",
    "US-GA",
    "US-HI",
    "US-ID",
    "US-IL",
    "US-IN",
    "US-IA",
    "US-KS",
    "US-KY",
    "US-LA",
    "US-ME",
    "US-MD",
    "US-MA",
    "US-MI",
    "US-MN",
    "US-MS",
    "US-MO",
    "US-MT",
    "US-NE",
    "US-NV",
    "US-NH",
    "US-NJ",
    "US-NM",
    "US-NY",
    "US-NC",
    "US-ND",
    "US-OH",
    "US-OK",
    "US-OR",
    "US-PA",
    "US-RI",
    "US-SC",
    "US-SD",
    "US-TN",
    "US-TX",
    "US-UT",
    "US-VT",
    "US-VA",
    "US-WA",
    "US-WV",
    "US-WI",
    "US-WY",
]

TARGET_COUNTRIES: dict[str, str] = {
    "US": "United States",
    "GB": "United Kingdom",
    "DE": "Germany",
    "FR": "France",
    "IT": "Italy",
    "ES": "Spain",
    "CA": "Canada",
    "AU": "Australia",
    "NL": "Netherlands",
    "BE": "Belgium",
    "CH": "Switzerland",
    "AT": "Austria",
    "SE": "Sweden",
    "NO": "Norway",
    "DK": "Denmark",
    "FI": "Finland",
    "IE": "Ireland",
    "PT": "Portugal",
    "PL": "Poland",
    "CZ": "Czechia",
    "JP": "Japan",
    "SG": "Singapore",
    "HK": "Hong Kong",
    "MY": "Malaysia",
    "TH": "Thailand",
    "VN": "Vietnam",
    "ID": "Indonesia",
    "PH": "Philippines",
    "KH": "Cambodia",
    "LA": "Laos",
    "MM": "Myanmar",
    "BN": "Brunei",
    "TL": "Timor-Leste",
    "NZ": "New Zealand",
    "LU": "Luxembourg",
}

COUNTRY_PRIORITY = {
    "DE": 1,
    "GB": 2,
    "US": 3,
    "CA": 4,
    "NL": 5,
    "PL": 6,
    "SE": 7,
    "AT": 8,
    "CH": 9,
    "BE": 10,
    "DK": 11,
    "IE": 12,
    "AU": 13,
    "NZ": 14,
    "ES": 15,
    "FR": 16,
    "IT": 17,
    "PT": 18,
    "CZ": 19,
    "NO": 20,
    "FI": 21,
    "LU": 22,
    "SG": 30,
    "MY": 31,
    "TH": 32,
    "VN": 33,
    "ID": 34,
    "PH": 35,
    "KH": 36,
    "LA": 37,
    "MM": 38,
    "BN": 39,
    "TL": 40,
    "HK": 40,
    "JP": 50,
}

EMAIL_RE = re.compile(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", re.I)
BAD_EMAIL_PREFIXES = {"example", "test", "privacy", "noreply", "no-reply", "donotreply"}


@dataclass
class City:
    geoname_id: str
    name: str
    country_code: str
    country: str
    lat: float
    lon: float
    population: int


@dataclass
class Prospect:
    name: str
    country: str
    city_hint: str
    segment: str
    email: str
    phone: str
    address: str
    website: str
    source_url: str
    source_type: str
    selection_reason: str
    dof_fit: str
    evidence: list[str]
    osm_type: str
    osm_id: int
    tags: dict[str, str]
    collected_at: str
    validation_status: str = "valid"


def ensure_dirs() -> None:
    for path in (DATA_DIR, CARDS_DIR, CACHE_DIR, LOG_DIR):
        path.mkdir(parents=True, exist_ok=True)


def log(message: str) -> None:
    stamp = datetime.now().isoformat(timespec="seconds")
    line = f"[{stamp}] {message}"
    print(line, flush=True)
    RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
    with RUN_LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def download_geonames() -> None:
    if GEONAMES_TXT.exists():
        return
    ensure_dirs()
    if not GEONAMES_ZIP.exists():
        log(f"Downloading GeoNames city index: {GEONAMES_URL}")
        with requests.get(GEONAMES_URL, headers={"User-Agent": USER_AGENT}, timeout=120, stream=True) as r:
            r.raise_for_status()
            with GEONAMES_ZIP.open("wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
    with zipfile.ZipFile(GEONAMES_ZIP) as zf:
        name = next(n for n in zf.namelist() if n.endswith(".txt"))
        GEONAMES_TXT.write_bytes(zf.read(name))


def load_cities(max_cities: int, countries: set[str] | None, skip_countries: set[str]) -> list[City]:
    download_geonames()
    cities: list[City] = []
    with GEONAMES_TXT.open("r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        for row in reader:
            country_code = row[8]
            feature_class = row[6]
            feature_code = row[7]
            if country_code not in TARGET_COUNTRIES:
                continue
            if feature_class != "P" or feature_code in {"PPLX", "PPLQ", "PPLH"}:
                continue
            if countries and country_code not in countries:
                continue
            if country_code in skip_countries:
                continue
            population = int(row[14] or 0)
            if population < 60000:
                continue
            cities.append(
                City(
                    geoname_id=row[0],
                    name=row[1],
                    country_code=country_code,
                    country=TARGET_COUNTRIES[country_code],
                    lat=float(row[4]),
                    lon=float(row[5]),
                    population=population,
                )
            )
    cities.sort(key=lambda c: (COUNTRY_PRIORITY.get(c.country_code, 99), -c.population))
    return cities[:max_cities]


def radius_degrees(population: int) -> float:
    if population >= 8_000_000:
        return 0.65
    if population >= 4_000_000:
        return 0.5
    if population >= 2_000_000:
        return 0.38
    if population >= 1_000_000:
        return 0.3
    if population >= 500_000:
        return 0.23
    if population >= 200_000:
        return 0.18
    return 0.14


def bbox_for(city: City) -> tuple[float, float, float, float]:
    r = radius_degrees(city.population)
    lon_scale = max(math.cos(math.radians(city.lat)), 0.35)
    lon_r = min(r / lon_scale, 0.9)
    return (city.lat - r, city.lon - lon_r, city.lat + r, city.lon + lon_r)


def overpass_query(city: City) -> str:
    south, west, north, east = bbox_for(city)
    bbox = f"{south:.5f},{west:.5f},{north:.5f},{east:.5f}"
    # Query by dental entity first, then apply strict contact-field validation
    # locally. Requiring every contact key inside Overpass creates a large OR
    # matrix and makes city queries much slower than filtering a few hundred
    # dental objects client-side.
    selectors = []
    entity_filters = [
        '["amenity"="dentist"]',
        '["healthcare"="dentist"]',
        '["craft"="dental_technician"]',
    ]
    for entity_filter in entity_filters:
        for osm_type in ("node", "way", "relation"):
            selectors.append(f'{osm_type}{entity_filter}({bbox});')
    body = "\n  ".join(selectors)
    return f"""[out:json][timeout:35];
(
  {body}
);
out center tags;"""


def fetch_overpass(city: City, pause_seconds: float) -> dict[str, Any]:
    return fetch_overpass_query(overpass_query(city), pause_seconds)


def fetch_overpass_query(query: str, pause_seconds: float) -> dict[str, Any]:
    errors: list[str] = []
    for attempt in range(1, 4):
        endpoint = OVERPASS_ENDPOINTS[(attempt - 1) % len(OVERPASS_ENDPOINTS)]
        try:
            if pause_seconds:
                time.sleep(pause_seconds)
            r = requests.get(
                endpoint,
                params={"data": query},
                headers={"User-Agent": USER_AGENT},
                timeout=70,
            )
            if r.status_code in {429, 502, 503, 504}:
                errors.append(f"{endpoint} HTTP {r.status_code}")
                time.sleep(5 * attempt)
                continue
            r.raise_for_status()
            return r.json()
        except Exception as exc:  # noqa: BLE001 - log and retry endpoint.
            errors.append(f"{endpoint} {type(exc).__name__}: {exc}")
            time.sleep(3 * attempt)
    return {"elements": [], "errors": errors}


def overpass_country_email_query(country_code: str) -> str:
    selectors = []
    entity_filters = [
        '["amenity"="dentist"]',
        '["healthcare"="dentist"]',
        '["craft"="dental_technician"]',
    ]
    for entity_filter in entity_filters:
        for osm_type in ("node", "way", "relation"):
            for email_key in ("email", "contact:email"):
                selectors.append(f'{osm_type}{entity_filter}["{email_key}"](area.a);')
    body = "\n  ".join(selectors)
    return f"""[out:json][timeout:90];
area["ISO3166-1"="{country_code}"][admin_level=2]->.a;
(
  {body}
);
out center tags;"""


def overpass_iso3166_2_email_query(area_code: str) -> str:
    selectors = []
    entity_filters = [
        '["amenity"="dentist"]',
        '["healthcare"="dentist"]',
        '["craft"="dental_technician"]',
    ]
    for entity_filter in entity_filters:
        for osm_type in ("node", "way", "relation"):
            for email_key in ("email", "contact:email"):
                selectors.append(f'{osm_type}{entity_filter}["{email_key}"](area.a);')
    body = "\n  ".join(selectors)
    return f"""[out:json][timeout:90];
area["ISO3166-2"="{area_code}"][admin_level=4]->.a;
(
  {body}
);
out center tags;"""


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def first_email(tags: dict[str, str]) -> str:
    candidates = []
    for key in ("email", "contact:email"):
        candidates.extend(EMAIL_RE.findall(tags.get(key, "")))
    for email in candidates:
        prefix = email.split("@", 1)[0].lower()
        domain = email.split("@", 1)[1].lower()
        if prefix in BAD_EMAIL_PREFIXES:
            continue
        if domain.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
            continue
        return email
    return ""


def first_phone(tags: dict[str, str]) -> str:
    for key in ("phone", "contact:phone", "mobile", "contact:mobile"):
        value = clean_text(tags.get(key))
        if value:
            return value
    return ""


def address_text(tags: dict[str, str], city_hint: str, country: str) -> str:
    full = clean_text(tags.get("addr:full"))
    if full:
        return full
    parts = [
        clean_text(tags.get("addr:housenumber")),
        clean_text(tags.get("addr:street")),
        clean_text(tags.get("addr:suburb")),
        clean_text(tags.get("addr:city") or city_hint),
        clean_text(tags.get("addr:state")),
        clean_text(tags.get("addr:postcode")),
        clean_text(tags.get("addr:country") or country),
    ]
    return ", ".join(p for p in parts if p)


def osm_url(element: dict[str, Any]) -> str:
    return f"https://www.openstreetmap.org/{element.get('type')}/{element.get('id')}"


def segment_and_reason(tags: dict[str, str]) -> tuple[str, str, str]:
    tag_blob = " ".join(str(v) for v in tags.values()).lower()
    if tags.get("craft") == "dental_technician" or "laborator" in tag_blob or "dental technician" in tag_blob:
        return (
            "Dental laboratory / dental technician",
            "Publicly listed dental lab or dental technician with direct email, phone, and address; likely buyer of lab scanners, model scanning workflow, and CAD/CAM production tools.",
            "Lab scanner, CAD/CAM workflow, production digitization",
        )
    if "orthodont" in tag_blob:
        return (
            "Dental clinic / orthodontics",
            "Publicly listed orthodontic or dental clinic with direct email, phone, and address; likely buyer or evaluator of intraoral scanning and digital treatment workflows.",
            "Intraoral scanner, digital impression, case communication workflow",
        )
    if "implant" in tag_blob or "oral surgery" in tag_blob or "maxillo" in tag_blob:
        return (
            "Dental clinic / implant and surgery",
            "Publicly listed implant/surgical dental provider with direct email, phone, and address; implant workflows often require accurate scans and lab collaboration.",
            "Intraoral scanner, implant planning workflow, lab communication",
        )
    return (
        "Dental clinic / practice",
        "Publicly listed dental practice with direct email, phone, and address; dental clinics are prospective buyers of intraoral scanners and digital impression workflows.",
        "Intraoral scanner, digital impression, clinic-to-lab workflow",
    )


def prospect_from_element(element: dict[str, Any], city: City) -> tuple[Prospect | None, dict[str, Any] | None]:
    tags = {str(k): str(v) for k, v in element.get("tags", {}).items()}
    name = clean_text(tags.get("name") or tags.get("operator"))
    email = first_email(tags)
    phone = first_phone(tags)
    address = address_text(tags, city.name, city.country)
    missing = [field for field, value in {"name": name, "email": email, "phone": phone, "address": address}.items() if not value]
    if missing:
        return None, {
            "source_url": osm_url(element),
            "city_hint": city.name,
            "country": city.country,
            "missing": missing,
            "tags": tags,
        }
    segment, reason, dof_fit = segment_and_reason(tags)
    website = clean_text(tags.get("website") or tags.get("contact:website"))
    evidence = [
        f"OSM tags: {', '.join(k for k in sorted(tags) if k in {'amenity', 'healthcare', 'craft', 'healthcare:speciality', 'name', 'operator'})}",
        f"Required contact fields found: email={email}, phone={phone}, address={address}",
    ]
    return (
        Prospect(
            name=name,
            country=city.country,
            city_hint=city.name,
            segment=segment,
            email=email,
            phone=phone,
            address=address,
            website=website,
            source_url=osm_url(element),
            source_type="OpenStreetMap public business tag",
            selection_reason=reason,
            dof_fit=dof_fit,
            evidence=evidence,
            osm_type=str(element.get("type")),
            osm_id=int(element.get("id")),
            tags=tags,
            collected_at=datetime.now().isoformat(timespec="seconds"),
        ),
        None,
    )


def dedupe_key(prospect: Prospect) -> str:
    if prospect.email:
        return prospect.email.lower()
    return f"{prospect.name.lower()}|{prospect.address.lower()}"


def existing_valid() -> dict[str, Prospect]:
    prospects: dict[str, Prospect] = {}
    if not VALID_JSONL.exists():
        return prospects
    with VALID_JSONL.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            data = json.loads(line)
            prospect = Prospect(**data)
            prospects[dedupe_key(prospect)] = prospect
    return prospects


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def rewrite_valid(prospects: list[Prospect]) -> None:
    json_tmp = VALID_JSONL.with_suffix(".jsonl.tmp")
    csv_tmp = VALID_CSV.with_suffix(".csv.tmp")
    with json_tmp.open("w", encoding="utf-8") as f:
        for prospect in prospects:
            f.write(json.dumps(asdict(prospect), ensure_ascii=False, sort_keys=True) + "\n")
    fieldnames = [
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
    with csv_tmp.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for prospect in prospects:
            row = asdict(prospect)
            writer.writerow({key: row.get(key, "") for key in fieldnames})
    json_tmp.replace(VALID_JSONL)
    csv_tmp.replace(VALID_CSV)


def slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower())
    return s.strip("-")[:80] or "prospect"


def write_cards(prospects: list[Prospect], limit: int | None = None) -> None:
    for old in CARDS_DIR.glob("*.md"):
        old.unlink()
    selected = prospects if limit is None else prospects[:limit]
    for idx, prospect in enumerate(selected, start=1):
        path = CARDS_DIR / f"{idx:04d}-{slug(prospect.name)}.md"
        website_line = f"- Website: {prospect.website}" if prospect.website else "- Website: 미확인"
        content = f"""# {prospect.name}

- Country: {prospect.country}
- City/market hint: {prospect.city_hint}
- Segment: {prospect.segment}
- Email: {prospect.email}
- Phone/contact: {prospect.phone}
- Address: {prospect.address}
{website_line}
- Source: {prospect.source_url}

## 선정이유
{prospect.selection_reason}

## DOF 관점의 가능성
{prospect.dof_fit}

## 근거
{chr(10).join(f"- {item}" for item in prospect.evidence)}
"""
        path.write_text(content, encoding="utf-8")


def write_schema() -> None:
    SCHEMA.write_text(
        """# DOF 해외 잠재고객 5000 수집 스키마

## Valid 통과 조건
- `name`: 업체명 또는 병원/기공소명
- `email`: 공개 이메일
- `phone`: 전화번호 또는 직접 연락 가능한 번호
- `address`: 공개 주소
- `selection_reason`: DOF 고객 후보로 보는 이유
- `source_url`: 연락정보 근거 URL

## 주요 필드
- `segment`: Dental clinic/practice, orthodontics, implant/surgery, dental laboratory/technician 등
- `dof_fit`: DOF가 제안할 수 있는 장비/워크플로우 관점
- `evidence`: 필수 연락정보와 업종 판단 근거
- `validation_status`: 현재는 필수 필드가 모두 있는 경우만 `valid`
""",
        encoding="utf-8",
    )


def write_readme(prospects: list[Prospect], sources: list[dict[str, Any]], target: int) -> None:
    by_country: dict[str, int] = {}
    by_segment: dict[str, int] = {}
    for prospect in prospects:
        by_country[prospect.country] = by_country.get(prospect.country, 0) + 1
        by_segment[prospect.segment] = by_segment.get(prospect.segment, 0) + 1
    top_countries = "\n".join(f"- {k}: {v}" for k, v in sorted(by_country.items(), key=lambda kv: kv[1], reverse=True)[:30])
    top_segments = "\n".join(f"- {k}: {v}" for k, v in sorted(by_segment.items(), key=lambda kv: kv[1], reverse=True))
    sample_cards = "\n".join(
        f"- [{p.name}](cards/{idx:04d}-{slug(p.name)}.md) | {p.country} | {p.segment} | {p.email}"
        for idx, p in enumerate(prospects[:100], start=1)
    )
    README.write_text(
        f"""# DOF 해외 잠재 고객사 5000 수집

## 현재 상태
- 목표: {target}개 valid prospect
- 현재 valid: {len(prospects)}개
- valid 기준: 이메일, 전화/연락처, 주소, 선정이유, 출처가 모두 있는 경우만 통과
- 데이터: `data/prospects_valid.jsonl`, `data/prospects_valid.csv`
- 카드: `cards/`

## 국가 분포
{top_countries or "- 아직 없음"}

## 세그먼트 분포
{top_segments or "- 아직 없음"}

## 샘플 카드
{sample_cards or "- 아직 없음"}

## 조사 소스
- Playwright MCP 검색: dental laboratory directory / dental lab email / intraoral scanner distributor 계열 쿼리로 소스 후보 확인
- OpenStreetMap public business tags: 업체명, 이메일, 전화번호, 주소, 업종 태그
- GeoNames city index: 해외 주요 도시 좌표 및 인구 기반 조회 순서

## 최근 조회 배치
{json.dumps(sources[-20:], ensure_ascii=False, indent=2)}
""",
        encoding="utf-8",
    )


def save_sources(sources: list[dict[str, Any]]) -> None:
    tmp = RAW_SOURCES_JSON.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(sources, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(RAW_SOURCES_JSON)


def collect(args: argparse.Namespace) -> int:
    ensure_dirs()
    write_schema()
    valid_by_key = existing_valid()
    sources: list[dict[str, Any]] = []
    if RAW_SOURCES_JSON.exists():
        sources = json.loads(RAW_SOURCES_JSON.read_text(encoding="utf-8"))
    completed = {f"{s.get('country_code')}:{s.get('geoname_id')}" for s in sources if s.get("status") == "ok"}

    countries = set(args.countries.split(",")) if args.countries else None
    skip_countries = set(args.skip_countries.split(",")) if args.skip_countries else set()
    cities = load_cities(args.max_cities, countries, skip_countries)
    log(f"Loaded {len(cities)} cities; existing valid={len(valid_by_key)}; target={args.target}")
    incomplete_buffer: list[dict[str, Any]] = []

    for city in cities:
        if len(valid_by_key) >= args.target:
            break
        city_key = f"{city.country_code}:{city.geoname_id}"
        if city_key in completed and not args.revisit:
            continue
        result = fetch_overpass(city, args.pause)
        elements = result.get("elements", [])
        new_count = 0
        incomplete_count = 0
        for element in elements:
            prospect, incomplete = prospect_from_element(element, city)
            if prospect:
                key = dedupe_key(prospect)
                if key not in valid_by_key:
                    valid_by_key[key] = prospect
                    new_count += 1
            elif incomplete:
                incomplete_buffer.append(incomplete)
                incomplete_count += 1
        source_record = {
            "status": "ok" if "errors" not in result else "error",
            "country_code": city.country_code,
            "country": city.country,
            "geoname_id": city.geoname_id,
            "city": city.name,
            "population": city.population,
            "bbox": bbox_for(city),
            "elements": len(elements),
            "new_valid": new_count,
            "incomplete": incomplete_count,
            "errors": result.get("errors", []),
            "queried_at": datetime.now().isoformat(timespec="seconds"),
        }
        sources.append(source_record)
        prospects = sorted(valid_by_key.values(), key=lambda p: (p.country, p.city_hint, p.name))
        rewrite_valid(prospects)
        save_sources(sources)
        if incomplete_buffer:
            write_jsonl(INCOMPLETE_JSONL, incomplete_buffer)
            incomplete_buffer = []
        log(
            f"{city.country_code} {city.name}: elements={len(elements)} new_valid={new_count} "
            f"total_valid={len(valid_by_key)}"
        )

    prospects = sorted(valid_by_key.values(), key=lambda p: (p.country, p.city_hint, p.name))
    write_cards(prospects, limit=args.card_limit)
    write_readme(prospects, sources, args.target)
    log(f"Done. valid={len(prospects)} cards={min(len(prospects), args.card_limit or len(prospects))}")
    return 0 if len(prospects) >= args.target else 2


def collect_country_sweep(args: argparse.Namespace) -> int:
    ensure_dirs()
    write_schema()
    valid_by_key = existing_valid()
    sources: list[dict[str, Any]] = []
    if RAW_SOURCES_JSON.exists():
        sources = json.loads(RAW_SOURCES_JSON.read_text(encoding="utf-8"))
    completed = {f"sweep:{s.get('country_code')}" for s in sources if s.get("status") == "ok" and s.get("geoname_id") == "country-sweep"}
    countries = args.countries.split(",") if args.countries else list(TARGET_COUNTRIES)
    skip_countries = set(args.skip_countries.split(",")) if args.skip_countries else set()
    countries = [cc for cc in countries if cc in TARGET_COUNTRIES and cc not in skip_countries]
    countries.sort(key=lambda cc: COUNTRY_PRIORITY.get(cc, 99))
    log(f"Country sweep loaded {len(countries)} countries; existing valid={len(valid_by_key)}; target={args.target}")

    incomplete_buffer: list[dict[str, Any]] = []
    for country_code in countries:
        if len(valid_by_key) >= args.target:
            break
        sweep_key = f"sweep:{country_code}"
        if sweep_key in completed and not args.revisit:
            continue
        fake_city = City(
            geoname_id="country-sweep",
            name="Countrywide",
            country_code=country_code,
            country=TARGET_COUNTRIES[country_code],
            lat=0,
            lon=0,
            population=0,
        )
        result = fetch_overpass_query(overpass_country_email_query(country_code), args.pause)
        elements = result.get("elements", [])
        new_count = 0
        incomplete_count = 0
        for element in elements:
            prospect, incomplete = prospect_from_element(element, fake_city)
            if prospect:
                key = dedupe_key(prospect)
                if key not in valid_by_key:
                    valid_by_key[key] = prospect
                    new_count += 1
            elif incomplete:
                incomplete_buffer.append(incomplete)
                incomplete_count += 1
        source_record = {
            "status": "ok" if "errors" not in result else "error",
            "country_code": country_code,
            "country": TARGET_COUNTRIES[country_code],
            "geoname_id": "country-sweep",
            "city": "Countrywide",
            "population": 0,
            "bbox": None,
            "elements": len(elements),
            "new_valid": new_count,
            "incomplete": incomplete_count,
            "errors": result.get("errors", []),
            "queried_at": datetime.now().isoformat(timespec="seconds"),
        }
        sources.append(source_record)
        prospects = sorted(valid_by_key.values(), key=lambda p: (p.country, p.city_hint, p.name))
        rewrite_valid(prospects)
        save_sources(sources)
        if incomplete_buffer:
            write_jsonl(INCOMPLETE_JSONL, incomplete_buffer)
            incomplete_buffer = []
        log(
            f"{country_code} country sweep: elements={len(elements)} new_valid={new_count} "
            f"total_valid={len(valid_by_key)}"
        )

    prospects = sorted(valid_by_key.values(), key=lambda p: (p.country, p.city_hint, p.name))
    write_cards(prospects, limit=args.card_limit)
    write_readme(prospects, sources, args.target)
    log(f"Done. valid={len(prospects)} cards={min(len(prospects), args.card_limit or len(prospects))}")
    return 0 if len(prospects) >= args.target else 2


def collect_area_sweep(args: argparse.Namespace) -> int:
    ensure_dirs()
    write_schema()
    valid_by_key = existing_valid()
    sources: list[dict[str, Any]] = []
    if RAW_SOURCES_JSON.exists():
        sources = json.loads(RAW_SOURCES_JSON.read_text(encoding="utf-8"))
    completed = {
        f"area:{s.get('geoname_id')}"
        for s in sources
        if s.get("status") == "ok" and str(s.get("geoname_id", "")).startswith("area-sweep:")
    }
    if args.areas:
        areas = [area.strip() for area in args.areas.split(",") if area.strip()]
    elif args.countries == "US":
        areas = list(US_STATE_AREAS)
    else:
        areas = []
    log(f"Area sweep loaded {len(areas)} areas; existing valid={len(valid_by_key)}; target={args.target}")

    incomplete_buffer: list[dict[str, Any]] = []
    for area_code in areas:
        if len(valid_by_key) >= args.target:
            break
        sweep_key = f"area:area-sweep:{area_code}"
        if sweep_key in completed and not args.revisit:
            continue
        country_code = area_code.split("-", 1)[0]
        country = TARGET_COUNTRIES.get(country_code, country_code)
        fake_city = City(
            geoname_id=f"area-sweep:{area_code}",
            name=area_code,
            country_code=country_code,
            country=country,
            lat=0,
            lon=0,
            population=0,
        )
        result = fetch_overpass_query(overpass_iso3166_2_email_query(area_code), args.pause)
        elements = result.get("elements", [])
        new_count = 0
        incomplete_count = 0
        for element in elements:
            prospect, incomplete = prospect_from_element(element, fake_city)
            if prospect:
                key = dedupe_key(prospect)
                if key not in valid_by_key:
                    valid_by_key[key] = prospect
                    new_count += 1
            elif incomplete:
                incomplete_buffer.append(incomplete)
                incomplete_count += 1
        source_record = {
            "status": "ok" if "errors" not in result else "error",
            "country_code": country_code,
            "country": country,
            "geoname_id": f"area-sweep:{area_code}",
            "city": area_code,
            "population": 0,
            "bbox": None,
            "elements": len(elements),
            "new_valid": new_count,
            "incomplete": incomplete_count,
            "errors": result.get("errors", []),
            "queried_at": datetime.now().isoformat(timespec="seconds"),
        }
        sources.append(source_record)
        prospects = sorted(valid_by_key.values(), key=lambda p: (p.country, p.city_hint, p.name))
        rewrite_valid(prospects)
        save_sources(sources)
        if incomplete_buffer:
            write_jsonl(INCOMPLETE_JSONL, incomplete_buffer)
            incomplete_buffer = []
        log(
            f"{area_code} area sweep: elements={len(elements)} new_valid={new_count} "
            f"total_valid={len(valid_by_key)}"
        )

    prospects = sorted(valid_by_key.values(), key=lambda p: (p.country, p.city_hint, p.name))
    write_cards(prospects, limit=args.card_limit)
    write_readme(prospects, sources, args.target)
    log(f"Done. valid={len(prospects)} cards={min(len(prospects), args.card_limit or len(prospects))}")
    return 0 if len(prospects) >= args.target else 2


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=int, default=5000)
    parser.add_argument("--max-cities", type=int, default=450)
    parser.add_argument("--pause", type=float, default=0.8)
    parser.add_argument("--card-limit", type=int, default=5000)
    parser.add_argument("--revisit", action="store_true")
    parser.add_argument("--countries", default="", help="Comma-separated ISO country codes to include.")
    parser.add_argument("--skip-countries", default="", help="Comma-separated ISO country codes to skip.")
    parser.add_argument("--country-sweep", action="store_true", help="Query each country once for dental entities with email.")
    parser.add_argument("--area-sweep", action="store_true", help="Query ISO3166-2 admin areas for dental entities with email.")
    parser.add_argument("--areas", default="", help="Comma-separated ISO3166-2 area codes for --area-sweep.")
    args = parser.parse_args(argv)
    if args.area_sweep:
        return collect_area_sweep(args)
    if args.country_sweep:
        return collect_country_sweep(args)
    return collect(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
