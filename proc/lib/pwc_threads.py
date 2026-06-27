"""Threads (threads.com) helpers for playwright-cli sessions.

Session convention: S('threads').

Bootstrap once (first-time login):
    playwright-cli -s=threads open https://www.threads.com/login --persistent --headed

Log in with Instagram or Threads account (2FA if needed). Then switch to headless:
    playwright-cli -s=threads close
    playwright-cli -s=threads open --persistent

Threads.com UI (verified 2026-05-11):
  * 2 Create buttons in DOM: top-nav + floating. The 2nd one opens compose modal.
  * Compose textbox: textbox "Empty text field. Type to compose a new post."
  * Chain: button "Add to thread" — disabled until current textbox has text.
    Click → new empty textbox appended below.
  * Final publish: button "Post" (modal-scoped, usually the last "Post" button
    in snapshot since feed cards also have "Post is shared..." but those are
    different roles).
  * Hard char limit per post: 500 (no auto-split).
"""

from __future__ import annotations

import re as _re
import time as _time
from pathlib import Path as _Path
from typing import Optional

from pwc import S, PWCError

THREADS_HOME = "https://www.threads.com/"
THREADS_LOGIN = "https://www.threads.com/login"
MAX_POST_CHARS = 500
_SPLIT_RE = _re.compile(r"^---+\s*$", _re.MULTILINE)
_REF_OF_CREATE = _re.compile(r'button "Create" \[ref=(e\d+)\]')
_REF_OF_POST = _re.compile(r'(?<!shared )(?<!is )button "Post" \[ref=(e\d+)\]')


# ---------------------------------------------------------------------------
# Snapshot helpers
# ---------------------------------------------------------------------------


def _find_refs(snap: str, role: str, name: str) -> list[str]:
    pat = _re.compile(
        rf'-\s+{_re.escape(role)}\s+"{_re.escape(name)}".*?\[ref=(e\d+)\]'
    )
    return pat.findall(snap)


def _find_textbox_refs(snap: str, name_substr: str) -> list[str]:
    pat = _re.compile(
        rf'-\s+textbox\s+"[^"]*{_re.escape(name_substr)}[^"]*".*?\[ref=(e\d+)\]'
    )
    return pat.findall(snap)


# ---------------------------------------------------------------------------
# Session / state
# ---------------------------------------------------------------------------


def is_logged_in(s: S) -> bool:
    """Quick check by snapshot — Create button only visible when logged in."""
    try:
        snap = s.snapshot()
    except PWCError:
        return False
    return bool(_REF_OF_CREATE.search(snap))


def ensure_home(s: S) -> str:
    """Ensure on home feed and logged in. Returns home snapshot."""
    cur = str(s.eval("location.href") or "")
    if not cur.startswith("https://www.threads.com"):
        s.goto(THREADS_HOME)
        _time.sleep(2)
    snap = s.snapshot()
    if not _REF_OF_CREATE.search(snap):
        raise PWCError(
            "Threads session not logged in. Bootstrap: "
            "`playwright-cli -s=threads open https://www.threads.com/login "
            "--persistent --headed` and log in manually."
        )
    return snap


# ---------------------------------------------------------------------------
# Markdown parsing
# ---------------------------------------------------------------------------


def parse_md(md_path: str | _Path) -> list[str]:
    """Read md, split on `---` lines, return trimmed post bodies.

    Optional YAML-like frontmatter at the top (first `---\\n...\\n---\\n`)
    is stripped (not used in v1 but accepted for future).

    Raises ValueError on empty result or block > MAX_POST_CHARS.
    """
    path = _Path(md_path)
    text = path.read_text(encoding="utf-8")

    # Strip leading frontmatter block if present
    if text.startswith("---\n") or text.startswith("---\r\n"):
        m = _re.search(r"^---\s*\r?\n.*?^---\s*\r?\n", text, _re.MULTILINE | _re.DOTALL)
        if m:
            text = text[m.end():]

    blocks = _SPLIT_RE.split(text)
    posts = [b.strip() for b in blocks if b.strip()]

    if not posts:
        raise ValueError(f"{path}: no post blocks found")
    for i, p in enumerate(posts, 1):
        if len(p) > MAX_POST_CHARS:
            raise ValueError(
                f"{path}: block {i} is {len(p)} chars (>{MAX_POST_CHARS}). "
                f"Threads hard limit is {MAX_POST_CHARS}; split manually."
            )
    return posts


# ---------------------------------------------------------------------------
# Compose / publish
# ---------------------------------------------------------------------------


def post_chain(s: S, posts: list[str], dry_run: bool = False) -> dict:
    """Open composer, fill root + chain, publish.

    Args:
        posts: list of post bodies. posts[0] is root; posts[1:] form the chain
               (each appended via "Add to thread").
        dry_run: if True, types everything then closes the modal without posting.

    Returns:
        {
          'posts_count': N,
          'url': result URL if redirect detected else None,
          'dry_run': bool,
          'screenshot': path to pre-publish screenshot,
        }
    """
    if not posts:
        raise ValueError("posts must be non-empty")
    for i, p in enumerate(posts, 1):
        if len(p) > MAX_POST_CHARS:
            raise ValueError(f"block {i} is {len(p)} chars (>{MAX_POST_CHARS})")

    snap = ensure_home(s)

    create_refs = _REF_OF_CREATE.findall(snap)
    if not create_refs:
        raise PWCError("Create button not found on home")
    # 2nd Create is the floating compose button (1st is nav)
    s.click(create_refs[1] if len(create_refs) >= 2 else create_refs[0])
    _time.sleep(1.5)

    # Root post
    snap = s.snapshot()
    tb = _find_textbox_refs(snap, "Empty text field")
    if not tb:
        raise PWCError("Compose textbox not found after opening composer")
    s.click(tb[-1])  # newest empty textbox
    _time.sleep(0.3)
    _safe_type(s, posts[0])
    _time.sleep(0.5)

    # Chain via 'Add to thread'
    for idx, body in enumerate(posts[1:], 2):
        snap = s.snapshot()
        atr = _find_refs(snap, "button", "Add to thread")
        if not atr:
            raise PWCError(f"'Add to thread' button not found before block {idx}")
        s.click(atr[0])
        _time.sleep(0.8)
        snap = s.snapshot()
        tb = _find_textbox_refs(snap, "Empty text field")
        if not tb:
            raise PWCError(f"new empty textbox not found for chain block {idx}")
        s.click(tb[-1])
        _time.sleep(0.3)
        _safe_type(s, body)
        _time.sleep(0.5)

    screenshot_path = s.screenshot()

    if dry_run:
        # Close compose modal. Threads asks "Save draft? Save / Don't save / Cancel".
        # We pick "Don't save" to leave no draft behind.
        s.press("Escape")
        _time.sleep(0.6)
        try:
            snap2 = s.snapshot()
            dont_save = _find_refs(snap2, "button", "Don't save")
            if dont_save:
                s.click(dont_save[0])
                _time.sleep(0.5)
        except PWCError:
            pass
        return {
            "posts_count": len(posts),
            "url": None,
            "dry_run": True,
            "screenshot": screenshot_path,
        }

    # Click final Post — modal-scoped. Use the last "Post" ref in snapshot
    # (feed cards have "Post is shared to Fediverse" etc. with different role
    # combinations; pure `button "Post"` only matches Reply/Compose buttons).
    snap = s.snapshot()
    post_refs = _find_refs(snap, "button", "Post")
    if not post_refs:
        raise PWCError("Post button not found in compose modal")
    s.click(post_refs[-1])

    # Wait for publish — modal closes, may redirect or stay
    _time.sleep(4)
    cur = str(s.eval("location.href") or "")
    url = cur if "/post/" in cur else None

    return {
        "posts_count": len(posts),
        "url": url,
        "dry_run": False,
        "screenshot": screenshot_path,
    }


def post_text(s: S, content: str, dry_run: bool = False) -> dict:
    """Single post. Convenience wrapper around post_chain."""
    return post_chain(s, [content], dry_run=dry_run)


def publish_markdown(s: S, md_path: str | _Path, dry_run: bool = False) -> dict:
    """End-to-end: parse md → validate → publish chain."""
    posts = parse_md(md_path)
    return post_chain(s, posts, dry_run=dry_run)


# ---------------------------------------------------------------------------
# Private
# ---------------------------------------------------------------------------


def _safe_type(s: S, text: str) -> None:
    """Type text into focused element. Avoid CLI option parsing if leading `-`."""
    if text.startswith("-"):
        # type-prefix workaround: type a space + backspace first
        s.type(" ")
        s.press("Backspace")
    s.type(text)


__all__ = [
    "S",
    "PWCError",
    "MAX_POST_CHARS",
    "is_logged_in",
    "ensure_home",
    "parse_md",
    "post_chain",
    "post_text",
    "publish_markdown",
]
