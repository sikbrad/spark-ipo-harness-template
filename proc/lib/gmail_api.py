"""Gmail API helper — list / search / get / parse.

Built on `proc/lib/google_auth.GoogleClient`. Pure functions: caller passes the
auth wrapper, helpers return normalized dicts.

Usage:
    from google_auth import GoogleClient
    from gmail_api import search, save_json

    g = GoogleClient('bispro89')
    msgs = search(g, q='after:2026/05/01 (is:starred OR is:important) -category:promotions', max_results=80)
    save_json(msgs, 'output/gmail-bispro89-2026-05-01-to-08.json')

CLI:
    python proc/lib/gmail_api.py search --account bispro89 \\
        --q 'after:2026/05/01 -category:promotions' --max 50 \\
        --out output/gmail-bispro89-may-week1.json

    python proc/lib/gmail_api.py get --account bispro89 --id 18f3a1b2c

Gmail search query syntax: https://support.google.com/mail/answer/7190
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
from email.utils import parseaddr, parsedate_to_datetime
from pathlib import Path
from typing import Any, Iterable, Optional

# Allow `python proc/lib/gmail_api.py ...` when run directly.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from google_auth import GoogleClient  # noqa: E402


def _decode_b64url(s: str) -> str:
    s = s.replace('-', '+').replace('_', '/')
    pad = (-len(s)) % 4
    return base64.b64decode(s + '=' * pad).decode('utf-8', errors='replace')


def _strip_html(html: str) -> str:
    text = re.sub(r'(?is)<(script|style)[^>]*>.*?</\1>', ' ', html)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def _walk_parts(payload: dict, want_html: bool = False) -> str:
    """Pull text/plain (or text/html if requested), walking multipart trees."""
    if not payload:
        return ''
    target = 'text/html' if want_html else 'text/plain'
    mime = payload.get('mimeType', '')
    body = payload.get('body', {})
    data = body.get('data')
    if data and mime == target:
        return _decode_b64url(data)
    for part in payload.get('parts', []) or []:
        t = _walk_parts(part, want_html=want_html)
        if t:
            return t
    # Last resort — any text/* if neither plain nor html matched
    if want_html:
        return ''
    if data and mime.startswith('text/'):
        text = _decode_b64url(data)
        return _strip_html(text) if mime == 'text/html' else text
    return ''


def _attachments(payload: dict) -> list[dict]:
    out: list[dict] = []

    def walk(p: dict) -> None:
        if not p:
            return
        fname = p.get('filename')
        body = p.get('body', {})
        if fname and body.get('attachmentId'):
            out.append({
                'filename': fname,
                'mime': p.get('mimeType'),
                'size': body.get('size'),
                'attachment_id': body['attachmentId'],
            })
        for sub in p.get('parts', []) or []:
            walk(sub)

    walk(payload)
    return out


def parse_message(full: dict) -> dict:
    """Normalize a `users.messages.get(format='full')` response."""
    payload = full.get('payload', {})
    headers = {h['name'].lower(): h['value'] for h in payload.get('headers', [])}
    name, email_addr = parseaddr(headers.get('from', ''))

    raw_date = headers.get('date')
    ts_iso = None
    if raw_date:
        try:
            ts_iso = parsedate_to_datetime(raw_date).isoformat()
        except (TypeError, ValueError):
            pass

    body_text = _walk_parts(payload, want_html=False)
    body_html = _walk_parts(payload, want_html=True)
    if not body_text and body_html:
        body_text = _strip_html(body_html)

    labels = full.get('labelIds', []) or []
    return {
        'id': full.get('id'),
        'thread_id': full.get('threadId'),
        'date_raw': raw_date,
        'ts': ts_iso,
        'from_name': name,
        'from_email': email_addr,
        'to': headers.get('to'),
        'cc': headers.get('cc'),
        'subject': headers.get('subject', ''),
        'snippet': full.get('snippet', ''),
        'body_text': body_text,
        'body_html': body_html,
        'attachments': _attachments(payload),
        'labels': labels,
        'is_unread': 'UNREAD' in labels,
        'is_starred': 'STARRED' in labels,
        'is_important': 'IMPORTANT' in labels,
        'is_inbox': 'INBOX' in labels,
        'category': next((l.replace('CATEGORY_', '').lower() for l in labels if l.startswith('CATEGORY_')), None),
    }


def list_messages(g: GoogleClient, q: str = '', max_results: int = 50, label_ids: Optional[list[str]] = None) -> list[dict]:
    """Return list of `{id, threadId}` dicts. Use `search()` for parsed bodies."""
    gmail = g.service('gmail', 'v1')
    out: list[dict] = []
    page_token = None
    remaining = max_results
    while remaining > 0:
        req = gmail.users().messages().list(
            userId='me',
            q=q,
            maxResults=min(500, remaining),
            pageToken=page_token,
            labelIds=label_ids,
        )
        resp = req.execute()
        msgs = resp.get('messages', []) or []
        out.extend(msgs)
        remaining -= len(msgs)
        page_token = resp.get('nextPageToken')
        if not page_token or not msgs:
            break
    return out[:max_results]


def get_message(g: GoogleClient, msg_id: str, fmt: str = 'full') -> dict:
    gmail = g.service('gmail', 'v1')
    return gmail.users().messages().get(userId='me', id=msg_id, format=fmt).execute()


def search(
    g: GoogleClient,
    q: str,
    max_results: int = 50,
    fetch_full: bool = True,
    skip_body: bool = False,
) -> list[dict]:
    """List + parse in one call.

    `skip_body=True` keeps `body_text`/`body_html` empty (faster, smaller).
    """
    ids = list_messages(g, q=q, max_results=max_results)
    if not fetch_full:
        return [{'id': m['id'], 'thread_id': m.get('threadId')} for m in ids]
    out: list[dict] = []
    for m in ids:
        full = get_message(g, m['id'], fmt='metadata' if skip_body else 'full')
        parsed = parse_message(full)
        if skip_body:
            parsed.pop('body_text', None)
            parsed.pop('body_html', None)
        out.append(parsed)
    out.sort(key=lambda x: x.get('ts') or '', reverse=True)
    return out


def get_profile(g: GoogleClient) -> dict:
    gmail = g.service('gmail', 'v1')
    return gmail.users().getProfile(userId='me').execute()


# ---- Mutations (require gmail.modify / gmail.send scopes)


def download_attachment(g: GoogleClient, msg_id: str, attachment_id: str, out_path: str | Path) -> Path:
    """Save an attachment to disk. `attachment_id` comes from `parsed['attachments'][i]['attachment_id']`."""
    gmail = g.service('gmail', 'v1')
    att = gmail.users().messages().attachments().get(
        userId='me', messageId=msg_id, id=attachment_id,
    ).execute()
    raw = att['data']
    raw = raw + '=' * ((-len(raw)) % 4)
    data = base64.urlsafe_b64decode(raw)
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return p


def mark_read(g: GoogleClient, msg_id: str) -> dict:
    return modify_labels(g, msg_id, remove=['UNREAD'])


def mark_unread(g: GoogleClient, msg_id: str) -> dict:
    return modify_labels(g, msg_id, add=['UNREAD'])


def star(g: GoogleClient, msg_id: str) -> dict:
    return modify_labels(g, msg_id, add=['STARRED'])


def unstar(g: GoogleClient, msg_id: str) -> dict:
    return modify_labels(g, msg_id, remove=['STARRED'])


def archive(g: GoogleClient, msg_id: str) -> dict:
    return modify_labels(g, msg_id, remove=['INBOX'])


def trash_message(g: GoogleClient, msg_id: str) -> dict:
    """Move to trash (recoverable for ~30d)."""
    gmail = g.service('gmail', 'v1')
    return gmail.users().messages().trash(userId='me', id=msg_id).execute()


def modify_labels(g: GoogleClient, msg_id: str, add: list[str] | None = None, remove: list[str] | None = None) -> dict:
    gmail = g.service('gmail', 'v1')
    return gmail.users().messages().modify(
        userId='me', id=msg_id,
        body={'addLabelIds': add or [], 'removeLabelIds': remove or []},
    ).execute()


def send_message(
    g: GoogleClient,
    to: str | list[str],
    subject: str,
    body_text: str,
    body_html: Optional[str] = None,
    cc: Optional[str | list[str]] = None,
    bcc: Optional[str | list[str]] = None,
    attachments: Optional[list[str | Path]] = None,
    thread_id: Optional[str] = None,
    in_reply_to: Optional[str] = None,
) -> dict:
    """Send an email. Returns the sent message metadata.

    `in_reply_to` is the parent message's `Message-Id` header (NOT the gmail msg id);
    pass it with `thread_id` to keep replies in the same thread.
    """
    from email.message import EmailMessage
    from email.utils import make_msgid

    msg = EmailMessage()
    msg['To'] = to if isinstance(to, str) else ', '.join(to)
    if cc:
        msg['Cc'] = cc if isinstance(cc, str) else ', '.join(cc)
    if bcc:
        msg['Bcc'] = bcc if isinstance(bcc, str) else ', '.join(bcc)
    msg['Subject'] = subject
    msg['Message-Id'] = make_msgid()
    if in_reply_to:
        msg['In-Reply-To'] = in_reply_to
        msg['References'] = in_reply_to

    msg.set_content(body_text)
    if body_html:
        msg.add_alternative(body_html, subtype='html')

    for att in attachments or []:
        p = Path(att)
        ctype = 'application/octet-stream'
        try:
            import mimetypes
            guessed, _ = mimetypes.guess_type(str(p))
            if guessed:
                ctype = guessed
        except Exception:
            pass
        maintype, _, subtype = ctype.partition('/')
        msg.add_attachment(p.read_bytes(), maintype=maintype, subtype=subtype or 'octet-stream', filename=p.name)

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    body: dict[str, Any] = {'raw': raw}
    if thread_id:
        body['threadId'] = thread_id
    gmail = g.service('gmail', 'v1')
    return gmail.users().messages().send(userId='me', body=body).execute()


# ---- Multi-account aggregate


def search_all_accounts(
    accounts: Iterable[str],
    q: str,
    max_results: int = 50,
    skip_body: bool = True,
) -> list[dict]:
    """Run the same query across multiple accounts; tag each result with `account`."""
    out: list[dict] = []
    for acct in accounts:
        g = GoogleClient(acct)
        msgs = search(g, q=q, max_results=max_results, skip_body=skip_body)
        for m in msgs:
            m['account'] = acct
        out.extend(msgs)
    out.sort(key=lambda x: x.get('ts') or '', reverse=True)
    return out


def save_json(data: Any, path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str))
    return p


# ---- CLI


def _cmd_search(args) -> int:
    g = GoogleClient(args.account)
    msgs = search(g, q=args.q, max_results=args.max, skip_body=args.no_body)
    if args.out:
        p = save_json(msgs, args.out)
        print(f'Wrote {len(msgs)} messages → {p}')
    else:
        for m in msgs:
            ts = (m.get('ts') or m.get('date_raw') or '')[:16]
            flags = ('🔵' if m['is_unread'] else '') + ('⭐' if m['is_starred'] else '') + ('❗' if m['is_important'] else '')
            sender = m['from_name'] or m['from_email']
            print(f'{ts}  {flags:<3}  {sender}: {m["subject"]}')
    return 0


def _cmd_get(args) -> int:
    g = GoogleClient(args.account)
    full = get_message(g, args.id)
    parsed = parse_message(full)
    if args.out:
        save_json(parsed, args.out)
        print(f'Wrote → {args.out}')
    else:
        print(json.dumps(parsed, ensure_ascii=False, indent=2, default=str))
    return 0


def _cmd_profile(args) -> int:
    g = GoogleClient(args.account)
    print(json.dumps(get_profile(g), ensure_ascii=False, indent=2))
    return 0


def _cmd_attach(args) -> int:
    g = GoogleClient(args.account)
    p = download_attachment(g, args.msg, args.attach, args.out)
    print(f'Saved → {p} ({p.stat().st_size}B)')
    return 0


def _cmd_send(args) -> int:
    g = GoogleClient(args.account)
    body_text = args.body if args.body else (Path(args.from_file).read_text() if args.from_file else '')
    if not body_text:
        sys.stderr.write('Need --body or --from-file\n')
        return 2
    res = send_message(
        g,
        to=args.to.split(',') if ',' in args.to else args.to,
        subject=args.subject,
        body_text=body_text,
        cc=args.cc.split(',') if args.cc and ',' in args.cc else args.cc,
        attachments=args.attach,
    )
    print(f'Sent: id={res["id"]}, threadId={res["threadId"]}')
    return 0


def _cmd_label(args) -> int:
    g = GoogleClient(args.account)
    res = modify_labels(
        g, args.id,
        add=args.add.split(',') if args.add else [],
        remove=args.remove.split(',') if args.remove else [],
    )
    print(f'Labels now: {res["labelIds"]}')
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog='gmail_api')
    sub = parser.add_subparsers(dest='cmd', required=True)
    common = lambda sp: sp.add_argument('--account', required=True, choices=['bispro89', 'sikbrad'])

    sp = sub.add_parser('search', help='Search and dump parsed messages'); common(sp)
    sp.add_argument('--q', required=True, help='Gmail search query')
    sp.add_argument('--max', type=int, default=50)
    sp.add_argument('--out', help='Path to write JSON; if omitted, prints summary')
    sp.add_argument('--no-body', action='store_true', help='Skip body parsing (faster)')

    sp = sub.add_parser('get', help='Get a single message'); common(sp)
    sp.add_argument('--id', required=True)
    sp.add_argument('--out')

    sp = sub.add_parser('profile', help='Show mailbox profile (email, total)'); common(sp)

    sp = sub.add_parser('attach', help='Download an attachment'); common(sp)
    sp.add_argument('--msg', required=True, help='Message id')
    sp.add_argument('--attach', required=True, help='Attachment id (from parse_message attachments[])')
    sp.add_argument('--out', required=True)

    sp = sub.add_parser('send', help='Send a new email'); common(sp)
    sp.add_argument('--to', required=True, help='Comma-sep list OK')
    sp.add_argument('--cc')
    sp.add_argument('--subject', required=True)
    sp.add_argument('--body', help='Body text inline')
    sp.add_argument('--from-file', help='Read body from file')
    sp.add_argument('--attach', action='append', help='Path to attachment (repeat for multiple)')

    sp = sub.add_parser('label', help='Add/remove labels (UNREAD, STARRED, INBOX, IMPORTANT, ...)'); common(sp)
    sp.add_argument('--id', required=True)
    sp.add_argument('--add')
    sp.add_argument('--remove')

    args = parser.parse_args(argv[1:])
    return {
        'search': _cmd_search,
        'get': _cmd_get,
        'profile': _cmd_profile,
        'attach': _cmd_attach,
        'send': _cmd_send,
        'label': _cmd_label,
    }[args.cmd](args)


if __name__ == '__main__':
    sys.exit(main(sys.argv))
