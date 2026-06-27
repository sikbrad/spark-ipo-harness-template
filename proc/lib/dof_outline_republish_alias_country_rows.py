#!/usr/bin/env python3
"""Republish rows in countries affected by alias/title normalization."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import dof_prospect_outline_publish as pub


RESULT_JSON = pub.PUBLISH_ROOT / "outline_alias_country_republish_result_2026-06-03.json"

AFFECTED_COUNTRIES = {
    "Brazil",
    "Burkina Faso",
    "Colombia",
    "Czechia",
    "Hong Kong",
    "Moldova",
    "North Macedonia",
    "Pakistan",
    "Palestine",
    "San Marino",
    "Saudi Arabia",
    "Somalia",
    "South Korea",
    "Spain",
    "Tunisia",
    "Turkey",
    "United States",
    "Hungary",
    "Italy",
    "Netherlands",
    "Nepal",
    "Sri Lanka",
    "Latvia",
    "Luxembourg",
    "Brunei",
    "Bahrain",
    "Slovenia",
}


def rename_if_needed(client: pub.OutlineClient, publisher: pub.OutlinePublisher, key: str, doc: pub.OutlineDoc, title: str) -> pub.OutlineDoc:
    if doc.title == title:
        return doc
    renamed = client.rename_document(doc.id, title)
    updated = pub.OutlineDoc(renamed["id"], renamed["urlId"], renamed["title"], pub.doc_url(renamed), doc.parent_document_id)
    publisher._remember(key, updated)
    return updated


def main() -> None:
    all_rows = pub.enrich_rows(pub.read_jsonl(pub.COMPLETE_JSONL))
    tree = pub.build_hierarchy(all_rows)
    client = pub.OutlineClient(pub.read_env_key("DOF_OUTLINE_KEY"))
    root = client.document_info(pub.TARGET_URL_ID)
    cache = pub.load_json(pub.DOC_CACHE, {"docs": {}})
    publisher = pub.OutlinePublisher(client, cache, dry_run=False)

    processed: list[dict[str, Any]] = []
    for region, statuses in sorted(tree.items(), key=pub.region_sort_key):
        region_doc = publisher.ensure_document(
            f"region:{region}",
            pub.region_label(region),
            root["id"],
            f"# {pub.region_label(region)}\n\nAlias country republish pass.\n",
            update_cached=False,
        )
        for status, countries in sorted(statuses.items(), key=pub.status_sort_key):
            status_doc = publisher.ensure_document(
                pub.status_key(region, status),
                status,
                region_doc.id,
                f"# {status}\n\nAlias country republish pass.\n",
                update_cached=False,
            )
            for country, country_rows in sorted(countries.items(), key=pub.country_sort_key):
                if country not in AFFECTED_COUNTRIES:
                    continue
                country_title = pub.country_title(country, len(country_rows))
                country_key = pub.country_key(region, status, country)
                country_doc = publisher.ensure_document(
                    country_key,
                    country_title,
                    status_doc.id,
                    f"# {pub.country_label(country)}\n\nAlias country republish pass.\n",
                    update_cached=False,
                )
                country_doc = rename_if_needed(client, publisher, country_key, country_doc, country_title)
                for row in country_rows:
                    number = country_rows.index(row) + 1
                    title = pub.company_title(row, number)
                    key = publisher.resolve_company_key(pub.company_key(region, row["_country"], row))
                    body = pub.build_company_markdown(region, row["_country"], row, number)
                    company_doc = publisher.ensure_company_document(key, title, country_doc.id, body)
                    updated = client.update_document(company_doc.id, title, body)
                    company_doc = pub.OutlineDoc(updated["id"], updated["urlId"], updated["title"], pub.doc_url(updated), country_doc.id)
                    publisher._remember(key, company_doc)
                    processed.append({"title": title, "country": country, "status": status, "region": region, "url": company_doc.url})
                    if len(processed) % 50 == 0:
                        print(json.dumps({"processed": len(processed), "latest": title, "url": company_doc.url}, ensure_ascii=False), flush=True)
                    time.sleep(pub.PAUSE_SECONDS)

    result = {"processed": len(processed), "documents": processed[:20], "resultJson": str(RESULT_JSON)}
    pub.save_json(RESULT_JSON, result)
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
