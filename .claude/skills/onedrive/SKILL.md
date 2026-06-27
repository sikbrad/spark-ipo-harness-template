---
name: onedrive
description: 회사 OneDrive (개인 `/me/drive`) 파일·폴더 검색·다운로드·**업로드·이동·복사·이름변경·공유·삭제** — MS Graph API. "원드라이브", "OneDrive에 업로드", "회사 드라이브에 저장", "OneDrive 공유링크", "내 드라이브 검색", "1TB 드라이브" 등 OneDrive 관련 요청 시 사용. 회사 SharePoint는 `/sharepoint`, 개인 Google Drive는 `/gdrive`.
---

# OneDrive 개인 드라이브 (MS Graph API)

`백인식 Brad <ins@doflab.com>` 의 OneDrive (`https://doflab-my.sharepoint.com/personal/ins_doflab_com/Documents`). SharePoint(`/sharepoint`)와 토큰·MailClient(`/outlook`)와 동일 토큰 공유.

## 도구 스택
- `proc/lib/msgraph.py` — `GraphClient`
- `proc/lib/onedrive.py` — `OneDriveClient`

## 전제
1. Graph 첫 로그인 (`python3 proc/lib/msgraph.py login`).
2. 사전 승인 권한: `Files.ReadWrite`, `Files.Read.All` (admin consent ✓).
3. 4MB 초과 업로드는 자동으로 uploadSession 으로 전환.

## 핵심 endpoint

```
GET    /v1.0/me/drive
GET    /v1.0/me/drive/root/children
GET    /v1.0/me/drive/root:/<path>
GET    /v1.0/me/drive/root:/<path>:/children
PUT    /v1.0/me/drive/root:/<path>:/content?@microsoft.graph.conflictBehavior=...
POST   /v1.0/me/drive/root:/<path>:/createUploadSession   (>4MB)
POST   /v1.0/me/drive/root:/<parent>:/children            (createFolder)
PATCH  /v1.0/me/drive/items/{id}                          (rename / move)
POST   /v1.0/me/drive/items/{id}/copy
POST   /v1.0/me/drive/items/{id}/createLink               (share)
DELETE /v1.0/me/drive/items/{id}
GET    /v1.0/me/drive/root/search(q='...')
```

`path`는 root 기준 상대경로 (`Documents/Projects/foo.pdf`).

## helper API (`onedrive.py`)

| 메서드 | 용도 |
|---|---|
| `drive_info()` | quota·owner·web_url |
| `list_root(top=200)`, `list_folder(path, top)` | 폴더 children |
| `get_item(path_or_id)` | 단일 item 메타 + downloadUrl |
| `search(query, top=25)` | 드라이브 전체 검색 |
| `download(path_or_id, dest)` | dest가 폴더/없는 dir면 파일명 자동 append |
| `upload(local, remote, conflict='rename'|'replace'|'fail')` | 4MB 자동 분기 |
| `create_folder(parent, name, conflict='fail')` | |
| `move(path_or_id, new_parent, new_name=None)` | |
| `rename(path_or_id, new_name)` | |
| `copy(path_or_id, new_parent, new_name=None)` | async (202) |
| `delete(path_or_id)` | 휴지통으로 이동 |
| `share(path_or_id, scope='view'|'edit', link_type='anonymous'|'organization')` | 공유링크 생성 |

## 표준 호출

### 1) 파일 업로드 + 공유링크
```python
import sys; sys.path.insert(0, 'proc/lib')
from onedrive import OneDriveClient
od = OneDriveClient()
od.create_folder('/', 'Reports', conflict='replace')
item = od.upload('/local/2026Q1-report.xlsx', 'Reports/2026Q1.xlsx')
print(item['web_url'])
link = od.share('Reports/2026Q1.xlsx', scope='view', link_type='organization')
print(link['link']['webUrl'])
```

### 2) 검색 + 일괄 다운로드
```python
for it in od.search('FREEDOM', top=20):
    if it['kind'] == 'file' and it['name'].endswith('.docx'):
        od.download(it['id'], 'output/freedom-docs/')
```

### 3) 백업 패턴 (이동 + 이름 변경)
```python
od.create_folder('Reports', 'Archive', conflict='replace')
od.move('Reports/2026Q1.xlsx', 'Reports/Archive', new_name='2026Q1-final.xlsx')
```

### 4) 큰 파일 업로드 (자동 chunked)
```python
od.upload('/big-video.mp4', 'Videos/big-video.mp4')   # 4MB+면 uploadSession 자동
```

### 5) 정리
```python
od.delete('Reports/Archive/2026Q1-final.xlsx')   # 휴지통
od.delete('Reports/Archive')                     # 휴지통
```

## ⚠️ 함정

- **`conflict` 기본값**: `upload`는 'rename', `create_folder`는 'fail'. 의도와 다르면 명시.
- **`download_url`은 5분 timeout** — get_item 후 즉시 사용.
- **uploadSession 청크는 5MB의 320KiB 배수 권장** (helper는 5MB 고정).
- **`delete`는 휴지통 이동** — 영구삭제는 Recycle Bin 까지 추가 처리 (Graph가 명시 endpoint 없음 → 웹UI 또는 별도 정리 작업).
- **동시 수정 충돌 (eTag)** — `move`/`rename`이 다른 곳에서 변경되면 412. 이 helper는 미커버.
- **공유링크 권한** — `link_type='anonymous'`는 테넌트 정책에 따라 차단될 수 있음. 일반적으로 `'organization'` 권장.

## 실패 시 fallback
- 401/403 → silent refresh 실패 → 재로그인
- 큰 파일 업로드 중 끊김 → uploadSession은 resume 가능하나 helper는 미구현 → 재호출

## 다른 드라이브 스킬과의 분리

| 스킬 | 대상 | 인증 |
|---|---|---|
| **`/onedrive`** | 회사 OneDrive 개인 (`/me/drive`) | Graph + MSAL |
| `/sharepoint` | 회사 SharePoint 사이트·라이브러리 | Graph + MSAL (read만) |
| `/gdrive` | 개인 Google Drive | Google API + OAuth |

## 검증 결과 (2026-05-08)
End-to-end smoke test 전 단계 통과:
- create_folder (`_test_msft_skills_2026-05-08/`) — 639ms
- upload `onedrive_smoke_test.txt` (141B) — 615ms
- download + md5 비교 — **MATCH** ✓
- share-link (organization view) — 1141ms
- delete file + folder, verify removed — 1.3s
