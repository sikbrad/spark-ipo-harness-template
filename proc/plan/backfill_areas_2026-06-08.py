"""Push Area assignments to Notion Task/Note pages with empty Areas.

Input  : backfill_areas_2026-06-08.mapping.json  (or path passed as argv[0])
Output : backfill_areas_2026-06-08.result.json

Safety guard (user-mandated):
  Before PATCH, re-fetch each page and skip if Areas relation is non-empty.
  This keeps re-runs idempotent and never touches pages that already have an Area.

Usage:
    python proc/plan/backfill_areas_2026-06-08.py [mapping.json] [--dry-run]
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from notion_api import NotionClient, normalize_id  # noqa: E402


def page_has_area(page: dict) -> bool:
    p = page.get("properties", {}).get("Areas")
    if not p:
        return False
    return bool(p.get("relation"))


def patch_area(c: NotionClient, page_id: str, area_page_id: str) -> dict:
    body = {
        "properties": {
            "Areas": {"relation": [{"id": normalize_id(area_page_id)}]}
        }
    }
    return c.request("PATCH", f"/pages/{normalize_id(page_id)}", json=body)


def process(c: NotionClient, items: list[dict], kind: str, *, dry_run: bool) -> list[dict]:
    out: list[dict] = []
    for it in items:
        pid = normalize_id(it["id"])
        page = c.pages_retrieve(pid)
        if page_has_area(page):
            print(f"  ↷ SKIP (already has Area): {it.get('title')}")
            out.append({**it, "status": "skipped_has_area"})
            continue
        if dry_run:
            print(f"  ◌ DRY  {kind}: {it.get('title')} → {it.get('area_name')}")
            out.append({**it, "status": "dry_run"})
            continue
        patch_area(c, pid, it["area_page_id"])
        print(f"  ✓ {kind}: {it.get('title')} → {it.get('area_name')}")
        out.append({**it, "status": "patched"})
    return out


def main(argv: list[str]) -> int:
    dry_run = "--dry-run" in argv
    positional = [a for a in argv if not a.startswith("--")]
    mapping_path = (
        Path(positional[0]) if positional
        else Path(__file__).with_suffix("").parent / "backfill_areas_2026-06-08.mapping.json"
    )
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))

    c = NotionClient.from_cache()
    results: dict = {"tasks": [], "notes": []}

    print(f"=== tasks ({'dry-run' if dry_run else 'apply'}) ===")
    results["tasks"] = process(c, mapping.get("tasks", []), "task", dry_run=dry_run)

    print(f"\n=== notes ({'dry-run' if dry_run else 'apply'}) ===")
    results["notes"] = process(c, mapping.get("notes", []), "note", dry_run=dry_run)

    out = Path(__file__).with_suffix(".result.json")
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    def count(rs, st):
        return sum(1 for r in rs if r["status"] == st)

    print(f"\n→ {out}")
    print(f"  tasks: patched={count(results['tasks'],'patched')}, "
          f"skipped={count(results['tasks'],'skipped_has_area')}, "
          f"dry={count(results['tasks'],'dry_run')}")
    print(f"  notes: patched={count(results['notes'],'patched')}, "
          f"skipped={count(results['notes'],'skipped_has_area')}, "
          f"dry={count(results['notes'],'dry_run')}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
