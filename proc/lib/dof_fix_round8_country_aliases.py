#!/usr/bin/env python3
"""Fix country labels introduced during round 8 distributor expansion."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path("/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04")
DATA = ROOT / "output/dof-overseas-customer-prospects/2026-05-30/scale5000/data"
JSONL_FILES = [DATA / "prospects_augmented_contact_complete.jsonl", DATA / "prospects_valid.jsonl"]
COMPLETE_CSV = DATA / "prospects_augmented_contact_complete.csv"
ALIASES = {
    "USA East Coast": "United States",
    "USA West Coast": "United States",
    "China Hong Kong": "Hong Kong",
    "Columbia": "Colombia",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
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


def fixed_country(row: dict[str, Any]) -> str:
    country = str(row.get("country") or "").strip()
    if country in ALIASES:
        return ALIASES[country]
    if row.get("source_type") == "Advanced Dental Designs official international dealer page":
        name = str(row.get("name") or "")
        match = re.match(r"AD2\s+(.+)", name)
        if match:
            candidate = match.group(1).strip()
            return ALIASES.get(candidate, candidate)
    return country


def write_complete_csv(rows: list[dict[str, Any]]) -> None:
    preferred = ["name", "country", "city_hint", "segment", "email", "phone", "address", "website", "source_url", "selection_reason", "dof_fit"]
    extra = sorted({key for row in rows for key in row if key not in preferred and key not in {"tags", "evidence"}})
    fieldnames = preferred + extra
    tmp = COMPLETE_CSV.with_suffix(COMPLETE_CSV.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})
    tmp.replace(COMPLETE_CSV)


def main() -> None:
    summary = {}
    complete_rows: list[dict[str, Any]] = []
    for path in JSONL_FILES:
        rows = read_jsonl(path)
        changed = 0
        for row in rows:
            country = fixed_country(row)
            if country != row.get("country"):
                row["country"] = country
                changed += 1
        write_jsonl(path, rows)
        summary[str(path)] = {"rows": len(rows), "changed": changed}
        if path.name == "prospects_augmented_contact_complete.jsonl":
            complete_rows = rows
    write_complete_csv(complete_rows)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
