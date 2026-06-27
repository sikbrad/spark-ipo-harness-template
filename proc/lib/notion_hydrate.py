"""Stage B — hydrate raw dump into per-page self-contained JSON.

Reads:
    <dump>/pages/<id>.json            page metadata
    <dump>/blocks/<id>.json           direct children of that page (or block)
    <dump>/data_sources/<id>.json     data source schemas
    <dump>/db_rows/<id>.json          rows of a data_source

Writes:
    <hydrated>/pages/<id>.json        page meta + nested blocks tree
    <hydrated>/data_sources/<id>.json data source schema + flat row list (each row is a hydrated page)
    <hydrated>/_index.json            run summary

Block tree expansion rule:
    - For every block with `has_children = true`, look up `<dump>/blocks/<block_id>.json`
      and inline the result under `block.children`.
    - `child_page` and `child_database` blocks keep just an id reference; the actual
      page/db is hydrated as a separate top-level file.

This stage is offline (no API calls) — depends only on raw dump on disk.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


def _load(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _norm(uid: str) -> str:
    s = uid.replace("-", "")
    if len(s) != 32:
        return uid
    return f"{s[0:8]}-{s[8:12]}-{s[12:16]}-{s[16:20]}-{s[20:32]}"


def _title_of_page(page: dict) -> str:
    for v in (page.get("properties") or {}).values():
        if v.get("type") == "title":
            parts = v.get("title") or []
            return "".join(p.get("plain_text", "") for p in parts) or "(untitled)"
    return "(untitled)"


def _title_of_ds(ds: dict) -> str:
    parts = ds.get("title") or []
    return "".join(p.get("plain_text", "") for p in parts) or "(untitled ds)"


class Hydrator:
    def __init__(self, dump_dir: Path, out_dir: Path, *, verbose: bool = True):
        self.dump = dump_dir
        self.out = out_dir
        self.verbose = verbose
        self.counts = {"pages": 0, "data_sources": 0, "rows_inlined": 0, "blocks_visited": 0, "errors": 0}
        self.errors: list[dict] = []
        # Cycle-safety for synced_block / weird recursion.
        self._block_stack: list[str] = []

    def log(self, *a):
        if self.verbose:
            print(*a, flush=True)

    # ── block tree ──

    def expand_blocks(self, parent_block_id: str) -> list[dict]:
        path = self.dump / "blocks" / f"{_norm(parent_block_id)}.json"
        f = _load(path)
        if not f:
            return []
        out: list[dict] = []
        for blk in f.get("results", []):
            self.counts["blocks_visited"] += 1
            bid = blk.get("id")
            if blk.get("has_children") and bid and bid not in self._block_stack:
                self._block_stack.append(bid)
                blk = dict(blk)
                blk["children"] = self.expand_blocks(bid)
                self._block_stack.pop()
            out.append(blk)
        return out

    # ── page ──

    def hydrate_page(self, page_id: str) -> dict | None:
        page_id = _norm(page_id)
        page = _load(self.dump / "pages" / f"{page_id}.json")
        if not page:
            self.errors.append({"op": "page_missing", "id": page_id})
            self.counts["errors"] += 1
            return None
        blocks = self.expand_blocks(page_id)
        # collect quick child references for downstream linking
        child_pages: list[str] = []
        child_dbs: list[str] = []
        def scan(blks):
            for b in blks:
                t = b.get("type")
                if t == "child_page":
                    child_pages.append(b["id"])
                elif t == "child_database":
                    child_dbs.append(b["id"])
                if b.get("children"):
                    scan(b["children"])
        scan(blocks)

        hydrated = {
            "id": page_id,
            "object": page.get("object", "page"),
            "url": page.get("url"),
            "public_url": page.get("public_url"),
            "icon": page.get("icon"),
            "cover": page.get("cover"),
            "archived": page.get("archived"),
            "in_trash": page.get("in_trash"),
            "created_time": page.get("created_time"),
            "last_edited_time": page.get("last_edited_time"),
            "created_by": page.get("created_by"),
            "last_edited_by": page.get("last_edited_by"),
            "parent": page.get("parent"),
            "properties": page.get("properties", {}),
            "blocks": blocks,
            "_meta": {
                "title": _title_of_page(page),
                "child_pages": child_pages,
                "child_databases": child_dbs,
            },
        }
        _save(self.out / "pages" / f"{page_id}.json", hydrated)
        self.counts["pages"] += 1
        return hydrated

    # ── data_source ──

    def hydrate_data_source(self, ds_id: str) -> dict | None:
        ds_id = _norm(ds_id)
        ds = _load(self.dump / "data_sources" / f"{ds_id}.json")
        if not ds:
            self.errors.append({"op": "data_source_missing", "id": ds_id})
            self.counts["errors"] += 1
            return None
        rows_file = _load(self.dump / "db_rows" / f"{ds_id}.json") or {}
        rows = rows_file.get("results", [])
        # Each row is itself a Notion page → reference by id (the per-page hydrated
        # file already has its own blocks). Inline minimal row metadata for indexing.
        row_refs = []
        for row in rows:
            rid = row.get("id")
            if not rid:
                continue
            row_refs.append({
                "id": rid,
                "url": row.get("url"),
                "last_edited_time": row.get("last_edited_time"),
                "title": _title_of_page(row),
                "properties": row.get("properties", {}),
            })
        self.counts["rows_inlined"] += len(row_refs)

        hydrated = {
            "id": ds_id,
            "object": ds.get("object", "data_source"),
            "title": ds.get("title"),
            "description": ds.get("description"),
            "icon": ds.get("icon"),
            "cover": ds.get("cover"),
            "parent": ds.get("parent"),
            "properties": ds.get("properties", {}),  # schema
            "rows": row_refs,
            "_meta": {
                "title": _title_of_ds(ds),
                "row_count": len(row_refs),
            },
        }
        _save(self.out / "data_sources" / f"{ds_id}.json", hydrated)
        self.counts["data_sources"] += 1
        return hydrated

    # ── driver ──

    def run(self) -> dict:
        page_dir = self.dump / "pages"
        ds_dir = self.dump / "data_sources"
        if page_dir.exists():
            for p in page_dir.iterdir():
                if p.suffix == ".json":
                    self.hydrate_page(p.stem)
        if ds_dir.exists():
            for p in ds_dir.iterdir():
                if p.suffix == ".json":
                    self.hydrate_data_source(p.stem)
        index = {
            "dump_dir": str(self.dump),
            "out_dir": str(self.out),
            "counts": self.counts,
            "errors": self.errors,
        }
        _save(self.out / "_index.json", index)
        return index


def _main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Stage B — hydrate raw dump")
    p.add_argument("--dump", default="data/notion/dump",
                   help="raw dump directory (default: data/notion/dump)")
    p.add_argument("--out", default="data/notion/hydrated",
                   help="hydrated output directory (default: data/notion/hydrated)")
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args(argv)
    h = Hydrator(Path(args.dump), Path(args.out), verbose=not args.quiet)
    t0 = time.time()
    idx = h.run()
    print(f"=== hydrate done in {time.time()-t0:.1f}s ===")
    print(f"  out      {args.out}")
    print(f"  counts   {idx['counts']}")
    print(f"  errors   {len(idx['errors'])}")
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
