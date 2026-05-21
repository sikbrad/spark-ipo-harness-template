#!/usr/bin/env python3
"""
dump JSON sanity check — 인접 메시지 사이 시간 단조성, 중복 패턴 탐지.
gap 의심 지점 리포트.

usage: kmsg_sanity.py <dump.json>
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


TIME_RE = re.compile(r"^(?P<h>\d{1,2}):(?P<m>\d{2})(?:\s*(?P<ampm>AM|PM))?$", re.I)


def parse_time(raw: str):
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
        else:
            h = h if h == 12 else h + 12
    return (h, mm)


def main() -> None:
    path = Path(sys.argv[1])
    data = json.loads(path.read_text(encoding="utf-8"))
    msgs = data.get("messages", [])
    print(f"messages: {len(msgs)}")

    # duplicate-window detection: (author, body) consecutive duplicates
    dup_windows = 0
    for i in range(1, len(msgs)):
        if (msgs[i]["author"], msgs[i].get("body", "")) == (
            msgs[i - 1]["author"],
            msgs[i - 1].get("body", ""),
        ) and msgs[i].get("body", ""):
            dup_windows += 1
    print(f"consecutive identical (author,body) lines: {dup_windows}")

    # time monotonicity within day (assume same day; flag big jumps)
    last_hm = None
    big_back_jumps = []
    for i, m in enumerate(msgs):
        t = parse_time(m.get("time_raw", ""))
        if t is None:
            continue
        if last_hm is not None:
            # 시간이 뒤로 점프 (현재 시각 < 이전) — 날짜 경계 OR gap
            cur = t[0] * 60 + t[1]
            prev = last_hm[0] * 60 + last_hm[1]
            if cur < prev:
                back = prev - cur
                big_back_jumps.append((i, last_hm, t, back))
        last_hm = t

    print(f"backward time jumps (likely day boundaries or gaps): {len(big_back_jumps)}")
    for idx, lhm, t, back in big_back_jumps[:20]:
        print(
            f"  idx={idx} prev={lhm[0]:02d}:{lhm[1]:02d} -> cur={t[0]:02d}:{t[1]:02d} (back {back}m)"
        )

    # show first/last
    print("\nfirst 5:")
    for m in msgs[:5]:
        print(f"  {m.get('time_raw',''):>8s} | {m['author']} | {m.get('body','')[:60]}")
    print("\nlast 5:")
    for m in msgs[-5:]:
        print(f"  {m.get('time_raw',''):>8s} | {m['author']} | {m.get('body','')[:60]}")


if __name__ == "__main__":
    main()
