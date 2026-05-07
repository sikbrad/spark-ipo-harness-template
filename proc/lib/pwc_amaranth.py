"""Amaranth ERP helpers for playwright-cli sessions.

Session convention: S('amaranth') for all amaranth-* skills.

Bootstrap once:
    playwright-cli -s=amaranth open https://erp.doflab.com/ --persistent --headed
  Then log in: 회사코드 doflab → ID (ERP_PERSONAL_ID) → PW (ERP_PERSONAL_PW)
  → 출퇴근 체크 popup 취소. Session persists on disk after that.

Auth note:
  All write/read endpoints require `wehago-sign` HMAC headers that the SPA
  bundle attaches automatically. Direct fetch from outside the SPA returns
  601 "허용된 쿠키 인증 URL이 아닙니다". Strategy:
    - Reads:  capture the SPA's own XHRs via s.requests() + s.response_body()
    - Writes: drive the SPA dialogs (they go through the signing pipeline)
    - ACC queries: capture one signed request, reuse headers with different body
"""

from __future__ import annotations

import json as _json
import re as _re
import time as _time
from typing import Optional

from pwc import S

ERP_URL = 'https://erp.doflab.com'


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


def _press_enter(s: S, sel: str) -> None:
    """Dispatch keyboard Enter events on a selector."""
    s.eval(
        f"""() => {{
            const el = document.querySelector({_json.dumps(sel)});
            if (!el) return;
            el.dispatchEvent(new KeyboardEvent('keydown',  {{key:'Enter', code:'Enter', keyCode:13, bubbles:true}}));
            el.dispatchEvent(new KeyboardEvent('keypress', {{key:'Enter', code:'Enter', keyCode:13, bubbles:true}}));
            el.dispatchEvent(new KeyboardEvent('keyup',    {{key:'Enter', code:'Enter', keyCode:13, bubbles:true}}));
        }}"""
    )


def _click_by_text(s: S, text: str, tag: str = '*') -> bool:
    """Click the first element matching tag whose trimmed textContent equals text."""
    return bool(s.eval(
        f"""() => {{
            const t = {_json.dumps(text)};
            const el = [...document.querySelectorAll({_json.dumps(tag)})].find(
                e => (e.textContent || '').trim() === t
            );
            if (el) {{ el.click(); return true; }}
            return false;
        }}"""
    ))


def _filter_requests(s: S, url_substr: str) -> list[dict]:
    """Return all captured requests whose URL contains url_substr."""
    return [r for r in s.requests() if url_substr in r.get('url', '')]


def _parse_request_headers(detail_text: str) -> dict:
    """Parse key: value header lines from request_detail() text dump.

    playwright-cli request detail output includes a 'Request Headers' section.
    We extract all `key: value` lines (case-insensitive key matching).
    """
    headers: dict = {}
    in_section = False
    for line in detail_text.splitlines():
        stripped = line.strip()
        # Detect section start
        if 'request header' in stripped.lower():
            in_section = True
            continue
        # Detect section end (blank line or next section header)
        if in_section:
            if not stripped:
                in_section = False
                continue
            # Lines like "  Authorization: Bearer ..."
            if ':' in stripped:
                key, _, val = stripped.partition(':')
                headers[key.strip()] = val.strip()
    return headers


def _amaranth_latest_auth(s: S, url_substring: str) -> tuple[Optional[dict], Optional[dict]]:
    """Return (headers_dict, sample_body_dict) from the latest captured request
    matching url_substring. Returns (None, None) if not found.

    Headers are parsed from request_detail() text dump. Body is parsed from
    the request payload embedded in the detail text or reconstructed from a
    known response.
    """
    reqs = _filter_requests(s, url_substring)
    if not reqs:
        return None, None
    last = reqs[-1]
    idx = last['index']

    detail = s.request_detail(idx)
    headers = _parse_request_headers(detail)

    # Body is fetched via the separate `request-body <idx>` CLI command — the
    # detail text only mentions it as a hint, not the payload itself.
    body: dict = {}
    try:
        raw_body = s.request_body(idx).strip()
        if raw_body:
            body = _json.loads(raw_body)
    except Exception:
        body = {}

    return headers, body


def _amaranth_post(s: S, url: str, headers: dict, body: dict) -> Optional[dict]:
    """POST a JSON body to an Amaranth endpoint via window.fetch inside the page.

    Uses page cookies + the supplied bearer/sign headers. Returns parsed JSON
    or None on timeout.
    """
    full_url = ERP_URL + url if url.startswith('/') else url
    # Inject async fetch; poll window.__bhResult
    expr = (
        "(() => { window.__bhResult = null;"
        "  fetch(__URL__, {method:'POST', headers:__HDRS__, body:__BODY__})"
        "    .then(r => r.text().then(t => ({status:r.status, body:t})))"
        "    .then(r => { window.__bhResult = r; })"
        "    .catch(e => { window.__bhResult = {err: e.message}; });"
        "  return true; })()"
    ).replace('__URL__', _json.dumps(full_url)) \
     .replace('__HDRS__', _json.dumps(headers)) \
     .replace('__BODY__', _json.dumps(_json.dumps(body, ensure_ascii=False)))
    s.eval(expr)

    deadline = _time.time() + 30
    while _time.time() < deadline:
        out = s.eval('() => window.__bhResult')
        if out:
            if isinstance(out, dict) and out.get('err'):
                return {'_err': out['err']}
            try:
                raw = out.get('body') if isinstance(out, dict) else str(out)
                return _json.loads(raw or '{}')
            except Exception:
                return {'_raw': str(out)}
        _time.sleep(0.2)
    return None


# ---------------------------------------------------------------------------
# Org helpers
# ---------------------------------------------------------------------------

def open_org_dialog(s: S) -> bool:
    """Click the top-nav org-chart icon (btn org). Returns True if found."""
    return bool(s.eval("""
    () => {
        const ico = document.querySelector('span.btn.org');
        if (!ico) return false;
        ico.click();
        return true;
    }
    """))


def search_org(s: S, text: str, wait_seconds: float = 2.5) -> Optional[dict]:
    """Type into the org-dialog search box, press Enter, return parsed result.

    Auto-opens the org dialog if closed. Returns the JSON body of the last
    gw102A02 response.
    """
    is_open = s.eval('() => document.querySelector(\'input[placeholder*="검색어"]\') ? true : false')
    if not is_open:
        open_org_dialog(s)
        _time.sleep(2)

    _set_input_value(s, 'input[placeholder*="검색어"]', '')
    _time.sleep(0.3)
    _set_input_value(s, 'input[placeholder*="검색어"]', text)
    _press_enter(s, 'input[placeholder*="검색어"]')
    _time.sleep(wait_seconds)

    reqs = _filter_requests(s, 'gw102A02')
    if not reqs:
        return None
    last_idx = reqs[-1]['index']
    raw = s.response_body(last_idx)
    try:
        return _json.loads(raw)
    except Exception:
        return {'_raw': raw}


def research_members(s: S) -> dict:
    """Return all 연구소 + 선행기술 members (the dev org), keyed by empName."""
    data = search_org(s, '연구원')
    if not data or 'resultData' not in data:
        return {}
    members = {}
    for u in data['resultData']:
        path = u.get('comOptPath') or ''
        if '연구소' in path or '선행기술' in path:
            members[u['empName']] = {
                'login': u.get('loginId'),
                'team': u.get('comOptName'),
                'pos': u.get('positionName'),
                'duty': u.get('dutyName'),
                'work': u.get('mainWork'),
                'mobile': u.get('mobileTelNum'),
                'email': u.get('emailAddr'),
                'dept_path': path,
            }
    return members


# ---------------------------------------------------------------------------
# Calendar helpers
# ---------------------------------------------------------------------------

def calendar_list_rows(s: S) -> list:
    """Scrape the 일정 list-view table (after switching to 목록 view).

    Returns a list of rows, each a list of cell strings. First row is the header.
    """
    return s.eval("""
    () => {
        const tables = Array.from(document.querySelectorAll('table'));
        const target = tables.find(t => {
            const r = t.getBoundingClientRect();
            return r.width > 800 && t.querySelectorAll('tr').length > 50;
        });
        if (!target) return [];
        const out = [];
        target.querySelectorAll('tr').forEach(tr => {
            const cells = Array.from(tr.querySelectorAll('th, td')).map(td => (td.innerText || '').trim());
            out.push(cells);
        });
        return out;
    }
    """) or []


def calendar_events(s: S) -> list:
    """Return parsed calendar events (with date-carry across rows) for the
    currently displayed month in 목록 view.
    """
    rows = calendar_list_rows(s)
    events = []
    last_date = None
    # Skip header (row 0)
    for row in rows[1:]:
        if len(row) == 7:
            date, t, ctype, title, reg, parts, contact = row
            last_date = date
        elif len(row) == 6:
            t, ctype, title, reg, parts, contact = row
            date = last_date
        else:
            continue
        events.append({
            'date': date, 'time': t, 'type': ctype, 'title': title,
            'registrar': reg, 'participants': parts, 'contact': contact,
        })
    return events


def dev_events(s: S) -> list:
    """Return calendar events that involve a 연구소/선행기술 member.

    Each event is annotated with 'dev_matched' (list of matched dev names).
    """
    members = research_members(s)
    names = set(members.keys())
    out = []
    for ev in calendar_events(s):
        haystack = f"{ev['title']} {ev['registrar']} {ev['participants']}"
        matched = [n for n in names if n in haystack]
        if matched:
            out.append({**ev, 'dev_matched': matched})

    def _key(ev):
        try:
            ymd = ev['date'].split('(')[0].strip()
            y, m, d = ymd.split('.')
            return f"20{y}{m.zfill(2)}{d.zfill(2)}"
        except Exception:
            return ev['date']
    out.sort(key=_key)
    return out


# ---------------------------------------------------------------------------
# Resource booking helpers (회의실/차량)
#
# Endpoints (POST, JSON):
#   /schres/rs121A05  list bookings for startDate..endDate × resList
#   /schres/rs121A06  create booking
#   /schres/rs121A45 / rs121A46  auxiliary daily summaries
# Auth: wehago-sign HMAC inside SPA bundle — direct fetch returns 601.
# Reads go via captured XHRs; writes go through the dialog UI.
#
# resSeq map (compSeq=1000):
#   회의실:  44=대표실, 45=302호, 47=601호(DDA), 48=602호, 63=306호
#   차량:   50=197하1718, 60=225하1481, 64=224허9910
# ---------------------------------------------------------------------------

RES_SEQ = {
    '대표실': '44', '302호': '45', '306호': '63',
    '601호': '47', '601호(DDA)': '47', '602호': '48',
    '197하1718': '50', '225하1481': '60', '224허9910': '64',
}


def resource_bookings(s: S, start_yyyymmdd: str, end_yyyymmdd: Optional[str] = None,
                      res_seqs=None) -> Optional[list]:
    """Return bookings via /schres/rs121A05 — captured from the SPA's own XHRs.

    Caller must have navigated the resource page so the SPA has issued the
    rs121A05 request for the desired date range. Returns the parsed resultList.
    """
    end_yyyymmdd = end_yyyymmdd or start_yyyymmdd
    reqs = _filter_requests(s, 'rs121A05')
    for r in reversed(reqs):
        try:
            idx = r['index']
            # Try to match date range from response body
            resp_raw = s.response_body(idx)
            resp = _json.loads(resp_raw or '{}')
            # rs121A05 response doesn't carry back startDate, so return first match
            return resp.get('resultData', {}).get('resultList', [])
        except Exception:
            continue
    return None


# ---------------------------------------------------------------------------
# Approval helpers (전자결재)
#
# Page codes:
#   UBA7000 = 결재 HOME
#   UBA2020 = 미결문서 (내가 결재해야 할 것)
#   UBA2030 = 기결문서 (내가 이미 처리한 것)
#   UBA2040 = 기결문서(진행)
#   UBA2050 = 기결문서(종결)
#
# Endpoint:
#   POST /eap/eap105A04 — list. SPA fires it on page enter / period change /
#   pagination. Direct fetch fails (cookie-bound auth).
# ---------------------------------------------------------------------------

APPROVAL_PAGES = {
    '결재HOME': 'UBA7000',
    '미결문서': 'UBA2020',
    '기결문서': 'UBA2030',
    '기결문서_진행': 'UBA2040',
    '기결문서_종결': 'UBA2050',
}


def approval_url(box: str = '기결문서') -> str:
    """Return the SPA hash URL for an approval box."""
    code = APPROVAL_PAGES.get(box, box)
    return (
        'https://erp.doflab.com/#/UB/UB/UBA0000'
        f'?specialLnb=Y&moduleCode=UB&menuCode=UBA&pageCode={code}'
    )


def approval_docs(s: S, min_action_dt: Optional[str] = None,
                  max_action_dt: Optional[str] = None) -> list:
    """Parse latest /eap/eap105A04 capture into a clean doc list.

    Caller must have navigated to approval_url(box) and waited for the SPA to
    fire the request. Filters by ACTION_TIME (string compare on
    'YYYY-MM-DD HH:MM:SS').

    Returns list[dict] with: 결재일시, REP_DT, 도착일, 양식, 제목, 문서번호,
    기안자, 직급, 부서, 상태, BIZ, OUT_PROC. Sorted desc by 결재일시.
    """
    reqs = _filter_requests(s, 'eap105A04')
    if not reqs:
        return []
    try:
        raw = s.response_body(reqs[-1]['index'])
        data = _json.loads(raw or '{}')
    except Exception:
        return []
    items = (data.get('resultData') or {}).get('map', {}).get('list', []) or []
    out = []
    for it in items:
        action_time = it.get('ACTION_TIME') or it.get('REP_DT') or ''
        if min_action_dt and action_time < min_action_dt:
            continue
        if max_action_dt and action_time > max_action_dt:
            continue
        out.append({
            '결재일시': action_time,
            'REP_DT': it.get('REP_DT'),
            '도착일': it.get('ARRIVED_DT'),
            '양식': it.get('FORM_NM'),
            '제목': it.get('DOC_TITLE') or it.get('DOC_TITLE_ORIGIN'),
            '문서번호': it.get('DOC_NO'),
            '기안자': it.get('USER_NM'),
            '직급': it.get('GRADE_NM'),
            '부서': it.get('DEPT_NM'),
            '상태': it.get('DOC_STSNM'),
            'BIZ': it.get('BIZ_NAME'),
            'OUT_PROC': it.get('OUT_PROC_NM'),
        })
    out.sort(key=lambda x: x['결재일시'] or '', reverse=True)
    return out


def approval_total_count(s: S) -> Optional[int]:
    """Return totalCount from latest eap105A04 capture, or None."""
    reqs = _filter_requests(s, 'eap105A04')
    if not reqs:
        return None
    try:
        raw = s.response_body(reqs[-1]['index'])
        data = _json.loads(raw or '{}')
        return (data.get('resultData') or {}).get('map', {}).get('totalCount')
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Accounting helpers (ACC3030 거래처계정내역, ACC3020 거래처계정잔액)
#
# Endpoints (POST, JSON):
#   /financial/ACC3030/00a00001  거래처계정내역
#   /financial/ACC3020/00a00001  거래처계정잔액
#
# Auth: SPA bearer flow — direct fetch fails. Strategy: navigate the SPA to
# the page, trigger ONE search via UI, capture the signed headers, then reuse
# those headers with arbitrary code lists / dates.
#
# Bootstrap: call acc303x_bootstrap('ACC3030' or 'ACC3020') first.
# ---------------------------------------------------------------------------


def acc3030_query(s: S, acct_codes: list, fdate: str, fill_dt: str,
                  sub_ty: str = '2', tr_codes=None) -> Optional[dict]:
    """Query 거래처계정내역 for a list of 계정과목코드 over a date range.

    fdate / fill_dt are YYYYMMDD strings. Call acc303x_bootstrap('ACC3030')
    first so at least one signed /financial/ACC3030/00a00001 capture exists.
    Returns the full parsed response (check .get('resultData')) or None.
    """
    headers, sample = _amaranth_latest_auth(s, 'ACC3030/00a00001')
    if not headers:
        return None
    body = dict(sample or {})
    body['vAcctCdStr'] = '|'.join(acct_codes) + '|'
    body['vFdate'] = fdate
    body['vFillDt'] = fill_dt
    body['vSubTy'] = sub_ty
    if tr_codes is not None:
        body['vTrCdStr'] = '|'.join(tr_codes) + ('|' if tr_codes else '')
    return _amaranth_post(s, '/financial/ACC3030/00a00001', headers, body)


def acc3020_query(s: S, acct_codes: list, fill_dt: str, fdate: Optional[str] = None,
                  sub_ty: int = 0, tr_codes=None) -> Optional[dict]:
    """Query 거래처계정잔액 (balance as-of fill_dt).

    fdate defaults to year start of fill_dt. Call acc303x_bootstrap('ACC3020')
    first. Returns the full parsed response or None.

    sub_ty=0 returns aggregated rows (one per 거래처, one acctAm{i+1} column
    per code). sub_ty=2 returned 0 rows in testing — keep at 0.
    """
    headers, sample = _amaranth_latest_auth(s, 'ACC3020/00a00001')
    if not headers:
        return None
    body = dict(sample or {})
    body['vAcctCdStr'] = '|'.join(acct_codes) + '|'
    body['vFillDt'] = fill_dt
    body['vFdate'] = fdate or (fill_dt[:4] + '0101')
    body['vSubTy'] = sub_ty
    body['acctInfo'] = list(acct_codes)
    if tr_codes is not None:
        body['vTrCdStr'] = '|'.join(tr_codes) + ('|' if tr_codes else '')
    return _amaranth_post(s, '/financial/ACC3020/00a00001', headers, body)


def acc303x_bootstrap(s: S, page_code: str, code: str = '1080000') -> int:
    """Navigate to ACC3030 / ACC3020 and trigger ONE search via UI so the
    SPA fires a signed XHR — captured headers can be reused for arbitrary
    multi-code queries via acc3030_query / acc3020_query.

    page_code: 'ACC3030' or 'ACC3020'.
    Returns the count of captured requests matching the endpoint.

    The 조회 button lives in `.OBTConditionPanel_primaryFunctions__SVUW_` —
    its inner BUTTON is laid out at 0×0 (Orbit framework wraps it), so DOM
    `.click()` does nothing. We compute the wrapper's bounding box and
    dispatch a mouse click at its center coordinate. Requires viewport ≥1500
    wide so the panel isn't clipped — we resize as a precaution.
    """
    target = f'{ERP_URL}/#/A/{page_code}/{page_code}'

    # Switch to the ERP tab if not already there
    tabs = s.tab_list()
    erp_tab = next((t for t in tabs if 'erp.doflab.com' in t.get('url', '')), None)
    if erp_tab and not erp_tab.get('current'):
        s.tab_select(erp_tab['index'])

    # Ensure viewport is wide enough — the right-side condition panel gets
    # clipped at narrow widths, hiding the 조회 button.
    s.raw('resize', '1600', '1000')
    _time.sleep(0.5)

    s.goto(target)
    _time.sleep(3)

    # Focus the 계정과목코드도움 input and type seed code
    s.eval(
        f"() => {{"
        f"  const inp = document.querySelectorAll('input[placeholder=\"계정과목코드도움\"]')[0];"
        f"  if (inp) inp.focus();"
        f"}}"
    )
    _time.sleep(0.2)
    s.type(code)
    _time.sleep(0.3)
    s.press('Enter')
    _time.sleep(1.0)

    # Locate the 조회 button. The OBTConditionPanel itself has zero-size
    # layout; the actual rendered button shows up as an `OBTButton_typedefault`
    # wrapper near the top-right (x>1400) with tooltip "조회". The 4 typeicon
    # wrappers at y≈110 are auxiliary toolbar actions; we want the
    # typedefault one at y≈180.
    bbox = s.eval(r"""
    () => {
        const cands = Array.from(document.querySelectorAll(
            '[class*="OBTButton_typedefault"] .OBTButton_wrapper__1_tA2'
        ));
        let best = null;
        for (const el of cands) {
            const r = el.getBoundingClientRect();
            if (r.width <= 0 || r.height <= 0) continue;
            if (r.x < 1000) continue;  // skip 계정등록 etc on the form left
            // Prefer the one with tooltip "조회"
            const tip = el.closest('[class*="OBTTooltip_root"]');
            const tipText = tip?.querySelector('.OBTTooltip_contents__2UdOU')?.innerText || '';
            const score = (tipText === '조회') ? 100 : (r.y > 150 ? 50 : 0);
            if (!best || score > best.score) {
                best = {x: r.x + r.width/2, y: r.y + r.height/2, score, tipText};
            }
        }
        return best;
    }
    """)
    if bbox:
        s.raw('mousemove', str(int(bbox['x'])), str(int(bbox['y'])))
        _time.sleep(0.1)
        s.raw('mousedown')
        _time.sleep(0.05)
        s.raw('mouseup')
    else:
        # Fallback to text-based click (legacy)
        _click_by_text(s, '조회', tag='button')
    _time.sleep(2.5)

    return len(_filter_requests(s, f'{page_code}/00a00001'))



__all__ = [
    'ERP_URL',
    # Private helpers exposed for advanced use
    '_set_input_value', '_press_enter', '_click_by_text',
    '_filter_requests', '_parse_request_headers',
    '_amaranth_latest_auth', '_amaranth_post',
    # Org
    'open_org_dialog', 'search_org', 'research_members',
    # Calendar
    'calendar_list_rows', 'calendar_events', 'dev_events',
    # Resource
    'RES_SEQ', 'resource_bookings',
    # Approval
    'APPROVAL_PAGES', 'approval_url', 'approval_docs', 'approval_total_count',
    # Accounting
    'acc3030_query', 'acc3020_query', 'acc303x_bootstrap',
]
