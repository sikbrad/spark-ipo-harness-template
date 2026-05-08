"""Outlook (Office 365 Mail) helper via MS Graph API.

Reads `MSFT_MYAGENT_*` from .env via `msgraph.GraphClient`. Scopes used:
- Mail.Read / Mail.ReadWrite — list/get/move/flag/markRead
- Mail.Send — send / reply / forward
- Files.ReadWrite — attachment upload (large items via uploadSession)

All output uses ISO timestamps in KST when possible.
"""

from __future__ import annotations

import base64
import mimetypes
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Iterable, Iterator, Optional, Sequence

from msgraph import GraphClient


KST = timezone(timedelta(hours=9))


def _kst(iso: Optional[str]) -> Optional[datetime]:
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso.replace('Z', '+00:00')).astimezone(KST)
    except ValueError:
        return None


def _fmt_addr(a: dict) -> str:
    ea = (a or {}).get('emailAddress') or {}
    name = ea.get('name') or ''
    addr = ea.get('address') or ''
    if name and addr and name != addr:
        return f'{name} <{addr}>'
    return addr or name


def _addr_list(items: Optional[list]) -> list[str]:
    return [_fmt_addr(a) for a in (items or [])]


def _to_addr_objs(addrs: Optional[Sequence[str]]) -> list[dict]:
    out = []
    for a in addrs or []:
        a = a.strip()
        if not a:
            continue
        # accept "Name <email>" or just "email"
        if '<' in a and '>' in a:
            name = a.split('<')[0].strip().strip('"')
            email = a.split('<', 1)[1].rstrip('>').strip()
        else:
            name, email = '', a
        out.append({'emailAddress': {'address': email, **({'name': name} if name else {})}})
    return out


def _msg_to_dict(m: dict) -> dict:
    """Normalize one /me/messages item."""
    return {
        'id': m.get('id'),
        'subject': m.get('subject') or '',
        'from': _fmt_addr(m.get('from') or {}),
        'to': _addr_list(m.get('toRecipients')),
        'cc': _addr_list(m.get('ccRecipients')),
        'bcc': _addr_list(m.get('bccRecipients')),
        'received_ts': _kst(m.get('receivedDateTime')),
        'sent_ts': _kst(m.get('sentDateTime')),
        'is_read': bool(m.get('isRead')),
        'has_attachments': bool(m.get('hasAttachments')),
        'importance': m.get('importance') or 'normal',
        'preview': (m.get('bodyPreview') or '').replace('\r', ''),
        'web_link': m.get('webLink'),
        'conversation_id': m.get('conversationId'),
        'parent_folder_id': m.get('parentFolderId'),
        'categories': m.get('categories') or [],
        'flag': ((m.get('flag') or {}).get('flagStatus') or 'notFlagged'),
    }


class MailClient:
    """Thin Outlook wrapper around `GraphClient`."""

    def __init__(self, g: Optional[GraphClient] = None):
        self.g = g or GraphClient()
        self._folder_cache: dict[str, str] = {}  # name lower -> id

    # ---- folders

    def list_folders(self) -> list[dict]:
        return self.g.get('/me/mailFolders', params={'$top': 100}).get('value', [])

    def folder_id(self, name_or_id: str) -> str:
        """Resolve a folder name (case-insensitive) to its id. Well-known names
        like 'inbox', 'sentitems', 'drafts', 'deleteditems', 'archive' are passed
        through as-is by Graph."""
        if not name_or_id:
            return 'inbox'
        WELL_KNOWN = {
            'inbox', 'sentitems', 'drafts', 'deleteditems', 'archive',
            'junkemail', 'outbox', 'clutter', 'conversationhistory',
        }
        key = name_or_id.lower()
        if key in WELL_KNOWN:
            return key
        if not self._folder_cache:
            for f in self.list_folders():
                self._folder_cache[(f.get('displayName') or '').lower()] = f.get('id')
        return self._folder_cache.get(key) or name_or_id

    # ---- list / search / get

    def list_messages(
        self,
        folder: str = 'inbox',
        q: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        top: int = 50,
        order_by: str = 'receivedDateTime desc',
        select: Optional[Sequence[str]] = None,
        max_pages: int = 5,
    ) -> list[dict]:
        """List messages.

        - `folder`: well-known name or display name or id
        - `q`: free-text `$search` (mutually exclusive with order_by/$filter on Graph;
               when set, ordering is by relevance and `since`/`until` ignored).
        - `since`/`until`: KST datetime; converted to UTC ISO 8601 for `$filter`.
        - `select`: subset of fields; default returns the full set we normalize.
        """
        path = f'/me/mailFolders/{self.folder_id(folder)}/messages'
        params: dict = {'$top': min(top, 50)}
        sel = select or [
            'id', 'subject', 'from', 'toRecipients', 'ccRecipients', 'bccRecipients',
            'receivedDateTime', 'sentDateTime', 'isRead', 'hasAttachments',
            'importance', 'bodyPreview', 'webLink', 'conversationId',
            'parentFolderId', 'categories', 'flag',
        ]
        params['$select'] = ','.join(sel)
        if q:
            # $search overrides $filter and $orderby per Graph semantics
            params['$search'] = f'"{q}"'
        else:
            params['$orderby'] = order_by
            filt = []
            if since:
                filt.append(f"receivedDateTime ge {since.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}")
            if until:
                filt.append(f"receivedDateTime lt {until.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}")
            if filt:
                params['$filter'] = ' and '.join(filt)
        out: list[dict] = []
        url = path
        first_call = True
        pages = 0
        while url:
            data = self.g.get(url, params=params if first_call else None,
                              headers={'Prefer': 'outlook.body-content-type="text"'} if q else None)
            first_call = False
            for m in data.get('value', []):
                out.append(_msg_to_dict(m))
                if len(out) >= top:
                    return out
            url = data.get('@odata.nextLink')
            pages += 1
            if pages >= max_pages:
                break
        return out

    def get_message(self, msg_id: str, with_body: bool = True,
                    body_type: str = 'text') -> dict:
        """Return a single message including body. `body_type` ∈ {'text','html'}."""
        headers = {'Prefer': f'outlook.body-content-type="{body_type}"'}
        m = self.g.get(f'/me/messages/{msg_id}', headers=headers)
        d = _msg_to_dict(m)
        if with_body:
            body = m.get('body') or {}
            d['body_content_type'] = body.get('contentType')
            d['body'] = body.get('content') or ''
        return d

    def list_attachments(self, msg_id: str) -> list[dict]:
        """List attachments metadata (does not download contents)."""
        return self.g.get(
            f'/me/messages/{msg_id}/attachments',
            params={'$select': 'id,name,contentType,size,isInline,@odata.type'},
        ).get('value', [])

    def download_attachments(self, msg_id: str, dest_dir: str) -> list[Path]:
        """Download all fileAttachments (skips itemAttachment / referenceAttachment)
        and return the saved paths."""
        Path(dest_dir).mkdir(parents=True, exist_ok=True)
        saved: list[Path] = []
        for att in self.list_attachments(msg_id):
            if att.get('@odata.type') != '#microsoft.graph.fileAttachment':
                continue
            full = self.g.get(f'/me/messages/{msg_id}/attachments/{att["id"]}')
            content_b64 = full.get('contentBytes')
            if not content_b64:
                continue
            name = att.get('name') or att['id']
            p = Path(dest_dir) / name
            p.write_bytes(base64.b64decode(content_b64))
            saved.append(p)
        return saved

    # ---- send / reply / forward

    def send_mail(
        self,
        to: Sequence[str],
        subject: str,
        body: str,
        *,
        cc: Optional[Sequence[str]] = None,
        bcc: Optional[Sequence[str]] = None,
        html: bool = False,
        attachments: Optional[Sequence[str]] = None,
        save_to_sent: bool = True,
    ) -> None:
        """Send a message. `attachments` are local file paths."""
        msg = {
            'subject': subject,
            'body': {'contentType': 'html' if html else 'text', 'content': body},
            'toRecipients': _to_addr_objs(to),
        }
        if cc:
            msg['ccRecipients'] = _to_addr_objs(cc)
        if bcc:
            msg['bccRecipients'] = _to_addr_objs(bcc)
        if attachments:
            msg['attachments'] = [_local_attachment(p) for p in attachments]
        self.g.post('/me/sendMail',
                    json_body={'message': msg, 'saveToSentItems': save_to_sent})

    def reply(self, msg_id: str, body: str, *, html: bool = False,
              reply_all: bool = False) -> None:
        path = f'/me/messages/{msg_id}/{"replyAll" if reply_all else "reply"}'
        comment_body = {
            'message': {
                'body': {'contentType': 'html' if html else 'text', 'content': body},
            },
            'comment': '',
        } if html else {'comment': body}
        self.g.post(path, json_body=comment_body)

    def forward(self, msg_id: str, to: Sequence[str], comment: str = '') -> None:
        self.g.post(
            f'/me/messages/{msg_id}/forward',
            json_body={'toRecipients': _to_addr_objs(to), 'comment': comment},
        )

    # ---- mutate

    def mark_read(self, msg_id: str, read: bool = True) -> dict:
        return self.g.patch(f'/me/messages/{msg_id}', json_body={'isRead': read})

    def flag(self, msg_id: str, status: str = 'flagged') -> dict:
        """status ∈ {'notFlagged', 'flagged', 'complete'}"""
        return self.g.patch(
            f'/me/messages/{msg_id}',
            json_body={'flag': {'flagStatus': status}},
        )

    def move(self, msg_id: str, dest_folder: str) -> dict:
        return self.g.post(
            f'/me/messages/{msg_id}/move',
            json_body={'destinationId': self.folder_id(dest_folder)},
        )

    def delete(self, msg_id: str) -> None:
        self.g.delete(f'/me/messages/{msg_id}')


def _local_attachment(local_path: str) -> dict:
    p = Path(local_path)
    if not p.is_file():
        raise FileNotFoundError(local_path)
    ctype, _ = mimetypes.guess_type(p.name)
    return {
        '@odata.type': '#microsoft.graph.fileAttachment',
        'name': p.name,
        'contentType': ctype or 'application/octet-stream',
        'contentBytes': base64.b64encode(p.read_bytes()).decode('ascii'),
    }


__all__ = ['MailClient', 'KST']
