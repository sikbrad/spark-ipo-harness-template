"""Raindrop.io auth helper — `.env` based personal token (test token) loader.

`.env` keys:
    RAINDROP_TEST_TOKEN     personal test token from raindrop.io app settings
    RAINDROP_CLIENT_ID      OAuth client id (reserved — not used by test token path)
    RAINDROP_CLIENT_SECRET  OAuth client secret (reserved)

Resolution order for an API token:
    1) process env  RAINDROP_TOKEN
    2) .env         RAINDROP_TEST_TOKEN
    3) .env         RAINDROP_TOKEN

CLI:
    python proc/lib/raindrop_auth.py token   # print resolved token
    python proc/lib/raindrop_auth.py whoami  # GET /user
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = REPO_ROOT / ".env"


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


def access_token() -> str:
    proc_env = os.environ.get("RAINDROP_TOKEN")
    if proc_env:
        return proc_env
    try:
        env = _load_env()
    except FileNotFoundError:
        env = {}
    for key in ("RAINDROP_TEST_TOKEN", "RAINDROP_TOKEN"):
        if env.get(key):
            return env[key]
    raise RuntimeError(
        "No Raindrop token found. Set RAINDROP_TEST_TOKEN in .env "
        "(raindrop.io → Settings → Integrations → For developers → Create new app → Test token)."
    )


def whoami() -> dict:
    tok = access_token()
    r = requests.get(
        "https://api.raindrop.io/rest/v1/user",
        headers={"Authorization": f"Bearer {tok}"},
        timeout=20,
    )
    r.raise_for_status()
    data = r.json()
    print(json.dumps(data, indent=2, ensure_ascii=False))
    return data


def _main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Raindrop.io auth helper")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("token", help="print resolved token")
    sub.add_parser("whoami", help="GET /user with token")
    args = p.parse_args(argv)
    if args.cmd == "token":
        print(access_token())
    elif args.cmd == "whoami":
        whoami()
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
