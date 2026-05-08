"""Delete all test posts created during this session (headless verification)."""
from __future__ import annotations

import sys
import traceback

import pwc_naver as nb
from pwc import S

# All logNos created during this session — order: oldest → newest
TEST_LOG_NOS = [
    224278980125,   # first write_post — "helper 검증 — 비공개 발행 테스트"
    224278993119,   # cooking↔AX (had 2 images via edit_markdown)
    224279043127,   # lifecycle v1 (auto-deleted via dialog side-effect)
    224279051391,   # lifecycle v1 redo (auto-deleted)
    224279056354,   # lifecycle v1 redo (auto-deleted)
    224279062556,   # lifecycle final (deleted by test [5])
]


def main() -> int:
    s = S("naver", persistent=True)
    print(f"[cleanup] {len(TEST_LOG_NOS)} log_nos to verify/delete (headless)", flush=True)
    for log_no in TEST_LOG_NOS:
        try:
            ok = nb.delete_post(s, log_no)
            print(f"  {log_no}: {'deleted/already-gone' if ok else 'still-present'}", flush=True)
        except Exception as e:
            print(f"  {log_no}: ERROR — {e}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)
