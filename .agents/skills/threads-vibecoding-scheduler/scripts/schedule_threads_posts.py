from __future__ import annotations

import argparse
import calendar
import json
import random
import subprocess
import time
from datetime import date, datetime
from pathlib import Path


ROOT = Path.cwd()
DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def parse_blocks(path: Path) -> list[str]:
    blocks = [block.strip() for block in path.read_text(encoding="utf-8").split("---") if block.strip()]
    if not blocks:
        raise ValueError(f"{path.name}: no post blocks found")
    for index, block in enumerate(blocks, 1):
        if len(block) > 500:
            raise ValueError(f"{path.name}: block {index} exceeds 500 chars ({len(block)})")
    return blocks


def label_for(path: Path) -> str:
    y, m, d = [int(part) for part in path.stem.split("-")]
    dt = date(y, m, d)
    return f"{DAY_NAMES[dt.weekday()]}, {calendar.month_name[m]} {d}, {y}"


def parse_time(value: str) -> tuple[str, str]:
    hour, minute = value.split(":", 1)
    hour_i = int(hour)
    minute_i = int(minute)
    if not 0 <= hour_i <= 23 or not 0 <= minute_i <= 59:
        raise ValueError("--time must be HH:MM")
    return f"{hour_i:02d}", f"{minute_i:02d}"


def minutes_for(value: str) -> int:
    hour, minute = parse_time(value)
    return int(hour) * 60 + int(minute)


def format_minutes(value: int) -> str:
    return f"{value // 60:02d}:{value % 60:02d}"


def pick_time(path: Path, fixed_time: str, time_window: str | None, seed: str | None) -> str:
    if not time_window:
        return fixed_time
    start_text, end_text = time_window.split("-", 1)
    start = minutes_for(start_text)
    end = minutes_for(end_text)
    if end < start:
        raise ValueError("--time-window end must be >= start")
    rng = random.Random(f"{seed or ''}:{path.name}")
    return format_minutes(rng.randint(start, end))


def run_code(session: str, blocks: list[str], label: str, hour: str, minute: str, root: Path) -> str:
    payload = json.dumps({"blocks": blocks, "label": label, "hour": hour, "minute": minute}, ensure_ascii=False)
    code = f"""
async page => {{
  const payload = {payload};
  const blocks = payload.blocks;
  const label = payload.label;

  async function clickTopModalMore() {{
    const buttons = await page.getByRole("button", {{ name: "More" }}).all();
    const viewport = page.viewportSize() || {{ height: 10000 }};
    let best = null;
    let bestBox = null;
    for (let i = buttons.length - 1; i >= 0; i--) {{
      const box = await buttons[i].boundingBox().catch(() => null);
      if (box && box.x > 900 && box.y > 80 && box.y < viewport.height - 40) {{
        if (!bestBox || box.x > bestBox.x) {{
          best = buttons[i];
          bestBox = box;
        }}
      }}
    }}
    if (best) {{
      await best.click();
      return;
    }}
    throw new Error("compose More button not found");
  }}

  async function openComposer() {{
    await page.goto("https://www.threads.com/", {{ waitUntil: "domcontentloaded" }});
    await page.waitForTimeout(1200);
    await page.getByRole("button", {{ name: "Create" }}).last().click({{ timeout: 10000 }});
    await page.getByRole("heading", {{ name: "New thread" }}).waitFor({{ timeout: 10000 }});
  }}

  async function fillChain() {{
    await page.getByRole("textbox", {{ name: /Empty text field/ }}).last().waitFor({{ timeout: 10000 }});
    let boxes = await page.getByRole("textbox", {{ name: /Empty text field/ }}).all();
    if (!boxes.length) throw new Error("compose textbox not found");
    await boxes[boxes.length - 1].fill(blocks[0]);
    await page.waitForTimeout(400);
    for (const block of blocks.slice(1)) {{
      await page.getByRole("button", {{ name: "Add to thread" }}).click({{ timeout: 8000 }});
      await page.waitForTimeout(400);
      await page.getByRole("textbox", {{ name: /Empty text field/ }}).last().waitFor({{ timeout: 10000 }});
      boxes = await page.getByRole("textbox", {{ name: /Empty text field/ }}).all();
      if (!boxes.length) throw new Error("chain textbox not found");
      await boxes[boxes.length - 1].fill(block);
      await page.waitForTimeout(400);
    }}
  }}

  async function setSchedule() {{
    await clickTopModalMore();
    await page.getByRole("menuitem", {{ name: "Schedule..." }}).click({{ timeout: 8000 }});
    let dayCell = page.getByRole("gridcell", {{ name: label }});
    for (let attempt = 0; attempt < 12; attempt++) {{
      if (await dayCell.count()) break;
      const nextButton = page.getByRole("button", {{ name: "Next Month" }});
      await nextButton.waitFor({{ timeout: 8000 }});
      await nextButton.evaluate((el) => el.click());
      await page.waitForTimeout(400);
      dayCell = page.getByRole("gridcell", {{ name: label }});
    }}
    await dayCell.waitFor({{ timeout: 8000 }});
    await dayCell.scrollIntoViewIfNeeded();
    const dayBox = await dayCell.boundingBox();
    if (!dayBox) throw new Error("schedule day cell not visible");
    await page.mouse.click(dayBox.x + dayBox.width / 2, dayBox.y + dayBox.height / 2);
    await page.waitForTimeout(300);
    await page.locator('input[type="text"]').last().waitFor({{ timeout: 8000 }});
    const textInputs = await page.locator('input[type="text"]').all();
    const visibleInputs = [];
    for (const input of textInputs) {{
      const box = await input.boundingBox().catch(() => null);
      if (box && box.width > 10 && box.height > 10) visibleInputs.push(input);
    }}
    if (visibleInputs.length < 2) throw new Error("schedule time inputs not found");
    await visibleInputs[visibleInputs.length - 2].fill(payload.hour);
    await visibleInputs[visibleInputs.length - 1].fill(payload.minute);
    await page.waitForFunction(() => {{
      const buttons = Array.from(document.querySelectorAll('[role="button"]'));
      return buttons.some((el) => {{
        const text = (el.textContent || "").trim();
        const disabled = el.getAttribute("aria-disabled") === "true" || el.hasAttribute("disabled");
        return text === "Done" && !disabled;
      }});
    }}, null, {{ timeout: 8000 }});
    await page.getByRole("button", {{ name: "Done", exact: true }}).click({{ timeout: 8000, force: true }});
    await page.waitForTimeout(700);
  }}

  await openComposer();
  await fillChain();
  await setSchedule();
  await page.getByRole("button", {{ name: "Schedule" }}).click({{ timeout: 10000 }});
  await page.waitForTimeout(3000);
  return {{ label, blocks: blocks.length, status: "scheduled" }};
}}
"""
    proc = subprocess.run(
        ["playwright-cli", f"-s={session}", "run-code", code],
        cwd=root,
        text=True,
        capture_output=True,
        timeout=120,
    )
    if proc.returncode != 0 or "### Error" in proc.stdout:
        raise RuntimeError(f"playwright-cli failed: {proc.stderr}\n{proc.stdout}")
    return proc.stdout


def main() -> int:
    parser = argparse.ArgumentParser(description="Schedule Threads markdown chains through playwright-cli.")
    parser.add_argument("--base", required=True, help="Directory containing YYYY-MM-DD.md files")
    parser.add_argument("--session", default="threads", help="playwright-cli session name")
    parser.add_argument("--time", default="08:00", help="Schedule time in HH:MM")
    parser.add_argument("--time-window", help="Random schedule window in HH:MM-HH:MM, inclusive")
    parser.add_argument("--seed", help="Stable seed for --time-window randomization")
    parser.add_argument("--result", help="Result JSON path")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--start-after", help="Skip files with names <= this value, e.g. 2026-06-15.md")
    parser.add_argument("--root", default=str(ROOT), help="Working directory for playwright-cli")
    args = parser.parse_args()

    base = Path(args.base)
    result = Path(args.result) if args.result else base / "schedule-result.json"
    root = Path(args.root)

    files = sorted(base.glob("*.md"))
    if args.start_after:
        files = [path for path in files if path.name > args.start_after]
    if args.limit:
        files = files[: args.limit]
    if not files:
        raise SystemExit("No markdown files to schedule")

    existing = json.loads(result.read_text(encoding="utf-8")) if result.exists() else []
    scheduled_names = {item.get("file") for item in existing if item.get("status") == "scheduled"}

    for path in files:
        if path.name in scheduled_names:
            continue
        item = {
            "file": path.name,
            "label": label_for(path),
            "time": pick_time(path, args.time, args.time_window, args.seed),
            "status": "started",
            "started_at": datetime.now().isoformat(timespec="seconds"),
        }
        hour, minute = parse_time(item["time"])
        existing.append(item)
        result.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            stdout = run_code(args.session, parse_blocks(path), item["label"], hour, minute, root)
            item["status"] = "scheduled"
            item["stdout_tail"] = stdout[-1000:]
            item["finished_at"] = datetime.now().isoformat(timespec="seconds")
        except Exception as exc:
            item["status"] = "failed"
            item["error"] = str(exc)
            item["finished_at"] = datetime.now().isoformat(timespec="seconds")
            result.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
            raise
        result.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
        time.sleep(1.5)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
