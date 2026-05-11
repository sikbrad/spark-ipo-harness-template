"""Stub fetchers for sites behind a login wall (Threads / Instagram / LinkedIn).

MVP behavior: try plain requests for OG metadata (works because Threads/IG/LI
all serve sociable OG tags to unauthenticated GETs). Mark status='partial'
with auth-required note so the driver can later swap in a pwc session.

The raindrop's own `title` + `excerpt` + `tags` carry significant info, so
the LLM prompt still has enough to produce a useful summary.
"""

from __future__ import annotations

from . import generic


def _wrap(fetcher_name: str, link: str, raindrop: dict | None) -> dict:
    r = generic.fetch(link, raindrop)
    r["fetcher"] = fetcher_name
    # All three sites mostly return only OG meta to unauth requests.
    # Mark partial regardless of generic.status so the driver knows.
    if r["status"] == "ok":
        r["status"] = "partial"
    r.setdefault("meta", {})
    r["meta"]["auth_wall"] = True
    return r


def fetch_threads(link: str, raindrop: dict | None = None) -> dict:
    return _wrap("threads", link, raindrop)


def fetch_instagram(link: str, raindrop: dict | None = None) -> dict:
    return _wrap("instagram", link, raindrop)


def fetch_linkedin(link: str, raindrop: dict | None = None) -> dict:
    return _wrap("linkedin", link, raindrop)
