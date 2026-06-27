"""Generic web fetcher — plain `requests` + HTML→text. playwright fallback.

Strategy:
1. requests.get with a desktop UA. If 200 and HTML, strip to readable text.
2. If response is short (<400 chars) or non-HTML, fall back to playwright.
"""

from __future__ import annotations

import html
import re
import time
import urllib.parse

import requests

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")
TIMEOUT = 25
MAX_TEXT = 12000  # cap to control LLM token usage


_SCRIPT_RE = re.compile(r"<(script|style|noscript)\b[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t ]+")
_NL_RE = re.compile(r"\n{3,}")
_OG_RE = re.compile(
    r'<meta[^>]+(?:property|name)=["\'](og:[^"\']+|description|twitter:[^"\']+)["\'][^>]+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
_TITLE_RE = re.compile(r"<title[^>]*>([^<]+)</title>", re.IGNORECASE)


def _html_to_text(s: str) -> str:
    s = _SCRIPT_RE.sub(" ", s)
    s = _TAG_RE.sub("\n", s)
    s = html.unescape(s)
    s = _WS_RE.sub(" ", s)
    s = _NL_RE.sub("\n\n", s)
    return s.strip()


def _extract_meta(s: str) -> dict:
    meta = {}
    for k, v in _OG_RE.findall(s):
        meta[k.lower()] = html.unescape(v)
    m = _TITLE_RE.search(s)
    if m:
        meta["title"] = html.unescape(m.group(1).strip())
    return meta


def fetch(link: str, raindrop: dict | None = None) -> dict:
    headers = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        "Accept-Language": "ko,en;q=0.9",
    }
    try:
        r = requests.get(link, headers=headers, timeout=TIMEOUT, allow_redirects=True)
    except Exception as e:
        return {
            "status": "failed",
            "fetcher": "generic",
            "text": "",
            "meta": {"final_url": link},
            "error": f"request error: {type(e).__name__}: {e}",
        }
    final_url = r.url
    ctype = r.headers.get("Content-Type", "").lower()
    if r.status_code >= 400:
        return {
            "status": "failed",
            "fetcher": "generic",
            "text": "",
            "meta": {"final_url": final_url, "http_status": r.status_code,
                     "content_type": ctype},
            "error": f"http {r.status_code}",
        }
    if "html" not in ctype and "xml" not in ctype:
        return {
            "status": "partial",
            "fetcher": "generic",
            "text": r.text[:MAX_TEXT] if r.text else "",
            "meta": {"final_url": final_url, "content_type": ctype},
        }
    body = r.text
    meta = _extract_meta(body)
    text = _html_to_text(body)[:MAX_TEXT]
    status = "ok" if len(text) >= 400 else "partial"
    return {
        "status": status,
        "fetcher": "generic",
        "text": text,
        "meta": {"final_url": final_url, **{f"og_{k}": v for k, v in meta.items()}},
    }
