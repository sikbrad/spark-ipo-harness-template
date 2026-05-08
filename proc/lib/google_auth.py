"""Google OAuth client for Gmail + Calendar APIs (per-account).

Two personal Google accounts are configured (registered 2026-05-08, see
proc/plan/2026-05-08_google-gmail-calendar-access.md):

| account   | env prefix         | project ID              |
|-----------|--------------------|-------------------------|
| bispro89  | GOOGLE_BISPRO89_*  | bold-bastion-495705-i4  |
| sikbrad   | GOOGLE_SIKBRAD_*   | pelagic-pod-495705-r2   |

Each account has its own GCP project (Production, External), Desktop OAuth
client, and token cache file.

Usage:
    from google_auth import GoogleClient
    g = GoogleClient('bispro89')                  # silent refresh if cached
    gmail = g.service('gmail', 'v1')
    profile = gmail.users().getProfile(userId='me').execute()

CLI:
    python proc/lib/google_auth.py login --account bispro89
    python proc/lib/google_auth.py whoami --account sikbrad
    python proc/lib/google_auth.py logout --account bispro89

First-time login opens a browser for OAuth consent. After that, the refresh
token in ~/.cache/dof-google-{account}.json keeps things headless.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Iterable, Optional

# Google's token endpoint normalizes scopes (collapses duplicates, reorders)
# and oauthlib treats "scope changed" as a Warning that requests_oauthlib
# raises as an exception. Relaxing this is the canonical workaround for
# Google OAuth — see https://github.com/googleapis/google-auth-library-python-oauthlib/issues/13
os.environ.setdefault('OAUTHLIB_RELAX_TOKEN_SCOPE', '1')

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


# Account aliases → env prefix. Add new accounts here.
_ACCOUNTS = {
    'bispro89': 'GOOGLE_BISPRO89',
    'sikbrad': 'GOOGLE_SIKBRAD',
}

# Default scope set — full read/write across Gmail/Calendar/Drive + identity.
# `gmail.modify` covers read + labels + drafts (NOT send, NOT permanent delete);
# `gmail.send` adds send. `calendar` and `drive` are full read+write.
# All four are "restricted/sensitive" tier — first-consent shows "unverified app"
# warning, but works for self-use after Advanced > Continue.
# Override per-call via `scopes=` if you want narrower.
_DEFAULT_SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/drive',
    'openid',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
]


def _load_env() -> dict:
    """Read .env keys without requiring python-dotenv."""
    env: dict = {}
    p = Path('.env')
    if not p.exists():
        return env
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


class GoogleClientError(RuntimeError):
    pass


class GoogleClient:
    """Thin wrapper around google-auth + googleapiclient.

    Pass `account='bispro89'` (or 'sikbrad'); the constructor pulls
    `GOOGLE_BISPRO89_CLIENT_ID` / `..._CLIENT_SECRET` / `..._TOKEN_PATH` from
    `.env` (or process env). On first call it runs `InstalledAppFlow.run_local_server`
    (browser pops, user consents); subsequent calls refresh silently.
    """

    def __init__(
        self,
        account: str,
        scopes: Optional[Iterable[str]] = None,
        token_path: Optional[Path] = None,
    ):
        if account not in _ACCOUNTS:
            raise GoogleClientError(
                f'Unknown account {account!r}. Known: {sorted(_ACCOUNTS)}'
            )
        self.account = account
        prefix = _ACCOUNTS[account]
        env = _load_env()

        def _get(key: str) -> Optional[str]:
            full = f'{prefix}_{key}'
            return env.get(full) or os.environ.get(full)

        self.client_id = _get('CLIENT_ID')
        self.client_secret = _get('CLIENT_SECRET')
        self.project_id = _get('PROJECT_ID')
        token_env = _get('TOKEN_PATH')
        if not (self.client_id and self.client_secret):
            raise GoogleClientError(
                f'Missing {prefix}_CLIENT_ID / {prefix}_CLIENT_SECRET '
                '(checked .env and process env).'
            )

        if token_path:
            self.token_path = Path(token_path)
        elif token_env:
            self.token_path = Path(token_env)
        else:
            self.token_path = Path.home() / '.cache' / f'dof-google-{account}.json'

        self.scopes = list(scopes) if scopes else list(_DEFAULT_SCOPES)
        self._creds: Optional[Credentials] = None

    # ---- token lifecycle

    def _client_config(self) -> dict:
        """Synthesize the credentials.json shape from env values."""
        return {
            'installed': {
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'project_id': self.project_id or '',
                'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
                'token_uri': 'https://oauth2.googleapis.com/token',
                'auth_provider_x509_cert_url': 'https://www.googleapis.com/oauth2/v1/certs',
                'redirect_uris': ['http://localhost'],
            }
        }

    def _save(self, creds: Credentials) -> None:
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        self.token_path.write_text(creds.to_json())
        try:
            os.chmod(self.token_path, 0o600)
        except OSError:
            pass

    def credentials(self) -> Credentials:
        """Return valid Credentials. Refreshes silently if possible.

        Raises if no cached token AND no interactive session is available
        (call `login()` explicitly when you want the browser to open).
        """
        if self._creds and self._creds.valid:
            return self._creds

        creds: Optional[Credentials] = None
        if self.token_path.exists():
            creds = Credentials.from_authorized_user_file(str(self.token_path), self.scopes)

        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            self._save(creds)

        if not creds or not creds.valid:
            raise GoogleClientError(
                f'No valid token for account={self.account!r}. '
                f'Run: python proc/lib/google_auth.py login --account {self.account}'
            )

        self._creds = creds
        return creds

    def login(self) -> Credentials:
        """Run the full OAuth flow (browser pops). Saves token cache."""
        flow = InstalledAppFlow.from_client_config(self._client_config(), self.scopes)
        creds = flow.run_local_server(port=0, open_browser=True, prompt='consent')
        self._save(creds)
        self._creds = creds
        return creds

    def logout(self) -> bool:
        """Delete the cached token. Returns True if a file was removed."""
        if self.token_path.exists():
            self.token_path.unlink()
            self._creds = None
            return True
        return False

    # ---- API services

    def service(self, api: str, version: str):
        """Build a Google API service (gmail/calendar/oauth2/people/etc)."""
        return build(api, version, credentials=self.credentials(), cache_discovery=False)

    def whoami(self) -> dict:
        """Resolve identity via OAuth2 userinfo endpoint."""
        svc = self.service('oauth2', 'v2')
        return svc.userinfo().get().execute()


# ---- CLI


def _parse_scopes(arg: Optional[str]) -> Optional[list[str]]:
    if not arg:
        return None
    out = []
    for raw in arg.split(','):
        s = raw.strip()
        if not s:
            continue
        if not s.startswith('http'):
            # Allow shortform like 'gmail.readonly' or 'calendar.events'.
            s = f'https://www.googleapis.com/auth/{s}'
        out.append(s)
    return out


def _cmd_login(args) -> int:
    g = GoogleClient(args.account, scopes=_parse_scopes(args.scopes))
    print(f'Account : {g.account}')
    print(f'Project : {g.project_id}')
    print(f'Client  : {g.client_id}')
    print(f'Token   : {g.token_path}')
    print(f'Scopes  : {len(g.scopes)} ({", ".join(s.split("/")[-1] for s in g.scopes)})')
    print('Opening browser for OAuth consent...')
    g.login()
    me = g.whoami()
    print(f'OK. Logged in as: {me.get("name")} <{me.get("email")}>')
    return 0


def _cmd_whoami(args) -> int:
    g = GoogleClient(args.account, scopes=_parse_scopes(args.scopes))
    me = g.whoami()
    print(json.dumps(me, indent=2, ensure_ascii=False))
    return 0


def _cmd_logout(args) -> int:
    g = GoogleClient(args.account, scopes=_parse_scopes(args.scopes))
    removed = g.logout()
    print(f'{"Removed" if removed else "No cache at"}: {g.token_path}')
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog='google_auth')
    sub = parser.add_subparsers(dest='cmd', required=True)
    for name in ('login', 'whoami', 'logout'):
        sp = sub.add_parser(name)
        sp.add_argument('--account', required=True, choices=sorted(_ACCOUNTS))
        sp.add_argument('--scopes', help='Comma-separated; shortform OK (gmail.readonly)')

    args = parser.parse_args(argv[1:])
    return {
        'login': _cmd_login,
        'whoami': _cmd_whoami,
        'logout': _cmd_logout,
    }[args.cmd](args)


if __name__ == '__main__':
    sys.exit(main(sys.argv))
