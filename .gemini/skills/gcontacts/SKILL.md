---
name: gcontacts
description: Google Contacts(People API) 연락처 조회·등록·검색 (read + create only). 두 개 개인 계정(bispro89@gmail.com, sikbrad@gmail.com) 지원. "연락처 추가", "구글 연락처에 등록", "Gmail 주소록", "사람 검색", "전화번호 저장", "연락처 백업", "주소록 dump" 등 Google Contacts 관련 요청 시 사용. **수정·삭제는 의도적으로 미지원 — Google Contacts UI에서 수동.** (메일은 `/gmail`, 캘린더는 `/gcal`, 드라이브는 `/gdrive`)
---

# Google Contacts (People API)

`google-api-python-client` + OAuth Desktop client 기반. 브라우저 0개, 헤드리스. `proc/lib/google_auth.GoogleClient`를 `/gmail`·`/gcal`·`/gdrive`와 공유 — refresh token 같은 캐시에 누적.

**범위 제한**: read(list/search/get) + create만. update/delete는 의도적으로 helper·CLI 모두에서 제외 — 주소록 mutation은 사람이 직접 확인 후 UI에서 처리.

## 도구 스택
- `proc/lib/google_auth.py` — `GoogleClient(account)` (OAuth, 토큰 캐시, silent refresh, scope: `contacts` 포함)
- `proc/lib/gcontacts_api.py` — People helper (`list_contacts`, `search_contacts`, `get_contact`, `create_contact`, `update_contact`, `delete_contact`)
- `.env`의 `GOOGLE_BISPRO89_*` / `GOOGLE_SIKBRAD_*`
- 토큰 캐시: `~/.cache/dof-google-{account}.json`

## 전제
1. `pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib` (1회).
2. **GCP 프로젝트에 People API 활성화** (계정당 1회): https://console.developers.google.com/apis/api/people.googleapis.com/overview
3. **scope에 `contacts` 추가된 토큰** (기존 토큰이라면 1회 재로그인):
   ```bash
   python proc/lib/google_auth.py login --account bispro89
   ```
4. 두 계정 모두 활성화·재로그인 끝났으면 더 이상 브라우저 안 뜸.

## 핵심 함수 (`gcontacts_api.py`)

| 함수 | 용도 |
|---|---|
| `list_contacts(g, sort='last_modified_desc', limit=1000)` | 본인 연결된 연락처 전체 (auto-pagination) |
| `search_contacts(g, query)` | 서버측 substring 검색 (이름·전화·이메일·org) |
| `get_contact(g, resource_name)` | 단건 |
| `get_contacts_batch(g, [resource_names])` | 최대 200개 batch |
| `create_contact(g, given=..., family=..., phones=[...], org=(...), ...)` | 신규 등록 |
| `save_json(data, path)` | 결과 저장 |

수정·삭제 helper는 **의도적으로 미구현**. 필요하면 https://contacts.google.com 에서 직접 처리.

정규화 스키마:
```python
{
  'resource_name', 'etag',
  'display_name', 'family_name', 'given_name',
  'phones': [{value, canonical, type}],          # canonical = '+82...' 정규화
  'emails': [{value, type}],
  'organizations': [{name, title, type}],
  'addresses': [{formatted, type}],
  'urls': [{value, type}],
  'biographies': [str],                          # 메모/약력
  'groups': [...],                               # contactGroups/myContacts 등
  'updated': ISO datetime,
}
```

`type` 값(전화/이메일): `mobile`, `work`, `home`, `homeFax`, `workFax`, `other`. 조직은 `work`/`school`.

## 표준 호출

### 1) 연락처 등록
```python
import sys; sys.path.insert(0, 'proc/lib')
from google_auth import GoogleClient
from gcontacts_api import create_contact

g = GoogleClient('bispro89')
p = create_contact(g,
    given='채린', family='김',
    phones=[('010-3117-9571', 'mobile')],
    org=('고려대학교 스타트업연구원', '연구원'),
    emails=[('chaerin@korea.ac.kr', 'work')],
    biography='2026-05 행사에서 만남',
)
print(p['resource_name'])  # people/c...
```

### 2) 검색 (서버측 substring)
```python
from gcontacts_api import search_contacts
hits = search_contacts(g, '김채린')
# 또는 전화·이메일·조직 부분일치
hits = search_contacts(g, '010-3117')
hits = search_contacts(g, '고려대')
```

### 3) 전체 dump (백업·grep용)
```python
from gcontacts_api import list_contacts, save_json
people = list_contacts(g, sort='last_modified_desc', limit=2000)
save_json(people, 'output/gcontacts-bispro89-all.json')
print(f'{len(people)} contacts')
```

### 4) 두 계정 동시
```python
from gcontacts_api import list_contacts
all_contacts = []
for acct in ('bispro89', 'sikbrad'):
    g = GoogleClient(acct)
    people = list_contacts(g, limit=2000)
    for p in people:
        p['account'] = acct
    all_contacts.extend(people)
```

### 5) CLI
```bash
# 검색
python proc/lib/gcontacts_api.py search --account bispro89 --q '김채린'

# 등록 (이름 split: "김채린" → family='김', given='채린' 자동)
python proc/lib/gcontacts_api.py create --account bispro89 \
    --name '김채린' \
    --phone '010-3117-9571' \
    --email 'chaerin@korea.ac.kr:work' \
    --org '고려대학교 스타트업연구원' --title 연구원

# 전체 dump
python proc/lib/gcontacts_api.py list --account bispro89 \
    --limit 2000 --out output/gcontacts-bispro89-all.json

# 단건
python proc/lib/gcontacts_api.py get --account bispro89 --id people/c4933657522678351938
```

CLI `--phone`/`--email`은 `value` 또는 `value:type` 형식, 여러 번 반복해서 다중. 이름 split은 한글이면 first char = family, latin은 last token = family.

**수정·삭제 명령 없음** — 의도적으로 미구현. 잘못 등록한 연락처는 https://contacts.google.com 에서 직접 수정/삭제.

## 출력 파일 컨벤션

`output/gcontacts-{account}-{description}.json`. 예시:
- `output/gcontacts-bispro89-all.json` — 전체 dump
- `output/gcontacts-sikbrad-search-frix.json` — 키워드 검색 결과

## ⚠️ 함정과 한계

- **People API 활성화 필요** — GCP project별 1회. `SERVICE_DISABLED` 403 뜨면 위 활성화 링크 클릭. `bold-bastion-495705-i4` (bispro89), `pelagic-pod-495705-r2` (sikbrad) 각각.
- **Scope `contacts`** — `/gmail`·`/gcal` 토큰 발급할 때 이미 안 들어있으면 재로그인 필요. 2026-05-11에 `_DEFAULT_SCOPES`에 추가됨.
- **search는 eventually-consistent** — 방금 만든 연락처는 몇 초~몇 분 후에야 인덱싱. fresh data 필요하면 `list_contacts` + 클라이언트측 filter. helper는 warm-up 빈 query를 한 번 보내고 검색.
- **수정·삭제 미지원** — 스킬 정책상 read+create만. People API 자체는 `updateContact`·`deleteContact` 메서드 지원하지만 helper에서 의도적으로 제외 (실수로 사용자 주소록 망가뜨리는 것 방지). 필요하면 https://contacts.google.com UI에서 직접.
- **list `sortOrder`** — `last_modified_desc`(기본), `last_modified_asc`, `first_name_asc`, `last_name_asc`. 전체 1526명 dump도 한 번에 됨.
- **`getBatchGet`은 200개 제한** — helper가 자동 chunking.
- **연락처는 unique 강제 없음** — 같은 이름·전화로 두 번 등록되면 그냥 둘 다 생김. 등록 전에 `search_contacts`로 중복 확인 권장.
- **photo / address / birthday는 helper에서 다 지원 안 함** — 필요하면 `g.service('people', 'v1')` 직접 호출. People API doc: https://developers.google.com/people/api/rest/v1/people#Person
- **회사 Outlook/Teams 연락처는 별개** — 회사 주소록은 MS Graph(`/me/contacts`)로 따로 처리 (현 프로젝트엔 미구현).

## 다른 Google 스킬과의 분리

| 스킬 | 용도 | API |
|---|---|---|
| `/gmail` | Gmail 메일 검색·본문·첨부·발송 | gmail.users.messages |
| `/gcal` | Google 캘린더 일정·free/busy | calendar.events |
| `/gdrive` | Google Drive 파일·Docs/Sheets | drive.files |
| **`/gcontacts`** | Google Contacts (주소록) | people.people |

네 스킬 모두 `proc/lib/google_auth.GoogleClient` 공유.
