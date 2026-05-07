# browser-harness 설치 및 브라우저 연결

## 목표
browser-use/browser-harness를 글로벌 도구로 설치하고, 사용자의 실제 Chrome 프로필(Way 1)에 CDP로 연결하여 에이전트가 브라우저를 조작할 수 있게 한다.

## 작업 항목
- [x] `install.md` 페치 및 절차 확인 (`gh api repos/browser-use/browser-harness/contents/install.md`)
- [x] 사전 조건 확인: `uv 0.9.30`, Chrome 설치 및 실행 상태
- [x] 저장소 클론: `~/Developer/browser-harness`
- [x] uv 편집 가능 설치: `uv tool install -e .` → `/Users/gq/.local/bin/browser-harness` v0.1.0
- [x] 글로벌 스킬 등록: `~/.claude/CLAUDE.md`에 `@~/Developer/browser-harness/SKILL.md` 추가
- [x] 진단: `browser-harness --doctor` (chrome ok / daemon FAIL → Way 1 셋업 미완료)
- [x] `chrome://inspect/#remote-debugging` 자동 오픈 (osascript)
- [x] 사용자가 "Allow remote debugging for this browser instance" 체크박스 활성화
- [x] 데몬 연결 검증: `browser-harness -c 'print(page_info())'` 성공
- [x] 데모: 새 탭에서 browser-harness 저장소 열기 → GitHub 비로그인 확인 → `browser-use.com`로 폴백 이동

## 환경 메모
- 연결 방식: Way 1 (실제 Chrome 프로필, 쿠키/확장/로그인 유지)
- 도구 경로: `/Users/gq/.local/bin/browser-harness`
- 저장소 경로: `/Users/gq/Developer/browser-harness` (편집 시 즉시 반영)
- IPC 소켓: `/tmp/bu-default.sock`
- 헬퍼 함수: `js`, `goto_url`, `new_tab`, `switch_tab`, `page_info`, `wait_for_load`, `click_at_xy`, `fill_input`, `type_text`, `capture_screenshot` 등

## 후속 주의사항
- Chrome 144+에서 첫 어태치 시 "Allow remote debugging?" 팝업이 다시 뜰 수 있음 → Allow 클릭
- 업데이트 배너 발견 시 `browser-harness --update -y` 실행 (편집 가능 클론은 깨끗한 워킹트리 필요)
- 클라우드 브라우저 사용 시 `BROWSER_USE_API_KEY` 설정, 프로필 동기화는 `profile-use` + `sync_local_profile()`
