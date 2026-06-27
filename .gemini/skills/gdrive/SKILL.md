---
name: gdrive
description: Google Drive 파일·문서 검색·다운로드·업로드·생성·수정. 두 개 개인 계정(bispro89@gmail.com, sikbrad@gmail.com) 지원. "구글 드라이브", "Drive 파일 찾아줘", "문서 만들어줘", "Google Doc 만들기", "PDF 업로드", "Sheet 다운로드", "내 드라이브에 X 있어?", "폴더 생성", "파일 정리해줘" 등 Drive 파일·Docs/Sheets/Slides 관련 요청 시 사용. (메일은 `/gmail`, 캘린더는 `/gcal`)
---

# Google Drive 파일·문서 조작 (Drive API)

`google-api-python-client` + OAuth Desktop client 기반. **`drive` scope (full read/write)** — 검색·다운로드·업로드·생성·수정·휴지통 모두 가능. 두 계정 각각 별도 GCP 프로젝트·refresh token.

## 도구 스택
- `proc/lib/google_auth.py` — `GoogleClient(account)`, gmail/gcal/gdrive 모두 같은 토큰 캐시 공유
- `proc/lib/gdrive_api.py` — Drive helper (`search`, `get_file`, `download`, `export_doc`, `upload`, `create_folder`, `create_doc`, `update_metadata`, `update_doc_text`, `trash`, `delete_permanent`, `about`)
- `.env`의 `GOOGLE_BISPRO89_*` / `GOOGLE_SIKBRAD_*`
- 토큰 캐시: `~/.cache/dof-google-{account}.json`

## 전제
1. `pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib` (1회).
2. **첫 로그인 (계정당 1회)** — 스코프에 `drive` 포함. 동의 화면에서 "See, edit, create, and delete all your Google Drive files" 체크 필수.
   ```bash
   python proc/lib/google_auth.py login --account bispro89
   python proc/lib/google_auth.py login --account sikbrad
   ```
3. Refresh token Production 게시 → 무기한.

## 핵심 함수 (`gdrive_api.py`)

| 함수 | 용도 |
|---|---|
| `search(g, name_contains=, mime=, parent=, raw_q=, max_results=100)` | 파일 검색. `mime` alias: `document`/`sheet`/`presentation`/`folder`/`pdf`/`image`. raw_q 우선 |
| `get_file(g, file_id)` | 메타데이터 |
| `download(g, file_id, out_path)` | **바이너리 파일** 다운로드 (PDF, 이미지 등). Docs/Sheets/Slides는 `export_doc()` 써야 함 |
| `export_doc(g, file_id, format='markdown', out_path=None)` | Google **Docs/Sheets/Slides** 변환 다운로드. format: `markdown`/`pdf`/`docx`/`xlsx`/`pptx`/`txt`/`html`/`csv`/`epub` 등 |
| `upload(g, src_path, folder_id='root', target_name=None, convert_to_doc=False)` | 로컬 파일 업로드. `convert_to_doc=True`면 .docx → Google Doc 자동 변환 |
| `create_folder(g, name, parent_id='root')` | 폴더 생성 |
| `create_doc(g, name, content='', parent_id='root')` | Google Doc 생성, 본문 plain text |
| `update_metadata(g, file_id, name=, starred=, add_parents=, remove_parents=)` | 이름·별·이동 |
| `update_doc_text(g, file_id, new_content)` | Google Doc 본문 통째로 교체 (plain text). 정밀 편집은 `docs.googleapis.com/v1/documents/{id}:batchUpdate` 별도 호출 필요 |
| `trash(g, file_id)` | 휴지통 (~30일 복구 가능) |
| `delete_permanent(g, file_id)` | 즉시 삭제, 복구 불가 |
| `about(g)` | 사용자 정보 + 스토리지 quota |
| `save_json(data, path)` | 결과 저장 |

스키마 (search/get):
```python
{
  'id', 'name', 'mimeType',
  'parents': [...],
  'owners': [{displayName, emailAddress}],
  'modifiedTime', 'createdTime', 'size',
  'webViewLink',                      # 브라우저 deep link
  'iconLink',
  'shared', 'starred', 'trashed',
}
```

## Drive 검색 쿼리 (raw_q 사용 시)

```
name contains 'Q1 plan'
name = 'budget.xlsx'
mimeType = 'application/vnd.google-apps.document'
mimeType contains 'image/'
'<folderId>' in parents
trashed = false
starred = true
modifiedTime > '2026-05-01T00:00:00'
fullText contains 'roadmap'           # Docs/Sheets/Slides 본문 검색
sharedWithMe = true
'someone@x.com' in writers
'someone@x.com' in readers
```

조합: `and`/`or`/`not`/`(...)`. 예: `name contains 'plan' and mimeType = 'application/vnd.google-apps.document' and trashed = false`.

전체 문법: https://developers.google.com/drive/api/guides/search-files

## 표준 호출

### 1) 문서 검색 + 본문(markdown) 추출
```python
import sys; sys.path.insert(0, 'proc/lib')
from google_auth import GoogleClient
from gdrive_api import search, export_doc

g = GoogleClient('bispro89')
docs = search(g, name_contains='plan', mime='document', max_results=20)
for d in docs:
    md = export_doc(g, d['id'], format='markdown')
    print(f"--- {d['name']} ---")
    print(md.decode()[:500])
```

### 2) 새 Google Doc 생성 (회의록 등)
```python
from gdrive_api import create_doc
g = GoogleClient('bispro89')
doc = create_doc(g, name='2026-05-08 회의록',
                 content='''# 2026-05-08 주간회의

## 참석자
- ...

## 안건
1. ...
''')
print(doc['webViewLink'])  # 브라우저로 열어 확인
```

### 3) 로컬 PDF 업로드 + 폴더 정리
```python
from gdrive_api import create_folder, upload
g = GoogleClient('bispro89')
folder = create_folder(g, '2026-Q1-reports')
f = upload(g, '/tmp/report.pdf', folder_id=folder['id'], target_name='Q1-summary.pdf')
print(f['webViewLink'])
```

### 4) Sheet → CSV 백업 (자동화)
```python
from gdrive_api import search, export_doc
g = GoogleClient('bispro89')
sheets = search(g, mime='sheet', name_contains='budget')
for s in sheets:
    export_doc(g, s['id'], format='csv',
               out_path=f'output/gdrive-{s["name"].replace(" ","_")}-backup.csv')
```

### 5) 본문 검색 (full-text)
```python
g = GoogleClient('bispro89')
hits = search(g, raw_q="fullText contains 'OKR' and trashed = false", max_results=30)
for h in hits:
    print(f"{h['modifiedTime'][:10]} {h['mimeType'].split('.')[-1]:<12} {h['name']}")
```

### 6) Doc 본문 교체 (자동 보고서 갱신)
```python
from gdrive_api import update_doc_text
g = GoogleClient('bispro89')
update_doc_text(g, '<docId>', new_content='업데이트된 보고서 본문...\n')
```

### 7) CLI
```bash
# 검색 (파일명 자유)
python proc/lib/gdrive_api.py search --account bispro89 \
    --name "plan" --mime document --max 20 \
    --out output/gdrive-bispro89-plan-docs.json

# Google Doc → markdown
python proc/lib/gdrive_api.py export --account bispro89 \
    --id <docId> --format markdown --out /tmp/notes.md

# 바이너리 다운로드
python proc/lib/gdrive_api.py download --account bispro89 \
    --id <fileId> --out /tmp/x.pdf

# 업로드
python proc/lib/gdrive_api.py upload --account bispro89 \
    --src /tmp/report.pdf --folder root

# Google Doc 생성 (파일에서 본문 읽음)
python proc/lib/gdrive_api.py doc-create --account bispro89 \
    --name "주간 노트 2026-05-08" --from-file /tmp/notes.md

# 폴더
python proc/lib/gdrive_api.py mkdir --account bispro89 --name "2026 reports"

# 휴지통
python proc/lib/gdrive_api.py trash --account bispro89 --id <fileId>

# Quota
python proc/lib/gdrive_api.py about --account bispro89
```

## 출력 파일 컨벤션

`output/gdrive-{account}-{description}.json` (검색 결과). description 자유.
- `output/gdrive-bispro89-plan-docs.json`
- `output/gdrive-sikbrad-q1-budget-sheets.json`
- 다운로드/export 산출물은 별도 경로(`/tmp/`, `output/exported/`) 자유.

## ⚠️ 함정과 한계

- **`download` vs `export_doc` 구분**: Google 네이티브 형식(Docs/Sheets/Slides/Drawings) → `export_doc` (자동 변환). PDF/이미지/Office 등 일반 파일 → `download` (raw bytes). 잘못 부르면 403 ("Use Export with Google Docs files").
- **`drive` scope = restricted tier**. Production 미검증 앱이라 동의 화면에 "Google hasn't verified this app" 경고 → Advanced > Continue. 본인 1인 사용엔 OK.
- **`update_doc_text`는 단순 통째 교체**. 정밀 편집(특정 paragraph만, 표 셀 수정 등)은 별도 **Google Docs API** (`docs.googleapis.com/v1/documents/{id}:batchUpdate`) 사용 — 현 helper엔 미구현.
- **공유 드라이브(Shared Drive)** — `supportsAllDrives=True`, `includeItemsFromAllDrives=True` 자동 적용. 내 Drive 외에 공유 드라이브 파일도 검색됨.
- **휴지통**: `trash()`는 30일 보관 후 자동 영구삭제. `delete_permanent()`는 즉시 영구삭제 → 매우 신중.
- **공유 권한 변경** — `permissions.create/delete` 미구현. 필요 시 Drive permissions API 별도 호출.
- **대용량 다운로드/업로드** — `MediaIoBaseDownload`/`MediaFileUpload`가 chunked, resumable 처리. 메모리 폭발 없음. 단 helper의 `export_doc`은 BytesIO에 모음 → 매우 큰 Doc(수백MB)이면 메모리 압박 가능.
- **Drive API quota**: 100M req/day per project, 1000 req/100sec/user. 대량 마이그레이션이면 batch API 고려.
- **`fullText contains` 한국어**: Google이 토크나이저 처리. 부분 매칭 안 될 수 있음 → 여러 키워드 시도.

## 다른 Google 스킬과의 분리

| 스킬 | 용도 | API |
|---|---|---|
| `/gmail` | Gmail 메일 검색·본문·발송·라벨·첨부 | gmail.users.messages |
| `/gcal` | Google 캘린더 일정·생성·삭제·free/busy | calendar.events |
| **`/gdrive`** | Drive 파일·Docs/Sheets/Slides 검색·다운·업·생성·수정 | drive.files |

세 스킬 모두 `proc/lib/google_auth.GoogleClient`를 공유 (같은 OAuth 토큰).
