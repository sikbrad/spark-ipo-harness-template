"""Atlassian Cloud (Jira + Confluence) API client.

Auth: Basic = email:API_token (id.atlassian.com tokens). Reads from .env
(`ATLASSIAN_EMAIL`, `ATLASSIAN_TOK`). Site URL is fixed to doflab.atlassian.net
because that's the only DOF Atlassian Cloud instance.

Scope: read-only daily-activity collection. JQL/CQL filters target "things
the current user created or modified on a given day" — pages, comments,
issues, issue-comments, and issue-changelog entries.
"""
from __future__ import annotations

import base64
import json
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

try:
    from dotenv import dotenv_values
except Exception:
    dotenv_values = None


SITE = "doflab.atlassian.net"
JIRA_BASE = f"https://{SITE}/rest/api/3"
CONF_BASE = f"https://{SITE}/wiki/rest/api"
CONF_V2_BASE = f"https://{SITE}/wiki/api/v2"
KST = timezone(timedelta(hours=9))


def _load_env() -> tuple[str, str]:
    env_path = Path('.env')
    if env_path.exists() and dotenv_values is not None:
        e = dotenv_values(str(env_path))
        email = e.get('ATLASSIAN_EMAIL')
        tok = e.get('ATLASSIAN_TOK')
        if email and tok:
            return email, tok
    import os
    email = os.environ.get('ATLASSIAN_EMAIL', '')
    tok = os.environ.get('ATLASSIAN_TOK', '')
    if not (email and tok):
        raise RuntimeError('ATLASSIAN_EMAIL / ATLASSIAN_TOK not set')
    return email, tok


@dataclass
class AtlassianClient:
    email: str = ''
    token: str = ''
    account_id: str = ''

    def __post_init__(self) -> None:
        if not (self.email and self.token):
            self.email, self.token = _load_env()
        if not self.account_id:
            me = self.get_json(f'{JIRA_BASE}/myself')
            self.account_id = me.get('accountId', '')

    def _auth_header(self) -> str:
        return 'Basic ' + base64.b64encode(f'{self.email}:{self.token}'.encode()).decode()

    def get_json(self, url: str, retries: int = 4) -> Any:
        last_err: Exception | None = None
        for attempt in range(retries):
            req = urllib.request.Request(url, headers={
                'Authorization': self._auth_header(),
                'Accept': 'application/json',
            })
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    return json.loads(r.read())
            except urllib.error.HTTPError as e:
                if e.code in (429, 502, 503, 504):
                    time.sleep(2 ** attempt)
                    last_err = e
                    continue
                if e.code in (400, 404):
                    return {'_error': f'HTTP {e.code}', '_body': e.read().decode('utf-8', 'replace')[:500]}
                raise
            except Exception as e:
                last_err = e
                time.sleep(2 ** attempt)
        raise RuntimeError(f'GET failed after retries: {url} :: {last_err}')

    # ---------- Jira ----------

    def jira_search(self, jql: str, fields: list[str] | None = None, max_total: int = 200) -> list[dict]:
        """JQL search via /rest/api/3/search/jql (paginated)."""
        out: list[dict] = []
        token: str | None = None
        fields = fields or ['summary', 'status', 'issuetype', 'project', 'created', 'updated',
                            'creator', 'reporter', 'assignee']
        while True:
            params = {'jql': jql, 'fields': ','.join(fields), 'maxResults': 100}
            if token:
                params['nextPageToken'] = token
            url = f'{JIRA_BASE}/search/jql?' + urllib.parse.urlencode(params)
            d = self.get_json(url)
            if isinstance(d, dict) and d.get('_error'):
                return [{'_error': d['_error'], '_body': d.get('_body', '')}]
            issues = d.get('issues', []) if isinstance(d, dict) else []
            out.extend(issues)
            if d.get('isLast') is True or not d.get('nextPageToken'):
                break
            token = d.get('nextPageToken')
            if len(out) >= max_total:
                break
        return out[:max_total]

    def jira_issue_comments(self, key: str) -> list[dict]:
        d = self.get_json(f'{JIRA_BASE}/issue/{key}/comment?maxResults=100')
        if isinstance(d, dict) and d.get('_error'):
            return []
        return d.get('comments', []) if isinstance(d, dict) else []

    def jira_issue_changelog(self, key: str) -> list[dict]:
        d = self.get_json(f'{JIRA_BASE}/issue/{key}/changelog?maxResults=100')
        if isinstance(d, dict) and d.get('_error'):
            return []
        return d.get('values', []) if isinstance(d, dict) else []

    # ---------- Confluence ----------

    def confluence_cql(self, cql: str, limit: int = 100) -> list[dict]:
        out: list[dict] = []
        start = 0
        while True:
            params = {'cql': cql, 'limit': limit, 'start': start,
                      'expand': 'content.history,content.version,content.space'}
            url = f'{CONF_BASE}/search?' + urllib.parse.urlencode(params)
            d = self.get_json(url)
            if isinstance(d, dict) and d.get('_error'):
                return [{'_error': d['_error'], '_body': d.get('_body', '')}]
            results = d.get('results', []) if isinstance(d, dict) else []
            out.extend(results)
            if len(results) < limit:
                break
            start += limit
            if start >= 500:
                break
        return out

    def confluence_page(self, page_id: str) -> dict:
        d = self.get_json(f'{CONF_V2_BASE}/pages/{page_id}?body-format=storage')
        return d if isinstance(d, dict) else {}


def kst_day_range(day_str: str) -> tuple[datetime, datetime]:
    """day_str = 'YYYY-MM-DD' -> (KST 00:00, next day KST 00:00)."""
    start = datetime.fromisoformat(f'{day_str}T00:00:00').replace(tzinfo=KST)
    return start, start + timedelta(days=1)


def jql_date(dt: datetime) -> str:
    """Jira accepts 'YYYY-MM-DD HH:mm' in instance time. We use YYYY/MM/DD HH:mm."""
    return dt.astimezone(KST).strftime('%Y-%m-%d %H:%M')


def cql_date(dt: datetime) -> str:
    """CQL accepts 'YYYY-MM-DD HH:mm' in UTC."""
    return dt.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M')
