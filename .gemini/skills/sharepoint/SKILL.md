---
name: sharepoint
description: 회사 SharePoint Online 사이트·문서 라이브러리·파일 검색·다운로드 — MS Graph API. "쉐어포인트", "SharePoint", "회사 문서 받아줘", "팀 사이트 파일", "doflab 사이트", "쉐포 검색" 등 회사 SharePoint 관련 요청 시 사용. 개인 OneDrive는 `/onedrive`, 개인 Google Drive는 `/gdrive`.
---

# SharePoint Online (MS Graph API)

회사(`doflab.sharepoint.com`)의 사이트·문서 라이브러리·파일 read 전용. 쓰기는 의도적으로 미커버 — 회사 SharePoint에 코드로 쓰는 건 위험성이 커서 OneDrive 개인 영역(`/onedrive`)이나 웹 UI 사용 권장.

## 도구 스택
- `proc/lib/msgraph.py` — `GraphClient`
- `proc/lib/sharepoint.py` — `SharePointClient`

## 전제
1. Graph 첫 로그인 (`python3 proc/lib/msgraph.py login`).
2. 사전 승인 권한: `Sites.Read.All`, `Files.Read.All` (admin consent ✓).
3. `MSFT_MYAGENT` 토큰 캐시 공유 (Outlook/Teams 등과 동일).

## 핵심 endpoint

```
GET /v1.0/sites/root
GET /v1.0/sites?search=*
GET /v1.0/sites/{site-id}/drives
GET /v1.0/sites/{site-id}/drive  (default doc library)
GET /v1.0/drives/{drive-id}/root/children
GET /v1.0/drives/{drive-id}/root:/<path>:/children
GET /v1.0/drives/{drive-id}/items/{item-id}
GET <@microsoft.graph.downloadUrl>  (short-lived; no Bearer needed)
POST /v1.0/search/query  (driveItem entityType)
```

`site-id`는 `<host>,<scid>,<sid>` 콤마-구분 GUID 트리플.

## helper API (`sharepoint.py`)

| 메서드 | 용도 |
|---|---|
| `get_root_site()` | 테넌트 루트(`https://<tenant>.sharepoint.com`) |
| `list_sites(query='*', top=50)` | 사용자가 접근 가능한 사이트 |
| `get_site(id_or_path)` | 단일 사이트 |
| `list_drives(site_id)` | 한 사이트의 라이브러리 목록 |
| `get_default_drive(site_id)` | "Documents" 같은 default 라이브러리 |
| `list_items(drive_id, path='/', top=200)` | 폴더 내용 — `[{id, name, kind, size, modified, ...}]` |
| `get_item(drive_id, path_or_id)` | 단일 item 메타 + `download_url` |
| `download_file(drive_id, path_or_id, dest)` | 파일 다운로드 (디렉토리·파일 둘 다 dest 허용) |
| `search(query, top=25)` | 테넌트 전체 driveItem 검색 |

## 표준 호출

### 1) 사이트 → 라이브러리 → 파일 트리
```python
import sys; sys.path.insert(0, 'proc/lib')
from sharepoint import SharePointClient

sp = SharePointClient()
sites = sp.list_sites('*', top=20)
target = next(s for s in sites if 'AX' in s['display_name'])
drives = sp.list_drives(target['id'])
items = sp.list_items(drives[0]['id'], '/')
for i in items:
    print(f"{i['kind'][0].upper()} {i['size']:>10} {i['name']}")
```

### 2) 키워드 검색
```python
hits = sp.search('주문현황', top=10)
for h in hits:
    print(f"{h['name']} — {h['web_url']}")
```

### 3) 특정 파일 다운로드
```python
sp.download_file(drive_id, '/Shared Documents/2026매출.xlsx',
                 dest='output/sp/2026매출.xlsx')
# 또는 item id 로
sp.download_file(drive_id, '01ABCDEF...', dest='output/sp/')
```

### 4) 사이트 path-form 으로 lookup
```python
site = sp.get_site('doflab.sharepoint.com:/sites/AXTeam')
```

## ⚠️ 함정

- **`list_sites('*')`** 가 매우 무거움 (테넌트 전체) — 가능하면 query 좁혀라.
- **download_url은 5분 timeout** — 받자마자 다운로드. helper는 1회용 fetch만.
- **page-size 상한 200** — `list_items`의 `top`은 200까지만 안전.
- **`search/query`는 "사용자가 접근 가능한 것만"** — 비공개 사이트는 안 보임.
- **쓰기 미지원**: 회사 SP에 업로드/수정/삭제는 본 helper 범위 밖. 필요시 [onedrive](onedrive)의 `OneDriveClient` 패턴을 참고해 별도 작성하거나 웹 UI 사용.

## 실패 시 fallback
- 401/403 → silent refresh 실패 → 재로그인
- 사이트가 `Sites.Selected` 식 제한 권한이면 안 보임 (관리자 정책)

## 검증 결과 (2026-05-08)
- list_sites('*') top 20 — 2.0s
- list_drives(DOF Inc.) — 698ms (3 라이브러리)
- list_items(root) — 474ms (3 entries)
- download(team.config.json, 31B) — 533ms
- search('AX') — 2.2s (5 hits)
