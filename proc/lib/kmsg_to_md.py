#!/usr/bin/env python3
"""
kmsg dump JSON → 날짜별 .md.

전제:
- 메시지는 위→아래(=옛→최신) 순서로 정렬돼 있음.
- time_raw 는 "11:11" / "3:09 PM" / "" 중 하나. 절대 날짜 없음.
- 따라서 마지막 메시지를 "오늘"(anchor_date)로 가정하고, 시간 역행이 일어나면
  하루 전으로 거슬러 올라간다.

휴리스틱:
- AM/PM 명시되면 그대로 24h로 환산.
- AM/PM 없으면 "오늘"의 hour 패턴 가정. KakaoTalk은 보통 같은 날 메시지에 AM/PM
  표시를 생략하니, AM/PM 없는 묶음 = 같은 날일 가능성이 높음. 단, 시간이 감소하면
  날짜 경계로 간주.
- 시간 자체가 비어있는 메시지(연속된 짧은 답장)는 직전 메시지의 시각을 승계.

usage: kmsg_to_md.py <input.json> <out_dir> [--anchor YYYY-MM-DD]
"""

from __future__ import annotations

import argparse
import json
import re
from collections import OrderedDict
from datetime import date, datetime, timedelta
from pathlib import Path


TIME_RE = re.compile(r"^(?P<h>\d{1,2}):(?P<m>\d{2})(?:\s*(?P<ampm>AM|PM))?$", re.I)


def parse_time(raw: str) -> tuple[int, int, str | None] | None:
    """raw → (hour24, minute, ampm_marker or None). 못 읽으면 None."""
    if not raw:
        return None
    m = TIME_RE.match(raw.strip())
    if not m:
        return None
    h = int(m.group("h"))
    mm = int(m.group("m"))
    ap = m.group("ampm")
    if ap:
        ap = ap.upper()
        if ap == "AM":
            h = 0 if h == 12 else h
        else:  # PM
            h = h if h == 12 else h + 12
        return (h, mm, ap)
    return (h, mm, None)


def assign_dates(messages: list[dict], anchor: date) -> list[dict]:
    """
    뒤(최신)에서 앞(옛)으로 거슬러 올라가며 날짜 부여.
    시간이 '커지면'(앞쪽 메시지 시간이 뒤쪽보다 크다 = 시간 역행 아님)
    이전 날일 가능성. 단, 비교는 24h hour:min 으로 한다.

    규칙:
    - cur_date 시작값 = anchor
    - 뒤에서부터 i 진행하며 현재 메시지의 시간을 t_i, 이미 본 직후(미래 쪽)
      메시지의 시간을 t_next 라 할 때:
        if t_i > t_next: 이건 '어제'다 (시간이 앞으로 갈수록 더 크다 = 하루 전).
                       cur_date -= 1; 그리고 이 메시지를 cur_date 에 배정.
        else: 같은 날.
    - 시간이 None 이면 t_next 와 같은 날로 간주.
    """
    if not messages:
        return []

    cur_date = anchor
    last_t: tuple[int, int, str | None] | None = None  # (h24, m, ampm)

    # day-boundary 임계값(분). 4시간 이하의 backward jump는 무시 — 같은 날 안에서
    # 시간 표시가 살짝 어긋난 것(예: 카톡이 분 정렬 안 함, 12h↔24h 오인) 으로 본다.
    THRESH_MIN = 240

    out: list[dict] = []
    # 뒤에서부터 처리 — 인덱스 N-1, N-2, ..., 0
    for m in reversed(messages):
        t = parse_time(m.get("time_raw", ""))
        if t is None:
            dt = m.copy()
            dt["date"] = cur_date.isoformat()
            dt["hm"] = ""
            out.append(dt)
            continue
        h, mi, ap = t
        if last_t is not None:
            lh, lm, lap = last_t
            cur_min = h * 60 + mi
            last_min = lh * 60 + lm
            # 현재(과거쪽)가 last_t(미래쪽) 보다 시간상 '나중'으로 보이면 = 이전 날.
            forward = cur_min - last_min  # >0 = 과거쪽이 더 늦은 시각 → 어제
            if forward > THRESH_MIN:
                cur_date = cur_date - timedelta(days=1)
            # AM/PM 표시가 둘 다 있고, 현재가 PM 인데 미래쪽이 AM 이면 day boundary (아침→밤 거꾸로)
            elif ap == "PM" and lap == "AM":
                cur_date = cur_date - timedelta(days=1)
        last_t = (h, mi, ap)
        dt = m.copy()
        dt["date"] = cur_date.isoformat()
        dt["hm"] = f"{h:02d}:{mi:02d}"
        out.append(dt)

    out.reverse()
    return out


def group_by_date(messages: list[dict]) -> "OrderedDict[str, list[dict]]":
    g: OrderedDict[str, list[dict]] = OrderedDict()
    for m in messages:
        d = m.get("date", "unknown")
        g.setdefault(d, []).append(m)
    return g


def render_md(date_str: str, msgs: list[dict], chat_name: str) -> str:
    lines = [
        f"# {chat_name} — {date_str}",
        "",
        f"_총 {len(msgs)}개 메시지_",
        "",
    ]
    last_author = None
    for m in msgs:
        author = m.get("author") or "(?)"
        body = (m.get("body") or "").rstrip()
        hm = m.get("hm") or m.get("time_raw") or ""
        # author label 변하면 헤더 한 줄
        if author != last_author:
            who = "**나**" if author == "(me)" else f"**{author}**"
            lines.append("")
            lines.append(f"### {who}")
            last_author = author
        time_prefix = f"`{hm}` " if hm else ""
        # 본문 멀티라인 안전 처리
        body_safe = body.replace("\r\n", "\n").replace("\r", "\n")
        body_lines = body_safe.split("\n") if body_safe else [""]
        for i, bl in enumerate(body_lines):
            if i == 0:
                lines.append(f"- {time_prefix}{bl}")
            else:
                lines.append(f"  {bl}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path)
    ap.add_argument("out_dir", type=Path)
    ap.add_argument("--anchor", default=None, help="YYYY-MM-DD; default=today")
    ap.add_argument("--chat", default=None, help="chat name override")
    args = ap.parse_args()

    data = json.loads(args.input.read_text(encoding="utf-8"))
    msgs = data.get("messages", [])
    chat_name = args.chat or data.get("chat") or "chat"

    anchor = (
        datetime.strptime(args.anchor, "%Y-%m-%d").date()
        if args.anchor
        else date.today()
    )

    dated = assign_dates(msgs, anchor)
    groups = group_by_date(dated)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    for d, ms in groups.items():
        out = args.out_dir / f"{d}.md"
        out.write_text(render_md(d, ms, chat_name), encoding="utf-8")
        print(f"wrote {out} ({len(ms)} msgs)")

    # index
    idx_lines = [f"# {chat_name} — index", "", f"총 {len(dated)} 메시지, {len(groups)}일분", ""]
    for d, ms in sorted(groups.items()):
        idx_lines.append(f"- [{d}]({d}.md) — {len(ms)}개")
    (args.out_dir / "INDEX.md").write_text("\n".join(idx_lines) + "\n", encoding="utf-8")
    print(f"wrote {args.out_dir / 'INDEX.md'}")


if __name__ == "__main__":
    main()
