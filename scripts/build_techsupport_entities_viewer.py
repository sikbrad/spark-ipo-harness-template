#!/usr/bin/env python3
"""Generate a static searchable HTML viewer for techsupport OneNote entities."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
ENTITIES_DIR = ROOT / "data" / "techsupport" / "onenote" / "entities"
VIEWER_DIR = ENTITIES_DIR / "viewer"
RAW_REVIEW_PAGES_DIR = ROOT / "data" / "techsupport" / "onenote" / "raw_review" / "pages"


def rel_from_viewer(path: str | None) -> str | None:
    if not path:
        return None
    target = ROOT / path
    return quote(target.relative_to(VIEWER_DIR, walk_up=True).as_posix(), safe="/")


def rel_path_from_viewer(path: Path) -> str:
    return quote(path.relative_to(VIEWER_DIR, walk_up=True).as_posix(), safe="/")


def compact_assets(row: dict) -> dict:
    source = row.get("source") or {}
    markdown = source.get("markdown")
    md_dir = (ROOT / markdown).parent if markdown else None
    assets = row.get("assets") or {}

    def expand(items: list[str], require_nonempty: bool = False) -> list[dict]:
        expanded = []
        for item in items:
            target = (md_dir / item) if md_dir else (ROOT / item)
            exists = target.exists() and (not require_nonempty or target.stat().st_size > 0)
            expanded.append({
                "name": Path(item).name,
                "href": rel_path_from_viewer(target),
                "exists": exists,
            })
        return expanded

    return {
        "images": expand(assets.get("images") or [], require_nonempty=True),
        "attachments": expand(assets.get("attachments") or []),
        "local_link_count": assets.get("local_link_count") or 0,
        "remote_link_count": assets.get("remote_link_count") or 0,
    }


def compact_entity(row: dict) -> dict:
    source = row.get("source") or {}
    raw_review_html = None
    raw_page_dir = source.get("raw_page_dir")
    if raw_page_dir:
        candidate = RAW_REVIEW_PAGES_DIR / f"{Path(raw_page_dir).name}.html"
        if candidate.exists():
            raw_review_html = rel_path_from_viewer(candidate)
    return {
        "id": row.get("id"),
        "title": row.get("title"),
        "product_area": row.get("product_area"),
        "support_type": row.get("support_type"),
        "section_path": row.get("section_path"),
        "tags": row.get("tags") or [],
        "summary": row.get("summary") or "",
        "steps_or_notes": row.get("steps_or_notes") or [],
        "full_text": row.get("full_text") or "",
        "source": {
            "markdown": rel_from_viewer(source.get("markdown")),
            "review_html": rel_from_viewer(source.get("review_html")),
            "raw_review_html": raw_review_html,
            "raw_page_dir": rel_from_viewer(source.get("raw_page_dir")),
            "onenote_url": source.get("onenote_url"),
            "created": source.get("created"),
            "modified": source.get("modified"),
        },
        "assets": compact_assets(row),
    }


def compact_excluded(row: dict) -> dict:
    return {
        "title": row.get("title") or "(untitled)",
        "section_path": row.get("section_path") or "",
        "source_markdown": rel_from_viewer(row.get("source_markdown")),
        "exclude_reason": row.get("exclude_reason"),
        "details": row.get("details") or [],
    }


def main() -> int:
    VIEWER_DIR.mkdir(parents=True, exist_ok=True)
    entities = json.loads((ENTITIES_DIR / "entities.json").read_text(encoding="utf-8"))
    excluded = json.loads((ENTITIES_DIR / "excluded.json").read_text(encoding="utf-8"))
    summary = json.loads((ENTITIES_DIR / "summary.json").read_text(encoding="utf-8"))
    payload = {
        "summary": summary,
        "entities": [compact_entity(row) for row in entities],
        "excluded": [compact_excluded(row) for row in excluded],
    }
    js = "window.TECHSUPPORT_ENTITIES_DATA = "
    js += json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    js += ";\n"
    (VIEWER_DIR / "data.js").write_text(js, encoding="utf-8")
    print(json.dumps({"viewer": str(VIEWER_DIR / "index.html"), "entities": len(entities), "excluded": len(excluded)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
