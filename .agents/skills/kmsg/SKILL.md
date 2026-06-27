---
name: kmsg
description: macOS KakaoTalk 데스크톱 앱을 macOS Accessibility API로 제어하는 [channprj/kmsg](https://github.com/channprj/kmsg) CLI 래퍼 — **읽기 중심**(채팅방 목록 / 메시지 읽기 / 실시간 감시) + 보조(전송). "카톡 메시지 읽어줘", "카톡 채팅방 목록", "특정 단톡방 최근 메시지", "카톡 실시간 감시", "카톡으로 알림 보내", "kmsg dump", "KakaoTalk 메시지 export" 등 macOS 카카오톡 관련 요청 시 사용. **카톡 GUI를 실제로 열고 포커스를 가져가므로 다른 작업 중일 때는 조심.**
---

# kmsg — macOS KakaoTalk CLI (읽기 중심)

[channprj/kmsg](https://github.com/channprj/kmsg)는 macOS Accessibility API(AXUIElement)로 KakaoTalk 데스크톱 앱의 UI를 직접 조작한다. LOCO 프로토콜 리버스가 아니라 OS 공식 접근성 API라 상대적으로 안전하지만 **실제로 카톡 창을 열고 포커스를 가져간다** — 다른 GUI 작업 중에는 방해될 수 있음.

## 도구

- 바이너리: `/opt/homebrew/bin/kmsg` (Homebrew tap: `channprj/tap/kmsg`)
- 자격 증명 캐시: `~/.config/kmsg/credentials/`
- 채팅방 ID registry: `~/.kmsg/chat-registry.json`
- AX 경로 캐시: kmsg 내부 (`kmsg cache status`로 확인)

## 전제 (1회)

1. `brew install channprj/tap/kmsg`
2. **시스템 설정 → 개인정보 보호 및 보안 → 손쉬운 사용**에서 `/opt/homebrew/bin/kmsg` 추가 + 토글 ON
3. `kmsg auth login` — **카톡이 로그아웃 화면 상태**여야 함 (이미 로그인된 상태에서는 로그인 폼을 못 찾아 실패)
4. `kmsg status` → `Accessibility ✓ / KakaoTalk ✓` 확인
5. ⚠️ KakaoTalk은 동시에 **하나의 PC에만 로그인** 가능 — 다른 맥/윈도우 카톡 켜져 있으면 그쪽이 로그아웃됨 (모바일 동시 OK)

이후 `chats`/`read`/`send` 등은 카톡이 로그인 풀려있으면 저장된 자격증명으로 자동 재로그인 시도.

## 표준 호출 (읽기)

### 1) 채팅방 목록
```bash
kmsg chats --limit 30 --json | jq '.'
```
- 각 채팅방의 synthetic `chat_id` 포함 (`~/.kmsg/chat-registry.json`에 영속)
- 이름이 같은 방이 여러 개여도 별도 ID 유지, 방 이름 바뀌면 새 ID로 취급
- `--keep-window` 없으면 자동 열린 창은 닫음

### 2) 특정 채팅방 메시지 읽기
```bash
kmsg read "단톡방이름" --limit 50 --json > data/kmsg/단톡방.json
# 또는 chat_id로 (더 안정적)
kmsg read --chat-id "chat_7f42c5e1d9ab" --limit 50 --json
```
JSON 출력 스키마:
```json
{
  "chat": "홍길동",
  "fetched_at": "2026-05-11T01:23:45.678Z",
  "count": 20,
  "messages": [
    { "author": "홍길동", "time_raw": "00:27", "body": "메시지 본문" }
  ]
}
```
- `author == "(me)"` 는 본인 메시지 또는 추론 불가
- `--deep-recovery`: 빠른 탐색 실패 시 창 재시작/복구 (느리지만 안정)

### 3) 실시간 감시 (JSON Lines)
```bash
kmsg watch "단톡방이름" --json --poll-interval 0.5
```
- 새 메시지 감지될 때마다 pretty JSON 객체 1개씩 stdout으로 흘림 (배열 아님)
- 시작 시점 이전 메시지는 baseline으로 잡고 출력 안 함
- `--include-system`: 날짜 구분선 등 시스템 이벤트도 포함
- `--trace-ax` 로그는 stderr로 분리되므로 `2>/dev/null | jq` 안전

### 4) Python에서 직접 호출 (subprocess 패턴)
```python
import subprocess, json
res = subprocess.run(
    ["kmsg", "read", "단톡방이름", "--limit", "50", "--json"],
    check=True, capture_output=True, text=True,
)
data = json.loads(res.stdout)
for m in data["messages"]:
    print(m["time_raw"], m["author"], m["body"])
```
`stderr`는 buffering 주의 — `--trace-ax` 켜면 노이즈 크므로 디버깅 외엔 끔.

## 표준 호출 (보조: 전송)

### 텍스트
```bash
kmsg send "단톡방이름" "안녕하세요"
kmsg send --chat-id "chat_7f42c..." "본문"
kmsg send "본인 / 단톡방" "$(date '+%H:%M') 자동 알림"
```
- 기본은 보내고 창 닫음, `--keep-window` 유지
- `--dry-run`: 시뮬레이션 (실제 전송 X) — 권한·경로만 검증
- `--refresh-cache`: AX 경로 캐시 강제 재구성 (카톡 업데이트 후 깨졌을 때)

### 이미지
```bash
kmsg send-image "단톡방" /absolute/path/image.png
```

## 캐시 / 디버깅

```bash
kmsg cache status                       # 캐시 상태
kmsg cache warmup --recipient "단톡방"   # send happy-path 미리 워밍업
kmsg cache clear                        # 카톡 UI 바뀌어 깨졌을 때

kmsg inspect --depth 20 --debug-layout  # AX 트리 덤프
kmsg inspect --row-summary --row-range 10:30  # 메시지 row 파싱 진단

kmsg read "방" --limit 5 --trace-ax     # 읽기 경로 AX 로그 (stderr)
```

## 환경 변수

| 변수 | 기본 | 효과 |
|---|---|---|
| `KMSG_AX_TIMEOUT` | (내장) | AX 호출 타임아웃(초). 느린 맥/큰 채팅방 list에서 늘림 |
| `KMSG_DEFAULT_DEEP_RECOVERY` | `false` | 매 호출에 `--deep-recovery` 강제 |
| `KMSG_TRACE_DEFAULT` | `false` | 매 호출에 `--trace-ax` 강제 |

## 출력 컨벤션 (본 저장소 권장)

- 단발 dump: `data/kmsg/<chat-slug>-YYYYMMDD-HHMM.json`
- 실시간 감시 로그: `data/kmsg/watch-<chat-slug>.jsonl` (append)
- (필요 시) `proc/lib/kmsg.py` 래퍼는 **아직 없음** — 현재는 직접 `subprocess`로 호출하는 게 가장 단순

## ⚠️ 함정

- **GUI를 실제로 건드림** — `chats`/`read`/`send` 모두 카톡 창을 띄우거나 포커스를 가져감. 화면 작업 중인 상태에서 백그라운드로 자동 호출하면 사용자 입력을 가로챌 수 있음. **사용자 명시 요청 시에만 실행**, 자동 hook으로 흘리지 말 것.
- **카톡 사이드바의 '채팅' 탭이 선택돼 있어야 동작** (실측 2026-05-11). 친구 탭/더보기 탭 상태면 `chats`가 `count: 0`으로 빈 결과 반환. kmsg가 사이드바를 자동으로 못 눌러서 사람이 먼저 채팅 탭을 켜둬야 함. 실패하면 `Tip: Make sure you're on the 'Chats' (채팅) tab in KakaoTalk` 메시지가 stderr로 나옴.
- **단일 PC 로그인 정책** — 다른 PC에서 로그인하면 이 맥은 로그아웃됨. 자동 재로그인이 카톡 자체 제재 트리거가 될 수 있어 과도한 반복 금지.
- **카톡 버전 따라 AX 구조 변경** — 이슈 [#5](https://github.com/channprj/kmsg/issues/5)처럼 채팅방 이름이 숫자로 잡히거나 search field 못 찾는 케이스 존재. 이럴 땐 `kmsg inspect`로 AX 트리 보고 kmsg 업데이트(`brew upgrade kmsg`) 시도.
- **`--json`은 stdout, 로그는 stderr** — 파이프 안정성 위해 `2>/dev/null` 또는 `2>data/kmsg/trace.log` 분리 권장.
- **닫힌 채팅방 read는 search field 의존** — 이슈 #5에 따르면 일부 macOS/카톡 조합에서 닫힌 방 접근 실패. 안전하게 가려면 `kmsg chats --keep-window`로 사이드바에서 한 번 열어둔 뒤 read.
- **`auth login`은 카톡 로그아웃 화면 필요** — 메인 창 떠있는 상태에선 ID 필드를 못 찾아 "did not complete successfully" 실패. 일단 한 번 성공시켜 자격증명만 저장해두면 이후엔 자동 로그인.
- **메시지 추적성 약함** — `author == "(me)"`로 합쳐지는 경우, 시각이 `time_raw`만 있고 절대시각이 없는 케이스. 시간 정렬은 보존되지만 hour-rollover 처리 직접 필요할 수 있음.

## MCP 모드 (선택)

```bash
kmsg mcp-server
```
Codex/Codex/Gemini의 `.mcp.json`에 등록하면 LLM이 직접 `kmsg_read`/`kmsg_send`/`kmsg_chats` 도구 호출 가능. 본 스킬과 중복이라 둘 다 쓸 필요는 없음 — 본 스킬은 명시적 CLI 호출 패턴, MCP 모드는 자율 LLM 도구 사용 패턴.

## 참고 reference

- [README (channprj/kmsg)](https://github.com/channprj/kmsg)
- [Issue #5: 채팅방 이름 미인식 / search field not found](https://github.com/channprj/kmsg/issues/5)
- [Issue #11: Auto login option (단일 PC 로그인 정책 명시)](https://github.com/channprj/kmsg/issues/11)
