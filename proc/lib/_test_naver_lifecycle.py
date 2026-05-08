"""Full lifecycle test: publish → edit → delete."""
from __future__ import annotations

import sys
import time
import traceback
from pathlib import Path

import pwc_naver as nb
from pwc import S

BASE = Path(
    "/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04/"
    "input/blog/naver-blog-post-auto-example"
)


def main() -> int:
    s = S("naver", persistent=True)

    print("[1] publish_markdown(lifecycle-v1.md)…", flush=True)
    log_no = nb.publish_markdown(s, BASE / "lifecycle-v1.md")
    print(f"    -> logNo = {log_no}", flush=True)

    print("[2] read_post (verify v1)…", flush=True)
    p = nb.read_post(s, log_no)
    print(f"    title: {p.get('title')!r}", flush=True)
    print(f"    body[:100]: {p.get('body','')[:100]!r}", flush=True)

    time.sleep(2)
    print("[3] edit_markdown(log_no, lifecycle-v2.md)…", flush=True)
    new_log = nb.edit_markdown(s, log_no, BASE / "lifecycle-v2.md")
    print(f"    -> returned logNo = {new_log}", flush=True)

    print("[4] read_post (verify v2)…", flush=True)
    p = nb.read_post(s, new_log)
    print(f"    title: {p.get('title')!r}", flush=True)
    print(f"    body[:100]: {p.get('body','')[:100]!r}", flush=True)

    time.sleep(2)
    print(f"[5] delete_post({new_log})…", flush=True)
    ok = nb.delete_post(s, new_log)
    print(f"    -> deleted = {ok}", flush=True)

    print("[6] read_post (verify deletion)…", flush=True)
    try:
        p = nb.read_post(s, new_log)
        print(f"    title: {p.get('title')!r}", flush=True)
        print(f"    body_len: {len(p.get('body',''))}", flush=True)
    except Exception as e:
        print(f"    read_post raised: {e}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)
