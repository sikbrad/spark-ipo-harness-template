#!/usr/bin/env python3
"""
kmsg dump JSON에서 머지 artifact 인 인접 중복 run 제거.

원인: scroll-and-read 시 두 viewport 가 (author, body, time_raw) 셋이 살짝 달라
overlap 탐지를 못 하면 같은 메시지 묶음(run) 이 두 번 prepend 된다.
보통 한쪽 run 의 time_raw 가 채워져 있고 다른쪽은 비어 있다 — KakaoTalk 이
adjacent same-author 묶음에서 시간 라벨을 하나만 보여주는 특성 때문.

알고리즘:
- 큰 윈도 W부터 작은 W까지 내려가며, 인접한 두 run [i..i+W] 와 [i+W..i+2W] 이
  (author, body) 만으로 같은지 검사.
- 같으면 time_raw 가 더 많이 채워진 쪽을 keep, 나머지는 drop.
- drop된 위치 이후로 인덱스를 갱신해서 계속 진행.

run 길이 1까지 내리면 흔한 chat artifact (같은 author 가 연속 같은 문구 두 번) 도
잘못 dedup 할 수 있어 W>=1 도 허용하되 time_raw 비대칭 조건을 더 엄격하게 본다.

usage: kmsg_dedup.py <in.json> <out.json>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def ab_key(m: dict) -> tuple[str, str]:
    """body 만으로 dedup key. author 는 viewport 마다 '(me)' vs 실제 발신자가
    바뀔 수 있어 신뢰 못 함."""
    return ("", m.get("body", ""))


def is_concrete_author(a: str) -> bool:
    return bool(a) and a != "(me)"


def run_quality(msgs: list[dict], start: int, length: int) -> tuple[int, int]:
    """(time_raw 채워진 개수, 구체적 author 개수) — 클수록 좋은 run."""
    t = sum(1 for j in range(start, start + length) if msgs[j].get("time_raw"))
    a = sum(1 for j in range(start, start + length) if is_concrete_author(msgs[j].get("author", "")))
    return (t, a)


def merge_msg(keeper: dict, donor: dict) -> dict:
    """keep keeper but pull in time_raw / concrete author from donor when better."""
    out = dict(keeper)
    if not out.get("time_raw") and donor.get("time_raw"):
        out["time_raw"] = donor["time_raw"]
    if not is_concrete_author(out.get("author", "")) and is_concrete_author(
        donor.get("author", "")
    ):
        out["author"] = donor["author"]
    return out


def dedup(messages: list[dict], max_window: int = 30) -> tuple[list[dict], int]:
    msgs = list(messages)
    removed_total = 0
    i = 0
    while i < len(msgs):
        replaced = False
        max_w = min(max_window, (len(msgs) - i) // 2)
        for w in range(max_w, 1, -1):
            a_keys = [ab_key(m) for m in msgs[i : i + w]]
            b_keys = [ab_key(m) for m in msgs[i + w : i + 2 * w]]
            if a_keys != b_keys:
                continue
            if any(k[1] == "" for k in a_keys):
                continue
            qa = run_quality(msgs, i, w)
            qb = run_quality(msgs, i + w, w)
            # 더 좋은 쪽을 keeper 로
            if qa >= qb:
                # keeper = i..i+w, donor = i+w..i+2w → 각 위치를 머지 후 donor 삭제
                for j in range(w):
                    msgs[i + j] = merge_msg(msgs[i + j], msgs[i + w + j])
                del msgs[i + w : i + 2 * w]
            else:
                for j in range(w):
                    msgs[i + w + j] = merge_msg(msgs[i + w + j], msgs[i + j])
                del msgs[i : i + w]
            removed_total += w
            replaced = True
            break

        # W=1: 단일 메시지 인접 중복 (같은 body, 다른 author/time_raw 라도)
        if not replaced and i + 1 < len(msgs):
            a = msgs[i]
            b = msgs[i + 1]
            if ab_key(a) == ab_key(b) and a.get("body", ""):
                ta, tb = a.get("time_raw") or "", b.get("time_raw") or ""
                aa, ab2 = a.get("author", ""), b.get("author", "")
                # 두 메시지가 진짜 두 번 보낸 것일 가능성도 있음 — 매우 보수적으로:
                # 한쪽만 time_raw 있거나 한쪽만 concrete author 면 머지
                only_one_time = bool(ta) ^ bool(tb)
                only_one_author = is_concrete_author(aa) ^ is_concrete_author(ab2)
                # same_time + same author → 진짜 두 번 보낸 거. dedup 안 함.
                if only_one_time or only_one_author:
                    keeper_i = i if (bool(ta) or is_concrete_author(aa)) else i + 1
                    donor_i = i + 1 if keeper_i == i else i
                    msgs[keeper_i] = merge_msg(msgs[keeper_i], msgs[donor_i])
                    del msgs[donor_i]
                    removed_total += 1
                    replaced = True
        if not replaced:
            i += 1
    return msgs, removed_total


def main() -> None:
    inp = Path(sys.argv[1])
    outp = Path(sys.argv[2])
    data = json.loads(inp.read_text(encoding="utf-8"))
    msgs = data.get("messages", [])
    before = len(msgs)
    cleaned, removed = dedup(msgs)
    data["messages"] = cleaned
    data["count"] = len(cleaned)
    outp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"before={before} after={len(cleaned)} removed={removed}")


if __name__ == "__main__":
    main()
