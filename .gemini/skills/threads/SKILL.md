---
name: threads
description: Meta Threads(threads.com) 본인 계정 발행 — 마크다운 파일 → 단일 글 또는 체인 스레드(1/N 2/N) 자동 게시. playwright-cli 기반. "쓰레드 올려줘", "thread 발행", "threads에 글 올려", "체인 스레드 써줘", "1/N 2/N 으로 올려", "md로 쓰레드 발행", "Threads 멀티 포스트" 등 Threads 발행 요청 시 사용.
---

# Threads(threads.com) 발행 자동화

`@playwright/cli` 기반. `proc/lib/pwc_threads.py`의 helper로 Threads compose 모달을 직접 조작한다. 공식 Threads Graph API는 OAuth + redirect URI 호스팅 + 60일 토큰 refresh 셋업 부담이 커서 본인 1인 발행에는 브라우저 자동화가 ROI 우위.

## 도구 스택

- `@playwright/cli` (전역 `playwright-cli`)
- `proc/lib/pwc.py` — 세션 wrapper (`S('threads')`)
- `proc/lib/pwc_threads.py` — Threads helper

## 전제

1. `playwright-cli` 설치 — `npm install -g @playwright/cli@latest` (한 번만).
2. **Threads 세션 부트스트랩 — 2단계**:
   - **첫 1회 헤디드** (로그인 + 2FA):
     ```bash
     playwright-cli -s=threads open https://www.threads.com/login --persistent --headed
     ```
     열리는 브라우저에서 Instagram/Threads 계정으로 로그인 → 2FA 통과 → 메인 피드 진입 확인.
   - **이후 항상 헤드리스**:
     ```bash
     playwright-cli -s=threads close
     playwright-cli -s=threads open --persistent
     ```
     `--persistent` 프로필이 쿠키 보존 → 재로그인 불필요.
3. 동시성: 다른 `-s=` 세션과 별개 브라우저라 충돌 없음.

## 워크플로우

```
사용자: (다른 작성 스킬로 md 파일 생성 — 예: /create-spec, /naver-blog 작성, 직접 작성)
사용자: "이거 threads에 올려줘 — input/threads/foo.md"
Claude: publish_markdown(s, 'input/threads/foo.md') → posts_count, url 반환
```

**초안 preview/confirm 단계 없음**. md 파일이 곧 발행 의도 — 받자마자 발행.

## md 포맷

```
첫 번째 글 본문 (500자 이하). 이게 root post.

여러 줄 OK.
---
두 번째 글. 직전 글에 대한 chain reply (1/N → 2/N).
---
세 번째 글. 또 chain.
---
N번째 글.
```

- 구분자: 단독 줄 `---`
- 첫 블록 = root post
- 이후 블록 = `Add to thread`로 chain 추가 (Twitter-style 1/N 2/N)
- **각 블록 500자 이하** — 초과 시 ValueError (자동 split 안 함)
- frontmatter (`---\\n...\\n---\\n`)가 있으면 파싱 시 무시됨 (v1 미사용)
- 파일 1개 = chain 1개. 여러 별개 글이면 파일 분리

## 핵심 helper (`proc/lib/pwc_threads.py`)

| 함수 | 용도 |
|---|---|
| `is_logged_in(s)` | Create 버튼 존재로 로그인 여부 판정 |
| `ensure_home(s)` | 홈 피드로 이동 + 로그인 검증. 실패 시 부트스트랩 안내 |
| `parse_md(md_path)` | md → 블록 리스트. 500자 검증, 빈 블록 제외 |
| `post_text(s, content, dry_run=False)` | 단일 글 발행 |
| `post_chain(s, posts, dry_run=False)` | 체인 발행 — posts[0]=root, posts[1:]=chain |
| `publish_markdown(s, md_path, dry_run=False)` | md 파일 → parse → chain 발행 (end-to-end) |

모두 `{posts_count, url, dry_run, screenshot}` 반환. `url`은 `/post/` 패턴이 redirect URL에 잡힐 때만 채워짐.

## 표준 호출

### 단일 글
```bash
python3 -c "
import sys; sys.path.insert(0, 'proc/lib')
from pwc import S
import pwc_threads as th

s = S('threads', persistent=True)
print(th.post_text(s, '오늘 처음 threads에 자동으로 글 올려봄. 🤖'))
"
```

### md 파일로 체인 발행
```bash
python3 -c "
import sys; sys.path.insert(0, 'proc/lib')
from pwc import S
import pwc_threads as th

s = S('threads', persistent=True)
print(th.publish_markdown(s, 'input/threads/example.md'))
"
```

### dry-run (실제 발행 안 함, typing만 검증)
```python
th.publish_markdown(s, 'input/threads/example.md', dry_run=True)
# 모달 열고 모든 글 입력 후 "Don't save"로 정리
```

## 발행 후 URL

- 성공 시 결과 dict의 `url`에 `https://www.threads.com/@{user}/post/{id}` 형태
- redirect 안 잡힐 경우 (홈에 머무는 경우) `None` — screenshot으로 발행 여부 시각 확인 가능
- 정확한 post URL이 필요하면 본인 프로필(`/@{user}`) 최상단 글에서 추출 (v2)

## 안정성 패턴 (코드 내장)

- **2개 Create 버튼**: top-nav + floating compose. 코드는 2번째(floating)를 클릭 (1번째는 메뉴 토글).
- **textbox 추적**: chain마다 새 textbox가 추가되지만 accessible name(`Empty text field...`)은 동일 — 항상 마지막(`tb[-1]`)을 찍음.
- **dry-run cleanup**: Escape → "Save / Don't save / Cancel" 다이얼로그 → `Don't save` 자동 클릭.
- **`-`-prefix type 우회**: 첫 글자가 `-`면 `playwright-cli type`이 옵션으로 파싱 → 공백+Backspace로 우회.
- **Post 버튼**: 모달 발행 버튼은 모든 `button "Post"` 매치 중 **마지막** (`post_refs[-1]`). 피드 카드의 다른 Post-prefixed 버튼들과 충돌 회피.

## 알려진 한계 / 주의

- **글자수 hard limit 500**: 초과 시 발행 안 함. 자동 분할 미구현 — 사용자가 직접 split하거나 md에서 `---`로 나눠야 함.
- **이미지/링크 첨부 미지원** (v1 텍스트 전용). 첨부 필요 시 v2 (`pwc_threads_media.py` 분리 예정).
- **답글(reply to existing post) 미지원**: 본 helper는 본인 작성 chain만. 타인 글에 답글은 v2 — `reply_to(post_url, body)` 추가 필요.
- **anti-bot**: 잦은 발행 빈도는 Meta 자동화 탐지 트리거 가능. 운영 시 호출 측에서 빈도 가드 권장.
- **URL 추출 실패 가능성**: 발행 직후 즉시 redirect 안 잡힐 수 있음. 그래도 발행은 됨 — screenshot으로 확인.

## 트러블슈팅

- **로그인 만료**: `is_logged_in(s)` False 또는 `ensure_home`에서 PWCError. 헤디드 재부트스트랩:
  ```bash
  playwright-cli -s=threads close
  playwright-cli -s=threads open https://www.threads.com/login --persistent --headed
  ```
- **모달이 안 닫힘 (드래프트 누적)**: 수동 정리:
  ```bash
  playwright-cli -s=threads press Escape
  # snapshot에서 "Don't save" ref 찾아 click
  ```
- **"Add to thread" 못 찾음**: 직전 블록 타이핑이 안 됐을 가능성. screenshot 확인 후 sleep 시간 증가 또는 helper 안의 `_time.sleep(0.5)` 늘려서 대응.

## 작업 plan

- `proc/plan/2026-05-11_threads-posting-automation.md` — 결정사항, md 포맷, 작업 체크리스트
