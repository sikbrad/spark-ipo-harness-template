#!/usr/bin/env python3
"""Collect 본인's Jira + Confluence activity for ONE day.

Saves to data/daily/<day>/raw/atlassian.json. Run from project root:

    python3 proc/lib/daily_atlassian.py YYYY-MM-DD

Output structure:
{
  "jira": {
    "created":         [{key, summary, project, type, status, ...}],
    "updated_with_me": [{key, summary, ...}],   # assignee or reporter & updated today
    "my_comments":     [{issueKey, ts, body, ...}],
    "my_changes":      [{issueKey, ts, items}]  # status / assignee / rank changes
  },
  "confluence": {
    "created":  [{id, title, space, ...}],
    "updated":  [{id, title, ...}],
    "comments": [{id, title, ...}]
  }
}

Filters target the current user (resolved from ATLASSIAN_EMAIL token).
KST day windows used for both Jira (JQL) and Confluence (CQL is UTC-internal
but we convert).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime as _dt
from pathlib import Path

sys.path.insert(0, 'proc/lib')
from atlassian_api import (  # noqa: E402
    AtlassianClient,
    SITE,
    kst_day_range,
    jql_date,
    cql_date,
)


def _flat_adf(node) -> str:
    parts = []
    if isinstance(node, dict):
        if node.get('type') == 'text':
            parts.append(node.get('text', ''))
        for ch in node.get('content', []) or []:
            parts.append(_flat_adf(ch))
    elif isinstance(node, list):
        for ch in node:
            parts.append(_flat_adf(ch))
    return ''.join(parts)


def _slim_issue(issue: dict) -> dict:
    f = issue.get('fields', {}) or {}
    return {
        'key': issue.get('key'),
        'summary': f.get('summary', ''),
        'project': (f.get('project') or {}).get('key', ''),
        'type': (f.get('issuetype') or {}).get('name', ''),
        'status': (f.get('status') or {}).get('name', ''),
        'created': f.get('created', ''),
        'updated': f.get('updated', ''),
        'creator': (f.get('creator') or {}).get('displayName', ''),
        'reporter': (f.get('reporter') or {}).get('displayName', ''),
        'assignee': (f.get('assignee') or {}).get('displayName', '') if f.get('assignee') else '',
        'url': f'https://{SITE}/browse/{issue.get("key")}',
    }


def collect_jira(c: AtlassianClient, day: str) -> dict:
    since, until = kst_day_range(day)
    s, u = jql_date(since), jql_date(until)

    created = c.jira_search(
        f'creator = currentUser() AND created >= "{s}" AND created < "{u}"',
    )
    updated_with_me = c.jira_search(
        f'(assignee = currentUser() OR reporter = currentUser()) '
        f'AND updated >= "{s}" AND updated < "{u}"',
    )

    j_created = [_slim_issue(x) for x in created if isinstance(x, dict) and x.get('key')]
    j_updated = [_slim_issue(x) for x in updated_with_me if isinstance(x, dict) and x.get('key')]

    me_id = c.account_id
    my_comments: list[dict] = []
    my_changes: list[dict] = []
    keys = sorted({x['key'] for x in j_created + j_updated if x.get('key')})

    for key in keys:
        for cm in c.jira_issue_comments(key):
            if (cm.get('author') or {}).get('accountId') != me_id:
                continue
            ts = cm.get('created', '')
            try:
                t = _dt.fromisoformat(ts.replace('Z', '+00:00'))
            except Exception:
                continue
            if not (since <= t < until):
                continue
            body = cm.get('body')
            text = _flat_adf(body) if isinstance(body, dict) else (body or '')
            my_comments.append({
                'issueKey': key,
                'ts': ts,
                'body': text[:2000],
                'url': f'https://{SITE}/browse/{key}',
            })
        for ch in c.jira_issue_changelog(key):
            if (ch.get('author') or {}).get('accountId') != me_id:
                continue
            ts = ch.get('created', '')
            try:
                t = _dt.fromisoformat(ts.replace('Z', '+00:00'))
            except Exception:
                continue
            if not (since <= t < until):
                continue
            my_changes.append({
                'issueKey': key,
                'ts': ts,
                'items': [{
                    'field': it.get('field'),
                    'from': it.get('fromString') or it.get('from'),
                    'to': it.get('toString') or it.get('to'),
                } for it in (ch.get('items') or [])],
                'url': f'https://{SITE}/browse/{key}',
            })

    return {
        'created': j_created,
        'updated_with_me': j_updated,
        'my_comments': my_comments,
        'my_changes': my_changes,
    }


def _slim_conf(it: dict) -> dict:
    if not isinstance(it, dict) or it.get('_error'):
        return {}
    co = it.get('content') or {}
    sp = co.get('space') or {}
    hist = co.get('history') or {}
    cb = hist.get('createdBy') or {}
    ver = co.get('version') or {}
    vb = ver.get('by') or {}
    url = it.get('url') or ''
    if url and not url.startswith('http'):
        url = f'https://{SITE}/wiki{url}'
    return {
        'id': co.get('id', ''),
        'title': co.get('title') or it.get('title', ''),
        'type': co.get('type', ''),
        'space': sp.get('key', ''),
        'spaceName': sp.get('name', ''),
        'createdAt': hist.get('createdDate', ''),
        'createdBy': cb.get('displayName', ''),
        'lastModifiedAt': ver.get('when', ''),
        'lastModifiedBy': vb.get('displayName', ''),
        'url': url,
    }


def collect_confluence(c: AtlassianClient, day: str) -> dict:
    since, until = kst_day_range(day)
    s_iso, u_iso = cql_date(since), cql_date(until)

    created = c.confluence_cql(
        f'creator = currentUser() AND type = page '
        f'AND created >= "{s_iso}" AND created < "{u_iso}"'
    )
    contributed = c.confluence_cql(
        f'contributor = currentUser() AND type = page '
        f'AND lastModified >= "{s_iso}" AND lastModified < "{u_iso}"'
    )
    comments = c.confluence_cql(
        f'creator = currentUser() AND type = comment '
        f'AND created >= "{s_iso}" AND created < "{u_iso}"'
    )

    return {
        'created':  [x for x in (_slim_conf(it) for it in created)     if x],
        'updated':  [x for x in (_slim_conf(it) for it in contributed) if x],
        'comments': [x for x in (_slim_conf(it) for it in comments)    if x],
    }


def main() -> None:
    if len(sys.argv) < 2:
        print('Usage: daily_atlassian.py YYYY-MM-DD')
        sys.exit(1)
    day = sys.argv[1]
    out = Path(f'data/daily/{day}/raw/atlassian.json')
    out.parent.mkdir(parents=True, exist_ok=True)

    try:
        c = AtlassianClient()
        payload = {
            'jira': collect_jira(c, day),
            'confluence': collect_confluence(c, day),
        }
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
        j = payload['jira']
        cf = payload['confluence']
        print(
            f'{day}: jira(created={len(j["created"])} '
            f'updated={len(j["updated_with_me"])} '
            f'cmts={len(j["my_comments"])} '
            f'changes={len(j["my_changes"])}) '
            f'conf(created={len(cf["created"])} '
            f'updated={len(cf["updated"])} '
            f'comments={len(cf["comments"])})'
        )
    except Exception as e:
        out.write_text(json.dumps({'error': f'{type(e).__name__}: {str(e)[:300]}'}, ensure_ascii=False))
        print(f'{day}: FAIL {e}')
        sys.exit(1)


if __name__ == '__main__':
    main()
