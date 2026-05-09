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

def calendar_bootstrap(s: S, wait: float = 5.0,
                       force_refresh: bool = False) -> int:
    """Ensure at least one signed `/schres/sc111A03` capture exists for reuse.

    Strategy:
      1. If any sc111A03 already captured AND not force_refresh, return immediately.
      2. Else navigate to UEA0000 and wait `wait` seconds.
      3. If still no capture, reload + wait again (handles "already on URL, SPA
         skips re-fire" case).

    Returns the final count of captured sc111A03 requests. Use before
    `calendar_query()` — the helper reuses captured headers/body via
    `_amaranth_latest_auth` + `_amaranth_post`.
    """
    if not force_refresh and len(_filter_requests(s, 'sc111A03')) > 0:
        return len(_filter_requests(s, 'sc111A03'))

    target = (
        f'{ERP_URL}/#/UE/UEA/UEA0000'
        '?specialLnb=Y&moduleCode=UE&menuCode=UEA&pageCode=UEA0000'
    )
    tabs = s.tab_list()
    erp_tab = next((t for t in tabs if 'erp.doflab.com' in t.get('url', '')), None)
    if erp_tab and not erp_tab.get('current'):
        s.tab_select(erp_tab['index'])
    s.goto(target)
    _time.sleep(wait)
    n = len(_filter_requests(s, 'sc111A03'))
    if n == 0:
        # Same-URL navigations sometimes don't re-fire XHRs — force reload.
        s.reload()
        _time.sleep(wait)
        n = len(_filter_requests(s, 'sc111A03'))
    return n


def calendar_query(s: S, start_yyyymmdd: str, end_yyyymmdd: str,
                   my_only: bool = False) -> Optional[dict]:
    """Query calendar events via /schres/sc111A03 (signed POST replay).

    `start_yyyymmdd` / `end_yyyymmdd` are YYYYMMDD. The captured calList
    (subscribed calendars) is reused; only the date range (and `mySchYn` if
    `my_only`) is overridden. Call calendar_bootstrap(s) first.

    Returns the full parsed JSON response (check .get('resultData')) or None.
    """
    headers, sample = _amaranth_latest_auth(s, 'sc111A03')
    if not headers:
        return None
    body = dict(sample or {})
    body['startDate'] = start_yyyymmdd
    body['endDate'] = end_yyyymmdd
    if my_only:
        body['mySchYn'] = 'Y'
    return _amaranth_post(s, '/schres/sc111A03', headers, body)


def parse_calendar(data: dict) -> list:
    """Normalize a sc111A03 response into a list of event dicts (sorted asc).

    Output shape is a strict superset of `calendar_events()` — the same
    {date,time,type,title,registrar,participants,contact} keys are present
    so callers can swap drop-in. Extra fields:
      sch_seq, mcal_seq, allday, start_dt, end_dt, gbn_code.
    """
    items = ((data or {}).get('resultData') or {}).get('resultList') or []
    out = []
    for it in items:
        if it.get('delYn') == 'Y':
            continue
        sd = it.get('startDate') or ''
        ed = it.get('endDate') or ''
        date = ''
        if len(sd) >= 8:
            date = f'{sd[2:4]}.{sd[4:6]}.{sd[6:8]}'
        time_s = ''
        if it.get('alldayYn') != 'Y' and len(sd) >= 12 and len(ed) >= 12:
            time_s = f'{sd[8:10]}:{sd[10:12]}~{ed[8:10]}:{ed[10:12]}'
        out.append({
            'date': date,
            'time': time_s,
            'type': it.get('calTitle') or '',
            'title': it.get('schTitle') or '',
            'registrar': it.get('createName') or '',
            'participants': it.get('partName') or '',
            'contact': '',
            # extras (API only)
            'sch_seq': it.get('schSeq'),
            'mcal_seq': it.get('mcalSeq'),
            'allday': it.get('alldayYn') == 'Y',
            'start_dt': sd,
            'end_dt': ed,
            'gbn_code': it.get('gbnCode'),
        })
    out.sort(key=lambda e: e.get('start_dt') or '')
    return out


def dev_events_api(s: S, start_yyyymmdd: str, end_yyyymmdd: str) -> list:
    """API version of dev_events(): query calendar + filter to 연구소/선행기술 names.

    Each match is annotated with `dev_matched: [name, ...]`. Sorted by start_dt.
    Requires both calendar_bootstrap(s) and that org search has been triggered
    once (research_members uses gw102A02 capture).
    """
    members = research_members(s)
    names = set(members.keys())
    data = calendar_query(s, start_yyyymmdd, end_yyyymmdd)
    if not data:
        return []
    out = []
    for ev in parse_calendar(data):
        haystack = f"{ev['title']} {ev['registrar']} {ev['participants']}"
        matched = [n for n in names if n in haystack]
        if matched:
            out.append({**ev, 'dev_matched': matched})
    return out


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
# Leave request submission (연차휴가신청서 상신)
#
# Submitting a leave goes through 4 stages — no direct API path because every
# write goes through the SPA's wehago-sign signed XHR pipeline:
#
#   1. UBA6000 (결재작성) — click the 연차휴가신청서 form card
#   2. HPD0110 step 1 — fill date + reason, click 연차 sub-type, click 신청완료
#   3. HPD0110 step 2 — fill 제목, click 결재상신 (this opens a NEW browser tab)
#   4. /#/popup tab — click 상신 (the actual approval-line submission)
#
# Gotchas captured from validation run on 2026-05-08:
#   - OBT buttons (.OBTButton_root) ignore .click() — must dispatch
#     mousedown/mouseup/click on the inner <button>, OR use playwright-cli's
#     native `click <ref>` against a snapshot ref.
#   - OBT date pickers (.OBTDatePickerRebuild_inputYMD__PtxMy) are
#     React-controlled — synthetic value setter is ignored. Use focus + select
#     + keyboard type "YYYY-MM-DD" + Tab. The wrapper is a range picker, so
#     setting start auto-syncs end.
#   - Clicking the 연차 sub-type button is required even when 연차휴가신청서
#     was already selected — without it the time fields stay invalid and
#     submit fails with toast "잔여시간 정보가 없습니다".
#   - Weekends/holidays return 잔여시간 0 and reject submission.
#   - The popup tab's 상신 button is a <div>, not a <button>.
# ---------------------------------------------------------------------------


def _dispatch_mouse_click(s: S, find_expr: str) -> bool:
    """Dispatch mousedown/mouseup/click on an element matched by `find_expr`.

    `find_expr` is a JS expression returning the element (or null). Used to
    bypass OBT button click interception. Returns True if click fired.
    """
    return bool(s.eval(
        f"""() => {{
            const el = ({find_expr});
            if (!el) return false;
            const r = el.getBoundingClientRect();
            const cx = r.x + r.width / 2;
            const cy = r.y + r.height / 2;
            for (const t of ['mousedown', 'mouseup', 'click']) {{
                el.dispatchEvent(new MouseEvent(t, {{
                    bubbles: true, cancelable: true, view: window,
                    clientX: cx, clientY: cy, button: 0, buttons: 1
                }}));
            }}
            return true;
        }}"""
    ))


def _click_obt_button(s: S, label: str) -> bool:
    """Click an OBT button by its text label via mouse-event dispatch.

    Targets the inner <button> inside `.OBTButton_root` so the framework's
    click handler fires correctly.
    """
    return _dispatch_mouse_click(
        s,
        f"""(() => {{
            const cands = Array.from(document.querySelectorAll('button'));
            return cands.find(b => (b.innerText || '').trim() === {_json.dumps(label)}) || null;
        }})()"""
    )


def submit_leave(s: S, leave_date: str, reason: str = '연차',
                 title: Optional[str] = None, end_date: Optional[str] = None,
                 sub_type: str = '연차', wait: float = 4.0) -> Optional[dict]:
    """Submit a 연차휴가신청서 end-to-end and return the resulting doc info.

    Args:
        s: S('amaranth') session (must be bootstrapped/logged in).
        leave_date: 'YYYY-MM-DD'. Must be a 평일 (weekend rejected with
            "잔여시간 정보가 없습니다" toast).
        reason: 사유 text (HPD0110 step 1).
        title: 제목 (HPD0110 step 2). Defaults to reason.
        end_date: 'YYYY-MM-DD'. Defaults to leave_date (single-day leave).
        sub_type: '연차' / '오전반차' / '오후반차' / '반반차' / '대체휴가(반반차)'.
            The button is required to activate hour calculation.
        wait: per-step delay seconds (raise if SPA is slow).

    Returns:
        dict { '문서번호': 'DOF-...', '제목': ..., '결재일시': ..., '상태': ... }
        of the just-submitted doc (parsed from /eap/eap105A04 capture in
        기결문서함). None if verification fails.

    Raises:
        RuntimeError on any required UI step that doesn't progress.
    """
    title = title or reason
    end_date = end_date or leave_date

    # Step 1 — 결재작성 → 연차휴가신청서 카드 클릭
    s.goto(approval_url('결재HOME').replace('UBA7000', 'UBA6000'))
    _time.sleep(wait)
    fired = _dispatch_mouse_click(
        s,
        """(() => {
            const els = Array.from(document.querySelectorAll('div, span, p'));
            return els.find(e => (e.innerText || '').trim() === '연차휴가신청서'
                && e.getBoundingClientRect().width > 0) || null;
        })()"""
    )
    if not fired:
        raise RuntimeError('연차휴가신청서 카드를 찾지 못함 (UBA6000)')
    _time.sleep(wait)

    # Step 2 — sub-type 클릭 (시간 계산 활성화)
    if not _click_obt_button(s, sub_type):
        raise RuntimeError(f'{sub_type} 버튼을 찾지 못함 (HPD0110 step 1)')
    _time.sleep(1.0)

    # 시작일 focus + select + type → Tab (range picker 자동 동기화)
    s.eval("""() => {
        const inputs = Array.from(document.querySelectorAll(
            'input.OBTDatePickerRebuild_inputYMD__PtxMy'
        )).filter(el => el.getBoundingClientRect().width > 0);
        if (inputs[0]) { inputs[0].focus(); inputs[0].select(); }
    }""")
    _time.sleep(0.3)
    s.type(leave_date)
    s.press('Tab')
    _time.sleep(0.5)

    # 종료일이 다르면 종료 input에 별도 세팅
    if end_date != leave_date:
        s.eval("""() => {
            const inputs = Array.from(document.querySelectorAll(
                'input.OBTDatePickerRebuild_inputYMD__PtxMy'
            )).filter(el => el.getBoundingClientRect().width > 0);
            if (inputs[1]) { inputs[1].focus(); inputs[1].select(); }
        }""")
        _time.sleep(0.3)
        s.type(end_date)
        s.press('Tab')
        _time.sleep(0.5)

    # 사유 input focus + type (마지막 wide input)
    s.eval("""() => {
        const inp = Array.from(document.querySelectorAll('input')).find(el => {
            const r = el.getBoundingClientRect();
            return r.x > 700 && r.x < 800 && r.y > 580 && r.y < 610 && r.width > 1000;
        });
        if (inp) { inp.focus(); inp.select(); }
    }""")
    _time.sleep(0.3)
    s.type(reason)
    _time.sleep(0.5)

    # 신청완료 클릭 (step 1 → step 2)
    if not _click_obt_button(s, '신청완료'):
        raise RuntimeError('신청완료 버튼 클릭 실패 (HPD0110 step 1→2)')
    _time.sleep(wait)

    # Step 3 — 제목 fill + 결재상신 클릭 (popup 탭 오픈)
    # 제목 textbox: x≈735, y≈659, w≈495 (active textbox after step 2 render)
    s.eval(f"""() => {{
        const inp = Array.from(document.querySelectorAll('input')).find(el => {{
            const r = el.getBoundingClientRect();
            return Math.abs(r.x - 735) < 10 && Math.abs(r.y - 659) < 10 && r.width > 400;
        }});
        if (inp) {{
            inp.focus();
            const setter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'value'
            ).set;
            setter.call(inp, {_json.dumps(title)});
            inp.dispatchEvent(new Event('input', {{ bubbles: true }}));
            inp.dispatchEvent(new Event('change', {{ bubbles: true }}));
        }}
    }}""")
    _time.sleep(0.5)

    if not _click_obt_button(s, '결재상신'):
        raise RuntimeError('결재상신 버튼 클릭 실패 (HPD0110 step 2)')
    _time.sleep(wait)

    # Step 4 — popup 탭으로 전환 → 상신 클릭
    tabs = s.tab_list()
    popup = next((t for t in tabs
                  if 'popup' in t.get('url', '') and 'callComp=UBAP001' in t.get('url', '')),
                 None)
    if not popup:
        raise RuntimeError('결재 popup 탭을 찾지 못함 — 결재상신 단계가 진행 안 됨')
    s.tab_select(popup['index'])
    _time.sleep(2.0)

    # popup 상신 버튼은 <div> with text "상신". Mouse-event dispatch.
    fired = _dispatch_mouse_click(
        s,
        """(() => {
            const els = Array.from(document.querySelectorAll('div, span, button'));
            return els.find(e =>
                (e.innerText || '').trim() === '상신'
                && e.getBoundingClientRect().width > 0
                && e.getBoundingClientRect().y < 60
            ) || null;
        })()"""
    )
    if not fired:
        raise RuntimeError('popup 탭의 상신 버튼을 찾지 못함')
    _time.sleep(wait)

    # popup이 자동 닫히면 tab list에서 사라짐. 안 닫혔으면 강제 close.
    tabs = s.tab_list()
    if any(t['index'] == popup['index'] for t in tabs):
        try:
            s.tab_close(popup['index'])
        except Exception:
            pass
        # tab_close는 인덱스 재배열을 트리거할 수 있으므로 첫 ERP 탭으로 select
        tabs = s.tab_list()
        first_erp = next((t for t in tabs if 'erp.doflab.com' in t.get('url', '')), None)
        if first_erp:
            s.tab_select(first_erp['index'])

    # 검증 — 기결문서함에서 방금 상신한 doc 확인
    s.goto(approval_url('기결문서'))
    _time.sleep(wait)
    docs = approval_docs(s)
    matched = next((d for d in docs
                    if d.get('양식') == '연차휴가신청서' and d.get('제목') == title),
                   None)
    return matched


# ---------------------------------------------------------------------------
# Recall (회수) — 상신문서함의 진행중 문서를 회수해 결재 라인에서 제거
#
# Flow:
#   1. UBA1010 (상신문서함) 진입 → SPA 자동 list-fetch
#   2. doc_no 매칭 row 찾아 제목 클릭 → popup tab 오픈
#      (URL: /#/popup?...&docID=...&pageCode=UBA1010&callComp=UBAP002)
#   3. popup 탭 우상단 "회수" <div> 클릭
#   4. 확인 다이얼로그 ("회수 하시겠습니까?") → "확인" 버튼 클릭
#   5. popup 자동 닫힘. 검증: 상신문서함 목록에서 doc_no 사라짐.
#
# 회수 후 문서는 결재 라인에서 완전히 제거됨 — 기결문서함/상신문서함 어느
# 쪽에도 안 보임. eap105A04 list에서도 제외. 영구 삭제는 아니고 별도
# "회수문서함" 같은 곳에 보관될 수 있으나, 본 helper는 단순 회수만 수행.
# ---------------------------------------------------------------------------


def _amaranth_outbox_url() -> str:
    """상신문서함 (UBA1010)."""
    return ('https://erp.doflab.com/#/UB/UB/UBA0000'
            '?specialLnb=Y&moduleCode=UB&menuCode=UBA&pageCode=UBA1010')


def _click_outbox_row_title(s: S, doc_no: str) -> bool:
    """상신문서함에서 doc_no 가 포함된 row 의 제목 영역을 클릭.

    eval 기반 DOM 검색 — snapshot ref 보다 row 구조 변화에 견고.
    doc_no 텍스트를 가진 노드의 row container 찾고, 그 내부의
    `[class*=title]` 또는 첫 번째 강조 span 을 클릭.
    """
    return bool(s.eval(
        f"""() => {{
            const docNo = {_json.dumps(doc_no)};
            const all = Array.from(document.querySelectorAll('*'));
            const docCell = all.find(el =>
                el.children.length === 0
                && (el.textContent || '').trim() === docNo);
            if (!docCell) return false;
            let row = docCell;
            for (let i = 0; i < 12; i++) {{
                if (row.parentElement && row.parentElement.tagName === 'LI') {{
                    row = row.parentElement;
                    break;
                }}
                if (row.parentElement) row = row.parentElement;
            }}
            const title = row.querySelector('[class*=title], [class*=Title]')
                || row.querySelector('strong, b, .link, [class*=link]');
            const target = title || row;
            const r = target.getBoundingClientRect();
            const cx = r.x + r.width / 2;
            const cy = r.y + r.height / 2;
            for (const t of ['mousedown', 'mouseup', 'click']) {{
                target.dispatchEvent(new MouseEvent(t, {{
                    bubbles: true, cancelable: true, view: window,
                    clientX: cx, clientY: cy, button: 0, buttons: 1
                }}));
            }}
            return true;
        }}"""
    ))


def recall_doc(s: S, doc_no: str, wait: float = 3.5) -> bool:
    """진행중 문서를 회수.

    Args:
        s: S('amaranth'). 로그인된 세션.
        doc_no: 'DOF-YYMM-####' 형식. 상신문서함에 보이는 문서만 가능.
        wait: per-step delay (회수 dialog가 느릴 때 늘리기).

    Returns:
        True 회수 성공, False 매칭 row 없음/실패.

    Raises:
        RuntimeError: 다이얼로그 단계에서 진행 안 될 때.
    """
    s.goto(_amaranth_outbox_url())
    _time.sleep(wait)

    # 제목 클릭 → popup 탭 오픈 (eval 기반 row→title 검색)
    before_tabs = {t['index'] for t in s.tab_list()}
    if not _click_outbox_row_title(s, doc_no):
        return False
    _time.sleep(wait)

    tabs = s.tab_list()
    new_tab = next(
        (t for t in tabs
         if t['index'] not in before_tabs
         and 'popup' in t.get('url', '')
         and ('callComp=UBAP002' in t.get('url', '')
              or f'docID' in t.get('url', ''))),
        None,
    )
    # 첫 진입 시 popup 탭이 신설되지 않을 수 있음 (이미 열려있거나) — 안전망
    if not new_tab:
        new_tab = next(
            (t for t in tabs if 'callComp=UBAP002' in t.get('url', '')),
            None,
        )
    if not new_tab:
        raise RuntimeError(
            f'문서 viewer popup 탭이 열리지 않음 (doc_no={doc_no})'
        )
    s.tab_select(new_tab['index'])
    _time.sleep(2.0)

    # 회수 버튼은 <div> generic. snapshot 에서 ref 식별.
    raw = s.snapshot()
    m = _re.search(r'-\s+generic\s+\[ref=(e\d+)\][^\n]*:\s*회수\s*$',
                   raw, _re.MULTILINE)
    if not m:
        raise RuntimeError('회수 버튼을 찾지 못함 — 이미 결재 진행되어 회수 불가일 수 있음')
    s.click(m.group(1))
    _time.sleep(1.5)

    # 확인 다이얼로그
    raw = s.snapshot()
    m = _re.search(r'-\s+button\s+"확인"\s+\[ref=(e\d+)\]', raw)
    if not m:
        raise RuntimeError('회수 확인 다이얼로그가 안 떴음')
    s.click(m.group(1))
    _time.sleep(wait)

    # popup 닫혔는지 확인 + 닫기
    tabs = s.tab_list()
    if any(t['index'] == new_tab['index'] for t in tabs):
        try:
            s.tab_close(new_tab['index'])
        except Exception:
            pass
    # 첫 ERP 탭으로 복귀
    tabs = s.tab_list()
    first_erp = next((t for t in tabs if 'erp.doflab.com' in t.get('url', '')),
                     None)
    if first_erp:
        s.tab_select(first_erp['index'])

    # 검증 — 상신문서함 다시 진입해 doc_no 가 사라졌는지
    s.goto(_amaranth_outbox_url())
    _time.sleep(wait)
    raw = s.snapshot()
    return doc_no not in raw


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
                  sub_ty: str = '2', tr_codes=None,
                  all_tr_cd: str = '1') -> Optional[dict]:
    """Query 거래처계정내역 for a list of 계정과목코드 over a date range.

    fdate / fill_dt are YYYYMMDD strings. Call acc303x_bootstrap('ACC3030')
    first so at least one signed /financial/ACC3030/00a00001 capture exists.
    Returns the full parsed response (check .get('resultData')) or None.

    all_tr_cd='1' (default) matches the ERP UI Excel export — includes ALL
    transactions per 거래처. The bootstrap-captured value is '0' which omits
    some transactions (e.g. 'Warranty 회차반제', some 렌탈료 entries) — set
    to '1' to align with manual export totals.
    """
    headers, sample = _amaranth_latest_auth(s, 'ACC3030/00a00001')
    if not headers:
        return None
    body = dict(sample or {})
    body['vAcctCdStr'] = '|'.join(acct_codes) + '|'
    body['vFdate'] = fdate
    body['vFillDt'] = fill_dt
    body['vSubTy'] = sub_ty
    body['vIsAllTrCd'] = all_tr_cd
    if tr_codes is not None:
        body['vTrCdStr'] = '|'.join(tr_codes) + ('|' if tr_codes else '')
    return _amaranth_post(s, '/financial/ACC3030/00a00001', headers, body)


def acc3020_query(s: S, acct_codes: list, fill_dt: str, fdate: Optional[str] = None,
                  sub_ty: int = 1, tr_codes=None,
                  all_tr_cd: str = '1') -> Optional[dict]:
    """Query 거래처계정잔액 (balance as-of fill_dt).

    fdate defaults to year start of fill_dt. Call acc303x_bootstrap('ACC3020')
    first. Returns the full parsed response or None.

    sub_ty=1 (default) matches the ERP UI Excel export — gives the
    period-net balance per 거래처 (manual file totals reproduce within ~7M).
    sub_ty=0 returns ALL 거래처 with carry-over inflated totals (~12B) and
    is useful only for current-snapshot view.
    sub_ty=2/3/4 return 0 rows — endpoint rejects.

    all_tr_cd='1' includes all 거래처 (default for parity with manual export).
    """
    headers, sample = _amaranth_latest_auth(s, 'ACC3020/00a00001')
    if not headers:
        return None
    body = dict(sample or {})
    body['vAcctCdStr'] = '|'.join(acct_codes) + '|'
    body['vFillDt'] = fill_dt
    body['vFdate'] = fdate or (fill_dt[:4] + '0101')
    body['vSubTy'] = sub_ty
    body['vIsAllTrCd'] = all_tr_cd
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

    # 조회 button click. The OBTConditionPanel wraps a button laid out at 0×0
    # so DOM `.click()` does nothing, and headless mouse coords don't reach
    # the right element either. The reliable trick is to find the
    # OBTButton_typedefault wrapper with tooltip "조회", walk up to the
    # OBTButton_root, and dispatch synthetic mousedown/mouseup/click on the
    # inner <button>. Works in both headed and headless.
    fired = s.eval(r"""
    () => {
        const cands = Array.from(document.querySelectorAll(
            '[class*="OBTButton_typedefault"] .OBTButton_wrapper__1_tA2'
        ));
        let target = null;
        for (const el of cands) {
            const r = el.getBoundingClientRect();
            if (r.width <= 0 || r.height <= 0 || r.x < 1000 || r.y < 150) continue;
            const tip = el.closest('[class*="OBTTooltip_root"]');
            const tipText = tip?.querySelector('.OBTTooltip_contents__2UdOU')?.innerText || '';
            if (tipText === '조회') { target = el; break; }
        }
        if (!target) return false;
        const root = target.closest('[class*="OBTButton_root"]');
        const inner = (root && root.querySelector('button')) || root || target;
        const r = target.getBoundingClientRect();
        const cx = r.x + r.width/2, cy = r.y + r.height/2;
        for (const t of ['mousedown', 'mouseup', 'click']) {
            inner.dispatchEvent(new MouseEvent(t, {
                bubbles: true, cancelable: true, view: window,
                clientX: cx, clientY: cy, button: 0
            }));
        }
        return true;
    }
    """)
    if not fired:
        _click_by_text(s, '조회', tag='button')
    _time.sleep(2.5)

    return len(_filter_requests(s, f'{page_code}/00a00001'))


# ---------------------------------------------------------------------------
# ACC3010 거래처원장 (transaction-level ledger per 거래처).
#
# Endpoint: POST /financial/acc3010/getGridDetailTab2 (the 원장 tab)
#
# Body schema (all required, captured from SPA):
#   vDivCds:    회계단위 (e.g. "1000|")
#   vGisu:      회계기수
#   vDtFrom:    FY start (YYYYMMDD)
#   vAcctCds:   "1080000|" (multi-account, pipe-separated)
#   vFillDtFrom/vFillDtTo: period bounds
#   vTDrcrFg:   "1" 차변기준 / "2" 대변기준
#   tab:        "2" (원장 tab)
#   nocodeOpt:  "1" 코드누락 포함 / "3" 제외
#   isAllTrCd:  "0" 일반 / "1" 모든 거래처 (manual-export equivalent)
#
# Response: array of rows with: acctCd, trCd, trNm, acctAmDr, acctAmCr,
# acctAmRest, fillDt, rmkDc (e.g. '[ 전 월 이 월 ]', '[ 월     계 ]',
# '[ 누     계 ]', or transaction memo), grp ('0' carry / '1' tx /
# '2' 월계 / '3' 누계), and many other metadata fields.
# ---------------------------------------------------------------------------


def acc3010_query(s: S, acct_codes: list, fdate: str, fill_dt_from: str, fill_dt_to: str,
                  gisu: int, all_tr_cd: str = '1', tdrcr_fg: str = '1',
                  nocode_opt: str = '3') -> Optional[dict]:
    """Query 거래처원장 (transaction-level) for a list of 계정과목코드.

    fdate: FY start (YYYYMMDD).
    fill_dt_from / fill_dt_to: period bounds.
    gisu: 회계기수 number (e.g. 15 for 2026 FY).

    Caller must call acc3010_bootstrap(s) first so signed headers exist.
    Returns full parsed response or None.
    """
    headers, sample = _amaranth_latest_auth(s, 'acc3010/getGridDetailTab2')
    if not headers:
        return None
    body = dict(sample or {})
    body['vAcctCds'] = '|'.join(acct_codes) + '|'
    body['vDtFrom'] = fdate
    body['vFillDtFrom'] = fill_dt_from
    body['vFillDtTo'] = fill_dt_to
    body['vGisu'] = gisu
    body['isAllTrCd'] = all_tr_cd
    body['vTDrcrFg'] = tdrcr_fg
    body['nocodeOpt'] = nocode_opt
    body['tab'] = '2'
    return _amaranth_post(s, '/financial/acc3010/getGridDetailTab2', headers, body)


def acc3010_bootstrap(s: S, code: str = '1080000') -> int:
    """Navigate to ACC3010 → click 원장 tab → seed 계정과목 → click 조회 to
    capture signed XHR headers + body. Returns count of acc3010 captures.
    """
    target = f'{ERP_URL}/#/A/ACC3010/ACC3010'
    tabs = s.tab_list()
    erp_tab = next((t for t in tabs if 'erp.doflab.com' in t.get('url', '')), None)
    if erp_tab and not erp_tab.get('current'):
        s.tab_select(erp_tab['index'])
    s.raw('resize', '1600', '1000')
    _time.sleep(0.5)
    s.goto(target)
    _time.sleep(3)

    # Click 원장 tab via real mouse coords
    bbox = s.eval(r"""
    () => {
        const tabs = Array.from(document.querySelectorAll('.OBTTabs_tabRoot__3jIwT'));
        const t = tabs.find(e => (e.innerText || '').trim() === '원장');
        if (!t) return null;
        const r = t.getBoundingClientRect();
        return {x: r.x + r.width/2, y: r.y + r.height/2};
    }
    """)
    if bbox:
        s.raw('mousemove', str(int(bbox['x'])), str(int(bbox['y'])))
        _time.sleep(0.2); s.raw('mousedown'); _time.sleep(0.05); s.raw('mouseup')
    _time.sleep(2)

    # CRITICAL: Switch 계정선택 from "계정별" to "세목별" — without this, the
    # server returns ALL sub-account entries (1080001/02/03 entries leak into
    # 1080000 query). With 세목별 (vPrtFg=2), responses are properly
    # partitioned by sub-account and match manual UI export.
    chevron = s.eval(r"""
    () => {
        const dd = Array.from(document.querySelectorAll('[class*="OBTDropDownList_default"]'))
            .find(e => e.offsetWidth > 0 && (e.innerText||'').trim() === '계정별');
        if (!dd) return null;
        const btn = dd.querySelector('button');
        if (!btn) return null;
        const r = btn.getBoundingClientRect();
        return {x: r.x + r.width/2, y: r.y + r.height/2};
    }
    """)
    if chevron:
        s.raw('mousemove', str(int(chevron['x'])), str(int(chevron['y'])))
        _time.sleep(0.2); s.raw('mousedown'); _time.sleep(0.05); s.raw('mouseup')
        _time.sleep(1)
        # Click 세목별 in the opened list
        opt = s.eval(r"""
        () => {
            const all = Array.from(document.querySelectorAll('li, div'));
            const o = all.find(e => (e.innerText||'').trim() === '세목별' && e.offsetWidth > 0 && e.offsetWidth < 200);
            if (!o) return null;
            const r = o.getBoundingClientRect();
            return {x: r.x + r.width/2, y: r.y + r.height/2};
        }
        """)
        if opt:
            s.raw('mousemove', str(int(opt['x'])), str(int(opt['y'])))
            _time.sleep(0.2); s.raw('mousedown'); _time.sleep(0.05); s.raw('mouseup')
        _time.sleep(1.5)

    # Focus VISIBLE 계정과목 input (원장 tab has its own; 잔액 tab's is hidden)
    s.eval(r"""
    () => {
        const visible = Array.from(document.querySelectorAll('input[placeholder="계정과목코드도움"]'))
            .find(i => i.offsetWidth > 0);
        if (visible) visible.focus();
    }
    """)
    _time.sleep(0.3)
    s.type(code)
    _time.sleep(0.4)
    s.press('Enter')
    _time.sleep(1.0)

    # Click 조회 (synthetic mouse events on OBTButton_root)
    s.eval(r"""
    () => {
        const cands = Array.from(document.querySelectorAll('[class*="OBTButton_typedefault"] .OBTButton_wrapper__1_tA2'));
        let target = null;
        for (const el of cands) {
            const r = el.getBoundingClientRect();
            if (r.width <= 0 || r.x < 1000 || r.y < 150) continue;
            const tip = el.closest('[class*="OBTTooltip_root"]');
            if (tip?.querySelector('.OBTTooltip_contents__2UdOU')?.innerText === '조회') { target = el; break; }
        }
        if (!target) return false;
        const root = target.closest('[class*="OBTButton_root"]');
        const inner = (root && root.querySelector('button')) || root || target;
        const r = target.getBoundingClientRect();
        for (const t of ['mousedown', 'mouseup', 'click']) {
            inner.dispatchEvent(new MouseEvent(t, {bubbles: true, cancelable: true, view: window, clientX: r.x+r.width/2, clientY: r.y+r.height/2, button: 0}));
        }
        return true;
    }
    """)
    _time.sleep(3)
    return len(_filter_requests(s, 'acc3010/getGridDetailTab2'))


def _acc3010_set_date_range(s: S, fdate_yymd_dash: str, tdate_yymd_dash: str):
    """Type new dates into the OBTDatePickerRebuild inputs (typing-driven —
    React state listens to keyboard input, not native setter).
    """
    # First date
    s.eval(r"""
    () => {
        const inputs = Array.from(document.querySelectorAll('input.OBTDatePickerRebuild_inputYMD__PtxMy')).filter(i => i.offsetWidth > 0);
        if (inputs[0]) { inputs[0].focus(); inputs[0].select(); }
    }
    """)
    _time.sleep(0.3)
    s.type(fdate_yymd_dash.replace('-', ''))
    _time.sleep(0.3)
    s.press('Tab')
    _time.sleep(0.3)
    # Second date
    s.eval(r"""
    () => {
        const inputs = Array.from(document.querySelectorAll('input.OBTDatePickerRebuild_inputYMD__PtxMy')).filter(i => i.offsetWidth > 0);
        if (inputs[1]) { inputs[1].focus(); inputs[1].select(); }
    }
    """)
    _time.sleep(0.3)
    s.type(tdate_yymd_dash.replace('-', ''))
    _time.sleep(0.3)
    s.press('Tab')
    _time.sleep(0.3)


def _acc3010_click_inquiry(s: S):
    """Click 조회 button via synthetic mouse events on OBTButton_root."""
    s.eval(r"""
    () => {
        const cands = Array.from(document.querySelectorAll('[class*="OBTButton_typedefault"] .OBTButton_wrapper__1_tA2'));
        let target = null;
        for (const el of cands) {
            const r = el.getBoundingClientRect();
            if (r.width <= 0 || r.x < 1000 || r.y < 150) continue;
            const tip = el.closest('[class*="OBTTooltip_root"]');
            if (tip?.querySelector('.OBTTooltip_contents__2UdOU')?.innerText === '조회') { target = el; break; }
        }
        if (!target) return false;
        const root = target.closest('[class*="OBTButton_root"]');
        const inner = (root && root.querySelector('button')) || root || target;
        const r = target.getBoundingClientRect();
        for (const t of ['mousedown', 'mouseup', 'click']) {
            inner.dispatchEvent(new MouseEvent(t, {bubbles: true, cancelable: true, view: window, clientX: r.x+r.width/2, clientY: r.y+r.height/2, button: 0}));
        }
        return true;
    }
    """)


def _acc3010_drive_query(s: S, fdate_from: str, fdate_to: str,
                         settle_seconds: float = 8.0) -> list[int]:
    """Drive ACC3010 UI: set date range + click 조회 → SPA fires one request
    per month within the range. Returns indexes of all NEW
    getGridDetailTab2 responses captured (after the click).

    fdate_from / fdate_to: 'YYYY-MM-DD' format.
    settle_seconds: how long to wait for monthly responses to settle.
    """
    pre_count = len(_filter_requests(s, 'acc3010/getGridDetailTab2'))
    _acc3010_set_date_range(s, fdate_from, fdate_to)
    _acc3010_click_inquiry(s)
    # Wait for SPA's monthly chunking to finish
    _time.sleep(settle_seconds)
    reqs = _filter_requests(s, 'acc3010/getGridDetailTab2')
    return [r['index'] for r in reqs[pre_count:]]


def acc3010_history(s: S, acct_codes: list, end_year: Optional[int] = None) -> dict:
    """Fetch all available 회계기수 (vGisu) for ACC3010 거래처원장.

    For ACC3010, `wehago-sign` is body-content-locked — we cannot replay a
    captured signed request with a modified body (server returns
    resultCode=-1 / FAIL). So we drive the SPA UI for each year:
        1. Set 승인기간 (date-range) inputs to the year's bounds
        2. Click 조회 → SPA fires a fresh signed request
        3. Read the response from the captured request

    Caller must set 계정과목 codes via the UI before calling, OR seed via
    acc3010_bootstrap() (single-code seed) — multi-code is achievable by
    interacting with the codepicker, which this helper does not yet do.
    For now, this helper assumes the SPA already has the desired
    계정과목 selected (e.g. all 외상매출금 sub-codes captured during
    bootstrap if user manually set them via the picker).

    Returns:
        {
          'transactions': [api_row, ...],
          'fy_carries':   {year: {(trCd, acctCd): {dr, cr}}},
          'fetched_years': [...]
        }
    """
    if end_year is None:
        from datetime import date
        end_year = date.today().year

    transactions: list[dict] = []
    fy_carries: dict[int, dict] = {}
    fetched_years: list[int] = []

    for year in range(EARLIEST_FY_YEAR, end_year + 1):
        fdt_from = f'{year}-01-01'
        fdt_to = f'{year}-12-31'
        idxs = _acc3010_drive_query(s, fdt_from, fdt_to, settle_seconds=10.0)
        if not idxs:
            continue
        # Merge all monthly responses for this year
        year_rows: list[dict] = []
        for idx in idxs:
            try:
                data = _json.loads(s.response_body(idx) or '{}')
            except Exception:
                continue
            rd = data.get('resultData')
            if isinstance(rd, list):
                year_rows.extend(rd)
        if not year_rows:
            continue
        fetched_years.append(year)

        # Carry: only the first month's response carries 전월이월 (= FY's
        # 전기이월 from prev year). Subsequent months show 전월이월 = previous
        # month's running balance — we only want FY-start carry. Detect by
        # finding the carry that has rmkDc='[ 전 월 이 월 ]' from earliest
        # captured response per (trCd, acctCd).
        carry_map: dict = {}
        for r in year_rows:
            tr, acct = r.get('trCd'), r.get('acctCd')
            if not (tr and acct) or tr.strip() == 'NOCODE':
                continue
            grp = str(r.get('grp') or '')
            rmk = str(r.get('rmkDc') or '')
            if grp == '0' or '이 월' in rmk:
                # Take the FIRST seen carry per (tr, acct) — represents FY-start
                if (tr, acct) not in carry_map:
                    carry_map[(tr, acct)] = {
                        'dr': r.get('acctAmDr') or 0,
                        'cr': r.get('acctAmCr') or 0,
                    }
            elif grp == '1' and r.get('fillDt'):
                transactions.append(r)
        fy_carries[year] = carry_map

    return {
        'transactions': transactions,
        'fy_carries': fy_carries,
        'fetched_years': fetched_years,
    }


def acc3010_period_view(history: dict, period_start: str, period_end: str) -> list[dict]:
    """Derive ACC3010-style row list for [period_start, period_end].

    Output is a list of API-row dicts ready for build_acc3010_xlsx.
    Only carry + period transactions; 월계/누계 are added by the Excel builder.
    """
    from collections import OrderedDict

    txs = history.get('transactions') or []
    fy_carries = history.get('fy_carries') or {}
    ps_year = int(period_start[:4])
    fy_carry = fy_carries.get(ps_year, {})
    fy_start = f'{ps_year}0101'

    grouped: OrderedDict = OrderedDict()
    for r in txs:
        tr, acct = r.get('trCd'), r.get('acctCd')
        if not (tr and acct):
            continue
        grouped.setdefault((tr, acct), []).append(r)

    out: list[dict] = []
    for pair, group in grouped.items():
        tr, acct = pair
        pre_period_dr = sum(
            (r.get('acctAmDr') or 0)
            for r in group
            if (r.get('fillDt') or '') >= fy_start
            and (r.get('fillDt') or '') < period_start
        )
        pre_period_cr = sum(
            (r.get('acctAmCr') or 0)
            for r in group
            if (r.get('fillDt') or '') >= fy_start
            and (r.get('fillDt') or '') < period_start
        )
        fy_c = fy_carry.get(pair, {'dr': 0, 'cr': 0})
        carry_dr = fy_c['dr'] + pre_period_dr
        carry_cr = fy_c['cr'] + pre_period_cr
        period_txs = [
            r for r in group
            if (r.get('fillDt') or '') >= period_start
            and (r.get('fillDt') or '') <= period_end
        ]
        if not (carry_dr or carry_cr) and not period_txs:
            continue
        sample = group[0]
        out.append({
            'trCd': tr,
            'trNm': sample.get('trNm'),
            'trgrpCd': sample.get('trgrpCd'),
            'trgrpNm': sample.get('trgrpNm'),
            'regNb': sample.get('regNb'),
            'acctCd': acct, 'acctNm': sample.get('acctNm'),
            'fillDt': None, 'fillNb': None,
            'rmkDc': '[ 전 월 이 월 ]', 'grp': '0',
            'acctAmDr': carry_dr, 'acctAmCr': carry_cr,
            'acctAmRest': carry_dr - carry_cr,
        })
        out.extend(period_txs)
    return out


# ---------------------------------------------------------------------------
# Multi-회계기수(vGisu) full-history ledger + arbitrary-period derivation.
#
# ERP segregates transactions per fiscal year (vGisu). Each FY has its own
# 전기이월 (carry) row that includes year-end closing entries (외화환산,
# 결산분개) NOT visible as raw transactions in earlier years' responses. So
# to reconstruct an arbitrary-period view we must:
#   1. Fetch each available vGisu's transactions + ERP-supplied carry.
#   2. To compute "전월이월" for any period [period_start, period_end]:
#        period_carry = vGisu_carry(FY of period_start)
#                       + sum of raw txs in [FY_start_of(period_start),
#                                            period_start - 1]
#   3. Period transactions = txs in [period_start, period_end].
#
# vGisu mapping for this ERP (DOF, 회사 설립 2012): vGisu = year - 2011.
#   vGisu=13 → 2024 FY  (earliest accessible)
#   vGisu=14 → 2025 FY
#   vGisu=15 → 2026 FY
#   vGisu≤12 → endpoint returns `resultData: 0` (rejected)
# ---------------------------------------------------------------------------


# Earliest accessible vGisu — endpoint rejects gisu < this. Mapping is
# year - 2011, so 13 = 2024.
EARLIEST_GISU = 13
EARLIEST_FY_YEAR = 2024


def _gisu_for_year(year: int) -> int:
    """Map calendar year → vGisu number for this ERP."""
    return year - 2011


def _year_bounds(year: int) -> tuple[str, str]:
    """Return (YYYY0101, YYYY1231)."""
    return f'{year}0101', f'{year}1231'


def acc3030_history(s: S, acct_codes: list, end_year: Optional[int] = None) -> dict:
    """Fetch all available 회계기수 (vGisu) for the given 계정과목 codes.

    Walks vGisu 13 (2024) → end_year (default: current year). Returns:
        {
          'transactions': [api_row, ...],          # all txs across all FYs
          'fy_carries':   {year: {(trCd, acctCd): {'dr': float, 'cr': float}}},
          'fetched_years': [2024, 2025, 2026],
        }

    Caller must call acc303x_bootstrap(s, 'ACC3030') first so signed headers
    are captured.
    """
    if end_year is None:
        from datetime import date
        end_year = date.today().year

    headers, sample = _amaranth_latest_auth(s, 'ACC3030/00a00001')
    if not headers:
        return {'transactions': [], 'fy_carries': {}, 'fetched_years': []}

    transactions: list[dict] = []
    fy_carries: dict[int, dict] = {}
    fetched_years: list[int] = []

    for year in range(EARLIEST_FY_YEAR, end_year + 1):
        gisu = _gisu_for_year(year)
        fdate, fill_dt = _year_bounds(year)
        body = dict(sample)
        body['vAcctCdStr'] = '|'.join(acct_codes) + '|'
        body['vFdate'] = fdate
        body['vFillDt'] = fill_dt
        body['vSubTy'] = '2'
        body['vIsAllTrCd'] = '1'
        body['vGisu'] = gisu
        data = _amaranth_post(s, '/financial/ACC3030/00a00001', headers, body)
        rows = (data or {}).get('resultData')
        if not isinstance(rows, list) or not rows:
            continue
        fetched_years.append(year)

        carry_map: dict = {}
        for r in rows:
            tr, acct = r.get('trCd'), r.get('acctCd')
            if not (tr and acct):
                continue
            if '이 월' in (r.get('rmkDc') or ''):
                carry_map[(tr, acct)] = {
                    'dr': r.get('drAm') or 0,
                    'cr': r.get('crAm') or 0,
                }
            else:
                transactions.append(r)
        fy_carries[year] = carry_map

    return {
        'transactions': transactions,
        'fy_carries': fy_carries,
        'fetched_years': fetched_years,
    }


def acc3030_period_view(history: dict, period_start: str, period_end: str) -> list[dict]:
    """Derive a 거래처계정내역 view for an arbitrary [period_start, period_end].

    history: dict from acc3030_history(s, codes).
    period_start, period_end: 'YYYYMMDD' inclusive.

    Returns list of API-shaped rows (carry + transactions) ready to feed into
    pwc_amaranth_excel.build_acc3030_xlsx().

    Carry per (거래처, 계정과목) is computed as:
        ERP-supplied vGisu carry for the FY of period_start
        + sum of raw txs in [FY_start_of(period_start), period_start - 1]

    If period_start precedes EARLIEST_FY_YEAR, the FY carry is treated as 0
    (no pre-data); the resulting carry comes purely from raw transactions
    (which is empty since this ERP has no pre-2024 data — net 0 carry).

    Group emitted only if (carry_dr or carry_cr or has_period_txs).
    """
    from collections import OrderedDict, defaultdict

    txs = history.get('transactions') or []
    fy_carries = history.get('fy_carries') or {}

    # Determine FY containing period_start
    ps_year = int(period_start[:4])
    fy_carry = fy_carries.get(ps_year, {})  # {} if ps_year < EARLIEST_FY_YEAR
    fy_start = f'{ps_year}0101'

    # Group all txs by (trCd, acctCd) preserving 거래처-first-seen ordering
    grouped: OrderedDict = OrderedDict()
    for r in txs:
        tr, acct = r.get('trCd'), r.get('acctCd')
        if not (tr and acct):
            continue
        grouped.setdefault((tr, acct), []).append(r)

    out: list[dict] = []
    seen_orderings = OrderedDict()  # to maintain emit order
    for pair, group in grouped.items():
        seen_orderings.setdefault(pair, group)

    for pair, group in seen_orderings.items():
        tr, acct = pair
        # Pre-period within current FY (additive to vGisu carry)
        pre_period_dr = sum(
            (r.get('drAm') or 0)
            for r in group
            if (r.get('fillDt') or '') >= fy_start
            and (r.get('fillDt') or '') < period_start
        )
        pre_period_cr = sum(
            (r.get('crAm') or 0)
            for r in group
            if (r.get('fillDt') or '') >= fy_start
            and (r.get('fillDt') or '') < period_start
        )

        fy_c = fy_carry.get(pair, {'dr': 0, 'cr': 0})
        carry_dr = fy_c['dr'] + pre_period_dr
        carry_cr = fy_c['cr'] + pre_period_cr

        # Period transactions
        period_txs = [
            r for r in group
            if (r.get('fillDt') or '') >= period_start
            and (r.get('fillDt') or '') <= period_end
        ]

        if not (carry_dr or carry_cr) and not period_txs:
            continue

        sample = group[0]
        out.append({
            'trCd': tr, 'attrNm': sample.get('attrNm'),
            'divCd': sample.get('divCd'), 'divNm': sample.get('divNm'),
            'acctCd': acct, 'acctNm': sample.get('acctNm'),
            'fillDt': None, 'fillNb': None,
            'rmkDc': '[ 전 월 이 월 ]',
            'drAm': carry_dr, 'crAm': carry_cr,
            'janAm': carry_dr - carry_cr,
        })
        out.extend(period_txs)

    return out


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
    'submit_leave', 'recall_doc',
    # Accounting (ACC3030/ACC3020)
    'acc3030_query', 'acc3020_query', 'acc303x_bootstrap',
    'acc3030_history', 'acc3030_period_view',
    'EARLIEST_GISU', 'EARLIEST_FY_YEAR',
    # ACC3010 거래처원장 (transaction-level)
    'acc3010_query', 'acc3010_bootstrap', 'acc3010_history', 'acc3010_period_view',
]
