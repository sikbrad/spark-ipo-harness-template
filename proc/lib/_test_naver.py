"""Smoke test for pwc_naver helper. Private publish + read-back."""
from __future__ import annotations

import sys
import traceback

import pwc_naver as nb
from pwc import S


def main() -> int:
    s = S("naver", persistent=True)
    print("[1] is_logged_in:", flush=True)
    print("    ", nb.is_logged_in(s), flush=True)

    print("[2] write_post (private)…", flush=True)
    log_no = nb.write_post(
        s,
        title="helper 검증 — 비공개 발행 테스트",
        body=(
            "안녕하세요.\n"
            "pwc_naver helper로 자동 발행된 글입니다.\n"
            "\n"
            "검증 항목:\n"
            "- 제목/본문 입력\n"
            "- 발행 패널: 비공개 / 태그\n"
            "- read_post / edit_post 동작\n"
        ),
        visibility="private",
        tags=["자동화", "playwright-cli"],
    )
    print(f"    -> logNo = {log_no}", flush=True)

    print("[3] read_post…", flush=True)
    post = nb.read_post(s, log_no)
    print(f"    title: {post.get('title')!r}", flush=True)
    print(f"    body[:120]: {post.get('body','')[:120]!r}", flush=True)
    print(f"    url: {post.get('url')}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)
