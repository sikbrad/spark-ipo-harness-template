"""SharePoint Online (Office 365 sites) helper via MS Graph API.

Read-focused: list sites/drives/items + download. Mutation on company SharePoint
is intentionally **not** wrapped here — use `onedrive.OneDriveClient` for
personal Drive writes, or open the document on the web for SP edits.

Scopes used:
- Sites.Read.All — list sites and items, search
- Files.Read.All — read file content (covers SP document libraries)
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Iterator, Optional

from msgraph import GraphClient


KST = timezone(timedelta(hours=9))


def _kst(iso: Optional[str]) -> Optional[datetime]:
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso.replace('Z', '+00:00')).astimezone(KST)
    except ValueError:
        return None


def _site_to_dict(s: dict) -> dict:
    return {
        'id': s.get('id'),                      # form: <host>,<siteCollectionId>,<siteId>
        'name': s.get('name') or s.get('displayName') or '',
        'display_name': s.get('displayName') or '',
        'web_url': s.get('webUrl'),
        'description': s.get('description') or '',
        'created': _kst(s.get('createdDateTime')),
        'modified': _kst(s.get('lastModifiedDateTime')),
    }


def _drive_to_dict(d: dict) -> dict:
    return {
        'id': d.get('id'),
        'name': d.get('name') or '',
        'drive_type': d.get('driveType') or '',
        'web_url': d.get('webUrl'),
        'owner': ((d.get('owner') or {}).get('user') or {}).get('displayName')
                 or ((d.get('owner') or {}).get('group') or {}).get('displayName') or '',
        'quota_used': (d.get('quota') or {}).get('used'),
        'quota_total': (d.get('quota') or {}).get('total'),
    }


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
        'created_by': ((i.get('createdBy') or {}).get('user') or {}).get('displayName'),
        'modified_by': ((i.get('lastModifiedBy') or {}).get('user') or {}).get('displayName'),
        'parent_path': (i.get('parentReference') or {}).get('path'),
        'child_count': (i.get('folder') or {}).get('childCount'),
        'download_url': i.get('@microsoft.graph.downloadUrl'),
    }


class SharePointClient:
    """Thin SharePoint Online wrapper around `GraphClient`."""

    def __init__(self, g: Optional[GraphClient] = None):
        self.g = g or GraphClient()

    # ---- sites

    def list_sites(self, query: str = '*', top: int = 50) -> list[dict]:
        """Search SharePoint sites the user can access. Default lists all (`*`)."""
        data = self.g.get('/sites', params={'search': query, '$top': top})
        return [_site_to_dict(s) for s in data.get('value', [])]

    def get_root_site(self) -> dict:
        """Tenant root site (https://<tenant>.sharepoint.com/)."""
        return _site_to_dict(self.g.get('/sites/root'))

    def get_site(self, site_id_or_path: str) -> dict:
        """Resolve by either the composite site id (host,scid,sid) or by the
        web path (host:/sites/<path>:)."""
        if ',' in site_id_or_path:
            return _site_to_dict(self.g.get(f'/sites/{site_id_or_path}'))
        # path form like 'doflab.sharepoint.com:/sites/MyTeam'
        return _site_to_dict(self.g.get(f'/sites/{site_id_or_path}'))

    # ---- drives & items

    def list_drives(self, site_id: str) -> list[dict]:
        return [_drive_to_dict(d) for d in
                self.g.get(f'/sites/{site_id}/drives').get('value', [])]

    def get_default_drive(self, site_id: str) -> dict:
        return _drive_to_dict(self.g.get(f'/sites/{site_id}/drive'))

    def list_items(self, drive_id: str, path: str = '/', top: int = 200) -> list[dict]:
        """List children of a folder. `path` like '/' or '/Shared Documents'."""
        if path in ('', '/'):
            url = f'/drives/{drive_id}/root/children'
        else:
            p = path.lstrip('/')
            url = f'/drives/{drive_id}/root:/{p}:/children'
        out = []
        for item in self.g.paged(url, params={'$top': min(top, 200)}):
            out.append(_item_to_dict(item))
            if len(out) >= top:
                break
        return out

    def get_item(self, drive_id: str, path_or_id: str) -> dict:
        if path_or_id.startswith('/') or '/' in path_or_id and not path_or_id.startswith('01'):
            p = path_or_id.lstrip('/')
            return _item_to_dict(self.g.get(f'/drives/{drive_id}/root:/{p}'))
        return _item_to_dict(self.g.get(f'/drives/{drive_id}/items/{path_or_id}'))

    def download_file(self, drive_id: str, path_or_id: str, dest: str) -> Path:
        """Download a file. Returns the saved path. Uses the short-lived
        `@microsoft.graph.downloadUrl` to avoid Bearer-on-redirect issues."""
        meta = self.get_item(drive_id, path_or_id)
        url = meta.get('download_url')
        if not url:
            raise RuntimeError(f'no downloadUrl for item: {meta.get("name")}')
        import requests
        r = requests.get(url, timeout=120)
        if not r.ok:
            raise RuntimeError(f'download failed [{r.status_code}]: {r.text[:200]}')
        # Heuristic: trailing slash OR no extension OR existing dir → treat as folder
        looks_like_dir = (
            dest.endswith('/') or dest.endswith('\\')
            or Path(dest).is_dir()
            or '.' not in Path(dest).name
        )
        p = Path(dest) / meta['name'] if looks_like_dir else Path(dest)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(r.content)
        return p

    # ---- search

    def search(self, query: str, top: int = 25) -> list[dict]:
        """Tenant-wide /search across drives/items the user can access.

        Uses /search/query (POST). Returns simplified hit dicts.
        """
        body = {
            'requests': [{
                'entityTypes': ['driveItem'],
                'query': {'queryString': query},
                'from': 0,
                'size': min(top, 25),
            }],
        }
        data = self.g.post('/search/query', json_body=body)
        out = []
        for resp in data.get('value', []):
            for cont in resp.get('hitsContainers', []):
                for hit in cont.get('hits', []):
                    res = hit.get('resource') or {}
                    out.append({
                        'name': res.get('name'),
                        'web_url': res.get('webUrl'),
                        'size': res.get('size'),
                        'last_modified': _kst(res.get('lastModifiedDateTime')),
                        'parent_drive_id': ((res.get('parentReference') or {}).get('driveId')),
                        'item_id': res.get('id'),
                        'summary': hit.get('summary'),
                    })
        return out


__all__ = ['SharePointClient', 'KST']
