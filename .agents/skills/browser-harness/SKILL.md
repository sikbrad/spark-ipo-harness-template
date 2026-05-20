---
name: browser-harness
description: (Legacy) browser-harness CDP REPL 사용 규칙. 사용자가 명시적으로 "browser-harness", "BH로 ~해줘", "하네스로 ~", "CDP로 ~" 라고 한 경우에만 사용. 일반적인 브라우저 자동화는 playwright-cli 기반 스킬(teams-activity, salesforce-record, amaranth-*)을 우선 사용.
---

# browser-harness 사용 규칙 (Legacy)

> **🟨 STATUS: Legacy fallback.** 신규 자동화는 [`@playwright/cli`](https://github.com/microsoft/playwright-cli) 기반 패턴(`proc/lib/pwc.py`)을 사용. 본 스킬은 사용자가 명시적으로 browser-harness를 지목하거나, 사용자의 데일리 Chrome 세션을 직접 제어해야 할 때만 사용.
>
> Legacy 이유:
> - 단일 Chrome 공유로 인한 `current_tab` 충돌 — 다른 SaaS 탭이 많을 때 daemon이 잘못된 탭에 attach.
> - Web Worker fetch 트래픽을 못 잡음 (Teams 등에서 한계).
> - 동시 worker 실행 시 race.
>
> 신규 패턴(`pwc`)은 `-s=<name>` 세션별로 격리된 브라우저를 띄워 위 문제를 해소함. 자세한 내용은 [proc/plan/playwright-cli-migration.md](../../../proc/plan/playwright-cli-migration.md).

`browser-harness`는 Chrome DevTools Protocol에 직접 붙는 thin Python REPL. Playwright MCP처럼 stateless tool이 아니다. **에이전트가 실행 중에 부족한 helper를 직접 작성해서 `agent_helpers.py`에 누적시키는** 것이 design intent다.

## 언제 이걸 쓰나
- 사용자가 명시적으로 "browser-harness" / "BH" / "하네스" / "CDP REPL" 지정
- 사용자의 **이미 로그인된 Chrome 세션**을 그대로 써야 할 때 (예: 사이트가 SSO 푸시 자동화 안 되고 사용자가 이미 그 Chrome에 로그인된 상태)
- 1회성 exploratory automation — 세션 격리/동시성이 필요 없을 때

그 외 모든 사이트별 자동화는 `pwc` 기반 스킬을 우선 사용.

## 절대 규칙

1. **임시 `/tmp/bh_*.py` 스크립트를 만들고 `-c "$(cat ...)"`로 실행하지 마라.** 동일 보일러플레이트(XHR 패치, input 셋팅 등)를 여러 번 작성하게 된다 — 잘못된 사용 패턴이다.
2. **새 task 시작 전 `~/Developer/browser-harness/agent-workspace/agent_helpers.py`를 먼저 읽어라.** 재사용 가능한 primitive가 이미 있을 수 있다.
3. **부족한 primitive는 그 파일에 함수로 추가하라.** 그 다음에 짧은 `browser-harness -c "result = my_helper(); print(result)"` 한 줄로 호출한다.
4. **사이트별 helper는 prefix를 붙여라** (예: `amaranth_*`, `salesforce_*`). 단 신규 사이트라면 `pwc_<site>.py`로 가는 편이 낫다.

## agent_helpers.py 작성 규칙

```python
from browser_harness.helpers import js  # noqa: F401

import json as _json
import time as _time

def my_helper(arg):
    """한 줄 docstring."""
    return js(f"""
    (function() {{
        // ...
        return ...;
    }})();
    """)
```

- 공개 함수명은 underscore로 시작하지 않게 한다.
- IIFE로 감싸라 — `const`/`let` 재선언 충돌 방지.
- React/Vue 입력은 native setter (`set_input_value` 참고).

## 호출 패턴

```bash
browser-harness -c "amaranth_dev_events()"
```

## 이미 등록된 범용 helper

- `install_xhr_capture()` / `captured_requests(url_substring)` / `clear_captured()` — fetch+XHR 트래픽 캡처 (단 worker traffic은 못 잡음 — pwc 우선)
- `set_input_value(selector, value)` — React-friendly 입력
- `press_enter(selector)` / `click_element_by_text(text, tag)` — 이벤트 디스패치
- `list_tabs()` / `switch_tab(targetId)` / `current_tab()` — 탭 제어

## 사용자가 요청하지 않은 일은 하지 마라
- 새 탭 열기, 다른 페이지로 이동, 로그인 시도 등은 명시 요청 없으면 금지.
- 인증 벽이 나오면 멈추고 사용자에게 물어라.
- 화면이 막히거나 selector가 안 잡힐 때만 screenshot을 찍어라.

## 참고

- 핵심 사용법: `~/Developer/browser-harness/SKILL.md`
- helper 파일: `~/Developer/browser-harness/agent-workspace/agent_helpers.py`
- 상호작용 패턴: `~/Developer/browser-harness/interaction-skills/`
- 신규 패턴(권장): `proc/lib/pwc.py` + `proc/lib/pwc_<site>.py`
