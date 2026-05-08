"""Stage X — download Notion-hosted asset URLs into local files.

Walks raw dump for any block with a fetchable URL:
    image, file, video, audio, pdf  (file_upload / file types)
    cover.external/file, icon.file (on pages and data_sources)

Notion-hosted URLs (`*.amazonaws.com`, `*.notion.so/file/*`) expire ~1h after
the API returned them. External URLs (user-added http(s)://) do not expire and
are skipped (they remain a remote link).

Writes:
    <assets>/<owner_id>/<asset_id>.<ext>     downloaded bytes
    <assets>/_index.json                     {asset_id: {url, owner, mime, size, sha256, status, error?}}

Idempotent: re-running skips already-downloaded files (same asset_id).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse, unquote

import requests

NOTION_HOST_PATTERNS = (
    re.compile(r"\.amazonaws\.com"),
    re.compile(r"prod-files-secure\.s3"),
    re.compile(r"\.notion\.so/.*\bfile\b"),
    re.compile(r"\bnotion-static\.com"),
    re.compile(r"\bfile\.notion\.so"),
)


def _is_notion_hosted(url: str) -> bool:
    if not url:
        return False
    return any(p.search(url) for p in NOTION_HOST_PATTERNS)


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


def _ext_from_url(url: str, content_type: str | None) -> str:
    parsed = urlparse(url)
    name = unquote(Path(parsed.path).name)
    if "." in name:
        return Path(name).suffix.lower()
    if content_type:
        guess = mimetypes.guess_extension(content_type.split(";")[0].strip()) or ""
        return guess
    return ""


def _filename_from_url(url: str) -> str:
    parsed = urlparse(url)
    return unquote(Path(parsed.path).name) or "asset"


def _block_url(blk: dict) -> tuple[str | None, str | None]:
    """Return (url, kind) for fetchable blocks; else (None, None)."""
    t = blk.get("type")
    if t not in ("image", "file", "video", "audio", "pdf"):
        return None, None
    payload = blk.get(t) or {}
    file_part = payload.get("file") or {}
    if isinstance(file_part, dict) and file_part.get("url"):
        return file_part["url"], t
    # `file_upload` and `external` types — external doesn't expire, skip
    return None, None


def _page_assets(page: dict) -> list[tuple[str, str]]:
    """(url, kind) pairs from cover + icon if they are file-type."""
    out: list[tuple[str, str]] = []
    cover = page.get("cover")
    if isinstance(cover, dict):
        f = cover.get("file") or {}
        if f.get("url"):
            out.append((f["url"], "cover"))
    icon = page.get("icon")
    if isinstance(icon, dict) and icon.get("type") == "file":
        f = icon.get("file") or {}
        if f.get("url"):
            out.append((f["url"], "icon"))
    return out


def _walk_blocks(results: list, owner_id: str, found: list) -> None:
    for blk in results:
        url, kind = _block_url(blk)
        if url and _is_notion_hosted(url):
            found.append({"url": url, "owner": owner_id, "kind": kind, "block_id": blk.get("id")})
        if blk.get("has_children"):
            pass  # children fetched via separate blocks/<bid>.json file by walker


class AssetDownloader:
    def __init__(self, dump_dir: Path, out_dir: Path, *, timeout: float = 30.0, verbose: bool = True):
        self.dump = dump_dir
        self.out = out_dir
        self.timeout = timeout
        self.verbose = verbose
        self.session = requests.Session()
        self.index_path = out_dir / "_index.json"
        self.index: dict = {}
        if self.index_path.exists():
            self.index = json.loads(self.index_path.read_text(encoding="utf-8"))
        self.counts = {"discovered": 0, "downloaded": 0, "skipped_existing": 0,
                       "skipped_external": 0, "errors": 0}

    def log(self, *a):
        if self.verbose:
            print(*a, flush=True)

    def discover(self) -> list[dict]:
        """Find every Notion-hosted URL by scanning raw dump."""
        out: list[dict] = []
        # 1) page covers/icons
        page_dir = self.dump / "pages"
        if page_dir.exists():
            for p in page_dir.iterdir():
                if p.suffix != ".json":
                    continue
                page = _load(p) or {}
                pid = page.get("id") or p.stem
                for url, kind in _page_assets(page):
                    if _is_notion_hosted(url):
                        out.append({"url": url, "owner": pid, "kind": kind, "block_id": None})

        # 2) data_source covers/icons
        ds_dir = self.dump / "data_sources"
        if ds_dir.exists():
            for p in ds_dir.iterdir():
                if p.suffix != ".json":
                    continue
                ds = _load(p) or {}
                did = ds.get("id") or p.stem
                for url, kind in _page_assets(ds):
                    if _is_notion_hosted(url):
                        out.append({"url": url, "owner": did, "kind": kind, "block_id": None})

        # 3) every block with a file payload
        block_dir = self.dump / "blocks"
        if block_dir.exists():
            for p in block_dir.iterdir():
                if p.suffix != ".json":
                    continue
                bf = _load(p) or {}
                owner = bf.get("block_id") or p.stem
                _walk_blocks(bf.get("results", []), owner, out)

        self.counts["discovered"] = len(out)
        return out

    def _asset_id_for(self, url: str, owner: str, block_id: str | None) -> str:
        # Notion S3 paths look like /<workspace_uuid>/<file_uuid>/<filename>.
        # Skip the query string (signed URL params) and pick the LAST UUID in
        # the path — that is the per-file id; the first one is workspace_id.
        path = urlparse(url).path
        uuids = re.findall(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", path)
        if uuids:
            return uuids[-1]
        # Fallback: hash of (block_id or owner) + filename
        h = hashlib.sha256(((block_id or owner) + "|" + _filename_from_url(url)).encode()).hexdigest()[:16]
        return h

    def download_one(self, asset: dict) -> dict:
        url = asset["url"]
        owner = asset["owner"]
        aid = self._asset_id_for(url, owner, asset.get("block_id"))
        # short-circuit if already downloaded successfully
        prev = self.index.get(aid)
        if prev and prev.get("status") == "ok" and (self.out / prev["path"]).exists():
            self.counts["skipped_existing"] += 1
            return prev

        try:
            r = self.session.get(url, timeout=self.timeout, stream=True)
            if r.status_code != 200:
                err = {"asset_id": aid, "url": url, "owner": owner, "status": "error",
                       "http_status": r.status_code, "body": r.text[:300]}
                self.index[aid] = err
                self.counts["errors"] += 1
                self.log(f"  ERR  {aid} [{r.status_code}] {url[:80]}")
                return err
            ctype = r.headers.get("Content-Type", "")
            ext = _ext_from_url(url, ctype) or ""
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
                "asset_id": aid,
                "url": url,
                "owner": owner,
                "kind": asset.get("kind"),
                "block_id": asset.get("block_id"),
                "path": rel_path,
                "mime": ctype,
                "size": size,
                "sha256": sha.hexdigest(),
                "status": "ok",
            }
            self.index[aid] = entry
            self.counts["downloaded"] += 1
            self.log(f"  OK   {aid} {size:>10} {rel_path}")
            return entry
        except requests.RequestException as e:
            err = {"asset_id": aid, "url": url, "owner": owner, "status": "error",
                   "exception": str(e)}
            self.index[aid] = err
            self.counts["errors"] += 1
            self.log(f"  ERR  {aid} exc {e} {url[:60]}")
            return err

    def run(self) -> dict:
        assets = self.discover()
        self.log(f"discovered {len(assets)} Notion-hosted assets")
        for a in assets:
            self.download_one(a)
            # flush index periodically so a kill doesn't lose progress
            if self.counts["downloaded"] % 50 == 0:
                _save(self.index_path, self.index)
        _save(self.index_path, self.index)
        return {
            "dump_dir": str(self.dump),
            "out_dir": str(self.out),
            "counts": self.counts,
        }


def _main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Stage X — download Notion-hosted assets")
    p.add_argument("--dump", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args(argv)
    d = AssetDownloader(Path(args.dump), Path(args.out), verbose=not args.quiet)
    t0 = time.time()
    summary = d.run()
    print(f"=== assets done in {time.time()-t0:.1f}s ===")
    print(f"  counts {summary['counts']}")
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
