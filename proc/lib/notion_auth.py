"""Notion OAuth helper — `.env` based public-integration login.

`.env` keys:
    NOTION_OAUTH_CLIENT_ID    UUID
    NOTION_OAUTH_CLIENT_PW    `secret_…` client secret
    NOTION_OAUTH_AUTH_URL     full authorize URL (with redirect_uri placeholder)

Token cache: ~/.cache/dof-notion/token.json

CLI:
    python proc/lib/notion_auth.py login          # interactive OAuth
    python proc/lib/notion_auth.py token          # print cached access_token
    python proc/lib/notion_auth.py whoami         # GET /users/me
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.parse
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = REPO_ROOT / ".env"
CACHE_DIR = Path.home() / ".cache" / "dof-notion"
TOKEN_PATH = CACHE_DIR / "token.json"

NOTION_VERSION = "2025-09-03"
TOKEN_URL = "https://api.notion.com/v1/oauth/token"


def _load_env() -> dict[str, str]:
    if not ENV_PATH.exists():
        raise FileNotFoundError(f".env not found at {ENV_PATH}")
    out: dict[str, str] = {}
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        v = v.strip().strip('"').strip("'")
        out[k.strip()] = v
    return out


def _basic_auth_header(client_id: str, client_secret: str) -> str:
    raw = f"{client_id}:{client_secret}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


def _redirect_uri_from_auth_url(auth_url: str) -> str:
    parsed = urllib.parse.urlparse(auth_url)
    qs = urllib.parse.parse_qs(parsed.query)
    if "redirect_uri" not in qs:
        raise ValueError("AUTH_URL has no redirect_uri parameter")
    return qs["redirect_uri"][0]


def _extract_code(text: str) -> str:
    """Accept either bare code or full redirect URL containing ?code=...&state=..."""
    text = text.strip()
    if "code=" in text:
        parsed = urllib.parse.urlparse(text)
        qs = urllib.parse.parse_qs(parsed.query)
        if "code" in qs:
            return qs["code"][0]
    return text


def save_token(payload: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    try:
        os.chmod(TOKEN_PATH, 0o600)
    except OSError:
        pass


def load_token() -> dict:
    if not TOKEN_PATH.exists():
        raise FileNotFoundError(
            f"No cached Notion token at {TOKEN_PATH}. Run: "
            f"python proc/lib/notion_auth.py login"
        )
    return json.loads(TOKEN_PATH.read_text(encoding="utf-8"))


# Order of resolution for an API token:
#   1) explicit env var NOTION_TOKEN (process env)
#   2) .env keys NOTION_INTEG_ACCESS_TOKEN_*  (internal integration)
#   3) .env key NOTION_TOKEN                  (any name caller chose)
#   4) cached OAuth access_token              (~/.cache/dof-notion/token.json)
TOKEN_ENV_PREFIX = "NOTION_INTEG_ACCESS_TOKEN_"


def access_token() -> str:
    proc_env = os.environ.get("NOTION_TOKEN")
    if proc_env:
        return proc_env
    try:
        env = _load_env()
    except FileNotFoundError:
        env = {}
    for k, v in env.items():
        if k.startswith(TOKEN_ENV_PREFIX) and v:
            return v
    if env.get("NOTION_TOKEN"):
        return env["NOTION_TOKEN"]
    return load_token()["access_token"]


def login() -> dict:
    env = _load_env()
    cid = env.get("NOTION_OAUTH_CLIENT_ID")
    cpw = env.get("NOTION_OAUTH_CLIENT_PW")
    auth_url = env.get("NOTION_OAUTH_AUTH_URL")
    if not (cid and cpw and auth_url):
        raise RuntimeError(
            "Missing NOTION_OAUTH_CLIENT_ID / NOTION_OAUTH_CLIENT_PW / NOTION_OAUTH_AUTH_URL in .env"
        )
    redirect_uri = _redirect_uri_from_auth_url(auth_url)

    print()
    print("=" * 78)
    print("Notion OAuth — open this URL in a browser:")
    print()
    print(auth_url)
    print()
    print("→ Choose the workspace and explicitly share the pages you want")
    print("  (must include 'Quick My Ocean' + 'Databases' subtree).")
    print(f"→ Notion will redirect to {redirect_uri}/?code=XXX&state=...")
    print("  The page will fail to load (placeholder host) — that is expected.")
    print("  Copy the FULL redirected URL from the address bar (or just the code=XXX value).")
    print("=" * 78)
    print()
    raw = input("Paste redirect URL or code: ").strip()
    code = _extract_code(raw)
    if not code:
        raise RuntimeError("Empty auth code")

    r = requests.post(
        TOKEN_URL,
        headers={
            "Authorization": _basic_auth_header(cid, cpw),
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        },
        json={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
        },
        timeout=30,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Token exchange failed [{r.status_code}]: {r.text}")
    payload = r.json()
    save_token(payload)
    print(f"✓ Token saved → {TOKEN_PATH}")
    print(f"  workspace_name : {payload.get('workspace_name')}")
    print(f"  workspace_id   : {payload.get('workspace_id')}")
    print(f"  bot_id         : {payload.get('bot_id')}")
    return payload


def whoami() -> dict:
    tok = access_token()
    r = requests.get(
        "https://api.notion.com/v1/users/me",
        headers={
            "Authorization": f"Bearer {tok}",
            "Notion-Version": NOTION_VERSION,
        },
        timeout=20,
    )
    r.raise_for_status()
    data = r.json()
    print(json.dumps(data, indent=2, ensure_ascii=False))
    return data


def _main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Notion OAuth helper")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("login", help="run OAuth code-exchange flow")
    sub.add_parser("token", help="print cached access_token")
    sub.add_parser("whoami", help="GET /users/me with cached token")
    args = p.parse_args(argv)
    if args.cmd == "login":
        login()
    elif args.cmd == "token":
        print(access_token())
    elif args.cmd == "whoami":
        whoami()
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
