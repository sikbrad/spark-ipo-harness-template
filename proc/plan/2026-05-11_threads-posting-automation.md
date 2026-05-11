# Threads(threads.net) 발행 자동화 스킬

## 목표
사용자 명령 → Claude 초안 작성 → confirm → 브라우저 자동화로 threads.net 본인 계정에 발행. `/threads` 스킬로 노출.

## 배경 & 결정
- **API 미사용 결정**: Meta Threads Graph API는 OAuth + redirect URI 호스팅 + 단명/장명 토큰 + 60일 refresh 셋업 부담. 본인 1인 발행에는 ROI 낮음.
- **브라우저 자동화 채택**: 한 번 로그인 → 쿠키 저장 → 이후 게시 박스 입력 + '게시' 클릭으로 발행.
- **엔진 선택 대기**: 사용자가 "playwright mcp" 라고 했으나 프로젝트 컨벤션은 playwright-cli (`proc/lib/pwc.py`). naver-blog/amaranth/salesforce 전부 pwc 패턴. 일관성 위해 pwc 권장하나 사용자 의도 확인 필요.

## 확정사항 (2026-05-11)
- [x] **엔진**: `proc/lib/pwc.py` 기반 (naver-blog/amaranth 동일 패턴)
- [x] **워크플로우**: 사용자가 별도 작성 스킬로 md 생성 → `/threads` 스킬이 md 읽어서 발행. 초안 preview/confirm 불필요.
- [x] **이미지 첨부**: 불포함 (v1 텍스트 전용)
- [x] **답글(reply chain)**: **필수**. md 한 파일에 여러 개 글이 들어있으면 첫 글 + 나머지는 reply chain으로 자동 게시.

## md 포맷 (확정)

```
첫 번째 글 본문 (500자 이하). 이게 root post.

여기 개행 있어도 OK.
---
두 번째 글. root에 대한 reply.
---
세 번째 글. 두 번째에 대한 reply (체인).
---
N번째 글. 직전 글에 대한 reply.
```

- 구분자: `---` (앞뒤 줄바꿈, 단독 줄)
- 첫 블록 = root post
- 이후 블록 = **직전 블록에 대한 reply** (Twitter-style 1/N 2/N 체인)
- 각 블록 500자 이하 — 초과 시 에러 (자동 split 안 함, v2로)
- frontmatter 없음 — 옵션은 CLI 인자로 (`--dry-run` 등)
- 파일 1개당 chain 1개

## 작업 항목

### 1. 엔진 확정 + 부트스트랩
- [x] 엔진: pwc.py 채택
- [x] threads.com 수동 로그인 1회 — Instagram 계정(malacca.whale) 통과
- [x] 세션 저장: `--persistent` 프로필 (naver와 동일 패턴, 별도 state JSON 불필요)

### 2. helper 작성 (`proc/lib/pwc_threads.py`)
- [x] `is_logged_in(s)` / `ensure_home(s)` — Create 버튼 존재로 검증
- [x] `parse_md(md_path)` — `---` split + 500자 검증
- [x] `post_text(s, content, dry_run)` — 단일 글
- [x] `post_chain(s, posts, dry_run)` — chain via "Add to thread"
- [x] `publish_markdown(s, md_path, dry_run)` — end-to-end
- [x] dry-run cleanup — "Don't save" 자동 클릭

### 3. 스킬 정의
- [x] `.claude/skills/threads/SKILL.md` — 트리거 + 부트스트랩 + 사용 예 + helper API + 트러블슈팅

### 4. 문서 반영
- [x] `CLAUDE.md` 스킬 표에 `/threads` 라인 추가

### 5. 검증
- [x] dry-run 단일 글 — 정상 typing + 모달 정리 OK
- [x] dry-run chain 2개 — 1/2, 2/2 marker + chain 정상 (screenshot 검증)
- [ ] **실제 발행 1회 검증** — 사용자 승인 후
- [ ] (옵션) 글자수 초과 케이스 거부 동작 — parse_md ValueError로 자동 보장됨
- [ ] (옵션) 세션 만료 후 재로그인 흐름

## 후속 (v2 후보)
- 이미지/링크 첨부
- 답글(reply to existing post) — `reply_to(post_url, body)`
- 발행 후 정확한 post URL 추출 (본인 프로필 최상단에서)
- 자동 글자수 split (500자 초과 시 chain으로 자동 분할)

## 참고
- threads.net 글자수 한도: 500자
- 본인 발행이라 rate limit 걱정 없음 (수동 페이스)
- naver-blog 패턴이 가장 유사 — `proc/lib/pwc_naver.py` + `.claude/skills/naver-blog/` 참조
