"""Notion REST API thin wrapper — pagination + 429 backoff.

All return values are raw `dict` from `response.json()` (no schema massaging).

Usage:
    from notion_api import NotionClient
    c = NotionClient.from_cache()
    page = c.pages_retrieve(page_id)
    for child in c.blocks_children_iter(page_id):
        ...
    db_meta = c.databases_retrieve(db_id)
    for row in c.databases_query_iter(db_id):
        ...
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Iterator

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from notion_auth import NOTION_VERSION, access_token  # noqa: E402

API_ROOT = "https://api.notion.com/v1"
DEFAULT_PAGE_SIZE = 100
MIN_INTERVAL_SEC = 0.34   # ~3 req/s, Notion's documented average rate-limit
MAX_RETRIES = 6


def normalize_id(uid: str) -> str:
    """Accept dashed or hex UUID, return dashed canonical form."""
    s = uid.strip().replace("-", "")
    if len(s) != 32:
        raise ValueError(f"Bad Notion id: {uid!r}")
    return f"{s[0:8]}-{s[8:12]}-{s[12:16]}-{s[16:20]}-{s[20:32]}"


class NotionClient:
    def __init__(self, token: str, *, version: str = NOTION_VERSION):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Notion-Version": version,
                "Content-Type": "application/json",
            }
        )
        self._last_ts = 0.0

    @classmethod
    def from_cache(cls) -> "NotionClient":
        return cls(access_token())

    # ───────────────────── core HTTP ─────────────────────

    def _throttle(self) -> None:
        delta = time.monotonic() - self._last_ts
        if delta < MIN_INTERVAL_SEC:
            time.sleep(MIN_INTERVAL_SEC - delta)
        self._last_ts = time.monotonic()

    def request(self, method: str, path: str, *, params=None, json=None) -> dict:
        url = f"{API_ROOT}{path}"
        for attempt in range(MAX_RETRIES):
            self._throttle()
            r = self.session.request(method, url, params=params, json=json, timeout=30)
            if r.status_code == 429:
                wait = float(r.headers.get("Retry-After", "1")) + 0.5
                time.sleep(wait)
                continue
            if 500 <= r.status_code < 600:
                time.sleep(min(2 ** attempt, 30))
                continue
            if r.status_code >= 400:
                raise NotionError(r.status_code, method, path, r.text)
            return r.json()
        raise NotionError(0, method, path, "max retries exceeded")

    # ───────────────────── endpoints ─────────────────────

    def pages_retrieve(self, page_id: str) -> dict:
        return self.request("GET", f"/pages/{normalize_id(page_id)}")

    def databases_retrieve(self, db_id: str) -> dict:
        return self.request("GET", f"/databases/{normalize_id(db_id)}")

    def blocks_retrieve(self, block_id: str) -> dict:
        return self.request("GET", f"/blocks/{normalize_id(block_id)}")

    def blocks_children_iter(self, block_id: str) -> Iterator[dict]:
        cursor: str | None = None
        while True:
            params = {"page_size": DEFAULT_PAGE_SIZE}
            if cursor:
                params["start_cursor"] = cursor
            data = self.request(
                "GET", f"/blocks/{normalize_id(block_id)}/children", params=params
            )
            for item in data.get("results", []):
                yield item
            if not data.get("has_more"):
                return
            cursor = data.get("next_cursor")

    def data_sources_retrieve(self, ds_id: str) -> dict:
        return self.request("GET", f"/data_sources/{normalize_id(ds_id)}")

    def data_sources_query_iter(self, ds_id: str) -> Iterator[dict]:
        cursor: str | None = None
        while True:
            body: dict = {"page_size": DEFAULT_PAGE_SIZE}
            if cursor:
                body["start_cursor"] = cursor
            data = self.request(
                "POST", f"/data_sources/{normalize_id(ds_id)}/query", json=body
            )
            for item in data.get("results", []):
                yield item
            if not data.get("has_more"):
                return
            cursor = data.get("next_cursor")


class NotionError(Exception):
    def __init__(self, status: int, method: str, path: str, body: str):
        self.status = status
        self.method = method
        self.path = path
        self.body = body
        super().__init__(f"[{status}] {method} {path} :: {body[:300]}")
