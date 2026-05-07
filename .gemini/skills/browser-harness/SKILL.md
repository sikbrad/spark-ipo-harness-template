---
name: browser-harness
description: 브라우저 자동화 요청 시 사용. "브라우저하네스 써", "browser-harness", "BH로 ~해줘", "브라우저로 ~ 받아와", "ERP 들어가서 ~" 등 실제 브라우저로 웹사이트에 접속·조작·데이터 추출이 필요한 요청에 적용. CDP 직결 + Python REPL 모델 — 부족한 helper는 직접 작성해 누적시킨다.
---

# browser-harness 사용 규칙

`browser-harness`는 Chrome DevTools Protocol에 직접 붙는 thin Python REPL이다. Playwright MCP처럼 stateless tool이 아니다. **에이전트가 실행 중에 부족한 helper를 직접 작성해서 `agent_helpers.py`에 누적시키는** 것이 design intent다.

## 절대 규칙

1. **임시 `/tmp/bh_*.py` 스크립트를 만들고 `-c "$(cat ...)"`로 실행하지 마라.** 동일 보일러플레이트(XHR 패치, input 셋팅 등)를 여러 번 작성하게 된다 — 잘못된 사용 패턴이다.
2. **새 task 시작 전 `~/Developer/browser-harness/agent-workspace/agent_helpers.py`를 먼저 읽어라.** 재사용 가능한 primitive가 이미 있을 수 있다.
3. **부족한 primitive는 그 파일에 함수로 추가하라.** 그 다음에 짧은 `browser-harness -c "result = my_helper(); print(result)"` 한 줄로 호출한다.
4. **사이트별 helper는 prefix를 붙여라** (예: `amaranth_*`, `salesforce_*`).

## agent_helpers.py 작성 규칙

```python
# 모듈 최상단에 반드시 추가 — 이 파일은 자체 namespace에서 실행되므로
# run.py globals에서 js()를 자동 상속받지 않는다.
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

- 공개 함수명은 underscore로 시작하지 않게 한다 (loader가 `_` 시작 이름은 export 안 함).
- IIFE로 감싸라 — 같은 세션에서 `const`/`let` 재선언 충돌 방지.
- React/Vue 입력은 native setter를 통해야 framework가 변경을 인식한다 (`set_input_value` 참고).

## 호출 패턴

```bash
# 새 helper 추가 후
browser-harness -c "amaranth_dev_events()" 
# 또는
browser-harness -c "
events = amaranth_dev_events()
print(f'{len(events)} events')
for ev in events[:5]: print(ev['date'], ev['title'])
"
```

## 이미 등록된 범용 helper

- `install_xhr_capture()` / `captured_requests(url_substring)` / `clear_captured()` — fetch+XHR 트래픽 캡처
- `set_input_value(selector, value)` — React-friendly 입력
- `press_enter(selector)` / `click_element_by_text(text, tag)` — 이벤트 디스패치

사이트별 helper는 별도 skill 문서 참조 (amaranth-calendar, amaranth-org).

## 사용자가 요청하지 않은 일은 하지 마라

- 새 탭 열기, 다른 페이지로 이동, 로그인 시도 등은 명시 요청 없으면 금지.
- 인증 벽이 나오면 멈추고 사용자에게 물어라.
- 화면이 막히거나 selector가 안 잡힐 때만 screenshot을 찍어라 — 모든 단계마다 찍지 마라.

## 참고

- 핵심 사용법: `~/Developer/browser-harness/SKILL.md`
- helper 파일: `~/Developer/browser-harness/agent-workspace/agent_helpers.py`
- 상호작용 패턴: `~/Developer/browser-harness/interaction-skills/`
