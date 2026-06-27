#!/usr/bin/env python3
"""Redownload empty or corrupt OneNote image resources."""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

import requests
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "proc" / "lib"))

from msgraph import GRAPH, GraphClient  # noqa: E402

BASE_OUT = ROOT / "data" / "techsupport" / "onenote"
RAW_DIR = BASE_OUT / "raw"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def image_bytes_ok(data: bytes) -> bool:
    if not data:
        return False
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.verify()
        return True
    except Exception:
        return False


def image_file_ok(path: Path) -> bool:
    if not path.exists() or path.stat().st_size == 0:
        return False
    try:
        with Image.open(path) as image:
            image.verify()
        return True
    except Exception:
        return False


def normalize_resource_url(url: str, site_id: str) -> str:
    if "/siteCollections/" not in url or "/onenote/resources/" not in url:
        return url
    match = re.search(r"/onenote/resources/([^/?#]+)(/[^?#]+)?", url)
    if not match:
        return url
    resource_id = match.group(1)
    suffix = match.group(2) or "/$value"
    return f"/sites/{site_id}/onenote/resources/{resource_id}{suffix}"


def fetch_resource(client: GraphClient, url: str, site_id: str) -> bytes:
    normalized = normalize_resource_url(url, site_id)
    full_url = normalized if normalized.startswith("http") else GRAPH + normalized
    last_error: Exception | None = None
    for attempt in range(8):
        try:
            response = requests.get(full_url, headers={"Authorization": "Bearer " + client.token()}, timeout=180)
            if response.status_code == 429:
                delay = int(response.headers.get("Retry-After") or 0) or min(30 * (attempt + 1), 180)
                time.sleep(delay)
                continue
            if response.status_code in {500, 502, 503, 504}:
                time.sleep(min(2**attempt, 30))
                continue
            if not response.ok:
                raise RuntimeError(f"resource fetch failed [{response.status_code}]: {response.text[:200]}")
            return response.content
        except requests.RequestException as exc:
            last_error = exc
            time.sleep(min(2**attempt, 30))
    if last_error:
        raise last_error
    raise RuntimeError(f"resource fetch failed after retries: {url}")


def iter_resource_files() -> list[Path]:
    return sorted(RAW_DIR.glob("pages/*/resources.json"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    site = read_json(RAW_DIR / "site.json")
    site_id = site["id"]
    client = GraphClient()
    checked = 0
    bad = 0
    repaired = 0
    failed: list[dict[str, str]] = []
    for resources_path in iter_resource_files():
        resources = read_json(resources_path)
        changed = False
        for item in resources:
            if item.get("kind") != "image" or item.get("status") != "ok" or not item.get("raw_path"):
                continue
            checked += 1
            raw_path = BASE_OUT / item["raw_path"]
            md_path = BASE_OUT / item["md_path"] if item.get("md_path") else None
            if image_file_ok(raw_path) and (not md_path or image_file_ok(md_path)):
                continue
            bad += 1
            if args.dry_run:
                continue
            try:
                data = fetch_resource(client, item["url"], site_id)
                if not image_bytes_ok(data):
                    raise RuntimeError("downloaded image body is empty or invalid")
                raw_path.parent.mkdir(parents=True, exist_ok=True)
                raw_path.write_bytes(data)
                if md_path:
                    md_path.parent.mkdir(parents=True, exist_ok=True)
                    md_path.write_bytes(data)
                item["bytes"] = len(data)
                item["status"] = "ok"
                item["error"] = None
                repaired += 1
                changed = True
                print(f"repaired {resources_path.parent.name}/{raw_path.name} {len(data)} bytes", flush=True)
            except Exception as exc:  # noqa: BLE001
                item["status"] = "error"
                item["error"] = f"{type(exc).__name__}: {exc}"
                failed.append({"page": resources_path.parent.name, "path": str(raw_path), "error": item["error"]})
                changed = True
                print(f"failed {resources_path.parent.name}/{raw_path.name}: {item['error']}", flush=True)
        if changed:
            write_json(resources_path, resources)
    result = {"checked": checked, "bad": bad, "repaired": repaired, "failed": len(failed), "failed_examples": failed[:20]}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
