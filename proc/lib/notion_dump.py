"""Recursive Notion subtree dumper with incremental SQLite state.

Walks pages → blocks → child pages / child databases / nested blocks, and
databases → rows (each row is a page). Saves raw JSON per object.

Incremental: SQLite at `data/notion_state.sqlite` records `last_edited_time`
per object. On rerun, an unchanged page/database skips its blocks-children /
db-query refetch and walks cached children instead.

Layout:
    <out>/
      _index.json          run summary {root_ids, counts, errors[]}
      _tree.json           {id: {type, parent, title, children[]}}
      pages/<uuid>.json    GET /pages/{id}
      blocks/<uuid>.json   {block_id, results: [...all children blocks...]}
      databases/<uuid>.json   GET /databases/{id}
      db_rows/<uuid>.json     {database_id, results: [...all rows...]}

CLI:
    python proc/lib/notion_dump.py login
    python proc/lib/notion_dump.py dump --root <id>... --out output/notion-dump-<date>
    python proc/lib/notion_dump.py status
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from notion_api import NotionClient, NotionError, normalize_id  # noqa: E402
from notion_assets import AssetDownloader, DEFAULT_ASSETS_DIR, page_assets, block_url, is_notion_hosted  # noqa: E402
from notion_auth import login as oauth_login  # noqa: E402
from notion_state import DEFAULT_STATE_PATH, State  # noqa: E402

DEFAULT_DUMP_DIR = Path("output/notion-dump")


def _title_of_page(page: dict) -> str:
    props = page.get("properties") or {}
    for prop in props.values():
        if prop.get("type") == "title":
            parts = prop.get("title") or []
            return "".join(p.get("plain_text", "") for p in parts) or "(untitled)"
    return "(untitled)"


def _title_of_database(db: dict) -> str:
    parts = db.get("title") or []
    return "".join(p.get("plain_text", "") for p in parts) or "(untitled db)"


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _parent_id_of(obj: dict) -> str | None:
    par = obj.get("parent") or {}
    for k in ("page_id", "database_id", "block_id", "workspace"):
        if k in par and par[k] is not True:
            return par[k]
    return None


class Dumper:
    def __init__(
        self,
        client: NotionClient,
        out_dir: Path,
        state: State,
        *,
        verbose: bool = True,
        force: bool = False,
        assets_dir: Path | None = None,
        asset_workers: int = 8,
    ):
        self.c = client
        self.out = out_dir
        self.state = state
        self.verbose = verbose
        self.force = force
        self.tree: dict[str, dict] = {}
        self.errors: list[dict] = []
        self.queue: deque[tuple[str, str, str | None]] = deque()  # (kind, id, parent)
        self.seen: set[tuple[str, str]] = set()
        self.counts = {
            "pages_fetched": 0, "pages_skipped": 0,
            "databases_fetched": 0, "databases_skipped": 0,
            "data_sources_fetched": 0, "data_sources_skipped": 0,
            "blocks_fetched": 0, "db_rows_fetched": 0,
            "errors": 0,
        }
        # Inline asset download (preferred — avoids 1h URL expiry on long walks).
        self.assets: AssetDownloader | None = None
        self.asset_pool: ThreadPoolExecutor | None = None
        self.asset_futures: list[Future] = []
        if assets_dir is not None:
            self.assets = AssetDownloader(state, assets_dir, verbose=False)
            self.asset_pool = ThreadPoolExecutor(
                max_workers=asset_workers, thread_name_prefix="asset"
            )
        self._maybe_migrate_state_v2()

    def _maybe_migrate_state_v2(self) -> None:
        """One-time migration when upgrading old (single-source) state to the
        2025-09-03 data_source-aware model. If the DB has database rows but no
        data_source rows yet, force every database to refetch by clearing its
        last_edited_time. The next walk will then discover data_sources and
        rebuild the proper child links."""
        con = self.state.con
        n_ds = con.execute(
            "SELECT COUNT(*) FROM notion_object WHERE kind='data_source'"
        ).fetchone()[0]
        n_db = con.execute(
            "SELECT COUNT(*) FROM notion_object WHERE kind='database'"
        ).fetchone()[0]
        if n_db > 0 and n_ds == 0:
            with con:
                con.execute(
                    "UPDATE notion_object SET last_edited_time=NULL WHERE kind='database'"
                )
                # Drop old database->page child rows; they will be replaced with
                # database->data_source links during the upgrade walk.
                con.execute(
                    "DELETE FROM notion_child WHERE parent_kind='database'"
                )
            self.log(f"  migrate: invalidated last_edited_time on {n_db} databases (state v2 upgrade)")

    def log(self, *a):
        if self.verbose:
            print(*a, flush=True)

    def _submit_asset(self, url: str | None, owner: str, kind: str, block_id: str | None = None) -> None:
        if not (url and self.assets and self.asset_pool):
            return
        if not is_notion_hosted(url):
            return
        fut = self.asset_pool.submit(self.assets.download_one, url, owner, kind, block_id)
        self.asset_futures.append(fut)

    def enqueue(self, kind: str, uid: str, parent: str | None) -> None:
        try:
            uid = normalize_id(uid)
        except ValueError:
            return
        key = (kind, uid)
        if key in self.seen:
            if uid in self.tree and parent and self.tree[uid].get("parent") is None:
                self.tree[uid]["parent"] = parent
            return
        self.seen.add(key)
        self.queue.append((kind, uid, parent))

    # ───────────── page ─────────────

    def _dump_page(self, uid: str, parent: str | None) -> None:
        try:
            page = self.c.pages_retrieve(uid)
        except NotionError as e:
            self._record_error("page_retrieve", uid, e)
            return

        cur_let = page.get("last_edited_time")
        prev_let = self.state.get_let("page", uid)
        title = _title_of_page(page)
        unchanged = (not self.force) and prev_let is not None and prev_let == cur_let

        self.tree[uid] = {
            "type": "page",
            "parent": parent or _parent_id_of(page),
            "title": title,
            "children": [],
            "last_edited_time": cur_let,
            "from_cache": unchanged,
        }

        if unchanged:
            self.counts["pages_skipped"] += 1
            self.log(f"  page  CACHE  {uid}  {title!r}")
            for ck, ci in self.state.get_children("page", uid):
                self.tree[uid]["children"].append(ci)
                self.enqueue(ck, ci, uid)
            return

        # changed or new — full fetch + write
        _write_json(self.out / "pages" / f"{uid}.json", page)
        self.counts["pages_fetched"] += 1
        self.log(f"  page  FETCH  {uid}  {title!r}  let={cur_let}")

        # cover/icon — Notion-hosted URLs expire ~1h; submit immediately.
        for url, kind in page_assets(page):
            self._submit_asset(url, owner=uid, kind=kind)

        try:
            children = list(self.c.blocks_children_iter(uid))
        except NotionError as e:
            self._record_error("blocks_children", uid, e)
            return
        _write_json(
            self.out / "blocks" / f"{uid}.json",
            {"block_id": uid, "results": children},
        )
        self.counts["blocks_fetched"] += len(children)

        child_links: list[tuple[str, str]] = []
        for blk in children:
            self._scan_block(blk, parent_page=uid, child_links=child_links)

        # de-dup child_links preserving order
        seen_l = set()
        deduped: list[tuple[str, str]] = []
        for ck, ci in child_links:
            try:
                ci_n = normalize_id(ci)
            except ValueError:
                continue
            key = (ck, ci_n)
            if key in seen_l:
                continue
            seen_l.add(key)
            deduped.append((ck, ci_n))

        self.state.upsert_object(
            kind="page", id_=uid, last_edited_time=cur_let,
            parent_id=parent or _parent_id_of(page), title=title,
        )
        self.state.replace_children("page", uid, deduped)

        for ck, ci in deduped:
            self.tree[uid]["children"].append(ci)
            self.enqueue(ck, ci, uid)

    def _scan_block(
        self,
        blk: dict,
        parent_page: str,
        child_links: list[tuple[str, str]],
    ) -> None:
        btype = blk.get("type")
        bid = blk.get("id")
        if not bid:
            return

        if btype == "child_page":
            child_links.append(("page", bid))
            return
        if btype == "child_database":
            child_links.append(("database", bid))
            return

        # File-bearing blocks: download right away while the signed URL is fresh.
        url, kind = block_url(blk)
        if url:
            self._submit_asset(url, owner=parent_page, kind=kind, block_id=bid)

        if blk.get("has_children"):
            try:
                grand = list(self.c.blocks_children_iter(bid))
            except NotionError as e:
                self._record_error("blocks_children_nested", bid, e)
                return
            try:
                bid_n = normalize_id(bid)
            except ValueError:
                return
            _write_json(
                self.out / "blocks" / f"{bid_n}.json",
                {"block_id": bid, "results": grand},
            )
            self.counts["blocks_fetched"] += len(grand)
            for sub in grand:
                self._scan_block(sub, parent_page=parent_page, child_links=child_links)

    # ───────────── database ─────────────

    def _dump_database(self, uid: str, parent: str | None) -> None:
        # Notion-Version 2025-09-03: a database is a CONTAINER of data_sources.
        # We retrieve the database meta (schema-less in new API, just metadata + sources list),
        # then enqueue each data_source as its own node (which holds the schema + rows).
        try:
            db = self.c.databases_retrieve(uid)
        except NotionError as e:
            self._record_error("database_retrieve", uid, e)
            return

        cur_let = db.get("last_edited_time")
        prev_let = self.state.get_let("database", uid)
        title = _title_of_database(db)
        unchanged = (not self.force) and prev_let is not None and prev_let == cur_let

        self.tree[uid] = {
            "type": "database",
            "parent": parent or _parent_id_of(db),
            "title": title,
            "children": [],
            "last_edited_time": cur_let,
            "from_cache": unchanged,
        }

        if unchanged:
            self.counts["databases_skipped"] += 1
            self.log(f"  db    CACHE  {uid}  {title!r}")
            for ck, ci in self.state.get_children("database", uid):
                self.tree[uid]["children"].append(ci)
                self.enqueue(ck, ci, uid)
            return

        _write_json(self.out / "databases" / f"{uid}.json", db)
        self.counts["databases_fetched"] += 1
        sources = db.get("data_sources") or []
        self.log(f"  db    FETCH  {uid}  {title!r}  sources={len(sources)}  let={cur_let}")

        child_links: list[tuple[str, str]] = []
        for ds in sources:
            ds_id = ds.get("id")
            if not ds_id:
                continue
            try:
                ds_id_n = normalize_id(ds_id)
            except ValueError:
                continue
            child_links.append(("data_source", ds_id_n))

        if not sources:
            # Either the DB really has no sources or the integration can't see them.
            self.errors.append({
                "op": "database_no_data_sources",
                "id": uid,
                "title": title,
                "note": "no accessible data_sources — share this database (or its data sources) with the integration",
            })

        self.state.upsert_object(
            kind="database", id_=uid, last_edited_time=cur_let,
            parent_id=parent or _parent_id_of(db), title=title,
        )
        self.state.replace_children("database", uid, child_links)

        for ck, ci in child_links:
            self.tree[uid]["children"].append(ci)
            self.enqueue(ck, ci, uid)

    def _dump_data_source(self, uid: str, parent: str | None) -> None:
        try:
            ds = self.c.data_sources_retrieve(uid)
        except NotionError as e:
            self._record_error("data_source_retrieve", uid, e)
            return

        cur_let = ds.get("last_edited_time")
        prev_let = self.state.get_let("data_source", uid)
        title_parts = ds.get("title") or []
        title = "".join(t.get("plain_text", "") for t in title_parts) or "(untitled ds)"
        unchanged = (not self.force) and prev_let is not None and prev_let == cur_let

        self.tree[uid] = {
            "type": "data_source",
            "parent": parent or _parent_id_of(ds),
            "title": title,
            "children": [],
            "last_edited_time": cur_let,
            "from_cache": unchanged,
        }

        if unchanged:
            self.counts.setdefault("data_sources_skipped", 0)
            self.counts["data_sources_skipped"] += 1
            self.log(f"  ds    CACHE  {uid}  {title!r}")
            for ck, ci in self.state.get_children("data_source", uid):
                self.tree[uid]["children"].append(ci)
                self.enqueue(ck, ci, uid)
            return

        _write_json(self.out / "data_sources" / f"{uid}.json", ds)
        self.counts.setdefault("data_sources_fetched", 0)
        self.counts["data_sources_fetched"] += 1
        self.log(f"  ds    FETCH  {uid}  {title!r}  let={cur_let}")

        for url, k in page_assets(ds):
            self._submit_asset(url, owner=uid, kind=k)

        try:
            rows = list(self.c.data_sources_query_iter(uid))
        except NotionError as e:
            self._record_error("data_source_query", uid, e)
            return
        _write_json(
            self.out / "db_rows" / f"{uid}.json",
            {"data_source_id": uid, "results": rows},
        )
        self.counts["db_rows_fetched"] += len(rows)

        child_links: list[tuple[str, str]] = []
        for row in rows:
            rid = row.get("id")
            if not rid:
                continue
            try:
                rid_n = normalize_id(rid)
            except ValueError:
                continue
            child_links.append(("page", rid_n))
            for url, k in page_assets(row):
                self._submit_asset(url, owner=rid_n, kind=k)

        self.state.upsert_object(
            kind="data_source", id_=uid, last_edited_time=cur_let,
            parent_id=parent or _parent_id_of(ds), title=title,
        )
        self.state.replace_children("data_source", uid, child_links)

        for ck, ci in child_links:
            self.tree[uid]["children"].append(ci)
            self.enqueue(ck, ci, uid)

    # ───────────── error helper ─────────────

    def _record_error(self, op: str, uid: str, e: NotionError) -> None:
        self.counts["errors"] += 1
        info = {
            "op": op,
            "id": uid,
            "status": e.status,
            "method": e.method,
            "path": e.path,
            "body": e.body[:500],
        }
        self.errors.append(info)
        self.log(f"  ERR   {op} {uid} [{e.status}] {e.body[:120]}")

    # ───────────── driver ─────────────

    def run(self, roots: list[str]) -> dict:
        started = datetime.now().isoformat(timespec="seconds")
        for r in roots:
            try:
                rid = normalize_id(r)
            except ValueError as e:
                self.errors.append({"op": "root_normalize", "id": r, "body": str(e)})
                continue
            self.enqueue("page", rid, None)

        while self.queue:
            kind, uid, parent = self.queue.popleft()
            try:
                if kind == "page":
                    self._dump_page(uid, parent)
                elif kind == "database":
                    self._dump_database(uid, parent)
                elif kind == "data_source":
                    self._dump_data_source(uid, parent)
            except NotionError as e:
                if kind == "page" and e.status in (400, 404):
                    # might actually be a database id
                    self.enqueue("database", uid, parent)
                else:
                    self._record_error(f"{kind}_unhandled", uid, e)
            except Exception as e:  # noqa: BLE001
                self.counts["errors"] += 1
                self.errors.append({
                    "op": f"{kind}_exception",
                    "id": uid,
                    "trace": traceback.format_exc(limit=5),
                    "msg": str(e),
                })

        # Drain asset downloads — wait for in-flight + queued futures to finish.
        if self.asset_pool is not None:
            n_pending = len(self.asset_futures)
            self.log(f"  draining {n_pending} asset downloads...")
            self.asset_pool.shutdown(wait=True)
            if self.assets is not None:
                self.counts["assets_downloaded"] = self.assets.counts.get("downloaded", 0)
                self.counts["assets_skipped"] = self.assets.counts.get("skipped_existing", 0)
                self.counts["assets_errors"] = self.assets.counts.get("errors", 0)
                # Emit JSON index too for any consumer that still reads it.
                try:
                    self.assets.export_index_json(self.assets.out / "_index.json")
                except Exception:
                    pass

        finished = datetime.now().isoformat(timespec="seconds")
        index = {
            "roots": roots,
            "started_at": started,
            "finished_at": finished,
            "counts": self.counts,
            "errors": self.errors,
            "state_path": str(self.state.path),
        }
        _write_json(self.out / "_index.json", index)
        _write_json(self.out / "_tree.json", self.tree)
        self.state.record_run(started, finished, self.counts, self.errors)
        return index


# ───────────── CLI ─────────────


def _main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Notion subtree raw-JSON dumper (incremental)")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("login", help="run OAuth code-exchange flow")

    pd = sub.add_parser("dump", help="dump subtree(s)")
    pd.add_argument("--root", action="append", required=True, help="root page or db id")
    pd.add_argument("--out", default=str(DEFAULT_DUMP_DIR),
                    help=f"raw dump output directory (default: {DEFAULT_DUMP_DIR})")
    pd.add_argument("--state", default=str(DEFAULT_STATE_PATH),
                    help=f"sqlite state path (default: {DEFAULT_STATE_PATH})")
    pd.add_argument("--assets", default=str(DEFAULT_ASSETS_DIR),
                    help=f"inline asset download dir (default: {DEFAULT_ASSETS_DIR}). "
                         f"Pass empty string to disable.")
    pd.add_argument("--asset-workers", type=int, default=8,
                    help="concurrent asset download threads (default: 8)")
    pd.add_argument("--force", action="store_true",
                    help="ignore state cache and refetch everything")
    pd.add_argument("--quiet", action="store_true")

    ps = sub.add_parser("status", help="print state DB summary")
    ps.add_argument("--state", default=str(DEFAULT_STATE_PATH))

    args = p.parse_args(argv)

    if args.cmd == "login":
        oauth_login()
        return 0

    if args.cmd == "status":
        s = State(args.state)
        print(json.dumps(s.stats(), ensure_ascii=False, indent=2))
        s.close()
        return 0

    if args.cmd == "dump":
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        assets_dir = Path(args.assets) if args.assets else None
        c = NotionClient.from_cache()
        s = State(args.state)
        d = Dumper(
            c, out, s,
            verbose=not args.quiet,
            force=args.force,
            assets_dir=assets_dir,
            asset_workers=args.asset_workers,
        )
        t0 = time.time()
        index = d.run(args.root)
        elapsed = time.time() - t0
        s.close()
        print()
        print(f"=== done in {elapsed:.1f}s ===")
        print(f"  out      {out}")
        print(f"  state    {args.state}")
        print(f"  counts   {index['counts']}")
        print(f"  errors   {len(index['errors'])}")
        return 0 if not index["errors"] else 1

    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
