"""One-shot runner: dump every chatgpt.com conversation to
output/chatgpt/conversation_data/{id}.json (resume-safe).

Usage:
    cd <repo root> && python3 proc/run_chatgpt_export.py
"""

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'proc' / 'lib'))

from pwc import S
import pwc_chatgpt as cg


def main() -> None:
    s = S('chatgpt')
    if not cg.is_logged_in(s):
        print('NOT LOGGED IN — run bootstrap:')
        print('  playwright-cli -s=chatgpt open https://chatgpt.com/ --persistent --headed')
        sys.exit(1)
    started = time.time()
    summary = cg.dump_all_conversations(
        s,
        out_dir=ROOT / 'output' / 'chatgpt',
        db_path=ROOT / 'data' / 'chatgpt.sqlite',
        sleep_sec=2.5,            # bumped from 0.6 → 1.0 → 2.0 → 2.5 after rate-limit clusters
        progress_every=25,
        refresh_index=False,      # already cached at output/chatgpt/conversations.json
    )
    elapsed = time.time() - started
    print(f'elapsed={elapsed:.1f}s')
    print(f'final={summary}')


if __name__ == '__main__':
    main()
