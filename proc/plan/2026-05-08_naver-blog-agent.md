# 네이버 블로그 자동 발행 에이전트

대상 계정: `malacca_whale@naver.com` (블로그 ID: `malacca_whale`)

## 목표

자연어로 제목/본문/카테고리/태그/공개범위만 주면 SmartEditor 3.0을 거쳐 **공개 발행까지 완전 자동화**한다. 1차는 텍스트, 2차에서 로컬 이미지 업로드 + URL 이미지 임베드.

## 핵심 결정사항

| 항목 | 선택 | 비고 |
|------|------|------|
| 콘텐츠 소스 | 유저가 매번 본문 제공 | 1차에서는 AI 생성 안 함 |
| 발행 모드 | 공개 발행까지 자동 | 비공개/임시저장은 옵션으로 노출 |
| 미디어 | text → local image → URL image | 단계별 도입 |
| 인증 | `.env` ID/PW + 자동 로그인 | **단, 캡차/새기기 인증 시 headed fallback** |
| 자동화 도구 | playwright-cli `-s=naver` | 기존 `proc/lib/pwc.py` 재사용 |
| 세션 영속성 | `--persistent` 프로필 | 한번 로그인 후 쿠키 보존 — 매 호출 자동 로그인 회피 |

## 위험 경고 (.env 직로그인 관련)

유저가 명시적으로 선택했지만 다음을 인지해야 함:

1. **캡차 트리거**: 네이버는 키 입력 패턴 + IP/기기 fingerprint 검사. 자동 로그인 반복 시 캡차 강제 발생
2. **새기기 인증**: SMS/이메일 OTP 요구 — 자동 통과 불가, headed 모드에서 사용자 개입 필요
3. **계정 잠금**: 비정상 활동 누적 시 임시 잠금. 운영 시 발행 빈도 제한 권장(하루 N건)
4. **ToS**: 자동 로그인 자체는 본인 계정에 한해 허용되지만, 대량 발행은 어뷰징 판정 가능

→ **완화책**: ① `--persistent` 프로필로 재로그인 빈도 최소화, ② 키 입력 사이 200~600ms jitter, ③ 자동 로그인 실패 감지 시 즉시 headed 모드 전환 prompt, ④ 발행 간 최소 인터벌 강제.

## 아키텍처

```
proc/lib/pwc_naver.py          # 도메인 helper (login, open_editor, write_post, publish)
proc/cli/naver_blog_post.py    # CLI 진입점 — JSON/YAML payload 받아 발행
.claude/skills/naver-blog/     # SKILL.md (명세 + 사용법)
.gemini/skills/naver-blog/     # 동일 (symlink 또는 복사)
.env                           # NAVER_ID, NAVER_PW (이미 .gitignore에 있음 — 확인됨)
```

세션 격리: `-s=naver`. 다른 사이트(teams/amaranth/salesforce)와 완전 독립, 동시 실행 OK.

## URL/엔드포인트 맵 (조사 필요)

- 로그인 폼: `https://nid.naver.com/nidlogin.login`
- 블로그 홈: `https://blog.naver.com/malacca_whale`
- 글쓰기: `https://blog.naver.com/PostWriteForm.naver?blogId=malacca_whale`
- 글관리: `https://admin.blog.naver.com/`
- SmartEditor 본문 iframe: `iframe[name="mainFrame"]` 내부 contenteditable (ProseMirror)
- 발행 사이드 패널: 우측 슬라이드 — 카테고리 드롭다운, 태그 입력, 공개범위 라디오, 발행 버튼

## 작업 항목

### Phase 0 — 인프라
- [x] `.env`에 `NAVER_MALACCA_ID`, `NAVER_MALACCA_PW` 추가 (`.env`은 `.gitignore` 적용됨 확인) — 변수명은 향후 다른 네이버 계정 추가 대비해 `NAVER_<ALIAS>_ID/PW` 네임스페이스
- [x] `playwright-cli list`로 기존 세션 충돌 없는지 확인 (naver 세션 없음 확인됨)
- [ ] `proc/plan/playwright-cli-bootstrap.md`에 `-s=naver` 부트스트랩 항목 추가
- [x] **첫 1회 헤디드 로그인 완료** (2026-05-08) — `--persistent` 프로필 생성, 자동 폼 입력으로 통과(캡차/새기기 인증 미발생), `https://www.naver.com/`으로 정상 redirect, `blog.naver.com/malacca_whale` 블로그 진입 확인("말라카의 AX Ocean"), `PostWriteForm.naver?blogId=malacca_whale`도 redirect 없이 진입 확인 — SmartEditor 3.0 정상 로드

### Phase 1 — 로그인 helper (`pwc_naver.py`)
- [ ] `is_logged_in(s)` — `nid.naver.com/user2/help/myInfo.naver` 또는 `blog.naver.com/{id}/postlist` 접속 후 redirect 여부로 판정
- [ ] `login_auto(s, id, pw)` — 키 입력 사이 jitter, 클립보드 붙여넣기 방식(`navigator.clipboard.writeText` + Ctrl+V)으로 봇 탐지 회피
- [ ] `login_headed_fallback(s)` — 자동 로그인 실패 감지 시 headed로 재오픈하여 사용자 수동 처리
- [ ] `ensure_login(s)` — `is_logged_in` → 미로그인이면 auto → 실패 시 headed fallback

### Phase 2 — 에디터 진입 + 본문 작성
- [ ] `open_editor(s)` — `PostWriteForm.naver?blogId=malacca_whale` 진입, mainFrame iframe 로드 대기
- [ ] **임시저장된 글 복원 다이얼로그** 처리 — "취소" 자동 클릭(중복 발행 방지)
- [ ] `set_title(s, title)` — 제목 영역 contenteditable 셀렉터 발견 → 클릭 → 기존 내용 select-all + delete → 입력
- [ ] `set_body(s, text)` — 본문 ProseMirror 영역에 입력. 줄바꿈/문단/헤딩 등 마크다운 → SmartEditor 단축키 매핑 검토
- [ ] 셀렉터 변동 시 대비 — `snapshot()` 결과를 fallback으로 검색

### Phase 3 — 발행 옵션 + 발행
- [ ] 우측 "발행" 버튼 클릭 → 발행 패널 슬라이드 인 대기
- [ ] `set_category(panel, name)` — 카테고리 드롭다운 클릭 → 이름으로 항목 검색·선택. 없는 카테고리면 명시적 에러
- [ ] `set_tags(panel, tags: list[str])` — 태그 입력란에 한 개씩 입력 + 엔터
- [ ] `set_visibility(panel, mode)` — `public` | `friends` | `private` 중 라디오 선택
- [ ] `set_options(panel, comments=True, search=True, ...)` — 댓글/검색/공감 토글 옵션
- [ ] `publish(panel)` — 최종 "발행" 클릭 → confirm 다이얼로그 처리 → 발행 완료 후 redirect되는 URL에서 `logNo` 추출하여 반환
- [ ] **임시저장 모드** 함수 별도 — `save_draft(s)` (비공개 발행과는 다름)

### Phase 4 — 이미지 (✅ 1차 검증 완료)
- [x] **로컬 이미지 업로드** — 사진 추가 버튼 클릭 → playwright-cli `upload <path>`로 hidden file input 우회 → 업로드 5초 대기 → SmartEditor 본문에 inline 임베드 확인 (postfiles.pstatic.net로 호스팅됨)
- [ ] **URL 이미지 임베드** — SmartEditor가 외부 핫링크 차단 시 fallback: `urllib`로 다운로드 → 임시 파일 → 로컬 업로드 경로 재사용 (미구현, 필요 시 추가)
- [ ] 이미지 캡션/정렬 옵션 (선택)

### Phase 5 — 스킬 패키징
- [ ] `.claude/skills/naver-blog/SKILL.md` 작성 — 트리거 키워드("네이버 블로그 글쓰기", "블로그 발행", "네이버 포스팅"), 입력 스키마, 사용 예
- [ ] `.gemini/skills/naver-blog/SKILL.md` — 동일 내용 (다른 스킬들 패턴 따라)
- [ ] `CLAUDE.md` Agent Skills 표에 `/naver-blog` 추가
- [ ] `proc/cli/naver_blog_post.py` — `python -m proc.cli.naver_blog_post --payload post.yaml` 실행 가능하도록

### Phase 6 — 검증/안전장치
- [ ] **멱등성**: payload에 `idempotency_key` 받기 → 발행 후 `output/naver_blog/published.json`에 기록. 같은 키 재실행 시 발행 거부 + 기존 logNo 반환
- [ ] **드라이런 모드**: `--dry-run` — 본문까지 입력하되 발행 직전 멈춤(임시저장만)
- [ ] **rate limit**: 같은 세션에서 N분 내 M건 초과 시 거부(어뷰징 방지)
- [ ] **스모크 테스트**: 빈 본문, 매우 긴 본문(>50KB), 특수문자, 이모지, 마크다운 실수입력 등 케이스 한 회 수동 검증
- [ ] 발행 후 자체 검증: 블로그 글 URL fetch → 제목·본문 일부가 들어갔는지 확인 후 결과 반환

## payload 스키마 (제안)

```yaml
title: "오늘의 글"
body: |
  본문 텍스트.
  여러 줄 가능.
category: "일상"
tags: ["자동화", "테스트"]
visibility: public          # public | friends | private
comments: true
search: true
images:                     # Phase 4
  - { type: local, path: "input/photo.jpg", caption: "사진1" }
  - { type: url, url: "https://...png" }
idempotency_key: "post-2026-05-08-001"
dry_run: false
```

## 1차 산출물 (MVP)

Phase 0~3 + Phase 5 + Phase 6 멱등성/드라이런까지. 텍스트 전용으로 "유저가 payload만 주면 발행" 동작 확인.

## 검증된 흐름 (2026-05-08)

**라이브 검증 완료**:
1. `write_post` (텍스트 전용, 비공개) → logNo `224278980125`
2. `read_post(log_no)` → 제목·본문 정상 추출
3. `edit_post` (본문) → 본문 갱신 성공 (제목 갱신은 폴링 추가 후 미재검증)
4. `publish_markdown(md_path)` (frontmatter + 텍스트 + 인라인 이미지 2장) → logNo `224278993119`
   - 제목: "AI Agent 시대의 자동화"
   - 태그: `[AI, Agent, 자동화, playwright]`
   - 이미지: hero.png, diagram.png 본문 내 위치에 inline 임베드 (Naver CDN postfiles.pstatic.net)
   - 공개범위: private

**Helper API**:
- `pwc_naver.write_post(s, title, body, ...)` — 단순 글쓰기
- `pwc_naver.read_post(s, log_no)` — 글 읽기
- `pwc_naver.edit_post(s, log_no, ...)` — 글 수정
- `pwc_naver.publish_markdown(s, md_path)` — frontmatter + 본문 + 이미지 통합 발행

**기술적 발견**:
- SmartEditor 3에서 제목/본문은 직접 contenteditable 아니고 `.se-title-text`, `.se-text-paragraph` 컴포넌트 — playwright `paragraph` role로 click 후 type 가능
- `playwright-cli type` 인자가 `-`로 시작하면 옵션 파싱 충돌 → `--` 구분자로 우회 (`_safe_type`)
- 네이버 SmartEditor의 beforeunload 리스너는 JS로 제거 불가능(Chrome 가드) — `_safe_goto`가 dialog-accept 후 재시도 패턴으로 우회
- 이미지 업로드: 사진 추가 버튼 클릭 → playwright-cli `upload`로 hidden file input 직접 set (네이티브 dialog 우회)
- edit 모드 진입 시 post content가 비동기 로드됨 → title polling이 필수 (placeholder "제목"이 실제 값으로 바뀔 때까지)

## 참조

- 기존 패턴: `proc/lib/pwc_amaranth.py`, `proc/lib/pwc_teams.py` (헬퍼 구조), `.claude/skills/amaranth-calendar/SKILL.md` (스킬 템플릿)
- 부트스트랩 패턴: `proc/plan/playwright-cli-bootstrap.md`
- 마이그레이션 컨텍스트: `proc/plan/playwright-cli-migration.md`
