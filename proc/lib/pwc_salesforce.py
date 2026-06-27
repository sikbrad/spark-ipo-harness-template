"""Salesforce Lightning helpers for playwright-cli sessions.

Session convention: S('salesforce') for the salesforce-record skill.

Bootstrap once (first-time SSO):
    playwright-cli -s=salesforce open https://d7f000002bofzuay.lightning.force.com/ --persistent --headed
  Log in with your Salesforce credentials. If TOTP/MFA appears, complete it
  manually — it is not automatable. Session persists on disk after that.

Auth note:
  Lightning Aura RPC endpoints are cookie+CSRF-bound. Direct fetch from
  outside the SPA returns 403. Strategy:
    - Navigate to the target record URL so the SPA fires its own Aura calls.
    - Capture responses via s.requests() + s.response_body().
    - Aura responses have a `while(1);` XSSI prefix — strip before JSON parse.
"""

from __future__ import annotations

import base64 as _b64
import json as _json
import os as _os
import re as _re
import time as _time
from typing import Optional

from pwc import S

INSTANCE = 'd7f000002bofzuay'  # this org's Lightning instance ID
LOGIN_URL = f'https://{INSTANCE}.lightning.force.com'

# Aura XSSI prefix — all Aura RPC responses begin with this guard string.
_AURA_PREFIX = 'while(1);'


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _set_input_value(s: S, sel: str, val: str) -> None:
    """Set an input's value via React-compatible native setter dispatch."""
    s.eval(
        f"""() => {{
            const el = document.querySelector({_json.dumps(sel)});
            if (!el) return;
            const nativeSet = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
            nativeSet.call(el, {_json.dumps(val)});
            el.dispatchEvent(new Event('input', {{ bubbles: true }}));
            el.dispatchEvent(new Event('change', {{ bubbles: true }}));
        }}"""
    )


def _filter_requests(s: S, url_substr: str) -> list[dict]:
    """Return all captured requests whose URL contains url_substr."""
    return [r for r in s.requests() if url_substr in r.get('url', '')]


def _parse_aura_body(raw: str) -> Optional[dict]:
    """Strip the `while(1);` XSSI prefix and JSON-parse the remainder.

    Returns parsed dict or None on failure.
    """
    if not raw:
        return None
    body = raw.strip()
    if body.startswith(_AURA_PREFIX):
        body = body[len(_AURA_PREFIX):]
    try:
        return _json.loads(body)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def login(s: S, login_url: str = LOGIN_URL,
          sf_id: Optional[str] = None, sf_pw: Optional[str] = None,
          wait_seconds: float = 7) -> None:
    """Navigate to the Salesforce login URL, fill credentials, click #Login.

    sf_id/sf_pw default to env SF_ACCOUNT_ID / SF_ACCOUNT_PW.
    TOTP/MFA screens are NOT handled — if the org enforces them, ask the user
    to complete the prompt manually and retry.
    """
    sf_id = sf_id or _os.environ.get('SF_ACCOUNT_ID')
    sf_pw = sf_pw or _os.environ.get('SF_ACCOUNT_PW')
    if not (sf_id and sf_pw):
        raise RuntimeError('SF_ACCOUNT_ID / SF_ACCOUNT_PW not set')

    s.goto(login_url)
    _time.sleep(3)
    s.eval(
        f"""() => {{
            const u = document.getElementById('username');
            const p = document.getElementById('password');
            if (!u || !p) return false;
            u.value = {_json.dumps(sf_id)};
            p.value = {_json.dumps(sf_pw)};
            u.dispatchEvent(new Event('input', {{bubbles: true}}));
            p.dispatchEvent(new Event('input', {{bubbles: true}}));
            const b = document.getElementById('Login');
            if (b) b.click();
            return true;
        }}"""
    )
    _time.sleep(wait_seconds)


def aura_records(s: S, api_name: Optional[str] = None) -> list[dict]:
    """Walk every captured /aura response and return a deduped flat list of records.

    Each item: {id, apiName, fields: {<fname>: <value-or-ref>, ...}}.
    Reference fields (e.g. Product2 inside OpportunityLineItem) become
    {'__ref__': apiName, 'id': ..., 'name': ...} in the parent fields, AND the
    referenced record is also emitted as its own top-level entry — so you can
    look it up by id even when the SPA did not cache it separately.

    Aura responses begin with `while(1);` — stripped automatically before parse.
    """
    seen: set = set()
    out: list[dict] = []

    def _flatten(rec: dict, obj_api: str, rid: str) -> None:
        if (rid, obj_api) in seen or not isinstance(rec, dict):
            return
        seen.add((rid, obj_api))
        fields: dict = {}
        for fname, fval in (rec.get('fields') or {}).items():
            if isinstance(fval, dict):
                v = fval.get('value')
                if isinstance(v, dict) and 'apiName' in v:
                    inner = v.get('fields') or {}
                    inner_id = (inner.get('Id') or {}).get('value')
                    fields[fname] = {
                        '__ref__': v.get('apiName'),
                        'id': inner_id,
                        'name': (inner.get('Name') or {}).get('value'),
                    }
                    # Surface the nested record itself as a top-level entry
                    if inner_id:
                        _flatten(v, v.get('apiName'), inner_id)
                else:
                    fields[fname] = v
            else:
                fields[fname] = fval
        if api_name is None or obj_api == api_name:
            out.append({'id': rid, 'apiName': obj_api, 'fields': fields})

    for r in _filter_requests(s, '/aura'):
        idx = r.get('index')
        if idx is None:
            continue
        try:
            raw = s.response_body(idx)
        except Exception:
            continue
        data = _parse_aura_body(raw)
        if not data:
            continue
        gvps = (data.get('context') or {}).get('globalValueProviders') or []
        for gvp in gvps:
            if gvp.get('type') != '$Record':
                continue
            records = (gvp.get('values') or {}).get('records') or {}
            for rid, wrapper in records.items():
                if not isinstance(wrapper, dict):
                    continue
                for obj_api, obj_inner in wrapper.items():
                    if not isinstance(obj_inner, dict):
                        continue
                    _flatten(obj_inner.get('record'), obj_api, rid)

    return out


def get_record_uis(s: S, record_id: Optional[str] = None) -> dict:
    """Records returned by aura.RecordUi.getRecordUis, keyed by id.

    The canonical "load record header" call for Lightning detail pages.
    Returns dict of {recordId: record_dict}. Caller pulls fields via
    `rec['fields'][fname]['value']` (or 'displayValue').

    Aura responses begin with `while(1);` — stripped automatically before parse.
    """
    out: dict = {}
    for r in _filter_requests(s, 'aura.RecordUi.getRecordUis'):
        idx = r.get('index')
        if idx is None:
            continue
        try:
            raw = s.response_body(idx)
        except Exception:
            continue
        data = _parse_aura_body(raw)
        if not data:
            continue
        for action in data.get('actions', []):
            rv = action.get('returnValue') or {}
            for rid, rec in (rv.get('records') or {}).items():
                if record_id and rid != record_id:
                    continue
                out[rid] = rec
    return out


def line_items(s: S, parent_id: str,
               parent_field: str = 'OpportunityId') -> list[dict]:
    """Line-item records (OpportunityLineItem / QuoteLineItem) for a parent.

    Walks the $Record cache for any record whose `parent_field` matches
    parent_id, attaches the Product2 record (looked up by id) when present,
    and returns clean dicts.

    parent_field='QuoteId' for QuoteLineItem; 'OpportunityId' (default) for
    OpportunityLineItem.

    Returns list of:
        {id, apiName, name, quantity, unitPrice, description,
         factory, currency, parentId,
         product: {id, name, code, currency} | None}
    """
    all_records = aura_records(s)
    products_by_id = {r['id']: r for r in all_records if r['apiName'] == 'Product2'}
    out: list[dict] = []
    for rec in all_records:
        f = rec['fields']
        parent_v = f.get(parent_field)
        match = parent_v == parent_id or (
            isinstance(parent_v, dict) and parent_v.get('id') == parent_id
        )
        if not match:
            continue
        p2_ref = f.get('Product2')
        prod = None
        if isinstance(p2_ref, dict) and p2_ref.get('id') in products_by_id:
            pf = products_by_id[p2_ref['id']]['fields']
            prod = {
                'id': pf.get('Id'),
                'name': pf.get('Name'),
                'code': pf.get('ProductCode'),
                'currency': pf.get('CurrencyIsoCode'),
            }
        out.append({
            'id': rec['id'],
            'apiName': rec['apiName'],
            'name': f.get('Name'),
            'quantity': f.get('Quantity'),
            'unitPrice': f.get('UnitPrice'),
            'description': f.get('Description'),
            'factory': f.get('Factory__c'),
            'currency': f.get('CurrencyIsoCode'),
            'parentId': parent_v if not isinstance(parent_v, dict) else parent_v.get('id'),
            'product': prod,
        })
    return out


def search_url(instance: str, term: str, scope: str = 'TOP_RESULTS') -> str:
    """Build a Lightning global-search URL that lands on the search results page.

    `instance` is the my-domain prefix (e.g. 'd7f000002bofzuay' for
    d7f000002bofzuay.lightning.force.com). Faster and more reliable than
    typing into the search box (which is in shadow DOM).
    """
    payload = {
        'componentDef': 'forceSearch:searchPageDesktop',
        'attributes': {
            'term': term,
            'scopeMap': {'type': scope},
            'context': {'FILTERS': {}, 'searchSource': 'FULL_SEARCH'},
        },
        'state': {},
    }
    b = _b64.urlsafe_b64encode(_json.dumps(payload).encode()).decode().rstrip('=')
    return f'https://{instance}.lightning.force.com/one/one.app#{b}'


__all__ = [
    'INSTANCE',
    'LOGIN_URL',
    # Private helpers exposed for advanced use
    '_set_input_value', '_filter_requests', '_parse_aura_body',
    # Public
    'login',
    'aura_records',
    'get_record_uis',
    'line_items',
    'search_url',
]
