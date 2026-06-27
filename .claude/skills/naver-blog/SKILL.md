---
name: naver-blog
description: 네이버 블로그(blog.naver.com) 글쓰기·읽기·수정 + 마크다운 파일 자동 발행. playwright-cli 기반. "네이버 블로그 글쓰기", "blog에 글 올려줘", "블로그 글 수정", "네이버 블로그 글 가져와", "마크다운으로 블로그 발행", "obsidian 글 네이버 블로그에 올려줘" 등 네이버 블로그 발행·읽기·수정 요청 시 사용.
---

# 네이버 블로그 자동 발행/조회/수정

`@playwright/cli` 기반. `proc/lib/pwc_naver.py`의 helper로 SmartEditor 3을 직접 조작한다. 네이버 공식 글쓰기 API는 OAuth 앱 심사 + 카테고리/태그/공개범위 미지원이고, MetaWeblog XMLRPC는 2020-05-06자 폐기됐기 때문에 브라우저 자동화가 사실상 유일한 길.

## 도구 스택

- `@playwright/cli` (전역 `playwright-cli` 명령) — 사이트별 격리 세션, 영속 프로필
- `proc/lib/pwc.py` — 세션 wrapper (`S('naver')`)
- `proc/lib/pwc_naver.py` — Naver blog helper

## 전제

1. `playwright-cli` 설치 — 한 번만: `npm install -g @playwright/cli@latest`.
2. `.env`에 자격증명 저장 (변수명은 계정별 namespace):
   ```
   NAVER_MALACCA_ID=malacca_whale@naver.com
   NAVER_MALACCA_PW=...
   ```
3. **Naver 세션 부트스트랩 — 2단계**:
   - **첫 1회 헤디드** (SMS 인증 때문에 사용자 화면 필요):
     ```bash
     playwright-cli -s=naver open https://nid.naver.com/nidlogin.login --persistent --headed
     ```
     브라우저 창 열리면 직접 ID/PW 입력 → "로그인 상태 유지" 체크 → SMS 새기기 인증 통과 → `blog.naver.com/{blog_id}` 진입 확인.
   - **이후 항상 헤드리스로 전환**:
     ```bash
     playwright-cli -s=naver close
     playwright-cli -s=naver open --persistent
     ```
     `--headed` 빠지면 헤드리스 (default). `--persistent` 프로필이 디스크에 로그인 쿠키 보존 → 재오픈 시 별도 로그인 불필요. 라이프사이클 검증 끝남 (write/edit/read/delete 전부 헤드리스 정상 동작).
4. 동시성: 다른 `-s=` 세션과 별개 브라우저라 충돌 없음.

## 핵심 helper (`proc/lib/pwc_naver.py`)

| 함수 | 용도 |
|---|---|
| `is_logged_in(s)` | 블로그 홈 redirect 검사로 로그인 여부 판정 |
| `login(s)` / `ensure_login(s)` | `.env` 자격증명으로 자동 로그인. 실패 시 헤디드 부트스트랩 안내 |
| `open_editor(s, blog_id=...)` | SmartEditor 진입. 임시저장 다이얼로그·도움말 패널 자동 처리 |
| `set_title(s, title)` / `set_body(s, body)` | 제목·본문 직접 입력 (Cmd+A → Backspace → type) |
| `publish(s, category=None, tags=None, visibility="public", allow_comments=True)` | 발행 패널 열고 옵션 적용 후 발행 → `logNo` 반환 |
| `write_post(s, title, body, ...)` | end-to-end: 로그인 → 에디터 → 입력 → 발행 |
| `read_post(s, log_no, blog_id=...)` | 게시 글의 제목/본문 추출 → `{title, body, url}` |
| `open_for_edit(s, log_no, ...)` | 기존 글을 에디터에 로드 (post content 비동기 로드 polling) |
| `edit_post(s, log_no, title=None, body=None, ...)` | 기존 글 수정 (텍스트만) → 같은 `logNo` 반환. **이미지가 있던 글에 호출하면 이미지 삭제됨** |
| `publish_markdown(s, md_path, ...)` | frontmatter + 본문 + 인라인 이미지 통합 발행 → `logNo` |
| `edit_markdown(s, log_no, md_path, ...)` | 마크다운 파일로 기존 글 교체 (이미지 포함). 이미지 있는 글 수정엔 이쪽 사용 |
| `delete_post(s, log_no, ...)` | 글 삭제. 멱등(이미 삭제됐으면 True 반환). PostView iframe의 본인-only 삭제 링크를 클릭하고 native confirm을 자동 수락 |

## 마크다운 frontmatter 스키마

```yaml
---
title: "글 제목"               # 필수
tags: [태그1, 태그2]           # 또는 block list:  tags:\n  - foo\n  - bar
category: "카테고리명"          # 옵션 (블로그에 존재해야)
visibility: private            # public | neighbors | mutual | private (기본 public)
allow_comments: true
---
```

본문에서 인식되는 이미지 문법:
- `![alt](images/foo.png)` (표준 Markdown — 절대/상대 경로)
- `![[name.png]]` (Obsidian 위키링크 — 파일명만 — md 파일 폴더 하위에서 자동 검색)

헤딩(`#`, `##`, `###`)은 marker 제거 후 일반 단락으로 변환됨 (SmartEditor가 마크다운 헤딩을 직접 지원하지 않음).

## 표준 호출 — write/read/edit (직접 인자)

```bash
python3 -c "
import sys; sys.path.insert(0, 'proc/lib')
from pwc import S
import pwc_naver as nb

s = S('naver', persistent=True)

# 글쓰기 (공개 발행)
log_no = nb.write_post(
    s,
    title='오늘의 노트',
    body='첫 줄.\n둘째 줄.\n',
    tags=['일상', '메모'],
    visibility='public',
)
print('logNo:', log_no)

# 글 읽기
post = nb.read_post(s, log_no)
print('title:', post['title'])
print('body[:120]:', post['body'][:120])

# 글 수정
nb.edit_post(s, log_no=log_no, title='오늘의 노트 (수정)', body='바뀐 본문.', visibility='public')
"
```

## 표준 호출 — 마크다운 파일 발행 (이미지 포함)

```bash
python3 -c "
import sys; sys.path.insert(0, 'proc/lib')
from pwc import S
import pwc_naver as nb

s = S('naver', persistent=True)
log_no = nb.publish_markdown(s, 'input/blog/naver-blog-post-auto-example/sample.md')
print('logNo:', log_no)
print('URL :', f'https://blog.naver.com/malacca_whale/{log_no}')
"
```

위 호출은 `sample.md`의 frontmatter(title/tags/visibility/allow_comments)를 그대로 사용한다. 임시 override:

```python
nb.publish_markdown(s, md_path, override_visibility='private')   # 검증 시 비공개로
```

## 발행 옵션

| 인자 | 값 | 비고 |
|---|---|---|
| `visibility` | `public` / `neighbors` / `mutual` / `private` | 기본 `public` |
| `allow_comments` | `True` / `False` | 기본 `True` |
| `tags` | `list[str]` (최대 30개) | 패널의 태그 입력에 한 개씩 Enter로 입력 |
| `category` | 카테고리명 (예: `"게시판"`) | 블로그에 등록된 카테고리만 가능. None이면 기본 카테고리 |

## 안정성 확보 패턴 (코드에 내장)

- **type `-`-prefix**: 줄이 `-`로 시작하면 `playwright-cli type`이 옵션으로 파싱 → `_safe_type`이 `--` 구분자로 우회.
- **네이티브 beforeunload "Leave site?" + delete confirm + 삭제됨 alert**: SmartEditor가 `addEventListener('beforeunload')`로 등록 → JS로 제거 불가. `ensure_login`에서 `_install_dialog_auto_accept(s)`를 호출해 세션 단위 `page.on('dialog', d => d.accept())` 핸들러를 등록 (멱등). 이후 모든 native modal은 사용자에게 보이지 않고 자동 수락됨. 추가로 `_safe_goto`가 dialog-accept 후 재시도 (`subprocess.TimeoutExpired`까지 포함).
- **이미지 업로드**: `사진 추가` 버튼 클릭 → `playwright-cli upload <path>`로 hidden file input에 직접 set → 네이티브 OS 파일 다이얼로그 우회. 5초 settle 후 다음 블록.
- **edit 모드 비동기 로드**: 진입 후 title이 placeholder("제목")에서 실제 값으로 바뀔 때까지 polling (최대 15초).

## 알려진 한계 / 주의

- **anti-bot**: 로그인 자동화는 캡차/새기기 인증 트리거 가능. 발생 시 헤디드 부트스트랩으로 재로그인. 발행 빈도가 너무 높으면 계정 임시 잠금 위험.
- **빈도 제한**: 운영 시 하루 N건 / 발행 사이 간격 N분 같은 가드를 호출 측에서 구현 권장.
- **마크다운 표현 한계**: SmartEditor 헤딩·리스트·코드블록은 직접 매핑 안 됨 → 일반 단락으로 들어감. 굵게/기울임은 별도 helper 추가 시 매핑 가능.
- **외부 URL 이미지**: SmartEditor가 외부 핫링크를 차단할 수 있음. 필요 시 `urllib.request`로 임시 다운로드 → 로컬 업로드 경로로 fallback (현재 미구현).
- **카테고리 dropdown**: 첫 검색은 listitem 텍스트 매치 — 동명 카테고리가 있으면 위에서부터 hit. 정확한 매칭이 필요하면 helper 측 selector 강화.

## 트러블슈팅

- **자동 로그인 실패 (캡차/새기기)**: 헤디드 모드로 재오픈 후 사용자 처리:
  ```bash
  playwright-cli -s=naver open https://nid.naver.com/nidlogin.login --persistent --headed
  ```
- **"Leave site?" dialog 막힘**: 보통 `_safe_goto`가 자동 처리하나, 잔류 modal이 있으면:
  ```bash
  playwright-cli -s=naver dialog-accept
  ```
- **임시저장 글 누적**: 자동저장이 매번 임시 draft를 만든다. `open_editor`가 "작성 중인 글" 다이얼로그에서 자동 취소를 시도하지만 누적되면 `https://blog.naver.com/{id}/postlist?categoryNo=0&from=postList&parentCategoryNo=0` 의 임시저장 목록에서 수동 정리.
- **`logNo` 추출 실패**: 발행 직후 redirect URL에 `logNo=` 또는 `/{blog_id}/{logNo}` 패턴이 있어야 함. 실패 시 발행 panel 응답 timing 이슈 — `publish` 내부 `_time.sleep(5)` 늘려서 대응.

## 관련 입력

- 예시 마크다운: `input/blog/naver-blog-post-auto-example/sample.md` + `images/{hero,diagram}.png`
- 작업 plan: `proc/plan/2026-05-08_naver-blog-agent.md`
