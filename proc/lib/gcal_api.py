"""Google Calendar API helper — list calendars / events / free-busy.

Built on `proc/lib/google_auth.GoogleClient`. Pure functions, normalized output.

Usage:
    from google_auth import GoogleClient
    from gcal_api import events_in_range, save_json

    g = GoogleClient('bispro89')
    events = events_in_range(g, '2026-05-01', '2026-05-08')
    save_json(events, 'output/gcal-bispro89-may-week1.json')

CLI:
    python proc/lib/gcal_api.py events --account bispro89 \\
        --since 2026-05-01 --until 2026-05-08 \\
        --out output/gcal-bispro89-may-week1.json

    python proc/lib/gcal_api.py calendars --account bispro89

    python proc/lib/gcal_api.py freebusy --account bispro89 \\
        --since 2026-05-12T09:00 --until 2026-05-12T18:00
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any, Iterable, Optional

# Allow `python proc/lib/gcal_api.py ...`.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from google_auth import GoogleClient  # noqa: E402


KST = dt.timezone(dt.timedelta(hours=9))


def _to_dt(s: str | dt.datetime, end_of_day: bool = False) -> dt.datetime:
    """Parse `2026-05-08`, `2026-05-08T13:00`, or full ISO. Naive → KST."""
    if isinstance(s, dt.datetime):
        return s if s.tzinfo else s.replace(tzinfo=KST)
    s = s.strip()
    # bare YYYY-MM-DD → start (or end of day if end_of_day)
    if len(s) == 10 and s[4] == '-' and s[7] == '-':
        d = dt.date.fromisoformat(s)
        if end_of_day:
            return dt.datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=KST)
        return dt.datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=KST)
    # ISO datetime — accept Z or offset, else assume KST
    iso = s.replace('Z', '+00:00')
    parsed = dt.datetime.fromisoformat(iso)
    if not parsed.tzinfo:
        parsed = parsed.replace(tzinfo=KST)
    return parsed


def parse_event(ev: dict, calendar_summary: Optional[str] = None) -> dict:
    """Normalize a calendar event."""
    start = ev.get('start', {})
    end = ev.get('end', {})
    start_value = start.get('dateTime') or start.get('date')
    end_value = end.get('dateTime') or end.get('date')
    is_all_day = bool(start.get('date'))
    attendees = ev.get('attendees', []) or []
    self_resp = next((a.get('responseStatus') for a in attendees if a.get('self')), None)
    return {
        'id': ev.get('id'),
        'calendar': calendar_summary,
        'summary': ev.get('summary', '(no title)'),
        'start': start_value,
        'end': end_value,
        'all_day': is_all_day,
        'location': ev.get('location'),
        'description': ev.get('description'),
        'organizer': (ev.get('organizer') or {}).get('email'),
        'creator': (ev.get('creator') or {}).get('email'),
        'attendees': [
            {'email': a.get('email'), 'name': a.get('displayName'), 'response': a.get('responseStatus'), 'self': bool(a.get('self'))}
            for a in attendees
        ],
        'self_response': self_resp,
        'recurring_event_id': ev.get('recurringEventId'),
        'status': ev.get('status'),
        'html_link': ev.get('htmlLink'),
        'hangout_link': ev.get('hangoutLink'),
        'conference_url': next(
            (e.get('uri') for e in ((ev.get('conferenceData') or {}).get('entryPoints') or []) if e.get('uri')),
            None,
        ),
        'updated': ev.get('updated'),
    }


def list_calendars(g: GoogleClient, hide_holidays: bool = False) -> list[dict]:
    cal = g.service('calendar', 'v3')
    items = cal.calendarList().list().execute().get('items', [])
    out = []
    for c in items:
        cid = c['id']
        if hide_holidays and (cid.endswith('@group.v.calendar.google.com') and 'holiday' in cid.lower()):
            continue
        out.append({
            'id': cid,
            'summary': c.get('summary'),
            'description': c.get('description'),
            'primary': bool(c.get('primary')),
            'access_role': c.get('accessRole'),
            'time_zone': c.get('timeZone'),
            'background_color': c.get('backgroundColor'),
            'selected': c.get('selected', True),
        })
    return out


def list_events(
    g: GoogleClient,
    calendar_id: str = 'primary',
    time_min: Optional[str | dt.datetime] = None,
    time_max: Optional[str | dt.datetime] = None,
    q: Optional[str] = None,
    max_results: int = 250,
    include_declined: bool = False,
    show_deleted: bool = False,
) -> list[dict]:
    """Single-calendar event listing. Auto-paginates."""
    cal = g.service('calendar', 'v3')
    cal_meta = None
    try:
        cal_meta = cal.calendars().get(calendarId=calendar_id).execute()
    except Exception:
        pass
    summary = (cal_meta or {}).get('summary') or calendar_id

    params: dict[str, Any] = {
        'calendarId': calendar_id,
        'singleEvents': True,
        'orderBy': 'startTime',
        'maxResults': min(2500, max_results),
        'showDeleted': show_deleted,
    }
    if time_min is not None:
        params['timeMin'] = _to_dt(time_min).isoformat()
    if time_max is not None:
        params['timeMax'] = _to_dt(time_max, end_of_day=True).isoformat()
    if q:
        params['q'] = q

    out: list[dict] = []
    page_token = None
    while True:
        if page_token:
            params['pageToken'] = page_token
        resp = cal.events().list(**params).execute()
        for ev in resp.get('items', []) or []:
            parsed = parse_event(ev, calendar_summary=summary)
            if not include_declined and parsed['self_response'] == 'declined':
                continue
            out.append(parsed)
            if len(out) >= max_results:
                return out
        page_token = resp.get('nextPageToken')
        if not page_token:
            break
    return out


def events_in_range(
    g: GoogleClient,
    since: str | dt.datetime,
    until: str | dt.datetime,
    calendars: str | Iterable[str] = 'all',
    skip_declined: bool = True,
    skip_holidays: bool = True,
    q: Optional[str] = None,
) -> list[dict]:
    """Aggregate events across calendars in [since, until].

    `calendars`:
      - 'all' (default): every calendar in calendarList (minus holidays if skip_holidays)
      - 'primary': only primary
      - iterable of calendar IDs: explicit list
    """
    if calendars == 'primary':
        return list_events(g, 'primary', since, until, q=q, include_declined=not skip_declined)

    if calendars == 'all':
        cal_ids = [c['id'] for c in list_calendars(g, hide_holidays=skip_holidays)]
    else:
        cal_ids = list(calendars)

    out: list[dict] = []
    for cid in cal_ids:
        try:
            evs = list_events(g, cid, since, until, q=q, include_declined=not skip_declined)
        except Exception as e:
            sys.stderr.write(f'[gcal] skip {cid}: {e}\n')
            continue
        out.extend(evs)
    out.sort(key=lambda e: str(e.get('start') or ''))
    return out


def create_event(
    g: GoogleClient,
    summary: str,
    start: str | dt.datetime,
    end: str | dt.datetime,
    calendar_id: str = 'primary',
    description: Optional[str] = None,
    location: Optional[str] = None,
    attendees: Optional[list[str]] = None,
    all_day: bool = False,
    send_updates: str = 'none',
    add_meet: bool = False,
) -> dict:
    """Create an event. `send_updates` ∈ {'all', 'externalOnly', 'none'}."""
    cal = g.service('calendar', 'v3')
    if all_day:
        sd = _to_dt(start).date().isoformat()
        ed = _to_dt(end).date().isoformat()
        body: dict[str, Any] = {
            'summary': summary,
            'start': {'date': sd},
            'end': {'date': ed},
        }
    else:
        body = {
            'summary': summary,
            'start': {'dateTime': _to_dt(start).isoformat()},
            'end': {'dateTime': _to_dt(end).isoformat()},
        }
    if description:
        body['description'] = description
    if location:
        body['location'] = location
    if attendees:
        body['attendees'] = [{'email': e} for e in attendees]
    params: dict[str, Any] = {'calendarId': calendar_id, 'body': body, 'sendUpdates': send_updates}
    if add_meet:
        body['conferenceData'] = {'createRequest': {'requestId': f'meet-{int(dt.datetime.now().timestamp())}'}}
        params['conferenceDataVersion'] = 1
    return cal.events().insert(**params).execute()


def update_event(
    g: GoogleClient,
    event_id: str,
    calendar_id: str = 'primary',
    patch: Optional[dict] = None,
    summary: Optional[str] = None,
    start: Optional[str | dt.datetime] = None,
    end: Optional[str | dt.datetime] = None,
    description: Optional[str] = None,
    location: Optional[str] = None,
    send_updates: str = 'none',
) -> dict:
    """Patch an event. Pass `patch=` for a full body, or named kwargs for common fields."""
    cal = g.service('calendar', 'v3')
    body: dict[str, Any] = dict(patch or {})
    if summary is not None:
        body['summary'] = summary
    if description is not None:
        body['description'] = description
    if location is not None:
        body['location'] = location
    if start is not None:
        body['start'] = {'dateTime': _to_dt(start).isoformat()}
    if end is not None:
        body['end'] = {'dateTime': _to_dt(end).isoformat()}
    if not body:
        raise ValueError('Nothing to update.')
    return cal.events().patch(
        calendarId=calendar_id, eventId=event_id, body=body, sendUpdates=send_updates,
    ).execute()


def delete_event(
    g: GoogleClient,
    event_id: str,
    calendar_id: str = 'primary',
    send_updates: str = 'none',
) -> None:
    cal = g.service('calendar', 'v3')
    cal.events().delete(
        calendarId=calendar_id, eventId=event_id, sendUpdates=send_updates,
    ).execute()


def respond_to_event(
    g: GoogleClient,
    event_id: str,
    response: str,
    calendar_id: str = 'primary',
) -> dict:
    """Set self attendee's responseStatus. `response` ∈ {'accepted','declined','tentative','needsAction'}."""
    cal = g.service('calendar', 'v3')
    ev = cal.events().get(calendarId=calendar_id, eventId=event_id).execute()
    attendees = ev.get('attendees', []) or []
    found = False
    for a in attendees:
        if a.get('self'):
            a['responseStatus'] = response
            found = True
            break
    if not found:
        raise ValueError("You're not an attendee of this event")
    return cal.events().patch(
        calendarId=calendar_id, eventId=event_id,
        body={'attendees': attendees},
    ).execute()


# ---- Multi-account aggregate


def events_in_range_all_accounts(
    accounts: Iterable[str],
    since: str | dt.datetime,
    until: str | dt.datetime,
    skip_declined: bool = True,
    skip_holidays: bool = True,
) -> list[dict]:
    """Aggregate events across multiple accounts; tag each with `account`."""
    out: list[dict] = []
    for acct in accounts:
        g = GoogleClient(acct)
        evs = events_in_range(g, since, until, calendars='all',
                              skip_declined=skip_declined, skip_holidays=skip_holidays)
        for e in evs:
            e['account'] = acct
        out.extend(evs)
    out.sort(key=lambda e: str(e.get('start') or ''))
    return out


def free_busy(
    g: GoogleClient,
    since: str | dt.datetime,
    until: str | dt.datetime,
    calendars: Iterable[str] = ('primary',),
) -> dict:
    cal = g.service('calendar', 'v3')
    body = {
        'timeMin': _to_dt(since).isoformat(),
        'timeMax': _to_dt(until, end_of_day=True).isoformat(),
        'items': [{'id': c} for c in calendars],
    }
    return cal.freebusy().query(body=body).execute()


def save_json(data: Any, path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str))
    return p


# ---- CLI


def _cmd_calendars(args) -> int:
    g = GoogleClient(args.account)
    cals = list_calendars(g, hide_holidays=args.no_holidays)
    if args.out:
        save_json(cals, args.out)
        print(f'Wrote {len(cals)} calendars → {args.out}')
    else:
        for c in cals:
            tag = '★' if c['primary'] else ' '
            print(f'  {tag} {c["summary"]:<40} {c["access_role"]:<10} {c["id"]}')
    return 0


def _cmd_events(args) -> int:
    g = GoogleClient(args.account)
    cals_arg = args.calendar if args.calendar else 'all'
    if cals_arg not in ('all', 'primary') and ',' in cals_arg:
        cals_arg = [s.strip() for s in cals_arg.split(',')]
    events = events_in_range(
        g,
        since=args.since,
        until=args.until,
        calendars=cals_arg,
        skip_declined=not args.include_declined,
        skip_holidays=not args.include_holidays,
        q=args.q,
    )
    if args.out:
        save_json(events, args.out)
        print(f'Wrote {len(events)} events → {args.out}')
    else:
        for e in events:
            loc = f'  @{e["location"]}' if e.get('location') else ''
            who = e['organizer'] or ''
            t = (e['start'] or '')[:16]
            print(f'{t}  {e["summary"]}{loc}  [{e["calendar"]}]  {who}')
    return 0


def _cmd_freebusy(args) -> int:
    g = GoogleClient(args.account)
    cals = [c.strip() for c in (args.calendars or 'primary').split(',')]
    fb = free_busy(g, args.since, args.until, calendars=cals)
    print(json.dumps(fb, ensure_ascii=False, indent=2))
    return 0


def _cmd_create(args) -> int:
    g = GoogleClient(args.account)
    ev = create_event(
        g,
        summary=args.summary,
        start=args.start,
        end=args.end,
        calendar_id=args.calendar or 'primary',
        description=args.description,
        location=args.location,
        attendees=args.attendees.split(',') if args.attendees else None,
        all_day=args.all_day,
        send_updates=args.send_updates,
        add_meet=args.add_meet,
    )
    print(f'Created: {ev["summary"]}  id={ev["id"]}  → {ev.get("htmlLink")}')
    return 0


def _cmd_delete(args) -> int:
    g = GoogleClient(args.account)
    delete_event(g, args.id, calendar_id=args.calendar or 'primary', send_updates=args.send_updates)
    print(f'Deleted {args.id}')
    return 0


def _cmd_respond(args) -> int:
    g = GoogleClient(args.account)
    ev = respond_to_event(g, args.id, args.response, calendar_id=args.calendar or 'primary')
    print(f'Responded {args.response}: {ev["summary"]}')
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog='gcal_api')
    sub = parser.add_subparsers(dest='cmd', required=True)
    common = lambda sp: sp.add_argument('--account', required=True, choices=['bispro89', 'sikbrad'])

    sp = sub.add_parser('calendars'); common(sp)
    sp.add_argument('--no-holidays', action='store_true')
    sp.add_argument('--out')

    sp = sub.add_parser('events'); common(sp)
    sp.add_argument('--since', required=True, help='YYYY-MM-DD or ISO datetime (KST if no tz)')
    sp.add_argument('--until', required=True, help='YYYY-MM-DD or ISO datetime; bare date = end-of-day')
    sp.add_argument('--calendar', help='"all" (default), "primary", or comma-sep IDs')
    sp.add_argument('--q', help='Free-text search across event fields')
    sp.add_argument('--include-declined', action='store_true')
    sp.add_argument('--include-holidays', action='store_true')
    sp.add_argument('--out', help='JSON output path; omit to print summary')

    sp = sub.add_parser('freebusy'); common(sp)
    sp.add_argument('--since', required=True)
    sp.add_argument('--until', required=True)
    sp.add_argument('--calendars', help='Comma-sep calendar IDs; default primary')

    sp = sub.add_parser('create', help='Create a new event'); common(sp)
    sp.add_argument('--summary', required=True)
    sp.add_argument('--start', required=True, help='ISO datetime or YYYY-MM-DD (with --all-day)')
    sp.add_argument('--end', required=True)
    sp.add_argument('--calendar', help='Calendar ID (default primary)')
    sp.add_argument('--description')
    sp.add_argument('--location')
    sp.add_argument('--attendees', help='Comma-sep emails')
    sp.add_argument('--all-day', action='store_true')
    sp.add_argument('--add-meet', action='store_true', help='Add Google Meet conference')
    sp.add_argument('--send-updates', default='none', choices=['none', 'externalOnly', 'all'])

    sp = sub.add_parser('delete'); common(sp)
    sp.add_argument('--id', required=True)
    sp.add_argument('--calendar')
    sp.add_argument('--send-updates', default='none', choices=['none', 'externalOnly', 'all'])

    sp = sub.add_parser('respond', help='RSVP to an event'); common(sp)
    sp.add_argument('--id', required=True)
    sp.add_argument('--response', required=True, choices=['accepted', 'declined', 'tentative', 'needsAction'])
    sp.add_argument('--calendar')

    args = parser.parse_args(argv[1:])
    return {
        'calendars': _cmd_calendars,
        'events': _cmd_events,
        'freebusy': _cmd_freebusy,
        'create': _cmd_create,
        'delete': _cmd_delete,
        'respond': _cmd_respond,
    }[args.cmd](args)


if __name__ == '__main__':
    sys.exit(main(sys.argv))
