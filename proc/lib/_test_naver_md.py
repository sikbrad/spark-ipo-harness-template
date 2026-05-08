"""Smoke test — parse a markdown file and (optionally) publish it to Naver."""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

import pwc_naver as nb
from pwc import S

MD_PATH = Path(
    "/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04/"
    "input/blog/naver-blog-post-auto-example/sample.md"
)


def dry_run() -> None:
    """Parse the markdown without touching the browser."""
    text = MD_PATH.read_text(encoding="utf-8")
    front, body = nb._parse_frontmatter(text)
    print("[frontmatter]", json.dumps(front, ensure_ascii=False, indent=2), flush=True)
    blocks = nb._markdown_blocks(body, base_dir=MD_PATH.parent)
    print(f"[blocks] {len(blocks)} block(s):", flush=True)
    for i, b in enumerate(blocks):
        if b["type"] == "text":
            preview = b["value"].replace("\n", " | ")
            print(f"  {i:>2} TEXT  {preview[:120]}", flush=True)
        else:
            ok = "OK" if Path(b["path"]).exists() else "MISSING"
            print(f"  {i:>2} IMAGE {b['path']} [{ok}]", flush=True)


def live_publish() -> int:
    s = S("naver", persistent=True)
    log_no = nb.publish_markdown(s, MD_PATH)
    print(f"[publish_markdown] -> logNo = {log_no}", flush=True)
    post = nb.read_post(s, log_no)
    print(f"[read_post] title={post.get('title')!r}", flush=True)
    print(f"[read_post] body[:200]={post.get('body','')[:200]!r}", flush=True)
    return 0


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "dry"
    try:
        if mode == "dry":
            dry_run()
        elif mode == "live":
            sys.exit(live_publish())
        else:
            print("usage: _test_naver_md.py [dry|live]", file=sys.stderr)
            sys.exit(2)
    except Exception:
        traceback.print_exc()
        sys.exit(1)
