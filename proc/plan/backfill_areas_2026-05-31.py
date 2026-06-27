"""Push 2026-05-31 Area assignments to Notion Task/Note pages.

Safety guard:
  Before PATCH, re-fetch each page and skip if Areas relation is non-empty.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from notion_api import NotionClient, normalize_id  # noqa: E402


BASE = Path(__file__).with_suffix("").parent
DEFAULT_MAPPING = BASE / "backfill_areas_2026-05-31.mapping.json"
DEFAULT_RESULT = BASE / "backfill_areas_2026-05-31.result.json"


def page_has_area(page: dict) -> bool:
    prop = page.get("properties", {}).get("Areas")
    if not prop:
        return False
    return bool(prop.get("relation"))


def patch_area(client: NotionClient, page_id: str, area_page_id: str) -> dict:
    return client.request(
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
            print(f"  skip already has Area: {item.get('title')}")
            results.append({**item, "status": "skipped_has_area"})
            continue
        if dry_run:
            print(f"  dry {kind}: {item.get('title')} -> {item.get('area_name')}")
            results.append({**item, "status": "dry_run"})
            continue
        patch_area(client, page_id, item["area_page_id"])
        print(f"  patched {kind}: {item.get('title')} -> {item.get('area_name')}")
        results.append({**item, "status": "patched"})
    return results


def main(argv: list[str]) -> int:
    dry_run = "--dry-run" in argv
    positional = [arg for arg in argv if not arg.startswith("--")]
    mapping_path = Path(positional[0]) if positional else DEFAULT_MAPPING
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))

    client = NotionClient.from_cache()
    results = {
        "tasks": process(client, mapping.get("tasks", []), "task", dry_run=dry_run),
        "notes": process(client, mapping.get("notes", []), "note", dry_run=dry_run),
    }
    DEFAULT_RESULT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    def count(rows: list[dict], status: str) -> int:
        return sum(1 for row in rows if row.get("status") == status)

    print(f"-> {DEFAULT_RESULT}")
    print(
        "tasks: "
        f"patched={count(results['tasks'], 'patched')} "
        f"skipped={count(results['tasks'], 'skipped_has_area')} "
        f"dry={count(results['tasks'], 'dry_run')}"
    )
    print(
        "notes: "
        f"patched={count(results['notes'], 'patched')} "
        f"skipped={count(results['notes'], 'skipped_has_area')} "
        f"dry={count(results['notes'], 'dry_run')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
