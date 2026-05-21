#!/usr/bin/env python3
"""
kmsg 기반 카톡 채팅방 전체 dump.

전제: kmsg가 한 번에 보여주는 건 카톡 윈도우에 현재 로드된 메시지뿐 (~40개).
전략: 윈도우 위에 마우스 두고 Quartz scroll-wheel 이벤트로 채팅 영역을 위로
스크롤하면 KakaoTalk이 lazy-load로 옛 메시지 가져옴. read → scroll up → read 반복하며
새로 등장한 prefix를 누적 리스트 앞쪽에 prepend. 더 이상 새로운 게 안 나오면 top.

호출: /usr/bin/python3 kmsg_scroll_dump.py "<chat title substring>" <out.json>
시스템 python3 — pyobjc(Quartz) 모듈 필요. brew python3엔 없음.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import Quartz


def get_window_bounds(title_contains: str) -> tuple[int, int, int, int] | None:
    """KakaoTalk 채팅 윈도우 bounds (x, y, w, h) on-screen 좌표."""
    opts = (
        Quartz.kCGWindowListOptionOnScreenOnly
        | Quartz.kCGWindowListExcludeDesktopElements
    )
    infos = Quartz.CGWindowListCopyWindowInfo(opts, Quartz.kCGNullWindowID)
    for w in infos:
        if w.get("kCGWindowOwnerName", "") != "KakaoTalk":
            continue
        title = w.get("kCGWindowName", "") or ""
        if title_contains in title:
            b = w["kCGWindowBounds"]
            return (int(b["X"]), int(b["Y"]), int(b["Width"]), int(b["Height"]))
    return None


def activate_kakao() -> None:
    subprocess.run(
        ["osascript", "-e", 'tell application "KakaoTalk" to activate'],
        check=False,
        capture_output=True,
    )


def move_mouse(x: int, y: int) -> None:
    ev = Quartz.CGEventCreateMouseEvent(
        None, Quartz.kCGEventMouseMoved, (x, y), Quartz.kCGMouseButtonLeft
    )
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)


def scroll_wheel(lines: int, repeats: int = 1, delay: float = 0.12) -> None:
    """lines>0 이면 위로 스크롤(=옛 메시지 노출)."""
    for _ in range(repeats):
        ev = Quartz.CGEventCreateScrollWheelEvent(
            None, Quartz.kCGScrollEventUnitLine, 1, lines
        )
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
        time.sleep(delay)


def read_chat(chat: str) -> list[dict]:
    """kmsg read JSON → message list."""
    res = subprocess.run(
        ["kmsg", "read", chat, "--limit", "5000", "--json", "--keep-window"],
        capture_output=True,
        text=True,
        timeout=180,
    )
    if res.returncode != 0:
        sys.stderr.write(f"kmsg read failed: {res.stderr[:500]}\n")
        return []
    try:
        data = json.loads(res.stdout)
    except json.JSONDecodeError as e:
        sys.stderr.write(f"json decode failed: {e}; stdout head={res.stdout[:200]!r}\n")
        return []
    return data.get("messages", [])


def msg_key(m: dict) -> str:
    """overlap detection 은 body 만 사용 — author / time_raw 는 viewport 마다
    표시 정책이 달라 (e.g. KakaoTalk이 동일 author 연속 메시지의 시간 라벨을
    그룹의 마지막에만 노출, scroll 위치에 따라 그룹 경계가 바뀜) 불안정."""
    return m.get("body", "")


def find_overlap_split(new: list[dict], acc: list[dict]) -> int:
    """
    new(현재 viewport, 위→아래 순) 와 acc(누적, 위→아래 순) 의 overlap 찾기.
    new 의 suffix가 acc 의 prefix와 매칭되는 지점 찾아 'prepend 길이' 반환.
    매칭 못 찾으면 new 전체 prepend (len(new) 반환). acc 비어있으면 len(new).

    반환: new[0:k] 를 acc 앞에 붙이면 된다 (k 길이만큼).
    """
    if not acc:
        return len(new)
    new_keys = [msg_key(m) for m in new]
    acc_keys = [msg_key(m) for m in acc]
    # 가장 긴 overlap부터 시도 (new의 끝 ↔ acc의 시작)
    max_ov = min(len(new), len(acc))
    for ov in range(max_ov, 0, -1):
        # body가 비어있는 msg는 비교에서 빼면 좋지만 일단 그대로 매칭
        if new_keys[-ov:] == acc_keys[:ov]:
            return len(new) - ov
    return len(new)


def merge_into_acc(new: list[dict], acc: list[dict], overlap: int) -> list[dict]:
    """overlap 위치에서 new[k:] 와 acc[0:overlap] 같다. acc 의 그 부분에
    new 의 더 풍부한 author/time_raw 정보가 있다면 머지."""
    if overlap == 0:
        return new + acc
    new_prefix = new[: len(new) - overlap]
    new_overlap = new[len(new) - overlap :]
    merged_overlap: list[dict] = []
    for new_m, acc_m in zip(new_overlap, acc[:overlap]):
        merged = dict(acc_m)
        if not merged.get("time_raw") and new_m.get("time_raw"):
            merged["time_raw"] = new_m["time_raw"]
        cur_author = merged.get("author", "")
        new_author = new_m.get("author", "")
        if (not cur_author or cur_author == "(me)") and new_author and new_author != "(me)":
            merged["author"] = new_author
        merged_overlap.append(merged)
    return new_prefix + merged_overlap + acc[overlap:]


def dump_chat(chat: str, out_path: Path, max_idle: int = 4) -> None:
    bounds = get_window_bounds(chat)
    if bounds is None:
        # 윈도우 아직 안 열렸을 수 있음 — 한 번 read 호출해서 열기
        sys.stderr.write("opening chat window via kmsg read…\n")
        read_chat(chat)
        time.sleep(0.5)
        bounds = get_window_bounds(chat)
    if bounds is None:
        sys.stderr.write(f"window for {chat!r} not found\n")
        sys.exit(2)
    x, y, w, h = bounds
    cx, cy = x + w // 2, y + h // 2
    sys.stderr.write(f"window bounds={bounds} center=({cx},{cy})\n")

    activate_kakao()
    time.sleep(0.8)
    move_mouse(cx, cy)
    time.sleep(0.3)
    # 시작 시 맨 아래(최신)로: 큰 scroll-down 으로 충분히 끝까지 보낸다.
    sys.stderr.write("scrolling to bottom first (large down-wheel)…\n")
    scroll_wheel(lines=-20, repeats=40, delay=0.04)
    time.sleep(0.8)

    accumulated: list[dict] = []
    idle = 0
    iteration = 0
    while True:
        iteration += 1
        msgs = read_chat(chat)
        if not msgs:
            sys.stderr.write(f"[iter {iteration}] empty read, idle++\n")
            idle += 1
        else:
            overlap = len(msgs) - find_overlap_split(msgs, accumulated)
            k = len(msgs) - overlap
            accumulated = merge_into_acc(msgs, accumulated, overlap)
            sys.stderr.write(
                f"[iter {iteration}] viewport={len(msgs)} overlap={overlap} prepended={k} total={len(accumulated)}\n"
            )
            if k == 0:
                idle += 1
            else:
                idle = 0
                # incremental save
                out_path.write_text(
                    json.dumps(
                        {
                            "chat": chat,
                            "count": len(accumulated),
                            "iteration": iteration,
                            "messages": accumulated,
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )
        if idle >= max_idle:
            sys.stderr.write(f"top reached after {idle} idle iters, stopping\n")
            break
        # KakaoTalk이 다른 윈도우 frontmost되면 scroll이 다른 데로 가니 재활성화
        activate_kakao()
        time.sleep(0.3)
        # bounds가 바뀌었을 수도 있으니 refresh
        nb = get_window_bounds(chat)
        if nb:
            nx, ny, nw, nh = nb
            cx, cy = nx + nw // 2, ny + nh // 2
        move_mouse(cx, cy)
        time.sleep(0.15)
        # viewport 의 1/2 ~ 2/3 정도 위로 스크롤 — 매 iter 마다 새 메시지를
        # 확보하되 직전 viewport 와 충분히 겹쳐서 overlap detection 작동.
        # KakaoTalk viewport 는 80~120 msgs 정도, line 단위로 5-7개 msg 이동.
        scroll_wheel(lines=10, repeats=10, delay=0.13)
        time.sleep(0.8)  # lazy load 대기

    out_path.write_text(
        json.dumps(
            {
                "chat": chat,
                "count": len(accumulated),
                "iteration": iteration,
                "messages": accumulated,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"OK: {len(accumulated)} messages → {out_path}")


def main() -> None:
    if len(sys.argv) < 3:
        print("usage: kmsg_scroll_dump.py <chat-title-substring> <out.json> [max-idle]")
        sys.exit(1)
    chat = sys.argv[1]
    out = Path(sys.argv[2])
    max_idle = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    out.parent.mkdir(parents=True, exist_ok=True)
    dump_chat(chat, out, max_idle=max_idle)


if __name__ == "__main__":
    main()
