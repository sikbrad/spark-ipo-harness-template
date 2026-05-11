"""share.google redirect resolver — resolve final URL, re-dispatch."""

from __future__ import annotations

import requests

from . import generic

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def resolve(link: str) -> str:
    try:
        r = requests.get(link, headers={"User-Agent": UA}, timeout=15,
                         allow_redirects=True)
        return r.url
    except Exception:
        return link


def fetch(link: str, raindrop: dict | None = None) -> dict:
    final = resolve(link)
    if final == link:
        return {"status": "failed", "fetcher": "share_google",
                "text": "", "meta": {"final_url": link},
                "error": "redirect did not resolve"}
    # delegate to generic for the resolved page; router could re-route by
    # domain, but for MVP we just use generic
    result = generic.fetch(final, raindrop)
    result.setdefault("meta", {})
    result["meta"]["original_url"] = link
    result["meta"]["final_url"] = final
    return result
