# Threads(threads.net) 발행 자동화 스킬

## 목표
사용자 명령 → Claude 초안 작성 → confirm → 브라우저 자동화로 threads.net 본인 계정에 발행. `/threads` 스킬로 노출.

## 배경 & 결정
- **API 미사용 결정**: Meta Threads Graph API는 OAuth + redirect URI 호스팅 + 단명/장명 토큰 + 60일 refresh 셋업 부담. 본인 1인 발행에는 ROI 낮음.
- **브라우저 자동화 채택**: 한 번 로그인 → 쿠키 저장 → 이후 게시 박스 입력 + '게시' 클릭으로 발행.
- **엔진 선택 대기**: 사용자가 "playwright mcp" 라고 했으나 프로젝트 컨벤션은 playwright-cli (`proc/lib/pwc.py`). naver-blog/amaranth/salesforce 전부 pwc 패턴. 일관성 위해 pwc 권장하나 사용자 의도 확인 필요.

## 확인 필요 (착수 전)
- [ ] 엔진: ① pwc.py (권장, 기존 패턴) vs ② Playwright MCP (`mcp__playwright__*` 직접 호출)
- [ ] confirm 단계: 매번 / skip 옵션 / `--yes` 플래그
- [ ] 이미지 첨부 우선순위 (v1 포함 vs v2 deferred)
- [ ] 답글(reply chain) 우선순위 (v1 포함 vs v2 deferred)

## 작업 항목

### 1. 엔진 확정 + 부트스트랩
- [ ] 엔진 선택 사용자 confirm
- [ ] threads.net 수동 로그인 1회 (Meta/Instagram 계정 — 어느 쪽인지도 확인)
- [ ] 세션 저장 경로 결정: `data/state/threads.json` (pwc 패턴) 또는 MCP 프로파일

### 2. helper 작성 (`proc/lib/pwc_threads.py` — pwc 채택 시)
- [ ] `S("threads")` 세션 초기화
- [ ] `post_text(content: str) -> dict` — 게시 박스 입력 + '게시' 클릭 + 결과 URL/스크린샷 반환
- [ ] (옵션) `post_with_image(content, image_path)`
- [ ] (옵션) `post_reply(parent_url, content)` — thread reply
- [ ] 오류 처리: 로그인 만료 감지, 게시 실패 감지, 글자수 한도(500자) 검증

### 3. 스킬 정의
- [ ] `.claude/skills/threads/SKILL.md`
  - 트리거: "thread 올려", "threads 글", "쓰레드에 올려" 등
  - 워크플로우: 초안 작성 → 사용자 confirm → 발행 → URL 보고
  - 사용 예 2~3개

### 4. 문서 반영
- [ ] `CLAUDE.md` 스킬 표에 한 줄 추가
- [ ] 부트스트랩 가이드 — 처음 1회 로그인 절차 (별도 md 또는 SKILL.md 내부)

### 5. 검증
- [ ] dry-run: 짧은 텍스트 1회 발행 → URL 확인 → 수동 삭제
- [ ] 세션 만료 후 재로그인 흐름 확인
- [ ] 글자수 초과 케이스 (>500자) 거부 동작 확인

## 참고
- threads.net 글자수 한도: 500자
- 본인 발행이라 rate limit 걱정 없음 (수동 페이스)
- naver-blog 패턴이 가장 유사 — `proc/lib/pwc_naver.py` + `.claude/skills/naver-blog/` 참조
