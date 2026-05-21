#!/usr/bin/env python3
"""
kmsg dump JSON에서 long-range 머지 artifact 제거.

증상: scroll-and-read 머지가 viewport 간 overlap 을 못 잡으면, 같은 메시지 run 이
멀리 떨어진 두 위치에 나타난다 (e.g. idx 58-67 ≡ idx 581-589). adjacent dedup
(kmsg_dedup.py)으로는 못 잡는다.

전략:
- body 들의 해시 시퀀스로 fingerprint 만들고
- 길이 W (>=5) 의 동일 시퀀스가 두 위치에 나타나면
  → 둘 중 정보 풍부한 쪽 (time_raw + concrete author 합쳐서) 살리고 다른 쪽 삭제
- 빈 body 가 포함된 run 은 노이즈가 많아 제외

W 5 이상으로만 검사 — 짧은 run 은 chat 에서 자연스럽게 반복될 수 있다.

usage: kmsg_dedup_long.py <in.json> <out.json>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def is_concrete_author(a: str) -> bool:
    return bool(a) and a != "(me)"


def msg_quality(m: dict) -> int:
    q = 0
    if m.get("time_raw"):
        q += 2
    if is_concrete_author(m.get("author", "")):
        q += 1
    return q


def merge_msg(keeper: dict, donor: dict) -> dict:
    out = dict(keeper)
    if not out.get("time_raw") and donor.get("time_raw"):
        out["time_raw"] = donor["time_raw"]
    if not is_concrete_author(out.get("author", "")) and is_concrete_author(
        donor.get("author", "")
    ):
        out["author"] = donor["author"]
    return out


def find_long_duplicate(
    msgs: list[dict], min_w: int = 5, max_w: int = 40
) -> tuple[int, int, int] | None:
    """가장 긴 long-range 중복 run 한 개 찾아 (i, j, w) 반환. 없으면 None."""
    n = len(msgs)
    bodies = [m.get("body", "") for m in msgs]
    # 빈 body 가 포함된 run은 검사 제외 — index set 으로 표시
    empty_idx = {i for i, b in enumerate(bodies) if not b}

    # body 별 occurrence index 모음
    occ: dict[str, list[int]] = {}
    for i, b in enumerate(bodies):
        if b and i not in empty_idx:
            occ.setdefault(b, []).append(i)

    # 두 번 이상 나타난 body 만 후보 시작점
    best = None
    for body, idxs in occ.items():
        if len(idxs) < 2:
            continue
        for a_pos in idxs:
            for b_pos in idxs:
                if b_pos <= a_pos:
                    continue
                # a_pos 와 b_pos 에서 동시에 시작하는 run 길이 측정
                w = 0
                while (
                    a_pos + w < b_pos
                    and b_pos + w < n
                    and bodies[a_pos + w] == bodies[b_pos + w]
                    and bodies[a_pos + w] != ""
                ):
                    w += 1
                if min_w <= w <= max_w:
                    if best is None or w > best[2]:
                        best = (a_pos, b_pos, w)
    return best


def dedup_long(messages: list[dict], min_w: int = 5) -> tuple[list[dict], int]:
    msgs = list(messages)
    removed = 0
    while True:
        found = find_long_duplicate(msgs, min_w=min_w)
        if found is None:
            break
        i, j, w = found
        sys.stderr.write(f"dup run w={w}: idx {i}..{i+w-1} ≡ idx {j}..{j+w-1}\n")
        # quality 비교
        qa = sum(msg_quality(msgs[i + k]) for k in range(w))
        qb = sum(msg_quality(msgs[j + k]) for k in range(w))
        if qa >= qb:
            for k in range(w):
                msgs[i + k] = merge_msg(msgs[i + k], msgs[j + k])
            del msgs[j : j + w]
        else:
            for k in range(w):
                msgs[j + k] = merge_msg(msgs[j + k], msgs[i + k])
            del msgs[i : i + w]
        removed += w
    return msgs, removed


def main() -> None:
    inp = Path(sys.argv[1])
    outp = Path(sys.argv[2])
    data = json.loads(inp.read_text(encoding="utf-8"))
    msgs = data.get("messages", [])
    before = len(msgs)
    cleaned, removed = dedup_long(msgs, min_w=int(sys.argv[3]) if len(sys.argv) > 3 else 5)
    data["messages"] = cleaned
    data["count"] = len(cleaned)
    outp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"before={before} after={len(cleaned)} removed={removed}")


if __name__ == "__main__":
    main()
