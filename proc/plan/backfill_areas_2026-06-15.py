"""Push Area assignments to Notion pages with empty Areas.

Safety guard:
  Before PATCH, re-fetch each page and skip if Areas relation is non-empty.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from notion_api import NotionClient, normalize_id  # noqa: E402


def page_has_area(page: dict) -> bool:
    prop = page.get("properties", {}).get("Areas")
    return bool(prop and prop.get("relation"))


def patch_area(client: NotionClient, page_id: str, area_page_id: str) -> None:
    client.request(
        "PATCH",
        f"/pages/{normalize_id(page_id)}",
        json={
            "properties": {
                "Areas": {"relation": [{"id": normalize_id(area_page_id)}]}
            }
        },
    )


def process(client: NotionClient, items: list[dict], kind: str, *, dry_run: bool) -> list[dict]:
    results: list[dict] = []
    for item in items:
        page_id = normalize_id(item["id"])
        page = client.pages_retrieve(page_id)
        if page_has_area(page):
            print(f"SKIP already has Area: {kind} {item.get('title')}")
            results.append({**item, "status": "skipped_has_area"})
            continue
        if dry_run:
            print(f"DRY {kind}: {item.get('title')} -> {item.get('area_name')}")
            results.append({**item, "status": "dry_run"})
            continue
        patch_area(client, page_id, item["area_page_id"])
        print(f"PATCH {kind}: {item.get('title')} -> {item.get('area_name')}")
        results.append({**item, "status": "patched"})
    return results


def main(argv: list[str]) -> int:
    dry_run = "--dry-run" in argv
    mapping_path = Path(__file__).with_suffix(".mapping.json")
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    client = NotionClient.from_cache()
    results = {
        "tasks": process(client, mapping.get("tasks", []), "task", dry_run=dry_run),
        "notes": process(client, mapping.get("notes", []), "note", dry_run=dry_run),
    }
    out_path = Path(__file__).with_suffix(".result.json")
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
