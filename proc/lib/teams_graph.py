"""Microsoft Teams chat helpers via MS Graph API.

Output schemas mirror `pwc_teams.parse_chat_messages` so callers can swap
between the playwright-backed REST helpers and Graph helpers without changing
downstream code.

Key differences vs `pwc_teams`:
- No browser. Pure HTTP via `msgraph.GraphClient`.
- `chat_id` for DM/group has identical 19:...@thread.v2 / @unq.gbl.spaces
  format → no translation needed.
- Channel access is *not* covered here — channel reads need
  `ChannelMessage.Read.All` (admin consent), which we did not request.
  Use `pwc_teams.channel_posts` (browser fallback) for channels.
"""

from __future__ import annotations

import html
import re
from datetime import datetime, timedelta, timezone
from typing import Iterator, Optional

from msgraph import GraphClient


KST = timezone(timedelta(hours=9))


_REPLY_QUOTE_RE = re.compile(
    r'<blockquote[^>]*itemtype="[^"]*Reply[^"]*"[^>]*>(.*?)</blockquote>',
    re.S | re.I,
)
_CHAT_THREAD_RE = re.compile(
    r'19:[\w-]+(?:_[\w-]+)?@(?:thread\.v2|unq\.gbl\.spaces|thread\.skype)',
    re.I,
)


def chat_thread_id_from_url(url: str) -> Optional[str]:
    """Extract the chat thread id from a Teams deeplink URL — same shape as
    `pwc_teams.chat_thread_id_from_url`."""
    m = _CHAT_THREAD_RE.search(url)
    return m.group(0) if m else None


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


def _extract_quote(content: str) -> Optional[dict]:
    m = _REPLY_QUOTE_RE.search(content or '')
    if not m:
        return None
    inner = m.group(1)
    sender_m = re.search(r'<strong[^>]*>([^<]+)</strong>', inner)
    body = re.sub(r'<strong[^>]*>.*?</strong>', '', inner, flags=re.S)
    body = re.sub(r'<span itemprop="time"[^>]*>.*?</span>', '', body, flags=re.S)
    return {
        'sender': (sender_m.group(1) if sender_m else '').strip(),
        'body': _strip_html(body),
    }


def _msg_to_dict(m: dict) -> Optional[dict]:
    """Normalize one Graph chat message into the same shape as
    `pwc_teams._chat_msg_to_dict`."""
    if not isinstance(m, dict):
        return None
    if (m.get('messageType') or '').startswith('systemEventMessage'):
        return None
    if m.get('deletedDateTime'):
        return None
    when = _kst(m.get('createdDateTime') or m.get('lastModifiedDateTime'))
    body = m.get('body') or {}
    raw = body.get('content') or ''
    quote = _extract_quote(raw) if body.get('contentType') == 'html' else None
    body_clean = _REPLY_QUOTE_RE.sub('', raw) if quote else raw
    text = _strip_html(body_clean) if body.get('contentType') == 'html' else (body_clean or '').strip()
    # adaptive cards: messages with no body but attached card content
    for att in m.get('attachments') or []:
        ctype = att.get('contentType') or ''
        if 'adaptive' in ctype.lower():
            content = att.get('content')
            if isinstance(content, str):
                try:
                    import json as _json
                    content = _json.loads(content)
                except Exception:
                    content = None
            if isinstance(content, dict):
                for b in (content.get('body') or []):
                    t = b.get('text')
                    if t:
                        text = (text + '\n' + t) if text else t
    text = (text or '').strip()
    if not text and not quote:
        return None
    who = (((m.get('from') or {}).get('user') or {}).get('displayName')
           or ((m.get('from') or {}).get('application') or {}).get('displayName')
           or '')
    return {
        'ts': when,
        'who': who,
        'text': text,
        'quote': quote,
        'id': m.get('id'),
        'type': m.get('messageType'),
    }


def chat_messages(
    g: GraphClient,
    chat_id: str,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    page_size: int = 50,
    max_pages: int = 20,
) -> list[dict]:
    """Return chronologically-sorted normalized messages for a 1:1 or group chat.

    `since` / `until` filter by `ts` (KST). `page_size` ≤ 50 (Graph max).
    `max_pages` caps `@odata.nextLink` walk to avoid runaway loops.
    """
    page_size = max(1, min(int(page_size), 50))
    # NOTE: /me/chats/{id}/messages does NOT support $filter on createdDateTime
    # nor $orderby. Server returns newest-first by default; we break client-side
    # once we cross the `since` boundary.
    params: dict = {'$top': page_size}
    out: list[dict] = []
    pages = 0
    url = f'/me/chats/{chat_id}/messages'
    next_link: Optional[str] = None
    while True:
        data = g.get(next_link or url, params=None if next_link else params)
        for raw in data.get('value', []):
            d = _msg_to_dict(raw)
            if not d:
                continue
            if since and d['ts'] and d['ts'] < since:
                # newest-first → once we cross 'since', remaining pages are older
                next_link = None
                break
            if until and d['ts'] and d['ts'] >= until:
                continue
            out.append(d)
        else:
            next_link = data.get('@odata.nextLink')
            pages += 1
            if not next_link or pages >= max_pages:
                break
            continue
        break
    out.sort(key=lambda e: e['ts'] or datetime.min.replace(tzinfo=KST))
    return out


def chat_list(g: GraphClient, top: int = 50) -> list[dict]:
    """List the user's chats with last-message preview.

    Each item: {chat_id, kind, name, last_msg_preview, last_who, last_ts,
                last_by_me, group}.
    `kind` ∈ {'oneOnOne', 'group', 'meeting'}.
    """
    me = g.get('/me')
    me_id = me.get('id') or ''
    items: list[dict] = []
    for c in g.paged('/me/chats', params={
        '$top': top,
        '$expand': 'lastMessagePreview',
        '$orderby': 'lastMessagePreview/createdDateTime desc',
    }):
        last = c.get('lastMessagePreview') or {}
        body = last.get('body') or {}
        text = body.get('content') or ''
        if body.get('contentType') == 'html':
            text = _strip_html(text)
        sender_user = ((last.get('from') or {}).get('user') or {})
        last_who = sender_user.get('displayName') or ''
        last_by_me = (sender_user.get('id') or '') == me_id
        items.append({
            'chat_id': c.get('id'),
            'kind': c.get('chatType') or '',
            'name': c.get('topic') or '',
            'last_msg_preview': text[:300],
            'last_who': last_who,
            'last_ts': _kst(last.get('createdDateTime')),
            'last_by_me': last_by_me,
            'group': c.get('chatType') in ('group', 'meeting'),
        })
    return items


def find_chat(g: GraphClient, query: str) -> list[dict]:
    """Substring match on chat topic / last sender name. Useful for resolving
    'Brad와의 DM' → chat_id."""
    q = query.lower()
    out = []
    for c in chat_list(g, top=200):
        hay = ((c.get('name') or '') + ' ' + (c.get('last_who') or '')).lower()
        if q in hay:
            out.append(c)
    return out


def send_chat_message(
    g: GraphClient,
    chat_id: str,
    text: str,
    *,
    html_body: bool = False,
) -> dict:
    """Send a message to a chat. Requires `Chat.ReadWrite` (or `ChatMessage.Send`).
    `text` is plain text by default; pass `html_body=True` to send raw HTML."""
    body = {'body': {
        'contentType': 'html' if html_body else 'text',
        'content': text,
    }}
    return g.post(f'/me/chats/{chat_id}/messages', json_body=body)


def today_kst() -> tuple[datetime, datetime]:
    now = datetime.now(KST)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


# --- Channels (requires Team.ReadBasic.All + ChannelMessage.Read.All, both admin-consented) ---


def joined_teams(g: GraphClient) -> list[dict]:
    """List teams the user is a member of."""
    return g.get('/me/joinedTeams').get('value', [])


def channels(g: GraphClient, team_id: str) -> list[dict]:
    """List channels in a team."""
    return g.get(f'/teams/{team_id}/channels').get('value', [])


def channel_map(g: GraphClient, cache_path: Optional[str] = None) -> list[dict]:
    """Enumerate every (team, channel) pair the user can see.

    Each item: {team_id, team_name, channel_id, channel_name, membership_type}.
    Pass `cache_path` to persist as JSON; the returned list is the same shape
    `find_channel_graph` expects.
    """
    out = []
    for t in joined_teams(g):
        tid = t.get('id'); tname = t.get('displayName')
        for c in channels(g, tid):
            out.append({
                'team_id': tid,
                'team_name': tname,
                'channel_id': c.get('id'),
                'channel_name': c.get('displayName'),
                'membership_type': c.get('membershipType'),
            })
    if cache_path:
        import json as _json
        from pathlib import Path
        Path(cache_path).write_text(
            _json.dumps(out, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )
    return out


def find_channel_graph(g: GraphClient, query: str,
                        cache: Optional[list[dict]] = None) -> list[dict]:
    """Substring match on channel/team name. `cache` lets callers reuse a
    previously-loaded `channel_map` to skip the team-walk."""
    rows = cache if cache is not None else channel_map(g)
    q = query.lower()
    return [
        r for r in rows
        if q in (r.get('channel_name') or '').lower()
        or q in (r.get('team_name') or '').lower()
    ]


def _channel_msg_to_dict(m: dict) -> Optional[dict]:
    """Normalize one channel message — same shape as `_msg_to_dict`."""
    if not isinstance(m, dict):
        return None
    if (m.get('messageType') or '').startswith('systemEventMessage'):
        return None
    if m.get('deletedDateTime'):
        return None
    when = _kst(m.get('createdDateTime') or m.get('lastModifiedDateTime'))
    body = m.get('body') or {}
    raw = body.get('content') or ''
    quote = _extract_quote(raw) if body.get('contentType') == 'html' else None
    body_clean = _REPLY_QUOTE_RE.sub('', raw) if quote else raw
    text = _strip_html(body_clean) if body.get('contentType') == 'html' else (body_clean or '').strip()
    text = (text or '').strip()
    if not text and not quote:
        return None
    who = (((m.get('from') or {}).get('user') or {}).get('displayName')
           or ((m.get('from') or {}).get('application') or {}).get('displayName')
           or '')
    return {
        'ts': when, 'who': who, 'text': text, 'quote': quote,
        'id': m.get('id'), 'type': m.get('messageType'),
    }


def channel_posts(
    g: GraphClient,
    team_id: str,
    channel_id: str,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    page_size: int = 50,
    max_pages: int = 10,
    include_replies: bool = True,
) -> list[dict]:
    """Return threads in a channel — output schema mirrors `pwc_teams.parse_posts`.

    Each thread: {parent: {ts, who, text, quote, id, type},
                  parent_in_window: bool, replies: [...same...], reply_total: int}.
    Channel `replies` is a separate Graph endpoint per parent — `include_replies`
    fetches them. Set False to skip (faster) when only top-level posts matter.
    """
    page_size = max(1, min(int(page_size), 50))
    params: dict = {'$top': page_size}
    out: list[dict] = []
    pages = 0
    next_link: Optional[str] = None
    base = f'/teams/{team_id}/channels/{channel_id}/messages'
    while True:
        data = g.get(next_link or base, params=None if next_link else params)
        for raw in data.get('value', []):
            parent = _channel_msg_to_dict(raw)
            if not parent:
                continue
            if since and parent['ts'] and parent['ts'] < since:
                next_link = None
                break
            if until and parent['ts'] and parent['ts'] >= until:
                continue
            replies: list[dict] = []
            reply_total = 0
            if include_replies:
                rdata = g.get(f"{base}/{raw.get('id')}/replies", params={'$top': 50})
                rmsgs = rdata.get('value', []) or []
                reply_total = len(rmsgs)
                for r in rmsgs:
                    d = _channel_msg_to_dict(r)
                    if not d:
                        continue
                    if since and d['ts'] and d['ts'] < since:
                        continue
                    if until and d['ts'] and d['ts'] >= until:
                        continue
                    replies.append(d)
                replies.sort(key=lambda e: e['ts'] or datetime.min.replace(tzinfo=KST))
            out.append({
                'parent': parent,
                'parent_in_window': not (since and parent['ts'] and parent['ts'] < since),
                'replies': replies,
                'reply_total': reply_total,
            })
        else:
            next_link = data.get('@odata.nextLink')
            pages += 1
            if not next_link or pages >= max_pages:
                break
            continue
        break
    out.sort(key=lambda t: (t['parent'] or {}).get('ts') or datetime.min.replace(tzinfo=KST))
    return out


# --- Activity replacement (Graph has no /48:notifications equivalent) ---


def unanswered_chats(g: GraphClient, top: int = 100) -> list[dict]:
    """Chats where the **last sender is not me** — best-effort Activity-feed
    surrogate now that `48:notifications` isn't exposed by Graph.

    Each item is the same shape as `chat_list()` rows; callers typically sort
    by `last_ts desc` and filter out muted threads.
    """
    return [c for c in chat_list(g, top=top) if not c.get('last_by_me') and c.get('last_ts')]


def at_mentions(g: GraphClient, since: Optional[datetime] = None,
                max_chats: int = 50, max_msgs_per_chat: int = 50) -> list[dict]:
    """Surface messages that @-mention me across recent chats.

    Walks `chat_list` newest-first, fetches recent messages per chat, filters
    by `mentions[].mentioned.user.id == me`. This is a polling surrogate —
    Graph subscriptions are the proper push solution if you need realtime.
    """
    me = g.get('/me')
    me_id = me.get('id') or ''
    out = []
    for c in chat_list(g, top=max_chats):
        cid = c.get('chat_id')
        if not cid:
            continue
        # /me/chats/{id}/messages doesn't support $filter; iterate and break on `since`.
        data = g.get(f'/me/chats/{cid}/messages', params={'$top': max_msgs_per_chat})
        for raw in data.get('value', []):
            ts_iso = raw.get('createdDateTime') or raw.get('lastModifiedDateTime')
            ts = _kst(ts_iso)
            if since and ts and ts < since:
                break
            for ment in (raw.get('mentions') or []):
                user = ((ment.get('mentioned') or {}).get('user') or {})
                if user.get('id') == me_id:
                    d = _msg_to_dict(raw)
                    if d:
                        d['chat_id'] = cid
                        d['chat_name'] = c.get('name') or c.get('last_who') or ''
                        out.append(d)
                    break
    out.sort(key=lambda e: e['ts'] or datetime.min.replace(tzinfo=KST), reverse=True)
    return out


def send_channel_message(
    g: GraphClient,
    team_id: str,
    channel_id: str,
    text: str,
    *,
    html_body: bool = False,
) -> dict:
    """Post a new top-level message to a channel.

    Requires `ChannelMessage.Send` (admin-consented). Returns the created
    message dict (`id`, `webUrl`, etc.) so callers can reply later.
    """
    body = {'body': {
        'contentType': 'html' if html_body else 'text',
        'content': text,
    }}
    return g.post(f'/teams/{team_id}/channels/{channel_id}/messages',
                  json_body=body)


def reply_channel_message(
    g: GraphClient,
    team_id: str,
    channel_id: str,
    parent_message_id: str,
    text: str,
    *,
    html_body: bool = False,
) -> dict:
    """Reply to an existing channel message (thread reply)."""
    body = {'body': {
        'contentType': 'html' if html_body else 'text',
        'content': text,
    }}
    return g.post(
        f'/teams/{team_id}/channels/{channel_id}/messages/{parent_message_id}/replies',
        json_body=body,
    )


def update_channel_message(
    g: GraphClient,
    team_id: str,
    channel_id: str,
    message_id: str,
    text: str,
    *,
    html_body: bool = False,
    mentions: Optional[list] = None,
    parent_message_id: Optional[str] = None,
) -> dict:
    """Edit a channel message (or its reply) you authored.

    PATCH only updates the body and `mentions`. `parent_message_id` switches
    to the reply path. Requires the same permission used to send.
    """
    body: dict = {'body': {
        'contentType': 'html' if html_body else 'text',
        'content': text,
    }}
    if mentions is not None:
        body['mentions'] = mentions
    base = f'/teams/{team_id}/channels/{channel_id}/messages'
    path = (f'{base}/{parent_message_id}/replies/{message_id}'
            if parent_message_id else f'{base}/{message_id}')
    return g.patch(path, json_body=body)


def delete_channel_message(
    g: GraphClient,
    team_id: str,
    channel_id: str,
    message_id: str,
    *,
    parent_message_id: Optional[str] = None,
    undo: bool = False,
) -> None:
    """Soft-delete (or undo-delete) a channel message you authored.

    Graph requires the `softDelete`/`undoSoftDelete` action — DELETE on the
    message returns 405. Pass `undo=True` to restore.
    """
    base = f'/teams/{team_id}/channels/{channel_id}/messages'
    target = (f'{base}/{parent_message_id}/replies/{message_id}'
              if parent_message_id else f'{base}/{message_id}')
    action = 'undoSoftDelete' if undo else 'softDelete'
    g.post(f'{target}/{action}')


def update_chat_message(
    g: GraphClient,
    chat_id: str,
    message_id: str,
    text: str,
    *,
    html_body: bool = False,
    mentions: Optional[list] = None,
) -> dict:
    """Edit a chat (DM/group) message you sent."""
    body: dict = {'body': {
        'contentType': 'html' if html_body else 'text',
        'content': text,
    }}
    if mentions is not None:
        body['mentions'] = mentions
    return g.patch(f'/me/chats/{chat_id}/messages/{message_id}', json_body=body)


def delete_chat_message(
    g: GraphClient,
    chat_id: str,
    message_id: str,
    *,
    undo: bool = False,
) -> None:
    """Soft-delete (or restore) a chat message you sent."""
    action = 'undoSoftDelete' if undo else 'softDelete'
    g.post(f'/me/chats/{chat_id}/messages/{message_id}/{action}')


__all__ = [
    'KST', 'chat_thread_id_from_url',
    'chat_messages', 'chat_list', 'find_chat', 'send_chat_message',
    'update_chat_message', 'delete_chat_message',
    'joined_teams', 'channels', 'channel_map', 'find_channel_graph',
    'channel_posts', 'send_channel_message', 'reply_channel_message',
    'update_channel_message', 'delete_channel_message',
    'unanswered_chats', 'at_mentions',
    'today_kst',
]
