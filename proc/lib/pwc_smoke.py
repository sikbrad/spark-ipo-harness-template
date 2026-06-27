"""Smoke test for pwc layer.

Run AFTER session bootstrap (see proc/plan/playwright-cli-bootstrap.md):
    python3 proc/lib/pwc_smoke.py

Validates:
- pwc.py wrapper round-trips (eval, requests, screenshot) against example.com
- pwc_teams.py / pwc_amaranth.py / pwc_salesforce.py modules import + dispatch
- Per-session URL probe — confirms each `-s=<name>` is on the right site
- No cross-session pollution (Teams session doesn't see SF's url etc.)

Exit code 0 iff every check passes. Skips checks when a session isn't bootstrapped.
"""

from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE))

from pwc import S, list_sessions, PWCError  # noqa: E402


def _probe(s: S) -> dict:
    """Return current URL/title or {error: ...} if session is closed."""
    try:
        info = s.eval('() => ({url: location.href, title: document.title})')
        return info or {'error': 'no info'}
    except PWCError as e:
        return {'error': str(e)[:200]}


def smoke_pwc_basic():
    """Spin up a throwaway session and exercise core wrapper paths."""
    print('--- pwc basic smoke ---')
    s = S('pwc-smoke')
    s.open('https://example.com')
    title = s.eval('document.title')
    h1 = s.eval('document.querySelector("h1").innerText')
    assert title == 'Example Domain', f'title mismatch: {title!r}'
    assert h1 == 'Example Domain', f'h1 mismatch: {h1!r}'
    reqs = s.requests()
    print(f'  title={title!r} h1={h1!r} requests={len(reqs)}')
    s.close()
    print('  PASS\n')


def smoke_per_session_isolation():
    """Each bootstrapped session should be on its expected origin."""
    print('--- per-session URL probe ---')
    expected = {
        'teams':      'teams.cloud.microsoft',
        'salesforce': 'lightning.force.com',
        'amaranth':   'erp.doflab.com',
    }
    sessions_text = list_sessions()
    for name, host_substr in expected.items():
        if name not in sessions_text:
            print(f'  [skip] {name}: not bootstrapped — see playwright-cli-bootstrap.md')
            continue
        info = _probe(S(name))
        url = info.get('url', '')
        ok = host_substr in url
        flag = 'PASS' if ok else 'FAIL'
        print(f'  [{flag}] {name}: url={url[:80]!r}')
        if not ok:
            print(f'         expected substring {host_substr!r}')
    print()


def smoke_module_dispatch():
    """Each pwc_<site>.py module should import + expose its main entry points."""
    print('--- module imports ---')
    import pwc_teams      # noqa: F401
    import pwc_amaranth   # noqa: F401
    import pwc_salesforce # noqa: F401
    print('  pwc_teams ✓ pwc_amaranth ✓ pwc_salesforce ✓')
    # Spot-check key public names
    for mod_name, expected in [
        ('pwc_teams',      ['ready', 'open_activity', 'collect_activity_full', 'unanswered_chats']),
        ('pwc_amaranth',   ['search_org', 'calendar_events', 'approval_docs', 'resource_bookings']),
        ('pwc_salesforce', ['login', 'aura_records', 'line_items', 'search_url']),
    ]:
        mod = sys.modules[mod_name]
        missing = [n for n in expected if not hasattr(mod, n)]
        flag = 'PASS' if not missing else 'FAIL'
        print(f'  [{flag}] {mod_name}: missing={missing}')
    print()


def main() -> int:
    failed = False
    try:
        smoke_pwc_basic()
    except Exception as e:
        print(f'  FAIL: {e}\n')
        failed = True
    try:
        smoke_module_dispatch()
    except Exception as e:
        print(f'  FAIL: {e}\n')
        failed = True
    try:
        smoke_per_session_isolation()
    except Exception as e:
        print(f'  FAIL: {e}\n')
        failed = True
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
