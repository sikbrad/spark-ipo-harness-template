"""OneDrive (personal `/me/drive`) helper via MS Graph API.

Read + write covering: list, get, download, upload (small ≤4MB and large via
uploadSession), create folder, move, copy, delete, share.

Scopes used: `Files.ReadWrite`, `Files.Read.All` (admin-consented).
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Iterator, Optional

import requests

from msgraph import GraphClient


KST = timezone(timedelta(hours=9))
_SMALL_UPLOAD_LIMIT = 4 * 1024 * 1024  # 4 MB — Graph PUT-content cap


def _kst(iso: Optional[str]) -> Optional[datetime]:
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso.replace('Z', '+00:00')).astimezone(KST)
    except ValueError:
        return None


def _item_to_dict(i: dict) -> dict:
    is_folder = 'folder' in i
    return {
        'id': i.get('id'),
        'name': i.get('name') or '',
        'kind': 'folder' if is_folder else 'file',
        'size': i.get('size') or 0,
        'web_url': i.get('webUrl'),
        'mime_type': (i.get('file') or {}).get('mimeType'),
        'created': _kst(i.get('createdDateTime')),
        'modified': _kst(i.get('lastModifiedDateTime')),
        'parent_path': (i.get('parentReference') or {}).get('path'),
        'child_count': (i.get('folder') or {}).get('childCount'),
        'download_url': i.get('@microsoft.graph.downloadUrl'),
    }


def _path_segment(p: str) -> str:
    """Normalize a remote path: leading slash stripped, trailing slash stripped."""
    return p.strip('/').strip()


class OneDriveClient:
    """`/me/drive` wrapper. All paths are relative to drive root.

    Examples:
        cli.list_root()
        cli.list_folder('Documents/Projects')
        cli.upload('local.txt', 'Documents/local.txt')
        cli.download('Documents/foo.pdf', 'output/foo.pdf')
    """

    def __init__(self, g: Optional[GraphClient] = None):
        self.g = g or GraphClient()

    # ---- meta

    def drive_info(self) -> dict:
        d = self.g.get('/me/drive')
        return {
            'id': d.get('id'),
            'drive_type': d.get('driveType'),
            'owner': ((d.get('owner') or {}).get('user') or {}).get('displayName'),
            'quota_used': (d.get('quota') or {}).get('used'),
            'quota_total': (d.get('quota') or {}).get('total'),
            'quota_remaining': (d.get('quota') or {}).get('remaining'),
            'web_url': d.get('webUrl'),
        }

    # ---- list

    def list_root(self, top: int = 200) -> list[dict]:
        return self.list_folder('/', top=top)

    def list_folder(self, path: str = '/', top: int = 200) -> list[dict]:
        seg = _path_segment(path)
        url = '/me/drive/root/children' if not seg else f'/me/drive/root:/{seg}:/children'
        out = []
        for it in self.g.paged(url, params={'$top': min(top, 200)}):
            out.append(_item_to_dict(it))
            if len(out) >= top:
                break
        return out

    def get_item(self, path_or_id: str) -> dict:
        if path_or_id.startswith('01') and '/' not in path_or_id:
            return _item_to_dict(self.g.get(f'/me/drive/items/{path_or_id}'))
        seg = _path_segment(path_or_id)
        if not seg:
            return _item_to_dict(self.g.get('/me/drive/root'))
        return _item_to_dict(self.g.get(f'/me/drive/root:/{seg}'))

    def search(self, query: str, top: int = 25) -> list[dict]:
        """Search across the user's drive."""
        out = []
        for it in self.g.paged(f"/me/drive/root/search(q='{query}')",
                                params={'$top': min(top, 25)}):
            out.append(_item_to_dict(it))
            if len(out) >= top:
                break
        return out

    # ---- download

    def download(self, path_or_id: str, dest: str) -> Path:
        meta = self.get_item(path_or_id)
        if meta['kind'] != 'file':
            raise ValueError(f'not a file: {meta["name"]}')
        url = meta.get('download_url')
        if not url:
            # fallback: request /content (302 to downloadUrl)
            data = self.g.get(f'/me/drive/items/{meta["id"]}',
                              params={'$select': '@microsoft.graph.downloadUrl'})
            url = data.get('@microsoft.graph.downloadUrl')
        r = requests.get(url, timeout=300)
        if not r.ok:
            raise RuntimeError(f'download failed [{r.status_code}]: {r.text[:200]}')
        looks_like_dir = (dest.endswith('/') or dest.endswith('\\')
                          or Path(dest).is_dir() or '.' not in Path(dest).name)
        p = Path(dest) / meta['name'] if looks_like_dir else Path(dest)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(r.content)
        return p

    # ---- upload

    def upload(self, local_path: str, remote_path: str,
               conflict: str = 'rename') -> dict:
        """Upload a local file to `remote_path`. `conflict` ∈
        {'rename', 'replace', 'fail'}.

        Picks small (PUT) vs uploadSession based on file size.
        """
        local = Path(local_path)
        if not local.is_file():
            raise FileNotFoundError(local_path)
        seg = _path_segment(remote_path)
        size = local.stat().st_size
        if size <= _SMALL_UPLOAD_LIMIT:
            return self._upload_small(local, seg, conflict)
        return self._upload_session(local, seg, conflict)

    def _upload_small(self, local: Path, remote_seg: str, conflict: str) -> dict:
        token = self.g.token()
        url = (f'https://graph.microsoft.com/v1.0/me/drive/root:/{remote_seg}:/'
               f'content?@microsoft.graph.conflictBehavior={conflict}')
        with local.open('rb') as f:
            r = requests.put(url, data=f, headers={
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/octet-stream',
            }, timeout=300)
        if not r.ok:
            raise RuntimeError(f'upload failed [{r.status_code}]: {r.text[:300]}')
        return _item_to_dict(r.json())

    def _upload_session(self, local: Path, remote_seg: str, conflict: str) -> dict:
        # 1) create session
        sess = self.g.post(
            f'/me/drive/root:/{remote_seg}:/createUploadSession',
            json_body={'item': {'@microsoft.graph.conflictBehavior': conflict}},
        )
        upload_url = sess['uploadUrl']
        size = local.stat().st_size
        # 2) chunked PUT
        CHUNK = 5 * 1024 * 1024  # 5 MB; must be multiple of 320KiB except last
        with local.open('rb') as f:
            offset = 0
            while offset < size:
                buf = f.read(CHUNK)
                end = offset + len(buf) - 1
                r = requests.put(upload_url, data=buf, headers={
                    'Content-Length': str(len(buf)),
                    'Content-Range': f'bytes {offset}-{end}/{size}',
                }, timeout=300)
                if r.status_code in (200, 201):
                    return _item_to_dict(r.json())
                if r.status_code != 202:
                    raise RuntimeError(f'chunk failed [{r.status_code}]: {r.text[:300]}')
                offset += len(buf)
        raise RuntimeError('upload finished without 200/201 — unexpected')

    # ---- mutate

    def create_folder(self, parent_path: str, name: str,
                      conflict: str = 'fail') -> dict:
        seg = _path_segment(parent_path)
        url = '/me/drive/root/children' if not seg else f'/me/drive/root:/{seg}:/children'
        return _item_to_dict(self.g.post(url, json_body={
            'name': name,
            'folder': {},
            '@microsoft.graph.conflictBehavior': conflict,
        }))

    def move(self, path_or_id: str, new_parent_path: str,
             new_name: Optional[str] = None) -> dict:
        item_id = self.get_item(path_or_id)['id']
        new_parent = self.get_item(new_parent_path)
        body = {'parentReference': {'id': new_parent['id']}}
        if new_name:
            body['name'] = new_name
        return _item_to_dict(self.g.patch(f'/me/drive/items/{item_id}',
                                          json_body=body))

    def rename(self, path_or_id: str, new_name: str) -> dict:
        item_id = self.get_item(path_or_id)['id']
        return _item_to_dict(self.g.patch(f'/me/drive/items/{item_id}',
                                          json_body={'name': new_name}))

    def copy(self, path_or_id: str, new_parent_path: str,
             new_name: Optional[str] = None) -> str:
        """Async copy. Returns the monitor URL (HTTP 202)."""
        item_id = self.get_item(path_or_id)['id']
        new_parent = self.get_item(new_parent_path)
        body = {'parentReference': {'driveId': new_parent.get('id') and 'me',  # noqa
                                    'id': new_parent['id']}}
        if new_name:
            body['name'] = new_name
        # NOTE: copy returns 202 with Location header; helper returns whatever JSON if any
        return self.g.post(f'/me/drive/items/{item_id}/copy', json_body=body)

    def delete(self, path_or_id: str) -> None:
        item_id = self.get_item(path_or_id)['id']
        self.g.delete(f'/me/drive/items/{item_id}')

    def share(self, path_or_id: str, scope: str = 'view',
              link_type: str = 'organization') -> dict:
        """Create a shareable link. `scope` ∈ {'view', 'edit'},
        `link_type` ∈ {'anonymous', 'organization'}."""
        item_id = self.get_item(path_or_id)['id']
        return self.g.post(f'/me/drive/items/{item_id}/createLink',
                           json_body={'type': scope, 'scope': link_type})


__all__ = ['OneDriveClient', 'KST']
