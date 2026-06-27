#!/usr/bin/env python3
"""Merge newly collected valid prospects into the Outline complete dataset.

Existing complete rows are preserved as-is, including historical duplicate-email
rows. New rows from prospects_valid.jsonl are appended only when their dedupe key
does not already exist in the complete dataset.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path("/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04")
DATA = ROOT / "output/dof-overseas-customer-prospects/2026-05-30/scale5000/data"
COMPLETE_JSONL = DATA / "prospects_augmented_contact_complete.jsonl"
COMPLETE_CSV = DATA / "prospects_augmented_contact_complete.csv"
VALID_JSONL = DATA / "prospects_valid.jsonl"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as file_obj:
        for line in file_obj:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def dedupe_key(row: dict[str, Any]) -> str:
    email = str(row.get("email") or "").strip().lower()
    if email:
        return email
    return f"{str(row.get('name') or '').strip().lower()}|{str(row.get('address') or '').strip().lower()}"


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as file_obj:
        for row in rows:
            file_obj.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    tmp.replace(path)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    preferred = [
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
    extra = sorted({key for row in rows for key in row if key not in preferred and key != "tags" and key != "evidence"})
    fieldnames = preferred + extra
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})
    tmp.replace(path)


def main() -> None:
    complete_rows = read_jsonl(COMPLETE_JSONL)
    valid_rows = read_jsonl(VALID_JSONL)
    existing_keys = {dedupe_key(row) for row in complete_rows if dedupe_key(row)}
    added: list[dict[str, Any]] = []
    for row in valid_rows:
        key = dedupe_key(row)
        if not key or key in existing_keys:
            continue
        complete_rows.append(row)
        existing_keys.add(key)
        added.append(row)
    write_jsonl(COMPLETE_JSONL, complete_rows)
    write_csv(COMPLETE_CSV, complete_rows)
    print(json.dumps({"completeRows": len(complete_rows), "validRows": len(valid_rows), "addedToComplete": len(added)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
