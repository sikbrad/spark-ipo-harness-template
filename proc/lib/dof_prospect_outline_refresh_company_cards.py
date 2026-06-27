#!/usr/bin/env python3
"""Refresh Outline company card bodies after tree or label changes."""

from __future__ import annotations

import argparse
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any

import requests

import dof_prospect_outline_publish as publish


DEFAULT_WORKERS = 8
RESULT_PATH = publish.PUBLISH_ROOT / "outline_company_refresh_result.json"


@dataclass(frozen=True)
class CompanyUpdate:
    key: str
    doc_id: str
    title: str
    text: str
    parent_document_id: str | None


_thread_local = threading.local()


def session_for(api_key: str) -> requests.Session:
    session = getattr(_thread_local, "session", None)
    if session is None:
        session = requests.Session()
        session.headers.update({"Authorization": f"Bearer {api_key}"})
        _thread_local.session = session
    return session


def update_document(api_key: str, update: CompanyUpdate) -> dict[str, Any]:
    body = {
        "id": update.doc_id,
        "title": update.title,
        "text": update.text,
        "publish": True,
        "fullWidth": True,
    }
    for attempt in range(1, 6):
        response = session_for(api_key).post(
            f"{publish.OUTLINE_BASE}/api/documents.update",
            json=body,
            timeout=publish.REQUEST_TIMEOUT,
        )
        if response.status_code < 400:
            return response.json()["data"]
        if response.status_code in {429, 500, 502, 503, 504} and attempt < 5:
            time.sleep(min(30, attempt * 2))
            continue
        raise RuntimeError(f"{update.title} failed {response.status_code}: {response.text[:500]}")
    raise RuntimeError(f"{update.title} failed after retries")


def resolve_company_key(cache: dict[str, Any], key: str) -> str:
    docs = cache.setdefault("docs", {})
    if key in docs:
        return key
    stable_id = key.removeprefix("company:")
    suffix = f":{stable_id}"
    matches = sorted(existing for existing in docs if existing.startswith("company:") and existing.endswith(suffix))
    if matches:
        docs[key] = docs.pop(matches[0])
    return key


def build_updates(limit: int | None = None) -> tuple[list[CompanyUpdate], dict[str, Any], list[str]]:
    rows = publish.enrich_rows(publish.read_jsonl(publish.COMPLETE_JSONL))
    tree = publish.build_hierarchy(rows)
    cache = publish.load_json(publish.DOC_CACHE, {"docs": {}})
    missing: list[str] = []
    updates: list[CompanyUpdate] = []

    for region, statuses in sorted(tree.items(), key=publish.region_sort_key):
        for status, countries in sorted(statuses.items(), key=publish.status_sort_key):
            for country, country_rows in sorted(countries.items(), key=publish.country_sort_key):
                country_doc = cache.get("docs", {}).get(publish.country_key(region, status, country), {})
                parent_document_id = country_doc.get("id")
                for order, row in enumerate(country_rows, start=1):
                    key = resolve_company_key(cache, publish.company_key(region, row["_country"], row))
                    cached = cache.get("docs", {}).get(key)
                    if not cached or not cached.get("id"):
                        missing.append(key)
                        continue
                    updates.append(
                        CompanyUpdate(
                            key=key,
                            doc_id=cached["id"],
                            title=publish.company_title(row, order),
                            text=publish.build_company_markdown(region, row["_country"], row, order),
                            parent_document_id=parent_document_id or cached.get("parent_document_id"),
                        )
                    )
                    if limit and len(updates) >= limit:
                        return updates, cache, missing
    return updates, cache, missing


def refresh_company_cards(workers: int = DEFAULT_WORKERS, limit: int | None = None) -> dict[str, Any]:
    api_key = publish.read_env_key("DOF_OUTLINE_KEY")
    updates, cache, missing = build_updates(limit)
    result = {
        "target_updates": len(updates),
        "updated": 0,
        "failed": [],
        "missing_cache": missing,
        "workers": workers,
    }
    if not updates:
        publish.save_json(RESULT_PATH, result)
        return result

    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_map = {executor.submit(update_document, api_key, update): update for update in updates}
        for future in as_completed(future_map):
            update = future_map[future]
            try:
                doc = future.result()
                cache.setdefault("docs", {})[update.key] = {
                    "id": doc["id"],
                    "url_id": doc.get("urlId", ""),
                    "title": doc.get("title", update.title),
                    "url": publish.doc_url(doc),
                    "parent_document_id": update.parent_document_id,
                }
                result["updated"] += 1
            except Exception as exc:  # noqa: BLE001 - capture per-document failures for retry/reporting.
                result["failed"].append({"key": update.key, "title": update.title, "error": str(exc)[:700]})
            if result["updated"] % 100 == 0 or result["updated"] == len(updates):
                print(
                    json.dumps(
                        {
                            "updated": result["updated"],
                            "target_updates": len(updates),
                            "failed": len(result["failed"]),
                            "latest": update.title,
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )

    publish.save_json(publish.DOC_CACHE, cache)
    publish.save_json(RESULT_PATH, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    print(json.dumps(refresh_company_cards(workers=args.workers, limit=args.limit), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
