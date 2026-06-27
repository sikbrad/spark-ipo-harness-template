# Playwright CLI 이전 계획

## Why
- 현재 `browser-harness`는 사용자의 단일 Chrome에 CDP attach. 한 Chrome 내 SaaS 탭이 많으면 daemon `current_tab`이 충돌.
- Web Worker fetch를 못 잡음 → Teams Activity API 직결 불가, DOM 스크레이핑에만 의존.
- 동시 실행 어려움.

## Target
[`@playwright/cli`](https://github.com/microsoft/playwright-cli) (v0.1.12, 2025-12) — 세션별 격리 브라우저, `-s=<name>` + `--persistent` 로 진짜 동시성 + 디스크 영속성.

## Mapping
| 기존 (browser-harness) | 신규 (playwright-cli) |
|---|---|
| `js("expr")` | `playwright-cli -s=X eval "expr"` |
| `capture_screenshot()` | `playwright-cli -s=X screenshot --filename=...` |
| `goto_url(url)` | `playwright-cli -s=X goto <url>` |
| `set_input_value(sel,v)` | `playwright-cli -s=X fill <ref> <text>` 또는 eval로 native setter |
| `install_xhr_capture()` + `captured_requests()` | **불필요** — `playwright-cli -s=X requests` (CDP-native, **워커 트래픽도 잡음**) |
| `list_tabs()` / `switch_tab()` | `playwright-cli -s=X tab-list` / `tab-select` |
| 한 Chrome 공유로 인한 충돌 | 사이트별 세션: `-s=teams`, `-s=salesforce`, `-s=amaranth` |

## 세션 정책
- `-s=teams` — Microsoft Teams (SSO + Authenticator 1회)
- `-s=salesforce` — Salesforce Lightning (SSO 1회)
- `-s=amaranth` — DOF Amaranth ERP (ID/PW 1회)
- 모두 `--persistent` 로 첫 실행. 이후 디스크 프로필 재사용.
- 동시 worker 안전 — 서로 다른 `-s` 는 서로 다른 브라우저 인스턴스.

## Phase 1 — 인프라 (sequential)
1. ✅ `npm install -g @playwright/cli@latest`
2. Python helper `proc/lib/pwc.py` 작성 — subprocess 래퍼:
   - `pwc(session, *args)` → 표준 출력 raw
   - `pwc_eval(session, jsfn)` → JSON 파싱 결과
   - `pwc_screenshot(session, path=None)` 등 thin wrapper
3. 첫 세션 부트스트랩 — `playwright-cli -s=teams open https://teams.cloud.microsoft/ --persistent --headed` 후 사용자 로그인.

## Phase 2 — 스킬 이전 (parallel via ultrawork)
각 스킬 SKILL.md + 동반 helper(있으면) 갱신:
- [ ] `teams-activity` (가장 먼저 — 워커 fetch 가로채기 검증 케이스)
- [ ] `salesforce-record`
- [ ] `amaranth-calendar`
- [ ] `amaranth-org`
- [ ] `amaranth-resource`
- [ ] `amaranth-approval`
- [ ] `amaranth-acc-ledger`
- [ ] `amaranth-acc-balance`

## Phase 3 — 정리
- `browser-harness` 스킬에 deprecation 주석 + playwright-cli 안내
- `CLAUDE.md` 스킬 표 갱신
- `.gemini/skills/` 미러링
- agent_helpers.py 의 사이트별 helper는 유지(참고 구현)하되 스킬 본문은 playwright-cli 호출만 권장

## 비범위
- agent_helpers.py 사이트별 helper 삭제: 유지 — 참조 가치 + 비상시 복귀용.
- 기존 browser-harness daemon 제거: 안 함. 사용자가 원하면 계속 사용 가능.

## 위험 / 함정
- 첫 SSO 1회 사람 손 필요 (Authenticator 푸시 / 수동 로그인) — 자동화 불가, 명세 필요.
- `eval` 의 JS는 한 줄 식 또는 `() => {...}` IIFE — playwright-cli 는 자동 IIFE wrap 안 함. helper에서 처리.
- `playwright-cli requests` 는 페이지 로드 이후의 누적 — 진입 후 트리거 액션 → 즉시 `requests` 호출 패턴.
- 한 세션 동시 호출은 직렬화 — 같은 `-s`로 두 명령을 동시에 보내면 race. 다른 `-s` 끼리만 진짜 병렬.
