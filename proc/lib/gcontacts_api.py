"""Google People API helper — list / search / get / create contacts.

Read + create only. Update and delete are intentionally NOT exposed (skill
policy — avoid destructive mutations on the user's address book).

Built on `proc/lib/google_auth.GoogleClient`. Pure functions: caller passes the
auth wrapper, helpers return normalized dicts.

Usage:
    from google_auth import GoogleClient
    from gcontacts_api import list_contacts, search_contacts, create_contact, save_json

    g = GoogleClient('bispro89')
    people = list_contacts(g, sort='last_modified_desc', limit=200)
    save_json(people, 'output/gcontacts-bispro89-all.json')

    hits = search_contacts(g, '김채린')
    new = create_contact(g, given='채린', family='김',
                         phones=[('010-3117-9571', 'mobile')],
                         org=('고려대학교 스타트업연구원', '연구원'))

CLI:
    python proc/lib/gcontacts_api.py list   --account bispro89 --limit 200 --out output/gcontacts-bispro89.json
    python proc/lib/gcontacts_api.py search --account bispro89 --q '김채린'
    python proc/lib/gcontacts_api.py get    --account bispro89 --id people/c4933657522678351938
    python proc/lib/gcontacts_api.py create --account bispro89 \\
        --name '김채린' --phone '010-3117-9571' --org '고려대학교 스타트업연구원' --title 연구원

People API field mask reference:
  names, nicknames, phoneNumbers, emailAddresses, organizations, addresses,
  biographies, birthdays, urls, memberships, userDefined, metadata, photos
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable, Optional

# Allow `python proc/lib/gcontacts_api.py ...` when run directly.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from google_auth import GoogleClient  # noqa: E402

DEFAULT_FIELDS = 'names,phoneNumbers,emailAddresses,organizations,addresses,biographies,urls,memberships,metadata'
COMPACT_FIELDS = 'names,phoneNumbers,emailAddresses,organizations'

_SORT_MAP = {
    'last_modified_desc': 'LAST_MODIFIED_DESCENDING',
    'last_modified_asc': 'LAST_MODIFIED_ASCENDING',
    'first_name_asc': 'FIRST_NAME_ASCENDING',
    'last_name_asc': 'LAST_NAME_ASCENDING',
}


# ---- Normalize


def parse_person(p: dict) -> dict:
    """Normalize a People `person` resource into a flat dict."""
    names = p.get('names') or []
    primary_name = next((n for n in names if n.get('metadata', {}).get('primary')), names[0] if names else {})
    return {
        'resource_name': p.get('resourceName'),
        'etag': p.get('etag'),
        'display_name': primary_name.get('displayName'),
        'family_name': primary_name.get('familyName'),
        'given_name': primary_name.get('givenName'),
        'phones': [{'value': x.get('value'), 'canonical': x.get('canonicalForm'), 'type': x.get('type')} for x in p.get('phoneNumbers', []) or []],
        'emails': [{'value': x.get('value'), 'type': x.get('type')} for x in p.get('emailAddresses', []) or []],
        'organizations': [{'name': x.get('name'), 'title': x.get('title'), 'type': x.get('type')} for x in p.get('organizations', []) or []],
        'addresses': [{'formatted': x.get('formattedValue'), 'type': x.get('type')} for x in p.get('addresses', []) or []],
        'urls': [{'value': x.get('value'), 'type': x.get('type')} for x in p.get('urls', []) or []],
        'biographies': [x.get('value') for x in p.get('biographies', []) or []],
        'groups': [x.get('contactGroupMembership', {}).get('contactGroupResourceName') for x in p.get('memberships', []) or [] if x.get('contactGroupMembership')],
        'updated': (p.get('metadata') or {}).get('sources', [{}])[0].get('updateTime'),
        '_raw': p if False else None,
    }


def _strip_none(d: dict) -> dict:
    return {k: v for k, v in d.items() if v is not None}


# ---- Read


def list_contacts(
    g: GoogleClient,
    fields: str = DEFAULT_FIELDS,
    sort: str = 'last_modified_desc',
    limit: int = 1000,
    page_size: int = 100,
    parsed: bool = True,
) -> list[dict]:
    """All connections of the authenticated user. Auto-paginates."""
    svc = g.service('people', 'v1')
    out: list[dict] = []
    token: Optional[str] = None
    while True:
        resp = svc.people().connections().list(
            resourceName='people/me',
            personFields=fields,
            pageSize=min(page_size, max(1, limit - len(out))),
            pageToken=token,
            sortOrder=_SORT_MAP.get(sort, sort),
        ).execute()
        out.extend(resp.get('connections', []) or [])
        token = resp.get('nextPageToken')
        if not token or len(out) >= limit:
            break
    out = out[:limit]
    return [parse_person(p) for p in out] if parsed else out


def search_contacts(
    g: GoogleClient,
    query: str,
    fields: str = DEFAULT_FIELDS,
    parsed: bool = True,
) -> list[dict]:
    """Server-side substring search across name/email/phone/org/etc.

    People API search is eventually-consistent — newly-added contacts may take
    a few seconds to be indexed. Use list+filter if you need fresh data.
    """
    svc = g.service('people', 'v1')
    # Warm-up call (required by People API to populate the cache).
    svc.people().searchContacts(query='', readMask=fields, pageSize=1).execute()
    resp = svc.people().searchContacts(query=query, readMask=fields).execute()
    results = [r['person'] for r in resp.get('results', []) or []]
    return [parse_person(p) for p in results] if parsed else results


def get_contact(g: GoogleClient, resource_name: str, fields: str = DEFAULT_FIELDS, parsed: bool = True) -> dict:
    svc = g.service('people', 'v1')
    person = svc.people().get(resourceName=resource_name, personFields=fields).execute()
    return parse_person(person) if parsed else person


def get_contacts_batch(g: GoogleClient, resource_names: list[str], fields: str = DEFAULT_FIELDS, parsed: bool = True) -> list[dict]:
    """Up to 200 resourceNames per call."""
    svc = g.service('people', 'v1')
    out: list[dict] = []
    for i in range(0, len(resource_names), 200):
        batch = resource_names[i:i + 200]
        resp = svc.people().getBatchGet(resourceNames=batch, personFields=fields).execute()
        for r in resp.get('responses', []) or []:
            if 'person' in r:
                out.append(parse_person(r['person']) if parsed else r['person'])
    return out


# ---- Write


def _build_body(
    given: Optional[str] = None,
    family: Optional[str] = None,
    display: Optional[str] = None,
    phones: Optional[list[tuple[str, str]]] = None,    # [(value, type)]
    emails: Optional[list[tuple[str, str]]] = None,
    org: Optional[tuple[str, str]] = None,             # (name, title)
    addresses: Optional[list[tuple[str, str]]] = None, # [(formatted, type)]
    biography: Optional[str] = None,
    urls: Optional[list[tuple[str, str]]] = None,
) -> dict:
    body: dict[str, Any] = {}
    name_part = _strip_none({'givenName': given, 'familyName': family, 'displayName': display, 'unstructuredName': display if (display and not given and not family) else None})
    if name_part:
        body['names'] = [name_part]
    if phones:
        body['phoneNumbers'] = [_strip_none({'value': v, 'type': t}) for v, t in phones]
    if emails:
        body['emailAddresses'] = [_strip_none({'value': v, 'type': t}) for v, t in emails]
    if org:
        name, title = org
        body['organizations'] = [_strip_none({'name': name, 'title': title, 'type': 'work'})]
    if addresses:
        body['addresses'] = [_strip_none({'formattedValue': v, 'type': t}) for v, t in addresses]
    if biography:
        body['biographies'] = [{'value': biography, 'contentType': 'TEXT_PLAIN'}]
    if urls:
        body['urls'] = [_strip_none({'value': v, 'type': t}) for v, t in urls]
    return body


def create_contact(
    g: GoogleClient,
    given: Optional[str] = None,
    family: Optional[str] = None,
    display: Optional[str] = None,
    phones: Optional[list[tuple[str, str]]] = None,
    emails: Optional[list[tuple[str, str]]] = None,
    org: Optional[tuple[str, str]] = None,
    addresses: Optional[list[tuple[str, str]]] = None,
    biography: Optional[str] = None,
    urls: Optional[list[tuple[str, str]]] = None,
    fields: str = DEFAULT_FIELDS,
) -> dict:
    """Create a new contact. Returns the normalized created person."""
    body = _build_body(given, family, display, phones, emails, org, addresses, biography, urls)
    if not body:
        raise ValueError('create_contact: no fields provided')
    svc = g.service('people', 'v1')
    resp = svc.people().createContact(body=body, personFields=fields).execute()
    return parse_person(resp)


# Note: update_contact and delete_contact are intentionally not implemented.
# Skill policy is read + create only — mutations to existing contacts must be
# done manually in the Google Contacts UI to avoid destructive automation.


# ---- Helpers


def save_json(data: Any, path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str))
    return p


def _kv_pairs(items: Optional[list[str]], default_type: str) -> Optional[list[tuple[str, str]]]:
    """Parse CLI --phone/--email forms like 'value' or 'value:type'."""
    if not items:
        return None
    out = []
    for raw in items:
        if ':' in raw:
            v, t = raw.split(':', 1)
            out.append((v.strip(), t.strip() or default_type))
        else:
            out.append((raw.strip(), default_type))
    return out


def _split_name(full: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Best-effort split. Returns (given, family, display).

    For Korean names (no whitespace): family = first char, given = rest.
    For Latin "First Last": family = last token, given = the rest.
    """
    name = full.strip()
    if not name:
        return None, None, None
    if ' ' in name:
        first, _, last = name.rpartition(' ')
        return first, last, name
    # No space — assume Korean style: family = first char.
    if len(name) >= 2 and all(0xAC00 <= ord(c) <= 0xD7A3 for c in name):
        return name[1:], name[:1], name
    return name, None, name


# ---- CLI


def _cmd_list(args) -> int:
    g = GoogleClient(args.account)
    people = list_contacts(g, sort=args.sort, limit=args.limit)
    if args.out:
        save_json(people, args.out)
        print(f'Wrote {len(people)} contacts → {args.out}')
    else:
        for p in people[:50]:
            phones = ', '.join(x['value'] for x in p['phones'])
            print(f'  {p["display_name"]:<20} | {phones:<24} | {", ".join(o["name"] or "" for o in p["organizations"])}')
        if len(people) > 50:
            print(f'  ... +{len(people) - 50} more (use --out to dump all)')
    return 0


def _cmd_search(args) -> int:
    g = GoogleClient(args.account)
    hits = search_contacts(g, args.q)
    if args.out:
        save_json(hits, args.out)
        print(f'Wrote {len(hits)} hits → {args.out}')
    else:
        if not hits:
            print('(no matches)')
        for p in hits:
            phones = ', '.join(x['value'] for x in p['phones'])
            print(f'  {p["resource_name"]}  {p["display_name"]:<20} | {phones}')
    return 0


def _cmd_get(args) -> int:
    g = GoogleClient(args.account)
    p = get_contact(g, args.id)
    print(json.dumps(p, ensure_ascii=False, indent=2, default=str))
    return 0


def _cmd_create(args) -> int:
    g = GoogleClient(args.account)
    given, family, display = _split_name(args.name) if args.name else (args.given, args.family, args.display)
    org = (args.org, args.title) if (args.org or args.title) else None
    p = create_contact(
        g,
        given=given, family=family, display=display,
        phones=_kv_pairs(args.phone, 'mobile'),
        emails=_kv_pairs(args.email, 'home'),
        org=org,
        biography=args.note,
    )
    print(f'Created: {p["resource_name"]}  {p["display_name"]}')
    print(json.dumps(p, ensure_ascii=False, indent=2, default=str))
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog='gcontacts_api')
    sub = parser.add_subparsers(dest='cmd', required=True)
    common = lambda sp: sp.add_argument('--account', required=True, choices=['bispro89', 'sikbrad'])

    sp = sub.add_parser('list', help='Dump connections of authenticated user'); common(sp)
    sp.add_argument('--sort', default='last_modified_desc',
                    choices=list(_SORT_MAP) + list(_SORT_MAP.values()))
    sp.add_argument('--limit', type=int, default=2000)
    sp.add_argument('--out', help='Path to write JSON; if omitted, prints summary')

    sp = sub.add_parser('search', help='Server-side substring search'); common(sp)
    sp.add_argument('--q', required=True)
    sp.add_argument('--out')

    sp = sub.add_parser('get', help='Get a single contact'); common(sp)
    sp.add_argument('--id', required=True, help='resourceName, e.g. people/c123...')

    sp = sub.add_parser('create', help='Create a new contact'); common(sp)
    sp.add_argument('--name', help='Full name; split heuristically. Use --given/--family for explicit split')
    sp.add_argument('--given'); sp.add_argument('--family'); sp.add_argument('--display')
    sp.add_argument('--phone', action='append', help='value or value:type (mobile/work/home). Repeat for multiple')
    sp.add_argument('--email', action='append', help='value or value:type')
    sp.add_argument('--org'); sp.add_argument('--title')
    sp.add_argument('--note', help='Biography / memo')

    args = parser.parse_args(argv[1:])
    return {
        'list': _cmd_list,
        'search': _cmd_search,
        'get': _cmd_get,
        'create': _cmd_create,
    }[args.cmd](args)


if __name__ == '__main__':
    sys.exit(main(sys.argv))
