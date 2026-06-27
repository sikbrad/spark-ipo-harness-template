"""Raindrop.io bookmark dumper with incremental SQLite state.

Walks all collections + every raindrop (across `-1` = all bookmarks), saving
raw JSON per object. Smart-resume: pagination is sorted by `-lastUpdate`, so
once we hit a full page of items whose `lastUpdate` already matches state,
we stop paginating.

Layout:
    data/raindrop/
      state.sqlite              # incremental state
      dump/
        _index.json             # run summary
        _tree.json              # collection hierarchy
        collections/<id>.json   # raw collection objects (root + nested + system)
        raindrops/<id>.json     # raw raindrop objects (one file per bookmark)
        tags.json               # raw /tags response

CLI:
    python proc/lib/raindrop_dump.py whoami
    python proc/lib/raindrop_dump.py status
    python proc/lib/raindrop_dump.py dump          # incremental
    python proc/lib/raindrop_dump.py dump --force  # ignore cache
    python proc/lib/raindrop_dump.py dump --since 2026-01-01  # explicit cutoff
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from raindrop_api import RaindropClient, RaindropError  # noqa: E402
from raindrop_state import DEFAULT_STATE_PATH, State  # noqa: E402

DEFAULT_DUMP_DIR = Path("data/raindrop/dump")
SYSTEM_COLLECTIONS = [
    (0, "Unsorted"),
    (-1, "All bookmarks"),
    (-99, "Trash"),
]
# After this many consecutive cache-hits in `-lastUpdate` order, we conclude
# the rest of the list is unchanged and stop pagination. One full perpage(=50)
# gives a comfortable buffer against minor reorderings.
STOP_AFTER_CACHED_RUN = 50


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _parent_id_of_collection(col: dict) -> int | None:
    parent = col.get("parent")
    if isinstance(parent, dict):
        return parent.get("$id")
    return None


class Dumper:
    def __init__(
        self,
        client: RaindropClient,
        out_dir: Path,
        state: State,
        *,
        verbose: bool = True,
        force: bool = False,
        since: str | None = None,
        stop_after_cached_run: int = STOP_AFTER_CACHED_RUN,
    ):
        self.c = client
        self.out = out_dir
        self.state = state
        self.verbose = verbose
        self.force = force
        self.since = since  # ISO date string; raindrops with lastUpdate < since are skipped early
        self.stop_after_cached_run = stop_after_cached_run
        self.tree: dict[str, dict] = {}
        self.errors: list[dict] = []
        self.counts = {
            "collections_fetched": 0,
            "collections_skipped": 0,
            "raindrops_fetched": 0,
            "raindrops_skipped": 0,
            "raindrops_seen": 0,
            "pages_walked": 0,
            "errors": 0,
        }

    def log(self, *a):
        if self.verbose:
            print(*a, flush=True)

    # ───────────── collections ─────────────

    def _dump_collections(self) -> None:
        try:
            cols = list(self.c.collections_iter())
        except RaindropError as e:
            self._record_error("collections_list", "*", e)
            return

        self.log(f"  collections  {len(cols)} returned by API")

        # System collections live outside the regular hierarchy — synthesize stub
        # entries so the tree is complete.
        seen_ids: set[int] = set()
        for col in cols:
            cid = col.get("_id")
            if cid is None:
                continue
            seen_ids.add(int(cid))
            self._dump_one_collection(col)

        for sys_id, sys_title in SYSTEM_COLLECTIONS:
            if sys_id in seen_ids:
                continue
            stub = {
                "_id": sys_id,
                "title": sys_title,
                "system": True,
                "parent": None,
            }
            self._dump_one_collection(stub, system=True)

    def _dump_one_collection(self, col: dict, *, system: bool = False) -> None:
        cid = col.get("_id")
        if cid is None:
            return
        cid_str = str(cid)
        cur_lu = col.get("lastUpdate")
        prev_lu = self.state.get_last_update("collection", cid_str)
        title = col.get("title") or "(untitled)"
        parent_id = _parent_id_of_collection(col)
        unchanged = (
            (not self.force)
            and (not system)
            and prev_lu is not None
            and cur_lu is not None
            and prev_lu == cur_lu
        )

        self.tree[cid_str] = {
            "type": "collection",
            "parent": str(parent_id) if parent_id is not None else None,
            "title": title,
            "system": system,
            "last_update": cur_lu,
            "from_cache": unchanged,
        }

        if unchanged:
            self.counts["collections_skipped"] += 1
            return

        _write_json(self.out / "collections" / f"{cid_str}.json", col)
        self.counts["collections_fetched"] += 1
        self.state.upsert_object(
            kind="collection",
            id_=cid_str,
            last_update=cur_lu,
            parent_id=parent_id,
            title=title,
        )

    # ───────────── raindrops (smart-resume) ─────────────

    def _dump_raindrops(self) -> None:
        """Paginate collection=-1 sorted by -lastUpdate. Stop when a full
        run of consecutive items is already cached at the same lastUpdate."""
        consecutive_cached = 0
        last_page_logged = -1
        try:
            stream = self.c.raindrops_iter_with_meta(
                collection_id=-1, sort="-lastUpdate"
            )
            for item, page, _i in stream:
                self.counts["raindrops_seen"] += 1
                if page != last_page_logged:
                    self.counts["pages_walked"] += 1
                    last_page_logged = page

                rid = item.get("_id")
                if rid is None:
                    continue
                rid_str = str(rid)
                cur_lu = item.get("lastUpdate")

                if self.since and cur_lu and cur_lu < self.since:
                    self.log(
                        f"  raindrops  stop: lastUpdate {cur_lu} < --since {self.since}"
                    )
                    return

                prev_lu = self.state.get_last_update("raindrop", rid_str)
                unchanged = (
                    (not self.force)
                    and prev_lu is not None
                    and cur_lu is not None
                    and prev_lu == cur_lu
                )

                if unchanged:
                    self.counts["raindrops_skipped"] += 1
                    consecutive_cached += 1
                    if consecutive_cached >= self.stop_after_cached_run:
                        self.log(
                            f"  raindrops  stop: {consecutive_cached} consecutive "
                            f"cache-hits at page={page}"
                        )
                        return
                    continue

                consecutive_cached = 0
                _write_json(self.out / "raindrops" / f"{rid_str}.json", item)
                self.counts["raindrops_fetched"] += 1

                col = item.get("collection") or {}
                parent_id = col.get("$id") if isinstance(col, dict) else None
                self.state.upsert_object(
                    kind="raindrop",
                    id_=rid_str,
                    last_update=cur_lu,
                    parent_id=parent_id,
                    title=item.get("title"),
                )

                if self.counts["raindrops_fetched"] % 50 == 0:
                    self.log(
                        f"  raindrops  fetched={self.counts['raindrops_fetched']} "
                        f"skipped={self.counts['raindrops_skipped']} "
                        f"page={page}"
                    )
        except RaindropError as e:
            self._record_error("raindrops_iter", "-1", e)

    # ───────────── tags ─────────────

    def _dump_tags(self) -> None:
        try:
            tags = self.c.tags()
        except RaindropError as e:
            self._record_error("tags", "*", e)
            return
        _write_json(self.out / "tags.json", tags)

    # ───────────── error helper ─────────────

    def _record_error(self, op: str, uid: str, e: RaindropError) -> None:
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

    def run(self) -> dict:
        started = datetime.now().isoformat(timespec="seconds")
        try:
            self._dump_collections()
            self._dump_raindrops()
            self._dump_tags()
        except Exception as e:  # noqa: BLE001
            self.counts["errors"] += 1
            self.errors.append(
                {
                    "op": "run_exception",
                    "trace": traceback.format_exc(limit=5),
                    "msg": str(e),
                }
            )

        finished = datetime.now().isoformat(timespec="seconds")
        index = {
            "started_at": started,
            "finished_at": finished,
            "force": self.force,
            "since": self.since,
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
    p = argparse.ArgumentParser(
        description="Raindrop.io bookmark dumper (incremental)"
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("whoami", help="GET /user")

    pd = sub.add_parser("dump", help="dump collections + raindrops")
    pd.add_argument(
        "--out",
        default=str(DEFAULT_DUMP_DIR),
        help=f"raw dump output directory (default: {DEFAULT_DUMP_DIR})",
    )
    pd.add_argument(
        "--state",
        default=str(DEFAULT_STATE_PATH),
        help=f"sqlite state path (default: {DEFAULT_STATE_PATH})",
    )
    pd.add_argument(
        "--force",
        action="store_true",
        help="ignore state cache and refetch everything",
    )
    pd.add_argument(
        "--since",
        default=None,
        help="ISO date (YYYY-MM-DD or full ISO timestamp) — stop paginating once "
             "raindrop lastUpdate < since",
    )
    pd.add_argument(
        "--stop-after",
        type=int,
        default=STOP_AFTER_CACHED_RUN,
        help=f"stop after N consecutive cache-hits (default: {STOP_AFTER_CACHED_RUN})",
    )
    pd.add_argument("--quiet", action="store_true")

    ps = sub.add_parser("status", help="print state DB summary")
    ps.add_argument("--state", default=str(DEFAULT_STATE_PATH))

    args = p.parse_args(argv)

    if args.cmd == "whoami":
        from raindrop_auth import whoami  # local import
        whoami()
        return 0

    if args.cmd == "status":
        s = State(args.state)
        info = s.stats()
        last = s.last_run()
        print(json.dumps({"stats": info, "last_run": last}, ensure_ascii=False, indent=2))
        s.close()
        return 0

    if args.cmd == "dump":
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        c = RaindropClient.from_env()
        s = State(args.state)
        d = Dumper(
            c, out, s,
            verbose=not args.quiet,
            force=args.force,
            since=args.since,
            stop_after_cached_run=args.stop_after,
        )
        t0 = time.time()
        index = d.run()
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
