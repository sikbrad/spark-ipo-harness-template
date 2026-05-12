"""Scan all Teams chats for two pending categories.

Category A — Asked-Me-Unanswered: last message was from someone else AND
that last message looks like a question/request directed at me, AND I
haven't replied since.

Category B — My-Request-No-Reply: my last message in the chat looks like a
question/request, no reply has arrived since, and the wait is non-trivial
(>1h) so we don't list freshly sent things.
"""

import sys, re
sys.path.insert(0, 'proc/lib')

import re as _re
import json as _json
import urllib.parse as _up
from datetime import datetime, timedelta
from msgraph import GraphClient
from teams_graph import chat_list, KST, _msg_to_dict  # type: ignore


def chat_message_link(chat_id: str, msg_id: str) -> str:
    """Build a Teams deep-link to a specific message in a personal/group chat.

    Graph's `webUrl` is null for chat messages; this synthesizes the same
    https://teams.microsoft.com/l/message/... format that Teams itself uses.
    """
    if not chat_id or not msg_id:
        return ''
    ctx = _up.quote(_json.dumps({"contextType": "chat"}, separators=(',', ':')), safe='')
    return f"https://teams.microsoft.com/l/message/{_up.quote(chat_id, safe='')}/{msg_id}?context={ctx}"

LOOKBACK_DAYS = 21
MIN_WAIT_FOR_B = timedelta(hours=1)

# Substrings that strongly signal a question/request anywhere in the message.
Q_SUBSTR = [
    '?', '？',
    '해주세요', '해 주세요', '해주실', '해주시', '해 주시', '해주시면', '해주실래',
    '부탁', '요청', '확인', '검토', '알려주', '알려 주', '알려줘', '알려주실',
    '필요', '가능하', '괜찮', '어떠',
    '언제', '어떻게', '어떤', '얼마나', '왜요', '어디',
    '주실 수', '주시면', '주시기', '주실래', '주실까',
    'please', 'could you', 'can you', 'would you', 'let me know',
    'pls', 'plz',
]

# Sentence-ending Korean question/soft-request patterns. Checked against
# each clause (split by . ! ? \n) trimmed of trailing punctuation/spaces.
Q_ENDS = (
    '까요', '까', '나요', '는지', '을까', '를까',
    '죠', '쥬', '죵', '쪼',
    '래요', '래', '려고',
    '인가요', '인지', '인가',
    '되나', '되요', '될까', '될까요',
    '봐주', '봐 주', '봐주실',
)

NEG_PATTERNS = [
    '감사', '고맙', '확인했', '알겠', '넵', '네!', '넹', '오케이', 'ok!',
    '수고하', '좋습니다', '좋아요', '잘했', 'thank',
]

_CLAUSE_SPLIT = _re.compile(r'[\.!?\n…ㆍ]+')


def _has_ending(clause: str) -> bool:
    c = clause.rstrip(' .!?…~ㆍ・,，。、ᆢㅜㅠ').lower()
    if not c:
        return False
    return any(c.endswith(end) for end in Q_ENDS)


def looks_like_request(text: str) -> bool:
    if not text:
        return False
    t = text.strip().lower()
    if any(p in t for p in Q_SUBSTR):
        return True
    # check each clause's tail
    for clause in _CLAUSE_SPLIT.split(t):
        if _has_ending(clause):
            # avoid false-positive on pure ack clauses
            if any(n in clause for n in NEG_PATTERNS):
                continue
            return True
    return False


def chat_messages_raw(g, chat_id: str, since: datetime, page_size: int = 30, max_pages: int = 2) -> list[dict]:
    """Like teams_graph.chat_messages but keeps webUrl from the raw payload."""
    out: list[dict] = []
    pages = 0
    url = f'/me/chats/{chat_id}/messages'
    next_link = None
    params = {'$top': page_size}
    stop = False
    while True:
        data = g.get(next_link or url, params=None if next_link else params)
        for raw in data.get('value', []):
            d = _msg_to_dict(raw)
            if not d:
                continue
            if d['ts'] and d['ts'] < since:
                stop = True
                break
            d['webUrl'] = raw.get('webUrl') or ''
            out.append(d)
        if stop:
            break
        next_link = data.get('@odata.nextLink')
        pages += 1
        if not next_link or pages >= max_pages:
            break
    out.sort(key=lambda e: e['ts'] or datetime.min.replace(tzinfo=KST))
    return out


def first_line(text: str, limit: int = 120) -> str:
    s = (text or '').replace('\n', ' ⏎ ').strip()
    return s[:limit] + ('…' if len(s) > limit else '')


def fmt_age(ts: datetime, now: datetime) -> str:
    d = now - ts
    if d.days >= 1:
        return f"{d.days}d"
    h = d.seconds // 3600
    if h >= 1:
        return f"{h}h"
    m = d.seconds // 60
    return f"{m}m"


def main() -> int:
    g = GraphClient()
    me = g.get('/me')
    my_id = me['id']
    my_name = me.get('displayName') or ''
    now = datetime.now(KST)
    since = now - timedelta(days=LOOKBACK_DAYS)
    print(f"me={my_name} oid={my_id}")
    print(f"window: last {LOOKBACK_DAYS}d  ({since.strftime('%Y-%m-%d %H:%M')} ~ {now.strftime('%Y-%m-%d %H:%M')} KST)")

    chats = chat_list(g, top=50)
    print(f"chats fetched: {len(chats)}")

    cat_a: list[dict] = []  # asked-me, unanswered
    cat_b: list[dict] = []  # i-asked, no reply

    for c in chats:
        if not c.get('last_ts') or c['last_ts'] < since:
            continue
        if (c.get('kind') or '') not in ('oneOnOne', 'group', 'meeting'):
            continue
        # skip self-chat
        if c.get('kind') == 'oneOnOne' and not c.get('last_who') and c.get('last_by_me'):
            continue

        # Pull last ~20 messages of the chat for context (with webUrl)
        try:
            msgs = chat_messages_raw(g, c['chat_id'], since=since, page_size=30, max_pages=2)
        except Exception as e:
            print(f"  skip {c['chat_id']}: {e}")
            continue
        if not msgs:
            continue
        last = msgs[-1]
        last_is_me = (last.get('who') or '') == my_name or c.get('last_by_me')

        chat_label = c.get('name') or c.get('last_who') or '(unnamed)'
        kind = c.get('kind') or ''

        # Resolve DM partner if chat has no topic
        partner = ''
        if not c.get('name') and kind == 'oneOnOne':
            try:
                mem = g.get(f'/me/chats/{c["chat_id"]}/members')
                others = [m.get('displayName') for m in mem.get('value', []) if (m.get('userId') or '') != my_id]
                partner = ', '.join(x for x in others if x)
            except Exception:
                partner = ''
        display_chat = c.get('name') or partner or c.get('last_who') or '(unnamed)'

        link = chat_message_link(c['chat_id'], last.get('id') or '')

        if not last_is_me:
            if looks_like_request(last.get('text') or ''):
                cat_a.append({
                    'chat': display_chat,
                    'kind': kind,
                    'who': last.get('who') or '',
                    'ts': last['ts'],
                    'text': last.get('text') or '',
                    'age': fmt_age(last['ts'], now),
                    'url': link,
                })
        else:
            wait = now - last['ts']
            if wait < MIN_WAIT_FOR_B:
                continue
            if not looks_like_request(last.get('text') or ''):
                continue
            cat_b.append({
                'chat': display_chat,
                'kind': kind,
                'ts': last['ts'],
                'text': last.get('text') or '',
                'age': fmt_age(last['ts'], now),
                'url': link,
            })

    cat_a.sort(key=lambda x: x['ts'], reverse=True)
    cat_b.sort(key=lambda x: x['ts'], reverse=True)

    # write a markdown report next to this script
    md_path = __file__.replace('.py', '.md')
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(f"# Teams Pending — {now.strftime('%Y-%m-%d %H:%M KST')}\n\n")
        f.write(f"- me: {my_name}\n- window: last {LOOKBACK_DAYS}d\n- chats scanned: {len(chats)}\n\n")
        f.write(f"## A. 남이 물어봤는데 내가 미답 — {len(cat_a)}건\n\n")
        f.write("| # | 시각 | 대기 | 채팅방 | 보낸 사람 | 본문 | 링크 |\n|---|---|---|---|---|---|---|\n")
        for i, r in enumerate(cat_a, 1):
            when = r['ts'].strftime('%m-%d %H:%M')
            txt = first_line(r['text'], limit=140).replace('|', '\\|')
            link = f"[열기]({r['url']})" if r['url'] else ''
            f.write(f"| {i} | {when} | {r['age']} | {r['chat']} | {r['who']} | {txt} | {link} |\n")
        f.write(f"\n## B. 내가 요청·질문 후 응답 없음 — {len(cat_b)}건\n\n")
        f.write("| # | 시각 | 대기 | 상대 | 본문 | 링크 |\n|---|---|---|---|---|---|\n")
        for i, r in enumerate(cat_b, 1):
            when = r['ts'].strftime('%m-%d %H:%M')
            txt = first_line(r['text'], limit=140).replace('|', '\\|')
            link = f"[열기]({r['url']})" if r['url'] else ''
            f.write(f"| {i} | {when} | {r['age']} | {r['chat']} | {txt} | {link} |\n")
    print(f"\n(markdown saved → {md_path})")

    print()
    print("=" * 80)
    print(f"[A] 남이 나에게 물어봤는데 내가 미답 — {len(cat_a)}건")
    print("=" * 80)
    if not cat_a:
        print("  (없음)")
    for i, r in enumerate(cat_a, 1):
        when = r['ts'].strftime('%m-%d %H:%M')
        chat = r['chat'][:24]
        who = r['who'][:14]
        print(f"{i:2}. [{when}] ({r['age']:>4}) {chat:24} | {who:14} | {first_line(r['text'])}")
        if r.get('url'):
            print(f"     {r['url']}")

    print()
    print("=" * 80)
    print(f"[B] 내가 요청·질문했는데 응답 없음 — {len(cat_b)}건")
    print("=" * 80)
    if not cat_b:
        print("  (없음)")
    for i, r in enumerate(cat_b, 1):
        when = r['ts'].strftime('%m-%d %H:%M')
        chat = r['chat'][:24]
        print(f"{i:2}. [{when}] ({r['age']:>4}) {chat:24} | {first_line(r['text'])}")
        if r.get('url'):
            print(f"     {r['url']}")

    return 0


if __name__ == '__main__':
    sys.exit(main())
