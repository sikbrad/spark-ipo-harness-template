#!/usr/bin/env python3
"""Normalize round 9 partial prospect country aliases and obvious PDF name noise."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path("/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04")
DATA = ROOT / "output/dof-overseas-customer-prospects/2026-05-30/scale5000/data"
COMPLETE_JSONL = DATA / "prospects_augmented_contact_complete.jsonl"
COMPLETE_CSV = DATA / "prospects_augmented_contact_complete.csv"
PROMOTIONS_JSONL = DATA / "partial_distributor_promotions_round9.jsonl"

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

COUNTRY_ALIASES = {
    "Brasil": "Brazil",
    "China Hong Kong": "Hong Kong",
    "Columbia": "Colombia",
    "Czech Republic": "Czechia",
    "Kingdom of Saudi Arabia (KSA)": "Saudi Arabia",
    "Korea": "South Korea",
    "Macedonia": "North Macedonia",
    "Republic of Korea": "South Korea",
    "Korea, Republic of": "South Korea",
    "Magyarország": "Hungary",
    "Magyarorszag": "Hungary",
    "Moldavia": "Moldova",
    "SPAIN (Andalusia only)": "Spain",
    "The Netherlands": "Netherlands",
    "Italy / China": "Italy",
    "Tunesia": "Tunisia",
    "Turkey Izmir": "Turkey",
    "USA East Coast": "United States",
    "USA West Coast": "United States",
}


def clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n", encoding="utf-8")
    tmp.replace(path)


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


def normalize_country(country: str) -> str:
    value = clean(country)
    if value.startswith("Pakistan "):
        return "Pakistan"
    return COUNTRY_ALIASES.get(value, value)


def legal_suffix_name(text: str) -> str:
    value = clean(text)
    match = re.match(r"(.+?\b(?:S\.?R\.?L\.?|SRL|S\.?P\.?A\.?|SPA|GmbH(?:\s*&\s*Co\.?\s*KG)?|AG|Ltd\.?|Inc\.?|LLC|Co\.?,?\s*Ltd\.?))\b", value, re.I)
    if match:
        return clean(match.group(1).rstrip(" ,.-"))
    return value


def normalize_name_and_website(row: dict[str, Any]) -> tuple[str, str]:
    name = clean(row.get("name"))
    website = clean(row.get("website"))
    if name.lower().startswith("any need: from traditional equipment"):
        return "EMERITALIA", website or "https://www.emeritalia.it"
    if name.lower().startswith("website:"):
        without_prefix = clean(re.sub(r"^Website:\s*", "", name, flags=re.I))
        parts = without_prefix.split(" ", 1)
        if parts and "." in parts[0]:
            website = website or ("https://" + parts[0].removeprefix("http://").removeprefix("https://"))
            name = clean(parts[1] if len(parts) > 1 else parts[0])
        name = legal_suffix_name(name)
    if " is a leading " in name.lower():
        name = clean(re.split(r"\bis a leading\b", name, maxsplit=1, flags=re.I)[0].rstrip(" ,.-"))
    if ", founded in " in name.lower():
        name = clean(re.split(r",\s*founded in\b", name, maxsplit=1, flags=re.I)[0].rstrip(" ,.-"))
    if " Hersteller von " in name:
        name = clean(name.split(" Hersteller von ", 1)[0])
    return name, website


def cleanup_row(row: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    changes: list[str] = []
    country = normalize_country(str(row.get("country") or ""))
    if country != row.get("country"):
        changes.append(f"country:{row.get('country')}->{country}")
        row["country"] = country
    if row.get("source_type") == "ICE/ITA AEEDC 2026 official Italian Pavilion PDF (partial contact)":
        original_name = clean(row.get("name"))
        name, website = normalize_name_and_website(row)
        if name and name != row.get("name"):
            changes.append(f"name:{row.get('name')}->{name}")
            row["name"] = name
            if original_name.lower().startswith("any need: from traditional equipment"):
                row["evidence"] = [
                    "ICE/ITA AEEDC 2026 PDF continuation line matched to the EMERITALIA exhibitor block",
                    "Public source URL: https://www.ice.it/it/sites/default/files/inline-files/AEEDC%202026_compressed.pdf",
                    "Correction note: original scraped line was product-description text, not a company name.",
                ]
                tags = row.get("tags")
                if isinstance(tags, dict):
                    tags["cleanup_note"] = "PDF continuation line normalized to EMERITALIA; full-contact EMERITALIA entry also exists in the complete dataset."
                    tags["site_business_summary"] = "EMERITALIA는 치과 및 귀금속 기공소용 집진 장비를 생산하는 이탈리아 업체로 ICE/ITA AEEDC 2026 Italian Pavilion PDF에 등재됨."
        if website and website != row.get("website"):
            changes.append(f"website:{row.get('website')}->{website}")
            row["website"] = website
            tags = row.get("tags")
            if isinstance(tags, dict):
                tags["contact_completeness"] = "website_only" if not row.get("email") and not row.get("phone") and not row.get("address") else tags.get("contact_completeness", "")
    return row, changes


def apply_to_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    changed: list[dict[str, Any]] = []
    for row in rows:
        before = json.dumps(row, ensure_ascii=False, sort_keys=True)
        row, changes = cleanup_row(row)
        if changes and before != json.dumps(row, ensure_ascii=False, sort_keys=True):
            changed.append({"name": row.get("name"), "country": row.get("country"), "changes": changes})
    return rows, changed


def main() -> None:
    complete_rows, complete_changed = apply_to_rows(read_jsonl(COMPLETE_JSONL))
    promotion_rows, promotion_changed = apply_to_rows(read_jsonl(PROMOTIONS_JSONL))
    write_jsonl(COMPLETE_JSONL, complete_rows)
    write_jsonl(PROMOTIONS_JSONL, promotion_rows)
    write_csv(COMPLETE_CSV, complete_rows)
    print(
        json.dumps(
            {
                "completeChanged": len(complete_changed),
                "promotionChanged": len(promotion_changed),
                "promotionSamples": promotion_changed[:20],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
