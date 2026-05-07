"""Microsoft Teams web helpers, ported from agent_helpers.py teams_* functions
to use the playwright-cli session wrapper (`pwc.S`).

Session convention: use S('teams') across the project. Bootstrap once with:
    playwright-cli -s=teams open https://teams.cloud.microsoft/ --persistent --headed
… then sign in via Microsoft Authenticator. After that, sessions persist on
disk and can be reused without re-login until the SSO refresh window expires.
"""

from __future__ import annotations

import html
import json
import re
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

from pwc import S


KST = timezone(timedelta(hours=9))


TEAMS_URL = 'https://teams.cloud.microsoft/'


def ready(s: S) -> bool:
    """True once the Teams app shell (left app bar) is rendered."""
    return bool(s.eval(
        '() => !!document.querySelector("[data-tid=\\"app-bar\\"]")'
        ' || !!document.querySelector("button[aria-label*=\\"Activity\\"]")'
        ' || !!document.querySelector("button[aria-label*=\\"활동\\"]")'
    ))


def open_activity(s: S) -> bool:
    """Click the Activity (bell) icon in the left app bar."""
    return bool(s.eval(r"""
    () => {
        const sels = [
            'button[aria-label*="Activity"]',
            'button[aria-label*="활동"]',
            '[data-tid="app-bar-activity"]'
        ];
        for (const x of sels) {
            const el = document.querySelector(x);
            if (el) { el.click(); return true; }
        }
        return false;
    }
    """))


def activity_items(s: S) -> list[dict]:
    """Scrape currently-rendered Activity feed rows.

    Selectors (verified Dec 2025): [data-tid="activity-feed-list-item"].
    """
    return s.eval(r"""
    () => {
        const rows = Array.from(document.querySelectorAll('[data-tid="activity-feed-list-item"]'));
        const seen = new Set();
        const out = [];
        for (const el of rows) {
            const aria = el.getAttribute('aria-label') || '';
            const text = (el.innerText || '').trim();
            const key = aria + '||' + text;
            if (!key.trim() || seen.has(key)) continue;
            seen.add(key);
            const titleEl = el.querySelector('[data-tid="activity-feed-item-title"]');
            const tsEl = el.querySelector('time, span[title*=":"], span[title*="2024"], span[title*="2025"], span[title*="2026"]');
            const unread = /unread|읽지/i.test(aria)
                || !!el.querySelector('[data-tid*="unread"], [class*="unread"], [class*="Unread"]');
            out.push({
                aria_label: aria,
                title: titleEl ? (titleEl.innerText || '').trim() : '',
                timestamp: tsEl ? ((tsEl.getAttribute('title') || tsEl.innerText || '').trim()) : '',
                unread: unread,
                raw_text: text
            });
        }
        return out;
    }
    """) or []


def _scroll_step(s: S, top: int) -> Optional[dict]:
    """Set the virtual-tree scroll container's scrollTop. Returns metrics."""
    return s.eval(f"""
    () => {{
        const c = document.querySelector('div.virtual-tree');
        if (!c) return null;
        c.scrollTop = {int(top)};
        return {{sh: c.scrollHeight, ch: c.clientHeight, st: c.scrollTop}};
    }}
    """)


def collect_activity_full(s: S, step_px: int = 400, max_rounds: int = 120, pause: float = 0.5) -> list[dict]:
    """Walk virtualized Activity feed top→bottom, accumulate items (dedup by raw_text)."""
    seen, order = {}, []

    def _ingest():
        for it in activity_items(s):
            key = it.get('raw_text') or it.get('aria_label')
            if not key or key in seen:
                continue
            seen[key] = it
            order.append(it)

    _scroll_step(s, 0)
    time.sleep(pause)
    _ingest()

    last_st = -1
    for _ in range(max_rounds):
        m = s.eval(
            "() => { const c = document.querySelector('div.virtual-tree');"
            " return c ? {sh: c.scrollHeight, ch: c.clientHeight, st: c.scrollTop} : null; }"
        )
        if not m:
            break
        next_top = m['st'] + step_px
        if next_top >= m['sh'] - m['ch']:
            _scroll_step(s, m['sh'])
            time.sleep(pause)
            _ingest()
            break
        _scroll_step(s, next_top)
        time.sleep(pause)
        _ingest()
        if m['st'] == last_st:
            break
        last_st = m['st']
    return order


# --- Chat list (좌측 채팅 아이콘) ---


def open_chat(s: S) -> bool:
    """Click the Chat icon in the left app bar."""
    return bool(s.eval(r"""
    () => {
        const sels = [
            'button[aria-label*="Chat"]',
            'button[aria-label*="채팅"]',
            '[data-tid="app-bar-chat"]'
        ];
        for (const x of sels) {
            const el = document.querySelector(x);
            if (el) { el.click(); return true; }
        }
        return false;
    }
    """))


def chat_list_raw(s: S) -> list[dict]:
    """All left-pane treeitem rows as {y, text, aria}."""
    return s.eval(r"""
    () => {
        const rows = Array.from(document.querySelectorAll('[role="treeitem"]'))
            .filter(e => {
                const r = e.getBoundingClientRect();
                return r.x < 360 && r.x > 50 && r.width > 100
                    && r.height > 30 && r.height < 130;
            });
        return rows.map(e => {
            const r = e.getBoundingClientRect();
            return {
                y: Math.round(r.y),
                text: (e.innerText || '').trim(),
                aria: e.getAttribute('aria-label') || ''
            };
        });
    }
    """) or []


def chat_list(s: S) -> list[dict]:
    """Parsed chat list with reply-status heuristics.

    Each item: {name, time, last_msg, last_by_me, unread, group, raw_text}.
    """
    rows = chat_list_raw(s)
    out = []
    for r in rows:
        text = r.get('text', '')
        parts = [p.strip() for p in text.split('\n') if p.strip()]
        if not parts or parts == ['Copilot']:
            continue
        if set(parts).issubset({'Quick views', 'Drafts', 'Saved'}):
            continue
        unread = parts[0] == 'Unread'
        if unread:
            parts = parts[1:]
        if len(parts) < 3:
            continue
        name = parts[0]
        time_s = parts[1]
        last_msg = ' '.join(parts[2:])
        last_by_me = last_msg.startswith('You:') or last_msg.startswith('나:')
        is_group = ('and ' in name) or ('+' in name) or name.startswith('📢')
        out.append({
            'name': name,
            'time': time_s,
            'last_msg': last_msg,
            'last_by_me': last_by_me,
            'unread': unread,
            'group': is_group,
            'raw_text': text,
        })
    return out


def unanswered_chats(s: S, unread_only: bool = False) -> list[dict]:
    """Chats where YOU did not send the last message — answer-pending candidates."""
    out = [c for c in chat_list(s) if not c['last_by_me']]
    if unread_only:
        out = [c for c in out if c['unread']]
    return out


def unread_chats(s: S) -> list[dict]:
    """Chats Teams marks as Unread."""
    return [c for c in chat_list(s) if c['unread']]


# --- Channel API (csa/api/v1/containers/{cid}/posts) ---


_SEARCH_INPUT = '[data-tid="AUTOSUGGEST_INPUT"]'


def find_channel(s: S, query: str, navigate: bool = True, wait: float = 3.0) -> Optional[dict]:
    """Search Teams for a channel by name and (optionally) navigate into it.

    Returns {name, team, container_id, team_id} on hit, else None.
    `team_id` is only resolved when `navigate=True` (extracted from captured /posts request).
    """
    s.eval(
        '() => { const e = document.querySelector(\'[data-tid="AUTOSUGGEST_INPUT"]\');'
        ' if (e) { e.focus(); } }'
    )
    s.fill(_SEARCH_INPUT, query)
    time.sleep(2)
    info = s.eval(r"""
    () => {
        const items = Array.from(document.querySelectorAll('[data-tid^="AUTOSUGGEST_SUGGESTION_CHANNELS"]'));
        if (!items.length) return null;
        const e = items[0];
        const tid = e.getAttribute('data-tid') || '';
        return {
            container_id: tid.replace(/^AUTOSUGGEST_SUGGESTION_CHANNELS/, ''),
            aria: e.getAttribute('aria-label') || '',
            text: (e.innerText || '').trim()
        };
    }
    """)
    if not info:
        return None
    parts = [p.strip() for p in (info.get('text') or '').split('\n') if p.strip()]
    name = parts[0] if parts else ''
    team = parts[1] if len(parts) > 1 else ''
    cid = info['container_id']
    team_id = None
    if navigate:
        s.eval(r"""
        () => {
            const items = document.querySelectorAll('[data-tid^="AUTOSUGGEST_SUGGESTION_CHANNELS"]');
            if (items.length) items[0].click();
        }
        """)
        time.sleep(wait)
        enc_cid = cid.replace(':', '%3A').replace('@', '%40')
        for r in s.requests():
            u = r.get('url', '')
            if enc_cid in u and 'teamId=' in u:
                m = re.search(r'teamId=([^&]+)', u)
                if m:
                    team_id = m.group(1)
                    break
    return {'name': name, 'team': team, 'container_id': cid, 'team_id': team_id}


_AUD_FOR_PATH = {
    'chatsvcagg': 'chatsvcagg.teams.microsoft.com',  # /api/csa/...
    'ic3': 'ic3.teams.office.com',                   # /api/chatsvc/...
    'spaces': 'api.spaces.skype.com',                # /api/mt/...
    'uis': 'uis.teams.microsoft.com',                # /api/nss/...
}


def _decode_aud(tok: str) -> Optional[str]:
    try:
        import base64
        payload = tok.split('.')[1]
        payload += '=' * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload)).get('aud')
    except Exception:
        return None


def get_bearer(s: S, audience: str = 'chatsvcagg') -> Optional[str]:
    """Pull a Bearer token from captured Teams API requests for the given audience.

    `audience` is a short key — one of {chatsvcagg, ic3, spaces, uis} — or a full
    aud URL. Default targets `/api/csa/...` (channel posts, threads, members).
    Requires that at least one such authenticated request has already been issued.
    """
    target = _AUD_FOR_PATH.get(audience, audience)
    for r in reversed(s.requests()):
        if 'teams.cloud.microsoft/api/' not in r.get('url', ''):
            continue
        detail = s.request_detail(r['index'])
        m = re.search(r'authorization:\s*Bearer\s+(\S+)', detail, re.I)
        if not m:
            continue
        tok = m.group(1)
        aud = _decode_aud(tok) or ''
        if target in aud:
            return tok
    return None


def channel_posts(
    s: S,
    container_id: str,
    team_id: str,
    page_size: int = 20,
    bearer: Optional[str] = None,
) -> dict:
    """Direct fetch of `/posts` for a channel container. Returns parsed JSON.

    Works from any Teams page once a Bearer token is available; no need to
    actually be inside the channel. Pagination via `data['continuationToken']`
    is not handled here — callers requesting older pages should pass
    `?startTime=` etc. via raw fetch.
    """
    if bearer is None:
        bearer = get_bearer(s)
    if not bearer:
        raise RuntimeError('No Bearer token captured. Open any chat/channel first.')
    cid_lit = json.dumps(container_id)
    tid_lit = json.dumps(team_id)
    tok_lit = json.dumps(bearer)
    js = (
        'async () => {\n'
        f'  const cid = {cid_lit};\n'
        f'  const tid = {tid_lit};\n'
        f'  const tok = {tok_lit};\n'
        f'  const ps = {int(page_size)};\n'
        '  const url = `/api/csa/apac/api/v1/containers/${encodeURIComponent(cid)}/posts`\n'
        '    + `?modality=post&pageSize=${ps}&teamId=${tid}`\n'
        '    + `&includeRcMetadata=true&filterSystemMessage=true&shouldIncludeSharedToL1Rc=true`;\n'
        '  const r = await fetch(url, {\n'
        "    credentials: 'include',\n"
        "    headers: {\n"
        "      'Authorization': 'Bearer ' + tok,\n"
        "      'x-ms-client-version': '1415/26040401723',\n"
        "      'x-ms-region': 'apac',\n"
        "      'x-ringoverride': 'general'\n"
        '    }\n'
        '  });\n'
        '  return {status: r.status, body: await r.text()};\n'
        '}'
    )
    out = s.eval(js)
    status = out.get('status') if isinstance(out, dict) else None
    if not isinstance(out, dict) or not (200 <= (status or 0) < 300):
        body_head = (out.get('body') or '')[:200] if isinstance(out, dict) else ''
        raise RuntimeError(f"channel_posts failed: status={status}, body={body_head}")
    return json.loads(out['body'])


def _strip_html(s: str) -> str:
    if not s:
        return ''
    s = re.sub(r'<br\s*/?>', '\n', s, flags=re.I)
    s = re.sub(r'</p>', '\n', s, flags=re.I)
    s = re.sub(r'<[^>]+>', '', s)
    s = html.unescape(s).replace('\xa0', ' ')
    return re.sub(r'\n{2,}', '\n', s).strip()


def _kst(iso: Optional[str]) -> Optional[datetime]:
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso.replace('Z', '+00:00')).astimezone(KST)
    except ValueError:
        return None


def _msg_to_dict(m: dict) -> Optional[dict]:
    if not isinstance(m, dict):
        return None
    if (m.get('properties') or {}).get('deletetime'):
        return None
    if (m.get('messageType') or '').startswith('ThreadActivity'):
        return None
    when = _kst(m.get('composeTime') or m.get('originalArrivalTime'))
    text = _strip_html(m.get('content') or '')
    cards = (m.get('properties') or {}).get('cards')
    if cards:
        try:
            for c in json.loads(cards):
                for b in (c.get('content') or {}).get('body') or []:
                    t = b.get('text')
                    if t:
                        text += '\n' + t
        except Exception:
            pass
    text = text.strip()
    if not text:
        return None
    return {
        'ts': when,
        'who': m.get('imDisplayName') or m.get('fromDisplayNameInToken') or '',
        'text': text,
        'id': m.get('id'),
        'type': m.get('messageType'),
    }


def parse_posts(
    data: dict,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
) -> list[dict]:
    """Normalize a /posts response into a list of threads.

    Each thread: {parent: {ts, who, text, id, type}, replies: [...same...], reply_total: int}.
    `since` / `until` filter by `ts` (KST). Threads with no parent and no reply
    inside the window are dropped.
    """
    out = []
    for p in data.get('posts') or []:
        parent = _msg_to_dict(p.get('message') or {})
        rep_block = (p.get('replies') or {})
        rep_msgs = rep_block.get('messages') or []
        replies = [_msg_to_dict(r) for r in rep_msgs]
        replies = [r for r in replies if r]

        def in_window(it):
            if since and it['ts'] and it['ts'] < since:
                return False
            if until and it['ts'] and it['ts'] >= until:
                return False
            return True

        parent_in = parent and in_window(parent)
        replies_in = [r for r in replies if in_window(r)]
        if not parent_in and not replies_in:
            continue
        out.append({
            'parent': parent,           # may be outside window when only replies match
            'parent_in_window': bool(parent_in),
            'replies': replies_in,
            'reply_total': rep_block.get('totalCount', len(replies)),
        })
    return out


def today_kst() -> tuple[datetime, datetime]:
    """[start, end) of today in KST as a half-open interval."""
    now = datetime.now(KST)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


__all__ = [
    'TEAMS_URL', 'KST', 'ready', 'open_activity', 'activity_items',
    'collect_activity_full', 'open_chat', 'chat_list_raw',
    'chat_list', 'unanswered_chats', 'unread_chats',
    'find_channel', 'get_bearer', 'channel_posts',
    'parse_posts', 'today_kst',
]
