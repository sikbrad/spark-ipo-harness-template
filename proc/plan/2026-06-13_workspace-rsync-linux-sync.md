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
- [x] 원격 파일 존재와 제외 디렉터리 미전송을 확인한다.

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
- 2026-06-13: 전체 workspace folder별 `push`/`pull` dry-run 감사를 다시 수행했다. 결과 로그는 `.omx/logs/workspace-rsync-audit-20260613-231619.json`, prefix 요약은 `.omx/logs/workspace-rsync-audit-20260613-231619-push-prefixes.json`에 저장했다.
- 2026-06-13: 감사 결과 `pull` 미전송은 모든 workspace에서 0건이었다. 즉 원격에서만 생긴 파일을 맥으로 못 받은 문제가 아니라, 맥에서 원격으로 아직 못 보낸 `push` 잔량이 문제다.
- 2026-06-14: `tmux` 세션 `workspace-rsync-linux`에서 전체 13개 workspace folder `push`를 완료했다. 실행 로그는 `.omx/logs/workspace-rsync-linux-20260613-235451.log`에 저장했다.
- 2026-06-14: 전체 완료 통계에서 `Completed workspace folder count: 13`을 확인했다.
- 2026-06-14: 사후 `push`/`pull` dry-run 감사 결과 `pull`은 모든 workspace에서 0건이었다. `push`는 `dof-work-startpoint-04`의 `data/daily/2026-06-08/raw/audio-260608-170245-kaitlyn.m4a` 1건만 남아 별도 재-push했다.
- 2026-06-14: `dof-work-startpoint-04` 재-push 후 dry-run에서 `Number of files transferred: 0`, `Total transferred file size: 0 B`를 확인했다. dry-run에 남는 `.L...p...` 라인은 심볼릭 링크 permission 메타데이터 표시이며 파일 내용 전송 잔량은 아니다.
- 2026-06-14: 원격 `/Users/gq`가 `/dev/sda1` mountpoint이고 `/Users`는 root filesystem임을 확인했다. 이후 스크립트에 원격 `/Users/gq` 또는 `/Users` 중 하나가 mountpoint가 아니면 sync/dry-run을 시작하지 않는 mount guard를 추가했다.
- 2026-06-14: 증분 push 중 `.omx/state` 런타임 상태 파일이 잡히는 것을 확인해, `.omx/state/`와 `.omx/metrics.json`을 제외 목록에 추가했다.

## 2026-06-13 dry-run 감사 결과

| Folder | Push missing files | Push missing size | Pull missing files |
|---|---:|---:|---:|
| `dof-work-startpoint-04` | 35,281 | 13.4GB | 0 |
| `dof-order-web-3-az` | 8,236 | 7.4GB | 0 |
| `dofing-order-portal-data-3-az` | 8,535 | 3.1GB | 0 |
| `dofing-order-porta-data-comparator-03` | 723 | 441.8MB | 0 |
| `kubit-bitbot-slack-01` | 1,544 | 16.9GB | 0 |
| `teams-bot-dofi-01` | 87 | 456.4KB | 0 |
| `hong-ledger-and-packages-02` | 3,331 | 513.8MB | 0 |
| `portal-ledger-invoice-gen-and-send` | 53,875 | 18.9GB | 0 |
| `vibe-coding-book-writing` | 1,319 | 16.7GB | 0 |
| `legacy_dofing_crm_facade` | 50,297 | 19.9GB | 0 |
| `legacy_shop-order-auto` | 131 | 2.2MB | 0 |
| `shop-order-auto-with-api` | 189 | 4.4MB | 0 |
| `cms-paper-analysis` | 98 | 69.7MB | 0 |

큰 잔량은 대부분 `output/`, `data/`, `input/` 등 포함하기로 한 데이터/산출물 경로다. `.git`, `node_modules`, 빌드/캐시 제외 정책 때문에 빠진 항목은 이 표의 문제 잔량으로 보지 않는다.
