"""Asset downloader — Notion-hosted file URLs → local cache, SQLite-backed state.

Two modes:
    1. **Inline** (preferred): instantiated by `notion_dump.Dumper`, called via a
       ThreadPoolExecutor as soon as an image/file URL surfaces during the walk.
       Avoids the 1-hour signed-URL expiry that bites multi-hour dumps.

    2. **Standalone** (fallback / retry): CLI scans an existing raw dump and
       attempts to download anything not already in the SQLite asset table.
       Useful for retrying expired URLs (only succeeds if you re-fetched the
       owning blocks via `notion_dump.py` to get fresh URLs first).

State table: `notion_asset` (see `notion_state.py`).
Idempotent: re-running skips entries with status='ok' and a present file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse, unquote

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from notion_state import State, DEFAULT_STATE_PATH  # noqa: E402


DEFAULT_ASSETS_DIR = Path("data/notion/assets")

NOTION_HOST_PATTERNS = (
    re.compile(r"\.amazonaws\.com"),
    re.compile(r"prod-files-secure\.s3"),
    re.compile(r"\.notion\.so/.*\bfile\b"),
    re.compile(r"\bnotion-static\.com"),
    re.compile(r"\bfile\.notion\.so"),
)
UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def is_notion_hosted(url: str | None) -> bool:
    if not url:
        return False
    return any(p.search(url) for p in NOTION_HOST_PATTERNS)


def asset_id_for(url: str, owner: str, block_id: str | None) -> str:
    """Stable id from URL — Notion S3 paths look like
    `/<workspace_uuid>/<file_uuid>/<filename>` so the LAST UUID is per-file."""
    path = urlparse(url).path
    uuids = UUID_RE.findall(path)
    if uuids:
        return uuids[-1]
    seed = (block_id or owner or url).encode() + b"|" + Path(path).name.encode()
    return hashlib.sha256(seed).hexdigest()[:16]


def _ext_from(url: str, content_type: str | None) -> str:
    name = unquote(Path(urlparse(url).path).name)
    if "." in name:
        return Path(name).suffix.lower()
    if content_type:
        return mimetypes.guess_extension(content_type.split(";")[0].strip()) or ""
    return ""


def block_url(blk: dict) -> tuple[str | None, str | None]:
    t = blk.get("type")
    if t not in ("image", "file", "video", "audio", "pdf"):
        return None, None
    payload = blk.get(t) or {}
    f = payload.get("file") or {}
    if isinstance(f, dict) and f.get("url"):
        return f["url"], t
    return None, None


def page_assets(obj: dict) -> list[tuple[str, str]]:
    """Cover/icon URLs as (url, kind)."""
    out: list[tuple[str, str]] = []
    cover = obj.get("cover")
    if isinstance(cover, dict):
        f = cover.get("file") or {}
        if isinstance(f, dict) and f.get("url"):
            out.append((f["url"], "cover"))
    icon = obj.get("icon")
    if isinstance(icon, dict) and icon.get("type") == "file":
        f = icon.get("file") or {}
        if isinstance(f, dict) and f.get("url"):
            out.append((f["url"], "icon"))
    return out


class AssetDownloader:
    """SQLite-backed downloader — thread-safe (each worker uses its own session).

    Usage:
        d = AssetDownloader(state, Path("data/notion/assets"))
        d.download_one(url, owner=page_id, kind="image", block_id=blk_id)
    """

    def __init__(
        self,
        state: State,
        out_dir: Path,
        *,
        timeout: float = 30.0,
        verbose: bool = False,
    ):
        self.state = state
        self.out = out_dir
        self.timeout = timeout
        self.verbose = verbose
        self.out.mkdir(parents=True, exist_ok=True)
        self._tlocal = None  # per-thread requests.Session via threading.local
        import threading
        self._tlocal = threading.local()
        self.counts = {
            "discovered": 0,
            "downloaded": 0,
            "skipped_existing": 0,
            "skipped_external": 0,
            "errors": 0,
        }

    def _session(self) -> requests.Session:
        s = getattr(self._tlocal, "session", None)
        if s is None:
            s = requests.Session()
            self._tlocal.session = s
        return s

    def log(self, *a):
        if self.verbose:
            print(*a, flush=True)

    def download_one(
        self,
        url: str,
        owner: str,
        kind: str,
        block_id: str | None = None,
    ) -> dict:
        if not is_notion_hosted(url):
            self.counts["skipped_external"] += 1
            return {"status": "external", "url": url}
        aid = asset_id_for(url, owner, block_id)
        prev = self.state.get_asset(aid)
        if prev and prev.get("status") == "ok" and prev.get("path"):
            if (self.out / prev["path"]).exists():
                self.counts["skipped_existing"] += 1
                return prev
            # state says ok but file is gone — refetch
        try:
            r = self._session().get(url, timeout=self.timeout, stream=True)
            if r.status_code != 200:
                entry = {
                    "asset_id": aid, "url": url, "owner_id": owner,
                    "block_id": block_id, "kind": kind, "path": None,
                    "size": None, "sha256": None, "mime": None,
                    "status": "error",
                    "error": f"HTTP {r.status_code}: {r.text[:200]}",
                }
                self.state.upsert_asset(**entry)
                self.counts["errors"] += 1
                return entry
            ctype = r.headers.get("Content-Type", "")
            ext = _ext_from(url, ctype) or ""
            rel_path = f"{owner}/{aid}{ext}"
            full = self.out / rel_path
            full.parent.mkdir(parents=True, exist_ok=True)
            sha = hashlib.sha256()
            size = 0
            with open(full, "wb") as fh:
                for chunk in r.iter_content(chunk_size=64 * 1024):
                    if chunk:
                        fh.write(chunk)
                        sha.update(chunk)
                        size += len(chunk)
            entry = {
                "asset_id": aid, "url": url, "owner_id": owner,
                "block_id": block_id, "kind": kind, "path": rel_path,
                "size": size, "sha256": sha.hexdigest(), "mime": ctype,
                "status": "ok", "error": None,
            }
            self.state.upsert_asset(**entry)
            self.counts["downloaded"] += 1
            self.log(f"  OK   {aid} {size:>10} {rel_path}")
            return entry
        except requests.RequestException as e:
            entry = {
                "asset_id": aid, "url": url, "owner_id": owner,
                "block_id": block_id, "kind": kind, "path": None,
                "size": None, "sha256": None, "mime": None,
                "status": "error", "error": str(e),
            }
            self.state.upsert_asset(**entry)
            self.counts["errors"] += 1
            return entry

    # ── compat: emit a JSON index that older Renderer consumers expect ──

    def export_index_json(self, dest: Path) -> int:
        rows = self.state.con.execute(
            "SELECT asset_id, url, owner_id, block_id, kind, path, size, "
            "sha256, mime, status, error FROM notion_asset"
        ).fetchall()
        cols = ("asset_id", "url", "owner_id", "block_id", "kind", "path",
                "size", "sha256", "mime", "status", "error")
        idx = {row[0]: dict(zip(cols, row)) for row in rows}
        # Backward compat: renderer reads `info['owner']` and `info['path']`.
        for v in idx.values():
            v["owner"] = v.get("owner_id")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")
        return len(idx)


# ───────────── standalone scanner (fallback) ─────────────


def _load(p: Path) -> dict | None:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def discover_in_dump(dump_dir: Path) -> Iterable[dict]:
    """Yield every Notion-hosted asset reference in raw dump as
    {url, owner, kind, block_id}. Used by standalone scanner only."""
    for sub in ("pages", "data_sources"):
        d = dump_dir / sub
        if not d.exists():
            continue
        for p in d.iterdir():
            if p.suffix != ".json":
                continue
            obj = _load(p) or {}
            owner = obj.get("id") or p.stem
            for url, kind in page_assets(obj):
                if is_notion_hosted(url):
                    yield {"url": url, "owner": owner, "kind": kind, "block_id": None}
    bd = dump_dir / "blocks"
    if bd.exists():
        for p in bd.iterdir():
            if p.suffix != ".json":
                continue
            bf = _load(p) or {}
            owner = bf.get("block_id") or p.stem
            for blk in bf.get("results") or []:
                url, kind = block_url(blk)
                if url and is_notion_hosted(url):
                    yield {
                        "url": url, "owner": owner, "kind": kind,
                        "block_id": blk.get("id"),
                    }


def _main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Standalone asset scanner / retrier")
    p.add_argument("--dump", default="data/notion/dump")
    p.add_argument("--out", default=str(DEFAULT_ASSETS_DIR))
    p.add_argument("--state", default=str(DEFAULT_STATE_PATH))
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--export-index", action="store_true",
                   help="also write _index.json (compat for Renderer)")
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args(argv)

    state = State(args.state)
    d = AssetDownloader(state, Path(args.out), verbose=not args.quiet)
    t0 = time.time()
    n = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = []
        for asset in discover_in_dump(Path(args.dump)):
            d.counts["discovered"] += 1
            n += 1
            futures.append(
                ex.submit(d.download_one, asset["url"], asset["owner"],
                          asset["kind"], asset.get("block_id"))
            )
        for f in futures:
            f.result()
    if args.export_index:
        d.export_index_json(Path(args.out) / "_index.json")
    print(f"=== assets done in {time.time()-t0:.1f}s ===")
    print(f"  discovered {n}  counts {d.counts}")
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
