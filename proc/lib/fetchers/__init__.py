"""Per-domain content fetchers for raindrop-infer.

Each fetcher exposes:

    def fetch(link: str, raindrop: dict) -> FetchResult

where FetchResult is a dict:

    {
        "status":  "ok" | "partial" | "auth-required" | "failed",
        "fetcher": "<name>",
        "text":    "<extracted content>",          # plain text, may be empty
        "meta":    {"final_url": ..., "extra": ...},
        "error":   "<optional error string>",
    }
"""

from __future__ import annotations

import urllib.parse


def domain_of(link: str) -> str:
    try:
        host = urllib.parse.urlparse(link).netloc.lower()
        return host.removeprefix("www.").removeprefix("m.")
    except Exception:
        return ""


def route(link: str) -> str:
    """Return the fetcher name to use for a given URL."""
    d = domain_of(link)
    if d in ("youtube.com", "youtu.be") or d.endswith(".youtube.com"):
        return "youtube"
    if d.endswith("github.com") or d == "raw.githubusercontent.com":
        return "github"
    if d == "share.google":
        return "share_google"
    if d == "threads.com" or d == "threads.net":
        return "threads"
    if d == "instagram.com":
        return "instagram"
    if d == "linkedin.com":
        return "linkedin"
    return "generic"
