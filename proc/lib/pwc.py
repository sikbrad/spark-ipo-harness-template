"""Thin Python wrapper around `@playwright/cli`.

Usage:
    from pwc import S
    s = S('teams')                 # or S('teams', persistent=True) on first run
    s.open('https://teams.cloud.microsoft/')
    title = s.eval('document.title')
    s.fill('e21', 'hello')
    s.click('e35')
    reqs = s.requests()
    body = s.response_body(3)

Sessions are isolated browsers — `S('teams')` and `S('amaranth')` are separate
processes with separate cookies. Multiple sessions can run concurrently.
The same session must NOT be hit by two callers simultaneously (race).
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any, Iterable, Optional

CLI = 'playwright-cli'

_RESULT_RE = re.compile(r'^### Result\s*\n(.*?)(?=^### |\Z)', re.MULTILINE | re.DOTALL)


class PWCError(RuntimeError):
    pass


def _run(args: list[str], input_data: Optional[str] = None, timeout: int = 60) -> str:
    """Run `playwright-cli <args>` and return stdout. Raise on non-zero."""
    proc = subprocess.run(
        [CLI, *args],
        input=input_data,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if proc.returncode != 0:
        raise PWCError(
            f'playwright-cli failed (code {proc.returncode}): '
            f'args={args!r} stderr={proc.stderr.strip()[:500]}'
        )
    return proc.stdout


def _parse_result(stdout: str) -> str:
    """Extract the `### Result` block payload as raw text."""
    m = _RESULT_RE.search(stdout)
    if not m:
        return ''
    return m.group(1).strip()


def _try_json(text: str) -> Any:
    """Best-effort JSON parse. Returns parsed value or original text."""
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


class S:
    """One session. All methods are thin wrappers around playwright-cli."""

    def __init__(self, name: str, persistent: bool = False):
        self.name = name
        self.persistent = persistent

    # ---- core args helper

    def _args(self, *cmd: str) -> list[str]:
        return [f'-s={self.name}', *cmd]

    def raw(self, *cmd: str, timeout: int = 60) -> str:
        """Run an arbitrary subcommand. Returns full stdout."""
        return _run(self._args(*cmd), timeout=timeout)

    # ---- lifecycle

    def open(self, url: Optional[str] = None, headed: bool = False) -> str:
        cmd = ['open']
        if url:
            cmd.append(url)
        if self.persistent:
            cmd.append('--persistent')
        if headed:
            cmd.append('--headed')
        return _run(self._args(*cmd))

    def close(self) -> str:
        return _run(self._args('close'))

    def goto(self, url: str) -> str:
        return _run(self._args('goto', url))

    def reload(self) -> str:
        return _run(self._args('reload'))

    # ---- evaluation

    def eval(self, expr: str, target: Optional[str] = None) -> Any:
        """Evaluate JS expression. `expr` can be a bare expression or arrow fn.
        Returns the parsed JSON result, or raw text if not JSON.
        """
        cmd = ['eval', expr]
        if target:
            cmd.append(target)
        out = _run(self._args(*cmd))
        return _try_json(_parse_result(out))

    # ---- input

    def click(self, ref: str, button: Optional[str] = None) -> str:
        cmd = ['click', ref]
        if button:
            cmd.append(button)
        return _run(self._args(*cmd))

    def fill(self, ref: str, text: str, submit: bool = False) -> str:
        cmd = ['fill', ref, text]
        if submit:
            cmd.append('--submit')
        return _run(self._args(*cmd))

    def type(self, text: str) -> str:
        return _run(self._args('type', text))

    def press(self, key: str) -> str:
        return _run(self._args('press', key))

    def hover(self, ref: str) -> str:
        return _run(self._args('hover', ref))

    def select(self, ref: str, value: str) -> str:
        return _run(self._args('select', ref, value))

    # ---- snapshot/screenshot

    def snapshot(self, target: Optional[str] = None, depth: Optional[int] = None) -> str:
        cmd = ['snapshot']
        if target:
            cmd.append(target)
        if depth is not None:
            cmd.append(f'--depth={depth}')
        return _run(self._args(*cmd))

    def screenshot(self, path: Optional[str] = None, target: Optional[str] = None) -> str:
        """Take a screenshot. If path is None, the CLI uses an auto path under
        `.playwright-cli/`. Returns the saved path (extracted from result).
        """
        cmd = ['screenshot']
        if target:
            cmd.append(target)
        if path:
            cmd.append(f'--filename={path}')
        out = _run(self._args(*cmd))
        # Result line: "- [Screenshot of viewport](some/path.png)"
        m = re.search(r'\(([^)]+\.png)\)', _parse_result(out))
        return m.group(1) if m else ''

    # ---- tabs

    def tab_list(self) -> list[dict]:
        """Return list of tabs as dicts: {index, current, title, url}."""
        out = _run(self._args('tab-list'))
        items = []
        # Lines like: "- 0: (current) [Title](https://...)"
        for line in _parse_result(out).splitlines():
            m = re.match(r'-\s+(\d+):\s+(\(current\)\s+)?\[(.*?)\]\((.*?)\)', line)
            if not m:
                continue
            items.append({
                'index': int(m.group(1)),
                'current': bool(m.group(2)),
                'title': m.group(3),
                'url': m.group(4),
            })
        return items

    def tab_select(self, index: int) -> str:
        return _run(self._args('tab-select', str(index)))

    def tab_new(self, url: Optional[str] = None) -> str:
        cmd = ['tab-new']
        if url:
            cmd.append(url)
        return _run(self._args(*cmd))

    def tab_close(self, index: Optional[int] = None) -> str:
        cmd = ['tab-close']
        if index is not None:
            cmd.append(str(index))
        return _run(self._args(*cmd))

    # ---- network

    def requests(self, include_static: bool = False) -> list[dict]:
        """Return captured requests since page load.

        Each dict: {index, method, url, status, summary}.
        Use `request_detail(i)` or `response_body(i)` for full info.
        Worker fetches ARE included (CDP-native capture).
        """
        cmd = ['requests']
        if include_static:
            cmd.append('--static')
        out = _run(self._args(*cmd))
        items = []
        # Lines like: "1. [GET] https://example.com/ => [200] "
        for line in _parse_result(out).splitlines():
            m = re.match(r'(\d+)\.\s+\[(\w+)\]\s+(\S+)(?:\s+=>\s+\[(\d+)\])?', line.strip())
            if not m:
                continue
            items.append({
                'index': int(m.group(1)),
                'method': m.group(2),
                'url': m.group(3),
                'status': int(m.group(4)) if m.group(4) else None,
                'summary': line.strip(),
            })
        return items

    def request_detail(self, index: int) -> str:
        """Return the full text dump (headers/timing) for one request."""
        return _parse_result(_run(self._args('request', str(index))))

    def response_body(self, index: int) -> str:
        """Return the raw response body for one request."""
        return _run(self._args('response-body', str(index)))

    def request_body(self, index: int) -> str:
        """Return the raw request body for one request (POST payload)."""
        return _run(self._args('request-body', str(index)))

    def response_json(self, index: int) -> Any:
        """response_body + JSON parse."""
        return _try_json(self.response_body(index).strip())

    # ---- storage state

    def state_save(self, path: str) -> str:
        return _run(self._args('state-save', path))

    def state_load(self, path: str) -> str:
        return _run(self._args('state-load', path))


def list_sessions() -> str:
    """Plain text from `playwright-cli list`."""
    return _run(['list'])


__all__ = ['S', 'PWCError', 'list_sessions']
