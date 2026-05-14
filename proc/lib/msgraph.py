"""Microsoft Graph client using MSAL device-code flow.

App registration (Entra admin center, single tenant):
- Client ID  : MSFT_MYAGENT_CLIENT_ID
- Tenant ID  : MSFT_MYAGENT_TENANT_ID
- Public client flows: enabled
- Delegated permissions: 150 scopes pre-consented (admin consent already granted)

Usage:
    from msgraph import GraphClient
    g = GraphClient()           # silent refresh if cached, else raises
    me = g.get('/me')
    chats = g.paged('/me/chats', params={'$top': 50})

First-time login (one-shot CLI):
    python proc/lib/msgraph.py login

Token cache lives at ~/.cache/dof-msgraph-msal.json. Refresh tokens are
sliding-window (~90d) — stays valid as long as used periodically.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Iterable, Iterator, Optional

import msal
import requests


GRAPH = 'https://graph.microsoft.com/v1.0'
AUTHORITY_BASE = 'https://login.microsoftonline.com'

# Cache lives in user-home, not repo, so it survives clones and isn't checked in.
_CACHE_PATH = Path.home() / '.cache' / 'dof-msgraph-msal.json'

# Scopes we registered. MSAL prepends `https://graph.microsoft.com/` automatically
# when the app is configured for Graph; the Bearer is for `aud=00000003-...`.
# We pass a SUPERSET we want; MSAL will request what's available.
# Keeping the list short here — admin consent was already granted, so any scope
# the app is registered for can be acquired silently after first login.
_DEFAULT_SCOPES = [
    # User & profile
    'User.Read',
    'User.ReadBasic.All',
    'People.Read',
    'Presence.Read',

    # Mail
    'Mail.ReadWrite',
    'Mail.ReadWrite.Shared',
    'Mail.Send',
    'Mail.Send.Shared',
    'MailboxSettings.ReadWrite',

    # Calendar
    'Calendars.ReadWrite',
    'Calendars.ReadWrite.Shared',

    # Contacts / Tasks / Notes
    'Contacts.ReadWrite',
    'Tasks.ReadWrite',
    'Notes.ReadWrite.All',

    # Files / Sites
    'Files.ReadWrite',
    'Files.ReadWrite.All',
    'Files.Read.All',
    'Sites.Read.All',
    'Sites.ReadWrite.All',

    # Teams chat
    'Chat.ReadWrite',
    'Chat.ReadWrite.All',
    'ChatMessage.Send',

    # Teams channel
    'Team.ReadBasic.All',
    'TeamMember.Read.All',
    'Channel.ReadBasic.All',
    'ChannelMessage.Read.All',
    'ChannelMessage.ReadWrite',  # PATCH / softDelete own channel messages
    'ChannelMessage.Send',
    'ChannelMember.Read.All',
    'ChannelMember.ReadWrite.All',  # add/remove private+shared channel members
    'TeamworkTag.Read',  # read Teams tag groups + their members

    # Online meetings
    'OnlineMeetings.ReadWrite',

    # Directory / Group
    'Group.Read.All',
    'Group.ReadWrite.All',
    'Directory.Read.All',

    # Places (conference rooms)
    'Place.Read.All',
]


def _load_env() -> dict:
    """Read .env keys we need without requiring python-dotenv."""
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


class GraphClientError(RuntimeError):
    pass


class GraphClient:
    """Thin Microsoft Graph wrapper with cached MSAL auth.

    Reads `MSFT_MYAGENT_CLIENT_ID` / `MSFT_MYAGENT_TENANT_ID` from `.env`
    (or process env). Token cache persists at `~/.cache/dof-msgraph-msal.json`.
    """

    def __init__(
        self,
        client_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        scopes: Optional[Iterable[str]] = None,
        cache_path: Optional[Path] = None,
    ):
        env = _load_env()
        self.client_id = client_id or env.get('MSFT_MYAGENT_CLIENT_ID') or os.environ.get('MSFT_MYAGENT_CLIENT_ID')
        self.tenant_id = tenant_id or env.get('MSFT_MYAGENT_TENANT_ID') or os.environ.get('MSFT_MYAGENT_TENANT_ID')
        if not self.client_id or not self.tenant_id:
            raise GraphClientError(
                'Missing MSFT_MYAGENT_CLIENT_ID / MSFT_MYAGENT_TENANT_ID '
                '(checked .env and process env).'
            )
        self.scopes = list(scopes) if scopes else list(_DEFAULT_SCOPES)
        self.cache_path = Path(cache_path) if cache_path else _CACHE_PATH
        self._cache = msal.SerializableTokenCache()
        if self.cache_path.exists():
            self._cache.deserialize(self.cache_path.read_text())
        self._app = msal.PublicClientApplication(
            client_id=self.client_id,
            authority=f'{AUTHORITY_BASE}/{self.tenant_id}',
            token_cache=self._cache,
        )

    # ---- token lifecycle

    def _save_cache(self) -> None:
        if self._cache.has_state_changed:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(self._cache.serialize())

    def _silent(self) -> Optional[dict]:
        accounts = self._app.get_accounts()
        if not accounts:
            return None
        return self._app.acquire_token_silent(self.scopes, account=accounts[0])

    def login(self, prompt_print=print) -> dict:
        """Run device code flow. Prints code+URL; user finishes on phone/web.
        Blocks until user finishes or timeout. Saves cache on success.
        """
        flow = self._app.initiate_device_flow(scopes=self.scopes)
        if 'user_code' not in flow:
            raise GraphClientError(f'device flow failed: {json.dumps(flow, ensure_ascii=False)}')
        prompt_print(flow['message'])
        result = self._app.acquire_token_by_device_flow(flow)
        if 'access_token' not in result:
            raise GraphClientError(f'login failed: {result.get("error_description") or result}')
        self._save_cache()
        return result

    def token(self) -> str:
        """Return a valid access token, refreshing silently when possible."""
        result = self._silent()
        if not result or 'access_token' not in result:
            raise GraphClientError(
                'No cached account or silent refresh failed. '
                'Run `python proc/lib/msgraph.py login` first.'
            )
        self._save_cache()
        return result['access_token']

    # ---- HTTP

    def _url(self, path_or_url: str) -> str:
        if path_or_url.startswith('http'):
            return path_or_url
        if not path_or_url.startswith('/'):
            path_or_url = '/' + path_or_url
        return GRAPH + path_or_url

    def _headers(self, extra: Optional[dict] = None) -> dict:
        h = {
            'Authorization': 'Bearer ' + self.token(),
            'Accept': 'application/json',
        }
        if extra:
            h.update(extra)
        return h

    def get(self, path: str, params: Optional[dict] = None, headers: Optional[dict] = None) -> Any:
        r = requests.get(self._url(path), params=params, headers=self._headers(headers), timeout=30)
        if not r.ok:
            raise GraphClientError(f'GET {path} failed [{r.status_code}]: {r.text[:300]}')
        if not r.content:
            return None
        return r.json()

    def post(self, path: str, json_body: Any = None, headers: Optional[dict] = None) -> Any:
        r = requests.post(
            self._url(path),
            json=json_body,
            headers=self._headers({'Content-Type': 'application/json', **(headers or {})}),
            timeout=30,
        )
        if not r.ok:
            raise GraphClientError(f'POST {path} failed [{r.status_code}]: {r.text[:300]}')
        return r.json() if r.content else None

    def patch(self, path: str, json_body: Any = None) -> Any:
        r = requests.patch(
            self._url(path),
            json=json_body,
            headers=self._headers({'Content-Type': 'application/json'}),
            timeout=30,
        )
        if not r.ok:
            raise GraphClientError(f'PATCH {path} failed [{r.status_code}]: {r.text[:300]}')
        return r.json() if r.content else None

    def delete(self, path: str) -> None:
        r = requests.delete(self._url(path), headers=self._headers(), timeout=30)
        if not r.ok:
            raise GraphClientError(f'DELETE {path} failed [{r.status_code}]: {r.text[:300]}')

    def paged(self, path: str, params: Optional[dict] = None) -> Iterator[dict]:
        """Iterate all items across @odata.nextLink pages."""
        url: Optional[str] = self._url(path)
        first = True
        while url:
            r = requests.get(
                url,
                params=params if first else None,
                headers=self._headers(),
                timeout=30,
            )
            if not r.ok:
                raise GraphClientError(f'GET {url} failed [{r.status_code}]: {r.text[:300]}')
            data = r.json()
            for item in data.get('value', []):
                yield item
            url = data.get('@odata.nextLink')
            first = False


# ---- CLI


def _cmd_login() -> int:
    g = GraphClient()
    print(f'Tenant : {g.tenant_id}')
    print(f'Client : {g.client_id}')
    print(f'Cache  : {g.cache_path}')
    print('Initiating device-code flow...')
    g.login()
    me = g.get('/me')
    print('OK. Logged in as:', me.get('displayName'), me.get('userPrincipalName'))
    return 0


def _cmd_whoami() -> int:
    g = GraphClient()
    me = g.get('/me')
    print(json.dumps(me, indent=2, ensure_ascii=False))
    return 0


def _cmd_logout() -> int:
    g = GraphClient()
    accounts = g._app.get_accounts()
    for a in accounts:
        g._app.remove_account(a)
    g._save_cache()
    print(f'Removed {len(accounts)} account(s) from cache.')
    return 0


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else 'login'
    handlers = {
        'login': _cmd_login,
        'whoami': _cmd_whoami,
        'logout': _cmd_logout,
    }
    h = handlers.get(cmd)
    if not h:
        print(f'Usage: python {argv[0]} {{login|whoami|logout}}', file=sys.stderr)
        return 2
    return h()


if __name__ == '__main__':
    sys.exit(main(sys.argv))
