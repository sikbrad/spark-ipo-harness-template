"""Register Amaranth roster (data/company/people/*.json) to Google Contacts.

Dedup key: last-10-digits of mobile (no hyphens, country-code agnostic).
Plan: proc/plan/2026-05-15_amaranth-people-to-gcontacts.md
"""
from __future__ import annotations

import glob as _glob
import json as _json
import os as _os
import sys as _sys
import time as _time
from typing import Any, Optional

_THIS_DIR = _os.path.dirname(_os.path.abspath(__file__))
if _THIS_DIR not in _sys.path:
    _sys.path.insert(0, _THIS_DIR)

from google_auth import GoogleClient  # type: ignore  # noqa: E402
from gcontacts_api import list_contacts, parse_person  # type: ignore  # noqa: E402


CO_ROOT = '주식회사 디오에프'  # comOptPath prefix to strip
TPL_CO = '디오에프'  # template fragment between name and dept
SELF_LOGIN_IDS = {'ins'}  # 본인(백인식) — Amaranth 명부에서 자동 제외


# ---------------------------------------------------------------------------
# Pure helpers (no API calls — unit-testable)
# ---------------------------------------------------------------------------

def norm_phone(s: Optional[str]) -> Optional[str]:
    """Last 10 digits as the dedup key. Returns None if <10 digits."""
    if not s:
        return None
    digits = ''.join(ch for ch in s if ch.isdigit())
    return digits[-10:] if len(digits) >= 10 else None


def _dept2_segments(dept_path: Optional[str]) -> list[str]:
    """Decision (A): strip CO_ROOT, then return the last 2 segments."""
    if not dept_path:
        return []
    segs = [s.strip() for s in dept_path.split('>') if s.strip()]
    if segs and segs[0] == CO_ROOT:
        segs = segs[1:]
    return segs[-2:]


def render_name(person: dict) -> str:
    """displayName = '{name} 디오에프 {끝2단계공백}'."""
    name = person.get('name') or ''
    parts = [name, TPL_CO] + _dept2_segments(person.get('dept_path'))
    return ' '.join(p for p in parts if p)


def render_memo(person: dict) -> Optional[str]:
    """Multi-line biography. Skips lines whose source value is empty."""
    lines = []
    if v := person.get('login_id'):
        lines.append(f'ID {v}')
    if v := person.get('birthday'):
        lines.append(f'생일 {v}')
    if v := person.get('join_day'):
        lines.append(f'입사일 {v}')
    if v := (person.get('main_work') or '').strip():
        lines.append(f'주업무: {v}')
    if v := person.get('dept_path'):
        lines.append(f'부서 경로: {v}')
    return '\n'.join(lines) if lines else None


def build_body(person: dict) -> dict:
    """Construct the People API createContact body for one Amaranth person."""
    body: dict[str, Any] = {
        'names': [{'unstructuredName': render_name(person)}],
    }

    phones = []
    if person.get('mobile'):
        phones.append({'value': person['mobile'], 'type': 'mobile'})
    for k in ('ext_num', 'tel_num'):
        if person.get(k):
            phones.append({'value': person[k], 'type': 'work'})
    if phones:
        body['phoneNumbers'] = phones

    if person.get('email'):
        body['emailAddresses'] = [{'value': person['email'], 'type': 'work'}]

    org: dict[str, Any] = {'type': 'work'}
    if person.get('company'):
        org['name'] = person['company']
    if person.get('dept'):
        org['department'] = person['dept']  # leaf only (decision: leaf 1개만)
    if person.get('position'):
        org['title'] = person['position']
    if person.get('duty'):
        org['jobDescription'] = person['duty']
    if len(org) > 1:  # at least one real field beyond 'type'
        body['organizations'] = [org]

    if person.get('addr'):
        formatted = person['addr']
        if person.get('zip_code'):
            formatted = f"({person['zip_code']}) {formatted}"
        body['addresses'] = [{'formattedValue': formatted, 'type': 'work'}]

    if memo := render_memo(person):
        body['biographies'] = [{'value': memo, 'contentType': 'TEXT_PLAIN'}]

    return body


# ---------------------------------------------------------------------------
# Live ops (Google API + file IO)
# ---------------------------------------------------------------------------

def load_people(base_dir: str = 'data/company/people') -> list[dict]:
    """Read every <name>_person_info.json (skips _archived/ via top-level glob)."""
    paths = sorted(_glob.glob(_os.path.join(base_dir, '*_person_info.json')))
    out = []
    for p in paths:
        try:
            out.append(_json.load(open(p, encoding='utf-8')))
        except Exception as e:
            print(f'  WARN skip unreadable file {p}: {e}', file=_sys.stderr)
    return out


def existing_phone_index(g: GoogleClient) -> tuple[set[str], list[dict]]:
    """Return (normalized phone set, raw contacts list).

    parse_person() returns phones as dicts {'value', 'canonical', 'type'} —
    normalize from BOTH `value` and `canonical` so that hyphenated locals and
    +82 E.164 forms both contribute the same last-10-digits key.
    """
    contacts = list_contacts(g, limit=5000)
    keys: set[str] = set()
    for c in contacts:
        for phone in c.get('phones') or []:
            if isinstance(phone, dict):
                for s in (phone.get('value'), phone.get('canonical')):
                    k = norm_phone(s)
                    if k:
                        keys.add(k)
            else:  # legacy: plain string
                k = norm_phone(phone)
                if k:
                    keys.add(k)
    return keys, contacts


def sync(
    account: str = 'bispro89',
    base_dir: str = 'data/company/people',
    dry_run: bool = True,
    sleep: float = 0.3,
) -> dict:
    """Main sync.

    Returns {
      'created': [...], 'dup_skip': [...], 'no_mobile': [...], 'errors': [...]
    }
    Each list contains dicts with at least {name, mobile, display_name}.
    """
    people = load_people(base_dir)
    g = GoogleClient(account)
    existing, _ = existing_phone_index(g)

    result = {'created': [], 'dup_skip': [], 'no_mobile': [],
              'self_skip': [], 'errors': []}
    svc = g.service('people', 'v1') if not dry_run else None

    for p in people:
        display = render_name(p)
        key = norm_phone(p.get('mobile'))
        rec = {'name': p.get('name'), 'mobile': p.get('mobile'),
               'display_name': display, 'dept_path': p.get('dept_path')}

        if (p.get('login_id') or '') in SELF_LOGIN_IDS:
            result['self_skip'].append(rec)
            continue
        if key is None:
            result['no_mobile'].append(rec)
            continue
        if key in existing:
            result['dup_skip'].append(rec)
            continue

        if dry_run:
            result['created'].append({**rec, 'resource_name': '(dry-run)'})
            existing.add(key)  # so same phone in input isn't double-counted
            continue

        body = build_body(p)
        try:
            resp = svc.people().createContact(  # type: ignore[union-attr]
                body=body,
                personFields='names,phoneNumbers,emailAddresses,organizations,'
                             'addresses,biographies',
            ).execute()
            created = parse_person(resp)
            result['created'].append({
                **rec, 'resource_name': created.get('resource_name')
            })
            existing.add(key)
        except Exception as e:
            result['errors'].append({**rec, 'error': str(e)})
        _time.sleep(sleep)

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_report(result: dict, mode: str) -> None:
    n_c, n_d, n_n, n_s, n_e = (
        len(result.get(k, [])) for k in
        ('created', 'dup_skip', 'no_mobile', 'self_skip', 'errors'))
    print(f'\n[{mode}] created={n_c} dup_skip={n_d} no_mobile={n_n} '
          f'self_skip={n_s} errors={n_e}\n')
    if result.get('self_skip'):
        print('-- self_skip (본인) --')
        for r in result['self_skip']:
            print(f"  {r['name']:<8}  ({r['dept_path']})")
    if result['no_mobile']:
        print('\n-- no_mobile (skipped) --')
        for r in result['no_mobile']:
            print(f"  {r['name']:<8}  ({r['dept_path']})")
    if result['dup_skip']:
        print('\n-- dup_skip (phone already in Google) --')
        for r in result['dup_skip']:
            print(f"  {r['name']:<8}  {r['mobile']:<15}  ({r['dept_path']})")
    if result['created']:
        print(f"\n-- {'will-create' if mode == 'dry-run' else 'created'} --")
        for r in result['created']:
            print(f"  {r['mobile']:<15}  {r['display_name']}")
    if result['errors']:
        print('\n-- ERRORS --')
        for r in result['errors']:
            print(f"  {r['name']:<8}  {r.get('error')}")


def main(argv: list[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--account', default='bispro89')
    ap.add_argument('--base-dir', default='data/company/people')
    ap.add_argument('--apply', action='store_true',
                    help='Actually create contacts. Default is dry-run.')
    ap.add_argument('--log', default='data/company/people/_gcontacts_sync.log',
                    help='Write structured result JSON here.')
    args = ap.parse_args(argv)

    dry = not args.apply
    result = sync(account=args.account, base_dir=args.base_dir, dry_run=dry)
    _print_report(result, 'dry-run' if dry else 'apply')

    log_path = args.log
    _os.makedirs(_os.path.dirname(log_path), exist_ok=True)
    log_path_tagged = log_path.replace('.log',
                                       f"_{'dry' if dry else 'apply'}.json")
    _json.dump(result, open(log_path_tagged, 'w', encoding='utf-8'),
               ensure_ascii=False, indent=2)
    print(f'\nlog → {log_path_tagged}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(_sys.argv[1:]))
