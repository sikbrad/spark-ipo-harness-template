"""Google Drive API helper — search / metadata / download / upload / Docs export.

Built on `proc/lib/google_auth.GoogleClient` with `drive` scope (full r/w).

Usage:
    from google_auth import GoogleClient
    from gdrive_api import search, download, upload, export_doc

    g = GoogleClient('bispro89')
    files = search(g, name_contains='Q1 plan', mime='document')
    doc_md = export_doc(g, files[0]['id'], format='markdown')
    upload(g, '/tmp/report.pdf', folder_id='root', target_name='2026-Q1-report.pdf')

CLI:
    python proc/lib/gdrive_api.py search --account bispro89 --q "name contains 'plan'"
    python proc/lib/gdrive_api.py download --account bispro89 --id <fileId> --out /tmp/x.pdf
    python proc/lib/gdrive_api.py export --account bispro89 --id <docId> --format markdown --out /tmp/x.md
    python proc/lib/gdrive_api.py upload --account bispro89 --src /tmp/x.pdf --folder root
    python proc/lib/gdrive_api.py mkdir --account bispro89 --name "2026 reports" --parent root

Drive query syntax: https://developers.google.com/drive/api/guides/search-files
Docs export formats: https://developers.google.com/drive/api/guides/ref-export-formats
"""

from __future__ import annotations

import argparse
import io
import json
import mimetypes
import os
import sys
from pathlib import Path
from typing import Any, Iterable, Optional

# Allow `python proc/lib/gdrive_api.py ...`.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from google_auth import GoogleClient  # noqa: E402
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload  # noqa: E402


# Friendly aliases → Drive MIME types
MIME_ALIAS = {
    'document': 'application/vnd.google-apps.document',
    'doc': 'application/vnd.google-apps.document',
    'spreadsheet': 'application/vnd.google-apps.spreadsheet',
    'sheet': 'application/vnd.google-apps.spreadsheet',
    'presentation': 'application/vnd.google-apps.presentation',
    'slides': 'application/vnd.google-apps.presentation',
    'folder': 'application/vnd.google-apps.folder',
    'pdf': 'application/pdf',
    'image': 'image/',     # prefix match — handle below
}

# Default fields list — what we want back from list/get
_FIELDS = (
    'id, name, mimeType, parents, owners(displayName,emailAddress), '
    'modifiedTime, createdTime, size, webViewLink, iconLink, '
    'shared, starred, trashed'
)


def _resolve_mime(mime: Optional[str]) -> Optional[str]:
    if not mime:
        return None
    return MIME_ALIAS.get(mime, mime)


def _build_query(
    name_contains: Optional[str] = None,
    name_equals: Optional[str] = None,
    mime: Optional[str] = None,
    parent: Optional[str] = None,
    trashed: bool = False,
    starred: Optional[bool] = None,
    raw_q: Optional[str] = None,
) -> str:
    if raw_q:
        return raw_q
    parts: list[str] = []
    if name_contains:
        parts.append(f"name contains '{name_contains.replace(chr(39), chr(92) + chr(39))}'")
    if name_equals:
        parts.append(f"name = '{name_equals.replace(chr(39), chr(92) + chr(39))}'")
    resolved_mime = _resolve_mime(mime)
    if resolved_mime:
        if mime == 'image':
            parts.append("mimeType contains 'image/'")
        else:
            parts.append(f"mimeType = '{resolved_mime}'")
    if parent:
        parts.append(f"'{parent}' in parents")
    parts.append(f"trashed = {'true' if trashed else 'false'}")
    if starred is True:
        parts.append('starred = true')
    elif starred is False:
        parts.append('starred = false')
    return ' and '.join(parts)


def search(
    g: GoogleClient,
    name_contains: Optional[str] = None,
    name_equals: Optional[str] = None,
    mime: Optional[str] = None,
    parent: Optional[str] = None,
    starred: Optional[bool] = None,
    trashed: bool = False,
    raw_q: Optional[str] = None,
    max_results: int = 100,
    order_by: str = 'modifiedTime desc',
    include_shared_drives: bool = True,
) -> list[dict]:
    """List Drive files matching the query. Auto-paginates."""
    drive = g.service('drive', 'v3')
    q = _build_query(name_contains, name_equals, mime, parent, trashed, starred, raw_q)
    out: list[dict] = []
    page_token: Optional[str] = None
    fields = f'nextPageToken, files({_FIELDS})'
    while True:
        params: dict[str, Any] = {
            'q': q,
            'fields': fields,
            'pageSize': min(1000, max_results - len(out)),
            'orderBy': order_by,
        }
        if include_shared_drives:
            params.update({
                'supportsAllDrives': True,
                'includeItemsFromAllDrives': True,
            })
        if page_token:
            params['pageToken'] = page_token
        resp = drive.files().list(**params).execute()
        for f in resp.get('files', []) or []:
            out.append(f)
            if len(out) >= max_results:
                return out
        page_token = resp.get('nextPageToken')
        if not page_token:
            break
    return out


def get_file(g: GoogleClient, file_id: str) -> dict:
    drive = g.service('drive', 'v3')
    return drive.files().get(
        fileId=file_id, fields=_FIELDS, supportsAllDrives=True,
    ).execute()


def download(g: GoogleClient, file_id: str, out_path: str | Path) -> Path:
    """Download binary file. For Google Docs/Sheets/Slides, use `export_doc()`."""
    drive = g.service('drive', 'v3')
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    request = drive.files().get_media(fileId=file_id, supportsAllDrives=True)
    buf = io.FileIO(str(out), 'wb')
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return out


# Google Docs/Sheets/Slides export MIME mapping
_EXPORT_FORMATS = {
    'pdf': 'application/pdf',
    'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'odt': 'application/vnd.oasis.opendocument.text',
    'ods': 'application/vnd.oasis.opendocument.spreadsheet',
    'odp': 'application/vnd.oasis.opendocument.presentation',
    'txt': 'text/plain',
    'html': 'text/html',
    'markdown': 'text/markdown',
    'md': 'text/markdown',
    'csv': 'text/csv',
    'epub': 'application/epub+zip',
    'rtf': 'application/rtf',
    'png': 'image/png',
    'jpeg': 'image/jpeg',
    'svg': 'image/svg+xml',
}


def export_doc(g: GoogleClient, file_id: str, format: str = 'markdown', out_path: Optional[str | Path] = None) -> bytes | Path:
    """Export a Google Docs/Sheets/Slides file. Returns bytes if no out_path, else path.

    `format` is a friendly alias (markdown/pdf/docx/csv/...). See `_EXPORT_FORMATS`.
    """
    drive = g.service('drive', 'v3')
    mime = _EXPORT_FORMATS.get(format.lower())
    if not mime:
        raise ValueError(f'Unknown export format {format!r}. Known: {sorted(_EXPORT_FORMATS)}')
    request = drive.files().export_media(fileId=file_id, mimeType=mime)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    data = buf.getvalue()
    if out_path:
        p = Path(out_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return p
    return data


def upload(
    g: GoogleClient,
    src_path: str | Path,
    folder_id: str = 'root',
    target_name: Optional[str] = None,
    convert_to_doc: bool = False,
) -> dict:
    """Upload a local file to Drive.

    `convert_to_doc=True` converts uploads to Google Docs/Sheets/Slides where applicable.
    """
    drive = g.service('drive', 'v3')
    src = Path(src_path)
    if not src.exists():
        raise FileNotFoundError(src)
    name = target_name or src.name
    mime, _ = mimetypes.guess_type(str(src))
    metadata: dict[str, Any] = {'name': name, 'parents': [folder_id]}
    if convert_to_doc:
        if mime in ('application/msword',
                    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                    'text/plain', 'text/html', 'text/markdown'):
            metadata['mimeType'] = 'application/vnd.google-apps.document'
        elif mime in ('application/vnd.ms-excel',
                      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                      'text/csv'):
            metadata['mimeType'] = 'application/vnd.google-apps.spreadsheet'
        elif mime in ('application/vnd.ms-powerpoint',
                      'application/vnd.openxmlformats-officedocument.presentationml.presentation'):
            metadata['mimeType'] = 'application/vnd.google-apps.presentation'
    media = MediaFileUpload(str(src), mimetype=mime, resumable=True)
    return drive.files().create(
        body=metadata, media_body=media,
        fields=_FIELDS, supportsAllDrives=True,
    ).execute()


def create_folder(g: GoogleClient, name: str, parent_id: str = 'root') -> dict:
    drive = g.service('drive', 'v3')
    return drive.files().create(
        body={
            'name': name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [parent_id],
        },
        fields=_FIELDS, supportsAllDrives=True,
    ).execute()


def create_doc(g: GoogleClient, name: str, content: str = '', parent_id: str = 'root') -> dict:
    """Create a new Google Doc with optional plain-text content."""
    drive = g.service('drive', 'v3')
    metadata = {
        'name': name,
        'mimeType': 'application/vnd.google-apps.document',
        'parents': [parent_id],
    }
    if content:
        # Upload plain text and let Drive auto-convert to Doc
        buf = io.BytesIO(content.encode('utf-8'))
        from googleapiclient.http import MediaIoBaseUpload
        media = MediaIoBaseUpload(buf, mimetype='text/plain', resumable=False)
        return drive.files().create(
            body=metadata, media_body=media,
            fields=_FIELDS, supportsAllDrives=True,
        ).execute()
    return drive.files().create(
        body=metadata, fields=_FIELDS, supportsAllDrives=True,
    ).execute()


def update_metadata(
    g: GoogleClient,
    file_id: str,
    name: Optional[str] = None,
    starred: Optional[bool] = None,
    add_parents: Optional[Iterable[str]] = None,
    remove_parents: Optional[Iterable[str]] = None,
) -> dict:
    drive = g.service('drive', 'v3')
    body: dict[str, Any] = {}
    if name is not None:
        body['name'] = name
    if starred is not None:
        body['starred'] = starred
    params: dict[str, Any] = {
        'fileId': file_id,
        'body': body,
        'fields': _FIELDS,
        'supportsAllDrives': True,
    }
    if add_parents:
        params['addParents'] = ','.join(add_parents)
    if remove_parents:
        params['removeParents'] = ','.join(remove_parents)
    return drive.files().update(**params).execute()


def trash(g: GoogleClient, file_id: str) -> dict:
    """Move file to trash (recoverable for ~30d)."""
    return update_metadata(g, file_id) if False else g.service('drive', 'v3').files().update(
        fileId=file_id, body={'trashed': True}, fields=_FIELDS, supportsAllDrives=True,
    ).execute()


def delete_permanent(g: GoogleClient, file_id: str) -> None:
    """Permanently delete (no recovery). Use with care."""
    g.service('drive', 'v3').files().delete(fileId=file_id, supportsAllDrives=True).execute()


def update_doc_text(g: GoogleClient, file_id: str, new_content: str) -> dict:
    """Replace a Google Doc body with plain text. Re-uploads via media."""
    drive = g.service('drive', 'v3')
    from googleapiclient.http import MediaIoBaseUpload
    buf = io.BytesIO(new_content.encode('utf-8'))
    media = MediaIoBaseUpload(buf, mimetype='text/plain', resumable=False)
    return drive.files().update(
        fileId=file_id, media_body=media, fields=_FIELDS, supportsAllDrives=True,
    ).execute()


def about(g: GoogleClient) -> dict:
    """User + storage quota info."""
    drive = g.service('drive', 'v3')
    return drive.about().get(fields='user,storageQuota').execute()


def save_json(data: Any, path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str))
    return p


# ---- CLI


def _cmd_search(args) -> int:
    g = GoogleClient(args.account)
    files = search(
        g,
        name_contains=args.name,
        mime=args.mime,
        parent=args.parent,
        raw_q=args.q,
        max_results=args.max,
    )
    if args.out:
        save_json(files, args.out)
        print(f'Wrote {len(files)} files → {args.out}')
    else:
        for f in files:
            owner = (f.get('owners') or [{}])[0].get('emailAddress', '?')
            kind = f['mimeType'].split('.')[-1]
            size = f.get('size', '-')
            print(f"  {f['modifiedTime'][:10]}  {kind:<12}  {f['id']:<33}  {f['name']}  ({owner}, {size}B)")
    return 0


def _cmd_get(args) -> int:
    g = GoogleClient(args.account)
    print(json.dumps(get_file(g, args.id), ensure_ascii=False, indent=2))
    return 0


def _cmd_download(args) -> int:
    g = GoogleClient(args.account)
    p = download(g, args.id, args.out)
    print(f'Downloaded → {p} ({p.stat().st_size}B)')
    return 0


def _cmd_export(args) -> int:
    g = GoogleClient(args.account)
    if args.out:
        p = export_doc(g, args.id, format=args.format, out_path=args.out)
        print(f'Exported {args.format} → {p} ({p.stat().st_size}B)')
    else:
        data = export_doc(g, args.id, format=args.format)
        sys.stdout.buffer.write(data)
    return 0


def _cmd_upload(args) -> int:
    g = GoogleClient(args.account)
    f = upload(g, args.src, folder_id=args.folder, target_name=args.name, convert_to_doc=args.convert)
    print(f'Uploaded: {f["name"]}  id={f["id"]}  → {f.get("webViewLink")}')
    return 0


def _cmd_mkdir(args) -> int:
    g = GoogleClient(args.account)
    f = create_folder(g, args.name, parent_id=args.parent)
    print(f'Created folder: {f["name"]}  id={f["id"]}  → {f.get("webViewLink")}')
    return 0


def _cmd_doc_create(args) -> int:
    g = GoogleClient(args.account)
    content = ''
    if args.from_file:
        content = Path(args.from_file).read_text()
    elif args.content:
        content = args.content
    f = create_doc(g, args.name, content=content, parent_id=args.parent)
    print(f'Created doc: {f["name"]}  id={f["id"]}  → {f.get("webViewLink")}')
    return 0


def _cmd_trash(args) -> int:
    g = GoogleClient(args.account)
    trash(g, args.id)
    print(f'Trashed {args.id}')
    return 0


def _cmd_about(args) -> int:
    g = GoogleClient(args.account)
    print(json.dumps(about(g), ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog='gdrive_api')
    sub = parser.add_subparsers(dest='cmd', required=True)
    common = lambda sp: sp.add_argument('--account', required=True, choices=['bispro89', 'sikbrad'])

    sp = sub.add_parser('search'); common(sp)
    sp.add_argument('--name', help="name contains (substring)")
    sp.add_argument('--mime', help="MIME alias: document/sheet/presentation/folder/pdf/image OR full MIME")
    sp.add_argument('--parent', help='Parent folder ID (or "root")')
    sp.add_argument('--q', help='Raw Drive query (overrides other flags)')
    sp.add_argument('--max', type=int, default=100)
    sp.add_argument('--out')

    sp = sub.add_parser('get'); common(sp)
    sp.add_argument('--id', required=True)

    sp = sub.add_parser('download'); common(sp)
    sp.add_argument('--id', required=True)
    sp.add_argument('--out', required=True)

    sp = sub.add_parser('export'); common(sp)
    sp.add_argument('--id', required=True)
    sp.add_argument('--format', default='markdown', help=f'One of: {", ".join(sorted(_EXPORT_FORMATS))}')
    sp.add_argument('--out')

    sp = sub.add_parser('upload'); common(sp)
    sp.add_argument('--src', required=True)
    sp.add_argument('--folder', default='root', help='Parent folder ID')
    sp.add_argument('--name', help='Target file name (default: source name)')
    sp.add_argument('--convert', action='store_true', help='Convert to Google Doc/Sheet/Slides')

    sp = sub.add_parser('mkdir'); common(sp)
    sp.add_argument('--name', required=True)
    sp.add_argument('--parent', default='root')

    sp = sub.add_parser('doc-create', help='Create a Google Doc with optional content'); common(sp)
    sp.add_argument('--name', required=True)
    sp.add_argument('--content', help='Plain text body')
    sp.add_argument('--from-file', help='Read body from a local file')
    sp.add_argument('--parent', default='root')

    sp = sub.add_parser('trash'); common(sp)
    sp.add_argument('--id', required=True)

    sp = sub.add_parser('about', help='User + storage quota'); common(sp)

    args = parser.parse_args(argv[1:])
    return {
        'search': _cmd_search,
        'get': _cmd_get,
        'download': _cmd_download,
        'export': _cmd_export,
        'upload': _cmd_upload,
        'mkdir': _cmd_mkdir,
        'doc-create': _cmd_doc_create,
        'trash': _cmd_trash,
        'about': _cmd_about,
    }[args.cmd](args)


if __name__ == '__main__':
    sys.exit(main(sys.argv))
