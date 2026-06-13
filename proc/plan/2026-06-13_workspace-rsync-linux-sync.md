# Workspace Rsync Linux Sync

## 목표
`dof-work-startpoint.code-workspace`의 모든 workspace folder를 `NotHome-WS-1203-new` 리눅스 장비로 rsync 전송한다.
`input/`, `output/`, `data/`는 포함하고, 재생성 가능한 의존성/빌드/캐시 산출물은 제외한다.

## 작업 항목
- [x] 동기화 정책과 기본 원격 경로를 정한다.
- [x] `scripts/sync_workspace_to_linux.sh`를 만든다.
- [x] SSH/rsync 사전 조건을 확인한다.
- [x] dry-run으로 포함/제외 규칙을 검증한다.
- [x] 실제 동기화를 실행한다.
- [x] 스크립트에 보내기/받기/양방향 방향 옵션을 추가한다.
- [x] `remote-workspace-sync` 스킬을 추가한다.
- [ ] 원격 파일 존재와 제외 디렉터리 미전송을 확인한다.

## 동기화 정책
- 기본 원격 호스트: `NotHome-WS-1203-new`
- 기본 원격 경로: 로컬 workspace folder의 절대경로와 동일한 원격 절대경로
- 기본 방향: 로컬 워크스페이스 -> 리눅스 장비
- 기본 삭제 정책: 원격 삭제 없음. 필요 시 스크립트의 `--delete` 옵션을 명시한다.
- 포함: 소스/문서/설정, `input/`, `output/`, `data/`
- 제외: `.git/`, `node_modules/`, `dist/`, `build/`, 캐시, 로그, Python bytecode, Playwright 런타임 캐시
- workspace folder 수: 13개
- dry-run 총 후보 크기: 약 110.5GB

## 진행 기록
- 2026-06-13: SSH 접속과 원격 rsync 설치를 확인했다.
- 2026-06-13: 초기 dry-run에서 `input/`, `output/`, `data/` 포함과 `node_modules`, `.DS_Store`, `.playwright` 제외를 확인했다.
- 2026-06-13: 원격 기본 경로를 사용자 정정에 따라 `/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04`로 변경했다.
- 2026-06-13: `dof-work-startpoint.code-workspace`의 13개 `folders[]`를 기준으로 스크립트를 수정했다.
- 2026-06-13: 전체 workspace dry-run이 13개 folder를 모두 순회했고 금지 패턴 매치 0개를 확인했다.
- 2026-06-13: 실제 동기화를 `tmux` 세션 `workspace-rsync-linux`에서 시작했다.
- 2026-06-13: 실행 로그: `.omx/logs/workspace-rsync-linux-20260613-215453.log`
- 2026-06-13: 첫 실행이 원격 임시 파일 6MB 지점에서 장시간 무진행 상태라 중단했다.
- 2026-06-13: 스크립트에 SSH keepalive, `--timeout=60`, folder별 재시도 기본 3회를 추가하고 재시작했다.
- 2026-06-13: 재시작 로그: `.omx/logs/workspace-rsync-linux-20260613-221655.log`
- 2026-06-13: 스크립트에 `--direction push|pull|both`를 추가했다.
- 2026-06-13: `both`는 `pull` 후 `push` 순서로 수행하고, `--delete`와 함께 쓰지 못하게 차단했다.
- 2026-06-13: `.agents/skills/remote-workspace-sync`, `.claude/skills/remote-workspace-sync`, `.gemini/skills/remote-workspace-sync`를 추가했다.
- 2026-06-13: `push`, `pull`, `both` dry-run과 `both --delete` 차단을 검증했다.
- 2026-06-13: 전체 `pull --dry-run`에서 원격 rsync 임시 partial 파일 2개가 후보로 잡혀, `.rsync-partial/`과 dot-temp 패턴을 제외하도록 보정했다.
