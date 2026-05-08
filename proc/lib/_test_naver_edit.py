"""Edit-post smoke test — modifies the post created by _test_naver.py."""
from __future__ import annotations

import sys
import traceback

import pwc_naver as nb
from pwc import S

LOG_NO = 224278980125  # from _test_naver.py run


def main() -> int:
    s = S("naver", persistent=True)
    print(f"[edit] log_no={LOG_NO}", flush=True)
    new_log_no = nb.edit_post(
        s,
        log_no=LOG_NO,
        title="helper 검증 — 비공개 발행 테스트 (수정됨)",
        body=(
            "이 글은 edit_post로 본문이 수정되었습니다.\n"
            "원래 본문은 사라졌어야 합니다.\n"
            "edit 검증 끝.\n"
        ),
        visibility="private",
    )
    print(f"    -> returned log_no = {new_log_no}", flush=True)

    print("[read after edit]", flush=True)
    post = nb.read_post(s, new_log_no)
    print(f"    title: {post.get('title')!r}", flush=True)
    print(f"    body[:200]: {post.get('body','')[:200]!r}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)
