#!/usr/bin/env python3
"""Publish only newly merged prospect rows to Outline.

This avoids reprocessing the full 18k-document tree. Parent region/status/country
documents are reused from the existing Outline cache whenever possible; only new
company cards are created or updated under the correct country document.
"""

from __future__ import annotations

import json
import time
import argparse
from pathlib import Path
from typing import Any

import dof_prospect_outline_publish as pub


DATA = pub.DATA
DEFAULT_BACKUP_JSONL = DATA / "backups/prospects_augmented_contact_complete.before_3000_20260603_014944.jsonl"
DEFAULT_RESULT_JSON = pub.PUBLISH_ROOT / "outline_incremental_new_publish_result_round8.json"
ROOT_DOC_ID = "89c2b595-26e3-43fd-b4d2-23d514515e2d"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
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


def publish_incremental(
    baseline_jsonl: Path = DEFAULT_BACKUP_JSONL,
    result_json: Path = DEFAULT_RESULT_JSON,
) -> dict[str, Any]:
    all_rows = pub.enrich_rows(pub.read_jsonl(pub.COMPLETE_JSONL))
    before_keys = {dedupe_key(row) for row in read_jsonl(baseline_jsonl) if dedupe_key(row)}
    new_keys = {dedupe_key(row) for row in all_rows if dedupe_key(row) and dedupe_key(row) not in before_keys}
    tree = pub.build_hierarchy(all_rows)

    client = pub.OutlineClient(pub.read_env_key("DOF_OUTLINE_KEY"))
    root = {"id": ROOT_DOC_ID}
    cache = pub.load_json(pub.DOC_CACHE, {"docs": {}})
    publisher = pub.OutlinePublisher(client, cache, dry_run=False)

    created_or_updated = []
    processed = 0
    for region, statuses in sorted(tree.items(), key=pub.region_sort_key):
        region_doc = publisher.ensure_document(
            f"region:{region}",
            pub.region_label(region),
            root["id"],
            f"# {pub.region_label(region)}\n\n증분 발행 중입니다.\n",
            update_cached=False,
        )
        for status, countries in sorted(statuses.items(), key=pub.status_sort_key):
            status_doc = publisher.ensure_document(
                pub.status_key(region, status),
                status,
                region_doc.id,
                f"# {status}\n\n증분 발행 중입니다.\n",
                update_cached=False,
            )
            for country, country_rows in sorted(countries.items(), key=pub.country_sort_key):
                new_country_rows = [row for row in country_rows if dedupe_key(row) in new_keys]
                if not new_country_rows:
                    continue
                country_doc = publisher.ensure_document(
                    pub.country_key(region, status, country),
                    pub.country_title(country, len(country_rows)),
                    status_doc.id,
                    f"# {pub.country_label(country)}\n\n증분 발행 중입니다.\n",
                    update_cached=False,
                )
                for row in new_country_rows:
                    number = country_rows.index(row) + 1
                    title = pub.company_title(row, number)
                    key = publisher.resolve_company_key(pub.company_key(region, row["_country"], row))
                    body = pub.build_company_markdown(region, row["_country"], row, number)
                    company_doc = publisher.ensure_company_document(key, title, country_doc.id, body)
                    created_or_updated.append({"title": title, "url": company_doc.url, "country": country, "status": status, "region": region})
                    processed += 1
                    if processed % 25 == 0:
                        print(json.dumps({"processed_new_company_docs": processed, "latest": title, "url": company_doc.url}, ensure_ascii=False), flush=True)
                    if processed % 100 == 0:
                        pub.save_json(
                            result_json,
                            {
                                "completeRows": len(all_rows),
                                "newRows": len(new_keys),
                                "processedNewCompanyDocs": processed,
                                "documents": created_or_updated,
                                "cache": str(pub.DOC_CACHE),
                                "baselineJsonl": str(baseline_jsonl),
                                "checkpoint": True,
                            },
                        )
                    time.sleep(pub.PAUSE_SECONDS)

    result = {
        "completeRows": len(all_rows),
        "newRows": len(new_keys),
        "processedNewCompanyDocs": processed,
        "documents": created_or_updated,
        "cache": str(pub.DOC_CACHE),
        "baselineJsonl": str(baseline_jsonl),
    }
    pub.save_json(result_json, result)
    print(json.dumps(result | {"documents": created_or_updated[:5]}, ensure_ascii=False, indent=2), flush=True)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-jsonl", type=Path, default=DEFAULT_BACKUP_JSONL)
    parser.add_argument("--result-json", type=Path, default=DEFAULT_RESULT_JSON)
    args = parser.parse_args()
    publish_incremental(args.baseline_jsonl, args.result_json)
