"""GitHub fetcher — repo README + metadata via REST API.

Unauthenticated (60 req/h shared). For owner/repo URLs we fetch:
  GET /repos/{o}/{r}            (description, topics, stars)
  GET /repos/{o}/{r}/readme     (with Accept: application/vnd.github.raw)

For non-repo URLs (issues, gist, user pages) we fall back to generic.
"""

from __future__ import annotations

import re
import urllib.parse

import requests

from . import generic

API = "https://api.github.com"
TIMEOUT = 20
MAX_TEXT = 12000

_REPO_RE = re.compile(r"^/([^/]+)/([^/]+)(?:/.*)?$")


def _parse_repo(link: str) -> tuple[str, str] | None:
    p = urllib.parse.urlparse(link)
    if p.netloc.lower() not in ("github.com", "www.github.com"):
        return None
    m = _REPO_RE.match(p.path)
    if not m:
        return None
    owner, repo = m.group(1), m.group(2)
    if owner in ("orgs", "users", "topics", "marketplace", "settings", "features"):
        return None
    repo = repo.removesuffix(".git")
    return owner, repo


def fetch(link: str, raindrop: dict | None = None) -> dict:
    parsed = _parse_repo(link)
    if not parsed:
        # gist or user/org page — let generic handle it
        return generic.fetch(link, raindrop)
    owner, repo = parsed
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "raindrop-infer",
    }
    try:
        rr = requests.get(f"{API}/repos/{owner}/{repo}", headers=headers, timeout=TIMEOUT)
    except Exception as e:
        return {"status": "failed", "fetcher": "github",
                "text": "", "meta": {"final_url": link},
                "error": f"repo request: {e}"}
    if rr.status_code == 404:
        return {"status": "failed", "fetcher": "github",
                "text": "", "meta": {"final_url": link, "repo": f"{owner}/{repo}"},
                "error": "repo not found"}
    if rr.status_code >= 400:
        return {"status": "failed", "fetcher": "github",
                "text": "", "meta": {"final_url": link, "repo": f"{owner}/{repo}"},
                "error": f"repo http {rr.status_code}: {rr.text[:200]}"}
    repo_meta = rr.json()

    # readme — raw text via Accept header
    readme_text = ""
    try:
        h2 = dict(headers, **{"Accept": "application/vnd.github.raw"})
        rd = requests.get(f"{API}/repos/{owner}/{repo}/readme", headers=h2, timeout=TIMEOUT)
        if rd.status_code == 200:
            readme_text = rd.text
    except Exception:
        readme_text = ""

    parts = [
        f"[Repo] {owner}/{repo}",
        f"[Description] {repo_meta.get('description') or ''}",
        f"[Stars] {repo_meta.get('stargazers_count')}",
        f"[Language] {repo_meta.get('language')}",
        f"[Topics] {', '.join(repo_meta.get('topics') or [])}",
        f"[Updated] {repo_meta.get('updated_at')}",
        f"[License] {(repo_meta.get('license') or {}).get('spdx_id')}",
    ]
    if readme_text:
        parts.append("[README]")
        parts.append(readme_text)
    text = "\n".join(parts)[:MAX_TEXT]
    return {
        "status": "ok" if readme_text else "partial",
        "fetcher": "github",
        "text": text,
        "meta": {
            "final_url": link,
            "github": {
                "repo": f"{owner}/{repo}",
                "stars": repo_meta.get("stargazers_count"),
                "language": repo_meta.get("language"),
                "topics": repo_meta.get("topics"),
                "updated_at": repo_meta.get("updated_at"),
            },
        },
    }
