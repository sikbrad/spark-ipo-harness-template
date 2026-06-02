#!/usr/bin/env python3
"""Create map points for the DOF customer prospect HTML report.

Public research rows already have OSM object ids, so their coordinates are
recovered from Overpass by id. Portal rows do not have OSM ids; for those, the
script uses city names found in the address and falls back to a country-level
anchor when a city cannot be found.
"""

from __future__ import annotations

import json
import math
import re
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests


ROOT = Path("/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04")
BASE = ROOT / "output/dof-overseas-customer-prospects/2026-05-30/scale5000"
DATA = BASE / "data"
CACHE = BASE / "cache"
GEONAMES_TXT = CACHE / "cities15000.txt"

COMPLETE_JSONL = DATA / "prospects_augmented_contact_complete.jsonl"
PORTAL_INCOMPLETE_JSONL = DATA / "portal_foreign_additions_contact_incomplete.jsonl"
MAP_POINTS_JSON = DATA / "prospect_map_points.json"
OSM_COORD_CACHE = DATA / "osm_coordinate_cache.json"

USER_AGENT = "DOF prospect map coordinate builder (local report; public OSM/GeoNames data)"
OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

COUNTRY_NAMES: dict[str, str] = {
    "AE": "United Arab Emirates",
    "AL": "Albania",
    "AM": "Armenia",
    "AR": "Argentina",
    "AT": "Austria",
    "AU": "Australia",
    "AZ": "Azerbaijan",
    "BA": "Bosnia and Herzegovina",
    "BD": "Bangladesh",
    "BE": "Belgium",
    "BH": "Bahrain",
    "BG": "Bulgaria",
    "BO": "Bolivia",
    "BR": "Brazil",
    "BW": "Botswana",
    "BY": "Belarus",
    "CA": "Canada",
    "CH": "Switzerland",
    "CL": "Chile",
    "CN": "China",
    "CO": "Colombia",
    "CR": "Costa Rica",
    "CY": "Cyprus",
    "CZ": "Czechia",
    "DE": "Germany",
    "DK": "Denmark",
    "DO": "Dominican Republic",
    "DZ": "Algeria",
    "EC": "Ecuador",
    "EE": "Estonia",
    "EG": "Egypt",
    "ES": "Spain",
    "ET": "Ethiopia",
    "FI": "Finland",
    "FR": "France",
    "GB": "United Kingdom",
    "GE": "Georgia",
    "GR": "Greece",
    "GT": "Guatemala",
    "HK": "Hong Kong",
    "HN": "Honduras",
    "HR": "Croatia",
    "HU": "Hungary",
    "ID": "Indonesia",
    "IE": "Ireland",
    "IL": "Israel",
    "IN": "India",
    "IQ": "Iraq",
    "IR": "Iran",
    "IS": "Iceland",
    "IT": "Italy",
    "JO": "Jordan",
    "JP": "Japan",
    "KE": "Kenya",
    "KG": "Kyrgyzstan",
    "KH": "Cambodia",
    "KR": "South Korea",
    "KW": "Kuwait",
    "KZ": "Kazakhstan",
    "LB": "Lebanon",
    "LI": "Liechtenstein",
    "LT": "Lithuania",
    "LY": "Libya",
    "MA": "Morocco",
    "MC": "Monaco",
    "MD": "Moldova",
    "MK": "North Macedonia",
    "MM": "Myanmar",
    "MT": "Malta",
    "MU": "Mauritius",
    "MX": "Mexico",
    "MY": "Malaysia",
    "NI": "Nicaragua",
    "NL": "Netherlands",
    "NO": "Norway",
    "NZ": "New Zealand",
    "OM": "Oman",
    "PA": "Panama",
    "PE": "Peru",
    "PH": "Philippines",
    "PK": "Pakistan",
    "PL": "Poland",
    "PT": "Portugal",
    "PY": "Paraguay",
    "QA": "Qatar",
    "RO": "Romania",
    "RS": "Serbia",
    "RU": "Russia",
    "SA": "Saudi Arabia",
    "SE": "Sweden",
    "SG": "Singapore",
    "SI": "Slovenia",
    "SK": "Slovakia",
    "SV": "El Salvador",
    "SY": "Syria",
    "TJ": "Tajikistan",
    "TH": "Thailand",
    "TN": "Tunisia",
    "TR": "Turkey",
    "TW": "Taiwan",
    "UA": "Ukraine",
    "US": "United States",
    "UY": "Uruguay",
    "UZ": "Uzbekistan",
    "VE": "Venezuela",
    "VG": "British Virgin Islands",
    "VN": "Vietnam",
    "XK": "Kosovo",
    "YE": "Yemen",
    "ZA": "South Africa",
}

COUNTRY_CODES_BY_NAME: dict[str, str] = {name.upper(): code for code, name in COUNTRY_NAMES.items()}
COUNTRY_CODES_BY_NAME.update(
    {
        "TÜRKIYE": "TR",
        "TÜRKİYE": "TR",
        "TURKIYE": "TR",
        "TURKEY": "TR",
    }
)

MANUAL_COUNTRY_ANCHORS: dict[str, dict[str, Any]] = {
    "LI": {
        "lat": 47.1410,
        "lon": 9.5209,
        "coordinate_source": "manual_country_anchor",
        "coordinate_precision": "country",
    },
    "VG": {
        "lat": 18.4207,
        "lon": -64.64,
        "coordinate_source": "manual_country_anchor",
        "coordinate_precision": "country",
    },
}


@dataclass
class City:
    name: str
    country_code: str
    lat: float
    lon: float
    population: int
    aliases: list[str]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def norm(text: Any) -> str:
    return re.sub(r"[^a-z0-9가-힣]+", " ", str(text or "").lower()).strip()


def load_json(path: Path, default: Any) -> Any:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def overpass_id_query(ids_by_type: dict[str, list[int]]) -> str:
    parts: list[str] = []
    for osm_type in ("node", "way", "relation"):
        ids = ids_by_type.get(osm_type) or []
        if ids:
            parts.append(f"{osm_type}(id:{','.join(str(i) for i in ids)});")
    body = "\n  ".join(parts)
    return f"""[out:json][timeout:90];
(
  {body}
);
out center;"""


def fetch_overpass(query: str) -> dict[str, Any]:
    errors: list[str] = []
    for attempt in range(1, 5):
        endpoint = OVERPASS_ENDPOINTS[(attempt - 1) % len(OVERPASS_ENDPOINTS)]
        try:
            response = requests.get(
                endpoint,
                params={"data": query},
                headers={"User-Agent": USER_AGENT},
                timeout=120,
            )
            if response.status_code in {429, 502, 503, 504}:
                errors.append(f"{endpoint} HTTP {response.status_code}")
                time.sleep(3 * attempt)
                continue
            response.raise_for_status()
            return response.json()
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{endpoint} {type(exc).__name__}: {exc}")
            time.sleep(3 * attempt)
    return {"elements": [], "errors": errors}


def recover_osm_coordinates(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    cache: dict[str, dict[str, Any]] = load_json(OSM_COORD_CACHE, {})
    wanted: dict[str, set[int]] = defaultdict(set)
    for row in rows:
        osm_type = row.get("osm_type")
        osm_id = row.get("osm_id")
        if osm_type in {"node", "way", "relation"} and osm_id:
            key = f"{osm_type}/{int(osm_id)}"
            if key not in cache:
                wanted[osm_type].add(int(osm_id))

    pending = sum(len(v) for v in wanted.values())
    if not pending:
        return cache

    batch_size = 300
    batches: list[dict[str, list[int]]] = []
    for osm_type, ids in wanted.items():
        sorted_ids = sorted(ids)
        for idx in range(0, len(sorted_ids), batch_size):
            batches.append({osm_type: sorted_ids[idx : idx + batch_size]})

    for index, batch in enumerate(batches, 1):
        data = fetch_overpass(overpass_id_query(batch))
        for element in data.get("elements", []):
            osm_type = element.get("type")
            osm_id = element.get("id")
            if not osm_type or not osm_id:
                continue
            lat = element.get("lat")
            lon = element.get("lon")
            precision = "exact"
            if lat is None or lon is None:
                center = element.get("center") or {}
                lat = center.get("lat")
                lon = center.get("lon")
                precision = "center"
            if lat is None or lon is None:
                continue
            cache[f"{osm_type}/{int(osm_id)}"] = {
                "lat": float(lat),
                "lon": float(lon),
                "coordinate_source": "osm_overpass",
                "coordinate_precision": precision,
            }
        write_json(OSM_COORD_CACHE, cache)
        time.sleep(0.25)
        print(f"OSM coordinate batch {index}/{len(batches)} cache={len(cache)}", flush=True)
    return cache


def load_cities() -> tuple[dict[str, list[City]], dict[str, dict[str, Any]]]:
    by_country: dict[str, list[City]] = defaultdict(list)
    country_anchor_acc: dict[str, dict[str, float]] = defaultdict(lambda: {"lat": 0.0, "lon": 0.0, "weight": 0.0})
    with GEONAMES_TXT.open("r", encoding="utf-8") as f:
        for line in f:
            row = line.rstrip("\n").split("\t")
            country_code = row[8]
            if country_code not in COUNTRY_NAMES:
                continue
            population = int(row[14] or 0)
            if population < 15000:
                continue
            name = row[1]
            lat = float(row[4])
            lon = float(row[5])
            aliases = [name]
            for alias in row[3].split(","):
                alias = alias.strip()
                if 3 <= len(alias) <= 40:
                    aliases.append(alias)
            city = City(name=name, country_code=country_code, lat=lat, lon=lon, population=population, aliases=aliases[:80])
            by_country[country_code].append(city)
            weight = max(math.sqrt(population), 1.0)
            acc = country_anchor_acc[country_code]
            acc["lat"] += lat * weight
            acc["lon"] += lon * weight
            acc["weight"] += weight
    anchors: dict[str, dict[str, Any]] = {}
    for country, acc in country_anchor_acc.items():
        if acc["weight"]:
            anchors[country] = {
                "lat": acc["lat"] / acc["weight"],
                "lon": acc["lon"] / acc["weight"],
                "coordinate_source": "geonames_country_anchor",
                "coordinate_precision": "country",
            }
    anchors.update(MANUAL_COUNTRY_ANCHORS)
    for cities in by_country.values():
        cities.sort(key=lambda c: (-c.population, -len(c.name)))
    return by_country, anchors


def portal_coordinate(row: dict[str, Any], cities_by_country: dict[str, list[City]], anchors: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    country_value = str(row.get("country") or "").upper()
    country = country_value if country_value in COUNTRY_NAMES else COUNTRY_CODES_BY_NAME.get(country_value, "")
    address_norm = f" {norm(row.get('address'))} "
    if not country:
        return None
    best: tuple[int, int, City, str] | None = None
    for city in cities_by_country.get(country, [])[:3000]:
        for alias in city.aliases:
            alias_norm = norm(alias)
            if len(alias_norm) < 3:
                continue
            if f" {alias_norm} " in address_norm:
                score = (len(alias_norm), city.population)
                if best is None or score > (best[0], best[1]):
                    best = (score[0], score[1], city, alias)
                break
    if best:
        city = best[2]
        return {
            "lat": city.lat,
            "lon": city.lon,
            "coordinate_source": "geonames_city_from_address",
            "coordinate_precision": "city",
            "coordinate_label": city.name,
        }
    anchor = anchors.get(country)
    if anchor:
        return dict(anchor)
    return None


def map_point(row: dict[str, Any], idx: int, complete: bool, coord: dict[str, Any]) -> dict[str, Any]:
    is_portal = row.get("source_type") == "DOF portal Company"
    return {
        "id": idx,
        "name": row.get("name", ""),
        "country": row.get("country", ""),
        "segment": row.get("segment", ""),
        "source": "DOF Portal" if is_portal else "Public research",
        "email": row.get("email", ""),
        "phone": row.get("phone", ""),
        "address": row.get("address", ""),
        "source_url": row.get("source_url", ""),
        "portal_company_id": row.get("portal_company_id", ""),
        "orders": row.get("portal_orders_count", ""),
        "complete": complete,
        "lat": coord["lat"],
        "lon": coord["lon"],
        "coordinate_source": coord.get("coordinate_source", ""),
        "coordinate_precision": coord.get("coordinate_precision", ""),
        "coordinate_label": coord.get("coordinate_label", ""),
    }


def main() -> int:
    complete_rows = read_jsonl(COMPLETE_JSONL)
    incomplete_rows = read_jsonl(PORTAL_INCOMPLETE_JSONL)
    all_rows = complete_rows + incomplete_rows
    osm_cache = recover_osm_coordinates(complete_rows)
    cities_by_country, anchors = load_cities()

    points: list[dict[str, Any]] = []
    missing = 0
    precision_counts: Counter[str] = Counter()
    for idx, row in enumerate(all_rows, 1):
        complete = idx <= len(complete_rows)
        coord: dict[str, Any] | None = None
        osm_type = row.get("osm_type")
        osm_id = row.get("osm_id")
        if osm_type and osm_id:
            coord = osm_cache.get(f"{osm_type}/{int(osm_id)}")
        else:
            coord = portal_coordinate(row, cities_by_country, anchors)
        if coord:
            points.append(map_point(row, idx, complete, coord))
            precision_counts[str(coord.get("coordinate_precision") or "unknown")] += 1
        else:
            missing += 1

    write_json(MAP_POINTS_JSON, points)
    result = {
        "mapPoints": len(points),
        "inputRows": len(all_rows),
        "missingCoordinates": missing,
        "precisionCounts": dict(precision_counts),
        "output": str(MAP_POINTS_JSON),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
