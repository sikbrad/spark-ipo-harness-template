"""Raindrop.io REST API thin wrapper — pagination + 429 backoff.

All return values are raw `dict` from `response.json()` (no schema massaging).

Usage:
    from raindrop_api import RaindropClient
    c = RaindropClient.from_env()
    for col in c.collections_iter():
        ...
    for rd in c.raindrops_iter(collection_id=-1, sort="-lastUpdate"):
        ...

Docs: https://developer.raindrop.io/v1/
Rate limit: 120 req/min per user → MIN_INTERVAL_SEC = 0.5
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Iterator

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from raindrop_auth import access_token  # noqa: E402

API_ROOT = "https://api.raindrop.io/rest/v1"
DEFAULT_PERPAGE = 50            # raindrop max per page for /raindrops endpoint
MIN_INTERVAL_SEC = 0.51         # ~120 req/min — be a touch under to avoid 429
MAX_RETRIES = 6


class RaindropError(Exception):
    def __init__(self, status: int, method: str, path: str, body: str):
        self.status = status
        self.method = method
        self.path = path
        self.body = body
        super().__init__(f"[{status}] {method} {path} :: {body[:300]}")


class RaindropClient:
    def __init__(self, token: str):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
        )
        self._last_ts = 0.0

    @classmethod
    def from_env(cls) -> "RaindropClient":
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
                wait = float(r.headers.get("Retry-After", "2")) + 0.5
                time.sleep(wait)
                continue
            if 500 <= r.status_code < 600:
                time.sleep(min(2 ** attempt, 30))
                continue
            if r.status_code >= 400:
                raise RaindropError(r.status_code, method, path, r.text)
            return r.json()
        raise RaindropError(0, method, path, "max retries exceeded")

    # ───────────────────── user ─────────────────────

    def user_me(self) -> dict:
        return self.request("GET", "/user")

    # ───────────────────── collections ─────────────────────

    def collections_root(self) -> dict:
        """Root-level collections."""
        return self.request("GET", "/collections")

    def collections_children(self) -> dict:
        """Nested (child) collections — single response, no pagination."""
        return self.request("GET", "/collections/childrens")

    def collections_iter(self) -> Iterator[dict]:
        """Yield every collection (root + nested)."""
        for resp in (self.collections_root(), self.collections_children()):
            for item in resp.get("items", []):
                yield item

    def collection_retrieve(self, cid: int) -> dict:
        return self.request("GET", f"/collection/{cid}")

    # ───────────────────── raindrops ─────────────────────

    def raindrops_page(
        self,
        collection_id: int,
        *,
        page: int = 0,
        perpage: int = DEFAULT_PERPAGE,
        sort: str = "-lastUpdate",
        search: str | None = None,
    ) -> dict:
        params: dict = {"page": page, "perpage": perpage, "sort": sort}
        if search:
            params["search"] = search
        return self.request("GET", f"/raindrops/{collection_id}", params=params)

    def raindrops_iter(
        self,
        collection_id: int = -1,
        *,
        sort: str = "-lastUpdate",
        perpage: int = DEFAULT_PERPAGE,
        search: str | None = None,
    ) -> Iterator[dict]:
        """Yield raindrops from a collection in sorted order, paginating."""
        page = 0
        while True:
            data = self.raindrops_page(
                collection_id, page=page, perpage=perpage, sort=sort, search=search
            )
            items = data.get("items", [])
            for item in items:
                yield item
            if len(items) < perpage:
                return
            page += 1

    def raindrops_iter_with_meta(
        self,
        collection_id: int = -1,
        *,
        sort: str = "-lastUpdate",
        perpage: int = DEFAULT_PERPAGE,
        search: str | None = None,
    ) -> Iterator[tuple[dict, int, int]]:
        """Like raindrops_iter but also yields (item, page_index, position_in_page).

        Lets the caller make per-page stop decisions (smart-resume)."""
        page = 0
        while True:
            data = self.raindrops_page(
                collection_id, page=page, perpage=perpage, sort=sort, search=search
            )
            items = data.get("items", [])
            for i, item in enumerate(items):
                yield item, page, i
            if len(items) < perpage:
                return
            page += 1

    def raindrop_retrieve(self, rid: int) -> dict:
        return self.request("GET", f"/raindrop/{rid}")

    # ───────────────────── tags ─────────────────────

    def tags(self, collection_id: int | None = None) -> dict:
        path = "/tags" if collection_id is None else f"/tags/{collection_id}"
        return self.request("GET", path)
