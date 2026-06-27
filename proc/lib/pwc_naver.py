"""Naver blog helpers for playwright-cli sessions.

Session convention: S('naver') for naver-blog skill.

Bootstrap once (first-time login + device verification):
    playwright-cli -s=naver open https://nid.naver.com/nidlogin.login --persistent --headed
  Log in with NAVER_MALACCA_ID / NAVER_MALACCA_PW from .env, check
  "Stay Signed in", complete SMS device verification if prompted. The
  --persistent profile keeps cookies after that.

Auth note:
  Naver Open API blog/writePost.json requires app-review approval and only
  supports title+contents+image (no category/tags/visibility). Naver
  XMLRPC was discontinued 2020-05-06. Browser automation is the only
  remaining path that controls category/tags/visibility/comments.

  Naver actively flags Selenium-style automation. Mitigations baked in:
    * --persistent profile keeps cookies → re-login is rare
    * key input via .type() with intrinsic CDP timing (not bulk paste)
    * graceful detection-fallback to headed mode

SmartEditor 3 ("Smart Editor ONE") layout (verified 2026-05-08):
  * Title placeholder: paragraph "제목" — click then type
  * Body placeholder:  paragraph "글감과 함께 나의 일상을 기록해보세요!"
  * Publish: top-right button "발행" → opens slide-in panel
  * Panel inside: 카테고리, 공개 설정 radios, 댓글허용 etc., 태그 input,
    final "발행" button (the second occurrence of "발행")
"""

from __future__ import annotations

import os as _os
import re as _re
import subprocess as _subprocess
import time as _time
from pathlib import Path as _Path
from typing import Iterable, Optional

from pwc import S, PWCError

BLOG_HOME = "https://blog.naver.com"
LOGIN_URL = "https://nid.naver.com/nidlogin.login"
DEFAULT_BLOG_ID = "malacca_whale"

# Path to the project .env (3 levels up: proc/lib/pwc_naver.py)
_ENV_PATH = _Path(__file__).resolve().parents[2] / ".env"

# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

_REF_RE = _re.compile(r"\[ref=(e\d+)\]")


def _read_env(key: str) -> str:
    """Read a value from .env without `source` (which breaks on unescaped &/!)."""
    if not _ENV_PATH.exists():
        raise FileNotFoundError(f"{_ENV_PATH} not found")
    for line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    raise KeyError(f"{key} missing in {_ENV_PATH}")


def _find_ref_by_role(snap: str, role: str, name: str) -> Optional[str]:
    """Find ref of an element by aria role + accessible name.

    Matches lines like:  - button "발행" [ref=e48]
                         - radio "전체공개" [checked] [ref=e626]
                         - paragraph [ref=e266]: 글감과 함께 ...

    For paragraph (no name in role tag), pass role="paragraph" name="<text>".
    """
    if role == "paragraph":
        # paragraph lines have ":<text>" instead of quoted name
        pat = _re.compile(
            rf"-\s+paragraph\s+\[ref=(e\d+)\]\s*:\s*{_re.escape(name)}"
        )
    else:
        pat = _re.compile(
            rf'-\s+{_re.escape(role)}\s+"{_re.escape(name)}".*?\[ref=(e\d+)\]'
        )
    for line in snap.splitlines():
        m = pat.search(line)
        if m:
            return m.group(1)
    return None


def _find_all_refs_by_role(snap: str, role: str, name: str) -> list[str]:
    """Return all refs matching role + name, in document order."""
    if role == "paragraph":
        pat = _re.compile(
            rf"-\s+paragraph\s+\[ref=(e\d+)\]\s*:\s*{_re.escape(name)}"
        )
    else:
        pat = _re.compile(
            rf'-\s+{_re.escape(role)}\s+"{_re.escape(name)}".*?\[ref=(e\d+)\]'
        )
    return pat.findall(snap)


def _find_ref_by_text(snap: str, marker: str) -> Optional[str]:
    """Loose: first ref on a line containing the marker substring."""
    for line in snap.splitlines():
        if marker in line:
            m = _REF_RE.search(line)
            if m:
                return m.group(1)
    return None


def _snap(s: S, depth: int = 12) -> str:
    return s.snapshot(depth=depth)


def _safe_type(s: S, text: str) -> None:
    """Type via playwright-cli with `--` end-of-options separator.

    Plain `s.type(text)` fails when text starts with `-` (parsed as flag).
    The `--` separator forces all subsequent args to be positional.
    """
    s.raw("type", "--", text)


def _drain_modal(s: S) -> None:
    """Best-effort: dismiss any pending native dialog (beforeunload, alert).

    Chrome's beforeunload can't be suppressed from JS once a listener is
    attached (browser UI guard). Our pattern: navigate, accept any dialog
    that pops, retry navigation if needed.
    """
    for _ in range(3):
        try:
            s.raw("dialog-accept")
            _time.sleep(0.4)
        except PWCError:
            return  # no more dialogs


def _install_dialog_auto_accept(s: S) -> None:
    """Install a session-level page.on('dialog') auto-accept.

    Idempotent — uses a window-level sentinel to avoid stacking listeners
    on repeated calls. Once installed, all native dialogs (beforeunload,
    confirm, alert) are auto-accepted before they block playwright-cli.
    """
    try:
        s.raw(
            "run-code",
            (
                "async () => {"
                "  if (page.__naverAutoDialog) return 'already-installed';"
                "  page.__naverAutoDialog = true;"
                "  page.on('dialog', async d => { try { await d.accept(); } catch(e) {} });"
                "  return 'installed';"
                "}"
            ),
        )
    except PWCError:
        pass  # don't fail on environments where run-code isn't available


def _safe_goto(s: S, url: str, settle: float = 2.0) -> None:
    """Navigate to URL, surviving native beforeunload dialogs.

    Pattern: pre-drain any pending modal, try goto; if blocked by a
    beforeunload modal (PWCError on ERR_ABORTED, or TimeoutExpired when the
    subprocess hangs on the dialog), accept the dialog and retry.
    """
    _drain_modal(s)
    last_err: Optional[Exception] = None
    for attempt in range(3):
        try:
            s.goto(url)
            _time.sleep(settle)
            try:
                href = s.eval("location.href") or ""
            except (PWCError, _subprocess.TimeoutExpired):
                _drain_modal(s)
                continue
            if href and "nid.naver.com" not in href:
                return
            # mismatched URL — keep retrying
        except PWCError as e:
            last_err = e
            _drain_modal(s)
            _time.sleep(0.5)
        except _subprocess.TimeoutExpired as e:
            last_err = e
            _drain_modal(s)
            _time.sleep(0.5)
    if last_err:
        # last resort — drain and one final attempt
        _drain_modal(s)
        try:
            s.goto(url)
        except (PWCError, _subprocess.TimeoutExpired):
            _drain_modal(s)
        _time.sleep(settle)


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


def is_logged_in(s: S) -> bool:
    """Check by visiting blog home; if redirect lands on nid.naver.com → not logged in."""
    _safe_goto(s, BLOG_HOME, settle=1.5)
    href = s.eval("location.href") or ""
    return "nid.naver.com" not in href


def login(s: S, naver_id: Optional[str] = None, naver_pw: Optional[str] = None) -> None:
    """Auto-login from .env. Raises PWCError if Naver demands captcha or device
    verification (which can't be auto-completed) — bootstrap headed in that case."""
    nid = naver_id or _read_env("NAVER_MALACCA_ID")
    npw = naver_pw or _read_env("NAVER_MALACCA_PW")
    _safe_goto(s, LOGIN_URL, settle=1.5)
    snap = _snap(s, depth=8)

    id_ref = (
        _find_ref_by_role(snap, "textbox", "ID or Phone number")
        or _find_ref_by_role(snap, "textbox", "아이디")
    )
    pw_ref = (
        _find_ref_by_role(snap, "textbox", ">Password")
        or _find_ref_by_role(snap, "textbox", "Password")
        or _find_ref_by_role(snap, "textbox", "비밀번호")
    )
    stay_ref = (
        _find_ref_by_role(snap, "checkbox", "Stay Signed in")
        or _find_ref_by_role(snap, "checkbox", "로그인 상태 유지")
    )
    signin_ref = (
        _find_ref_by_role(snap, "button", "Sign in")
        or _find_ref_by_role(snap, "button", "로그인")
    )
    if not (id_ref and pw_ref and signin_ref):
        raise PWCError("login form refs not found — page may have changed")

    s.fill(id_ref, nid)
    _time.sleep(0.3)
    s.fill(pw_ref, npw)
    if stay_ref:
        s.click(stay_ref)
    _time.sleep(0.3)
    s.click(signin_ref)
    _time.sleep(3)

    if not is_logged_in(s):
        raise PWCError(
            "auto-login failed; likely captcha or new-device verification.\n"
            "Bootstrap headed: "
            "playwright-cli -s=naver open https://nid.naver.com/nidlogin.login --persistent --headed"
        )


def ensure_login(s: S) -> None:
    if not is_logged_in(s):
        login(s)
    # Always (re-)attempt to install the dialog auto-accept handler at the
    # start of any helper call. Idempotent — safe to call repeatedly.
    _install_dialog_auto_accept(s)


# ---------------------------------------------------------------------------
# Editor: open / set title / set body
# ---------------------------------------------------------------------------


def open_editor(s: S, blog_id: str = DEFAULT_BLOG_ID) -> None:
    """Open SmartEditor write form. Dismiss draft-restore dialog and help panel."""
    url = f"https://blog.naver.com/PostWriteForm.naver?blogId={blog_id}"
    _safe_goto(s, url, settle=3.0)

    snap = _snap(s)

    # 1) Draft restore dialog ("작성 중인 글이 있습니다 ... 이어서 작성하시겠습니까?")
    #    Click 취소 to start fresh — the new content will overwrite the existing draft.
    if "작성 중인 글" in snap or "이어서 작성" in snap:
        cancel_ref = _find_ref_by_role(snap, "button", "취소")
        if cancel_ref:
            try:
                s.click(cancel_ref)
                _time.sleep(1)
                snap = _snap(s)
            except PWCError:
                pass

    # 2) Help panel (도움말) — close button has aria role "button" name "닫기"
    if '도움말' in snap and 'se-help-title' in snap:
        close_ref = _find_ref_by_role(snap, "button", "닫기")
        if close_ref:
            try:
                s.click(close_ref)
                _time.sleep(0.5)
            except PWCError:
                pass


def set_title(s: S, title: str) -> None:
    """Set the post title. Clears any existing content first."""
    snap = _snap(s)
    title_ref = _find_ref_by_role(snap, "paragraph", "제목")
    if not title_ref:
        # already has content — find first paragraph in the title section
        # (heuristic: first occurrence of paragraph ref, since title is on top)
        m = _re.search(r"paragraph \[ref=(e\d+)\]", snap)
        title_ref = m.group(1) if m else None
    if not title_ref:
        raise PWCError("title element not found")
    s.click(title_ref)
    _time.sleep(0.2)
    s.press("Meta+a")
    s.press("Backspace")
    _time.sleep(0.2)
    _safe_type(s, title)


def set_body(s: S, body: str) -> None:
    """Set the post body. Multi-line text becomes multiple paragraphs."""
    snap = _snap(s)
    body_ref = _find_ref_by_role(
        snap, "paragraph", "글감과 함께 나의 일상을 기록해보세요!"
    )
    if not body_ref:
        # fallback: pick the second paragraph (first is title)
        all_paras = _re.findall(r"paragraph \[ref=(e\d+)\]", snap)
        body_ref = all_paras[1] if len(all_paras) >= 2 else None
    if not body_ref:
        raise PWCError("body element not found")
    s.click(body_ref)
    _time.sleep(0.3)
    # Clear in case existing content
    s.press("Meta+a")
    s.press("Backspace")
    _time.sleep(0.2)
    for i, line in enumerate(body.split("\n")):
        if i > 0:
            s.press("Enter")
        if line:
            _safe_type(s, line)


# ---------------------------------------------------------------------------
# Publish
# ---------------------------------------------------------------------------

VISIBILITY_LABELS = {
    "public": "전체공개",
    "neighbors": "이웃공개",
    "mutual": "서로이웃공개",
    "private": "비공개",
}


def _open_publish_panel(s: S) -> str:
    """Click the top-right 발행 button to slide in the panel. Returns fresh snapshot."""
    snap = _snap(s)
    # Top-right 발행: there's only one initially, panel adds another below
    pub_refs = _find_all_refs_by_role(snap, "button", "발행")
    if not pub_refs:
        raise PWCError("top 발행 button not found")
    s.click(pub_refs[0])
    _time.sleep(2)
    return _snap(s)


def _click_visibility(s: S, snap: str, visibility: str) -> None:
    if visibility not in VISIBILITY_LABELS:
        raise ValueError(f"unknown visibility: {visibility}")
    ref = _find_ref_by_role(snap, "radio", VISIBILITY_LABELS[visibility])
    if not ref:
        raise PWCError(f"visibility radio '{VISIBILITY_LABELS[visibility]}' not found")
    s.click(ref)
    _time.sleep(0.3)


def _set_category(s: S, snap: str, category: str) -> None:
    cat_btn = _find_ref_by_role(snap, "button", "카테고리 목록 버튼")
    if not cat_btn:
        return
    s.click(cat_btn)
    _time.sleep(0.5)
    snap2 = _snap(s)
    # Category items are listitems with the category name as text.
    # Find by listitem with matching text — first occurrence.
    cat_ref = None
    pat = _re.compile(rf"listitem\s+\[ref=(e\d+)\]\s*[^\n]*\b{_re.escape(category)}\b")
    m = pat.search(snap2)
    if m:
        cat_ref = m.group(1)
    if not cat_ref:
        # fallback: any line that contains the category text
        cat_ref = _find_ref_by_text(snap2, category)
    if not cat_ref:
        raise PWCError(f"category '{category}' not found in dropdown")
    s.click(cat_ref)
    _time.sleep(0.3)


def _set_tags(s: S, snap: str, tags: Iterable[str]) -> None:
    tag_input = _find_ref_by_role(snap, "combobox", "태그 입력 (최대 30개)")
    if not tag_input:
        return
    s.click(tag_input)
    _time.sleep(0.2)
    for tag in tags:
        _safe_type(s, tag)
        s.press("Enter")
        _time.sleep(0.1)


def _toggle_comments(s: S, snap: str, allow: bool) -> None:
    """The comment checkbox starts checked; only toggle if disabling."""
    if allow:
        return
    ref = _find_ref_by_role(snap, "checkbox", "댓글허용")
    if ref:
        s.click(ref)
        _time.sleep(0.2)


def _click_final_publish(s: S) -> None:
    """The last (panel-internal) 발행 button confirms publication."""
    snap = _snap(s)
    pub_refs = _find_all_refs_by_role(snap, "button", "발행")
    if not pub_refs:
        raise PWCError("final 발행 button not found")
    s.click(pub_refs[-1])
    _time.sleep(5)


def _extract_log_no(s: S, blog_id: str) -> Optional[int]:
    href = s.eval("location.href") or ""
    m = _re.search(r"logNo=(\d+)", href)
    if not m:
        m = _re.search(rf"{_re.escape(blog_id)}/(\d+)", href)
    return int(m.group(1)) if m else None


def publish(
    s: S,
    blog_id: str = DEFAULT_BLOG_ID,
    category: Optional[str] = None,
    tags: Optional[Iterable[str]] = None,
    visibility: str = "public",
    allow_comments: bool = True,
) -> int:
    """Open the publish panel, apply options, click final 발행. Returns logNo."""
    snap = _open_publish_panel(s)
    _click_visibility(s, snap, visibility)
    if category:
        _set_category(s, _snap(s), category)
    if tags:
        _set_tags(s, _snap(s), tags)
    _toggle_comments(s, _snap(s), allow_comments)
    _click_final_publish(s)

    log_no = _extract_log_no(s, blog_id)
    if log_no is None:
        raise PWCError(
            f"publish appeared to succeed but logNo could not be extracted from "
            f"current URL: {s.eval('location.href')}"
        )
    return log_no


# ---------------------------------------------------------------------------
# Composite operation
# ---------------------------------------------------------------------------


def write_post(
    s: S,
    title: str,
    body: str,
    blog_id: str = DEFAULT_BLOG_ID,
    category: Optional[str] = None,
    tags: Optional[Iterable[str]] = None,
    visibility: str = "public",
    allow_comments: bool = True,
) -> int:
    """End-to-end: ensure login → open editor → set title/body → publish."""
    ensure_login(s)
    open_editor(s, blog_id=blog_id)
    set_title(s, title)
    set_body(s, body)
    return publish(
        s,
        blog_id=blog_id,
        category=category,
        tags=tags,
        visibility=visibility,
        allow_comments=allow_comments,
    )


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------


def read_post(s: S, log_no: int, blog_id: str = DEFAULT_BLOG_ID) -> dict:
    """Fetch and parse a published blog post. Returns {title, body, url}.

    Naver blog posts render inside an iframe (mainFrame) on the public page.
    Direct PostView.naver URL also wraps the actual content in an iframe.
    """
    url = f"https://blog.naver.com/{blog_id}/{log_no}"
    _safe_goto(s, url, settle=2.0)

    info = s.eval(
        "(()=>{"
        "const f=document.querySelector('iframe#mainFrame')||document.querySelector('iframe[name=mainFrame]');"
        "const d=f?f.contentDocument:document;"
        "const t=d.querySelector('.se-title-text, .pcol1, h3.se_textarea, .htitle')||d.querySelector('h2,h3');"
        "const b=d.querySelector('.se-main-container, #postViewArea, .post-view, .post_ct, .se-component-container');"
        "return {"
        "  title: t? (t.innerText||'').trim() : '',"
        "  body:  b? (b.innerText||'').trim() : '',"
        "  has_iframe: !!f"
        "};"
        "})()"
    )
    return {"url": url, "log_no": log_no, **(info or {})}


# ---------------------------------------------------------------------------
# Edit (re-open existing post in editor)
# ---------------------------------------------------------------------------


def open_for_edit(s: S, log_no: int, blog_id: str = DEFAULT_BLOG_ID) -> None:
    """Open existing post in editor. URL pattern: PostWriteForm with logNo.

    Critical: Naver renders the editor frame first, then async-fetches post
    content. If we don't wait for content to load, our typing happens against
    the placeholder and gets clobbered when the real content arrives. We
    poll the title text until it changes from the placeholder "제목".
    """
    url = (
        f"https://blog.naver.com/PostWriteForm.naver"
        f"?blogId={blog_id}&logNo={log_no}&redirect=Update"
    )
    _safe_goto(s, url, settle=2.0)

    # Wait for post content load — title element changes from "제목" to actual.
    for _ in range(30):  # up to ~15s
        try:
            title_text = s.eval(
                "(()=>{const t=document.querySelector('.se-title-text');"
                "return t? (t.innerText||'').trim() : '';})()"
            )
        except PWCError:
            title_text = ""
        if title_text and title_text != "제목":
            break
        _time.sleep(0.5)

    # Help panel may pop on first visit
    snap = _snap(s)
    if '도움말' in snap and 'se-help-title' in snap:
        close_ref = _find_ref_by_role(snap, "button", "닫기")
        if close_ref:
            try:
                s.click(close_ref)
                _time.sleep(0.5)
            except PWCError:
                pass


def edit_post(
    s: S,
    log_no: int,
    blog_id: str = DEFAULT_BLOG_ID,
    title: Optional[str] = None,
    body: Optional[str] = None,
    category: Optional[str] = None,
    tags: Optional[Iterable[str]] = None,
    visibility: Optional[str] = None,
    allow_comments: Optional[bool] = None,
) -> int:
    """Edit an existing post. Only fields you pass are changed.

    Naver re-publish keeps the same logNo, so the return value matches input.
    """
    ensure_login(s)
    open_for_edit(s, log_no, blog_id=blog_id)
    if title is not None:
        set_title(s, title)
    if body is not None:
        set_body(s, body)
    # For options, we always need to interact with the publish panel —
    # if the user passes None for visibility/comments, we still publish but
    # don't override. Thread defaults through.
    return publish(
        s,
        blog_id=blog_id,
        category=category,
        tags=tags,
        visibility=visibility or "public",
        allow_comments=allow_comments if allow_comments is not None else True,
    )


# ---------------------------------------------------------------------------
# Markdown publishing — frontmatter + body + inline images
# ---------------------------------------------------------------------------

# Image syntax we recognize:
#   - ![alt](relative/or/absolute/path.png)        — standard markdown
#   - ![[name.png]]                                — Obsidian wikilink
_MD_IMAGE_RE = _re.compile(
    r"!\[(?P<alt>[^\]]*)\]\((?P<path>[^)]+)\)|"
    r"!\[\[(?P<wpath>[^\]|]+?)(?:\|[^\]]*)?\]\]"
)


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Parse Obsidian-style YAML-ish frontmatter at the top of a markdown file.

    Supports:  key: value            (str)
               key: [a, b, c]        (inline list)
               key:                  (block list)
                 - a
                 - b
               numeric/bool coercion for visibility/allow_comments

    Returns (frontmatter_dict, body_text). No frontmatter → ({}, text).
    """
    if not text.startswith("---"):
        return {}, text
    parts = text.split("\n", 1)[1].split("\n---", 1)
    if len(parts) < 2:
        return {}, text
    fm_raw, body = parts[0], parts[1].lstrip("\n")
    fm: dict = {}
    cur_key: Optional[str] = None
    for raw in fm_raw.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        # block list item under previous key
        if line.startswith(" ") or line.startswith("\t"):
            item = line.strip().lstrip("-").strip().strip('"').strip("'")
            if cur_key and item:
                fm.setdefault(cur_key, [])
                if isinstance(fm[cur_key], list):
                    fm[cur_key].append(item)
            continue
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        k = k.strip()
        v = v.strip()
        cur_key = k
        if not v:
            fm[k] = []  # list begins on next line(s)
            continue
        # inline list  [a, b]
        if v.startswith("[") and v.endswith("]"):
            items = [
                x.strip().strip('"').strip("'")
                for x in v[1:-1].split(",")
                if x.strip()
            ]
            fm[k] = items
            continue
        v = v.strip('"').strip("'")
        # bool coercion
        if v.lower() in ("true", "yes"):
            fm[k] = True
        elif v.lower() in ("false", "no"):
            fm[k] = False
        else:
            fm[k] = v
    return fm, body


def _markdown_blocks(body: str, base_dir: _Path) -> list[dict]:
    """Split a markdown body into a flat block sequence.

    Each block:  {'type': 'text' | 'image', 'value' | 'path'}
    Heading lines (# / ## / ###) → text (markdown punctuation stripped).
    Lines containing image refs → image blocks (one per ref).
    Consecutive non-image text lines are joined with '\\n'.
    """
    blocks: list[dict] = []
    text_buf: list[str] = []

    def flush_text() -> None:
        if not text_buf:
            return
        joined = "\n".join(text_buf).strip("\n")
        if joined.strip():
            blocks.append({"type": "text", "value": joined})
        text_buf.clear()

    for raw_line in body.splitlines():
        m = _MD_IMAGE_RE.search(raw_line)
        if m:
            # split surrounding text on the same line
            before = raw_line[: m.start()].rstrip()
            after = raw_line[m.end():].lstrip()
            if before:
                text_buf.append(before)
            flush_text()
            path_str = m.group("path") or m.group("wpath")
            # resolve relative path
            p = _Path(path_str.strip())
            if not p.is_absolute():
                # try base_dir/path first
                candidate = base_dir / path_str.strip()
                if not candidate.exists():
                    # Obsidian wikilinks reference by filename only — search base_dir
                    matches = list(base_dir.rglob(p.name))
                    if matches:
                        candidate = matches[0]
                p = candidate
            blocks.append({"type": "image", "path": str(p)})
            if after:
                text_buf.append(after)
            continue
        # strip markdown heading markers — SmartEditor treats them literally
        if raw_line.lstrip().startswith("#"):
            stripped = _re.sub(r"^\s*#+\s*", "", raw_line)
            if stripped.strip():
                text_buf.append(stripped)
            continue
        text_buf.append(raw_line)
    flush_text()
    return blocks


def _insert_image(s: S, image_path: str, settle: float = 5.0) -> None:
    """Insert an image into the body at the current cursor position.

    Strategy: find the hidden `<input type="file">` that SmartEditor exposes
    when "사진 추가" is set up; populate it via `upload`. SmartEditor wires up
    the hidden input on first photo button click, so we click first, then
    upload, then wait for the embed to render.
    """
    if not _Path(image_path).exists():
        raise PWCError(f"image not found: {image_path}")
    snap = _snap(s)
    photo_btn = (
        _find_ref_by_role(snap, "button", "사진 추가")
        or _find_ref_by_role(snap, "button", "사진")
    )
    if not photo_btn:
        raise PWCError("'사진 추가' button not found")
    s.click(photo_btn)
    _time.sleep(0.4)
    # The hidden file input should now be available — playwright-cli `upload`
    # finds it. Native macOS file dialog (if any) is bypassed.
    s.raw("upload", image_path)
    _time.sleep(settle)


def publish_markdown(
    s: S,
    md_path: str | _Path,
    blog_id: str = DEFAULT_BLOG_ID,
    override_visibility: Optional[str] = None,
) -> int:
    """Publish a markdown file as a Naver blog post.

    Frontmatter keys consumed:
        title          (str, required)
        tags           (list[str], optional)
        category       (str, optional)
        visibility     (str: public/neighbors/mutual/private, default public)
        allow_comments (bool, default True)

    Body markdown:
        - Headings (#, ##, ###) → plain paragraphs (markers stripped)
        - Paragraphs → typed as text
        - Images (![alt](path), ![[name]]) → uploaded to SmartEditor inline
    """
    md_path = _Path(md_path).resolve()
    if not md_path.exists():
        raise FileNotFoundError(md_path)

    text = md_path.read_text(encoding="utf-8")
    front, body = _parse_frontmatter(text)
    title = front.get("title")
    if not title:
        raise PWCError(f"missing 'title' in frontmatter of {md_path}")
    blocks = _markdown_blocks(body, base_dir=md_path.parent)

    visibility = override_visibility or front.get("visibility") or "public"
    tags = front.get("tags") or None
    category = front.get("category") or None
    allow_comments = front.get("allow_comments")
    if allow_comments is None:
        allow_comments = True

    ensure_login(s)
    open_editor(s, blog_id=blog_id)

    set_title(s, title)
    _set_body_blocks(s, blocks)

    return publish(
        s,
        blog_id=blog_id,
        category=category,
        tags=tags,
        visibility=visibility,
        allow_comments=bool(allow_comments),
    )


def _set_body_blocks(s: S, blocks: list[dict]) -> None:
    """Clear the editor body and write a sequence of {type: text|image} blocks.

    Used by both publish_markdown (fresh post) and edit_markdown (existing
    post). Walks blocks in order: text blocks become paragraphs separated by
    Enter; image blocks click the photo button + upload at that position.
    """
    snap = _snap(s)
    body_ref = _find_ref_by_role(
        snap, "paragraph", "글감과 함께 나의 일상을 기록해보세요!"
    )
    if not body_ref:
        all_paras = _re.findall(r"paragraph \[ref=(e\d+)\]", snap)
        body_ref = all_paras[1] if len(all_paras) >= 2 else None
    if not body_ref:
        raise PWCError("body element not found before block walk")
    s.click(body_ref)
    _time.sleep(0.3)
    # Clear any existing body content (text + images)
    s.press("Meta+a")
    _time.sleep(0.1)
    s.press("Backspace")
    _time.sleep(0.3)

    for i, block in enumerate(blocks):
        if i > 0:
            s.press("Enter")
            _time.sleep(0.1)
        if block["type"] == "text":
            for j, line in enumerate(block["value"].split("\n")):
                if j > 0:
                    s.press("Enter")
                if line:
                    _safe_type(s, line)
        elif block["type"] == "image":
            _insert_image(s, block["path"])


def _is_post_deleted(s: S, log_no: int, blog_id: str) -> bool:
    """Probe whether a post is already deleted.

    Behavior on Naver: visiting `/malacca_whale/{log_no}` of a deleted post
    fires a native alert "게시물이 삭제되었거나 다른 페이지로 변경되었습니다."
    and the URL ends up at `/malacca_whale` (blog root, no logNo). We use
    that as the deletion signal without depending on iframe content (which
    can mislead because the home iframe falls back to the most recent
    valid post).
    """
    url = f"https://blog.naver.com/{blog_id}/{log_no}"
    _safe_goto(s, url, settle=2.0)
    _drain_modal(s)
    _time.sleep(0.5)
    href = s.eval("location.href") or ""
    # Deleted post → URL strips logNo, lands on blog root (or PostList)
    if str(log_no) not in href:
        return True
    # Or the iframe shows different logNo than expected
    iframe_log = s.eval(
        "(()=>{const f=document.querySelector('iframe#mainFrame');"
        "if(!f) return null;"
        "const m=(f.src||'').match(/logNo=(\\d+)/);"
        "return m? m[1] : null;})()"
    )
    if iframe_log and iframe_log != str(log_no):
        return True
    return False


def delete_post(s: S, log_no: int, blog_id: str = DEFAULT_BLOG_ID) -> bool:
    """Delete a post by logNo.

    Visit the post page → wait for the iframe to surface the owner-only
    delete link `a.btn_del._deletePost` → click it (triggers native
    `confirm()`: "삭제된 글은 복구할 수 없습니다. 삭제하시겠습니까?") →
    accept the confirm + any followup alert. Verify via `_is_post_deleted`.

    Idempotent: if the post is already deleted (probed first), returns True
    without doing anything.

    Returns True on confirmed deletion. Raises PWCError only if the post
    still exists after the delete attempt.
    """
    ensure_login(s)

    if _is_post_deleted(s, log_no, blog_id):
        return True  # already gone

    url = f"https://blog.naver.com/{blog_id}/{log_no}"
    _safe_goto(s, url, settle=2.5)
    _drain_modal(s)

    # Poll iframe for the owner's delete link — Naver loads PostView.naver
    # inside iframe#mainFrame asynchronously, often after the outer page
    # settles. Match by logNo in the _param(...) class to ignore whatever
    # post the iframe might transiently fall back to.
    link_found = False
    for _ in range(20):  # ~10s
        res = s.eval(
            f"(()=>{{"
            f"const f=document.querySelector('iframe#mainFrame');"
            f"const d=f?f.contentDocument:document;"
            f"if(!d) return false;"
            f"const links=Array.from(d.querySelectorAll('a._deletePost'));"
            f"const target=links.find(a=>a.className.includes('_param({log_no}|'));"
            f"if(!target) return false;"
            f"target.click(); return true;"
            f"}})()"
        )
        if res is True:
            link_found = True
            break
        _time.sleep(0.5)

    if not link_found:
        # The auto-dialog handler may have accepted an "이미 삭제..." alert
        # mid-navigation, which strips logNo from URL and lands on blog root.
        # Probe explicitly — if so, the post is gone and delete is moot.
        if _is_post_deleted(s, log_no, blog_id):
            return True
        raise PWCError(
            f"delete link for logNo={log_no} not found inside iframe "
            f"(post may already be gone or owner check failed)"
        )

    # Native confirm fires immediately after click — accept it.
    _time.sleep(0.5)
    try:
        s.raw("dialog-accept")
    except PWCError:
        pass
    _time.sleep(2.0)
    _drain_modal(s)
    _time.sleep(1.0)

    # Verify by probing again — deletion makes the URL strip logNo on revisit.
    if _is_post_deleted(s, log_no, blog_id):
        return True
    raise PWCError(
        f"delete attempt did not take — post {log_no} still resolves on visit"
    )


def edit_markdown(
    s: S,
    log_no: int,
    md_path: str | _Path,
    blog_id: str = DEFAULT_BLOG_ID,
    override_visibility: Optional[str] = None,
) -> int:
    """Edit an existing post using a markdown file with frontmatter + images.

    Counterpart to `publish_markdown` for updates: replaces title, body
    (text + inline images), and publish options on the existing logNo.
    Returns the same logNo (Naver keeps URL on edit).
    """
    md_path = _Path(md_path).resolve()
    if not md_path.exists():
        raise FileNotFoundError(md_path)

    text = md_path.read_text(encoding="utf-8")
    front, body = _parse_frontmatter(text)
    title = front.get("title")
    if not title:
        raise PWCError(f"missing 'title' in frontmatter of {md_path}")
    blocks = _markdown_blocks(body, base_dir=md_path.parent)

    visibility = override_visibility or front.get("visibility") or "public"
    tags = front.get("tags") or None
    category = front.get("category") or None
    allow_comments = front.get("allow_comments")
    if allow_comments is None:
        allow_comments = True

    ensure_login(s)
    open_for_edit(s, log_no, blog_id=blog_id)

    set_title(s, title)
    _set_body_blocks(s, blocks)

    return publish(
        s,
        blog_id=blog_id,
        category=category,
        tags=tags,
        visibility=visibility,
        allow_comments=bool(allow_comments),
    )


__all__ = [
    "BLOG_HOME",
    "LOGIN_URL",
    "DEFAULT_BLOG_ID",
    "VISIBILITY_LABELS",
    "is_logged_in",
    "login",
    "ensure_login",
    "open_editor",
    "set_title",
    "set_body",
    "publish",
    "write_post",
    "read_post",
    "open_for_edit",
    "edit_post",
    "publish_markdown",
    "edit_markdown",
    "delete_post",
]
