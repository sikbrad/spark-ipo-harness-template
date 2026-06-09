from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import date, datetime
from pathlib import Path

ROOT = Path("/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04")
BASE = ROOT / "output/threads-vibecoding-2026-06"
RESULT = BASE / "schedule-result.json"

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MONTH_NAMES = {
    6: "June",
    7: "July",
}


def parse_blocks(path: Path) -> list[str]:
    blocks = [b.strip() for b in path.read_text(encoding="utf-8").split("---") if b.strip()]
    if len(blocks) != 3:
        raise ValueError(f"{path.name}: expected 3 blocks, got {len(blocks)}")
    for idx, block in enumerate(blocks, 1):
        if len(block) > 500:
            raise ValueError(f"{path.name}: block {idx} exceeds 500 chars")
    return blocks


def label_for(path: Path) -> str:
    y, m, d = [int(x) for x in path.stem.split("-")]
    dt = date(y, m, d)
    return f"{DAY_NAMES[dt.weekday()]}, {MONTH_NAMES[m]} {d}, {y}"


def run_code(blocks: list[str], label: str) -> str:
    payload = json.dumps({"blocks": blocks, "label": label}, ensure_ascii=False)
    code = f"""
async page => {{
  const payload = {payload};
  const blocks = payload.blocks;
  const label = payload.label;

  async function clickTopModalMore() {{
    const buttons = await page.getByRole("button", {{ name: "More" }}).all();
    for (let i = buttons.length - 1; i >= 0; i--) {{
      const box = await buttons[i].boundingBox().catch(() => null);
      if (box && box.x > 1000 && box.y > 100 && box.y < 380) {{
        await buttons[i].click();
        return;
      }}
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
    const dayCell = page.getByRole("gridcell", {{ name: label, exact: true }});
    await dayCell.waitFor({{ timeout: 8000 }});
    await dayCell.scrollIntoViewIfNeeded();
    const dayBox = await dayCell.boundingBox();
    if (!dayBox) throw new Error("schedule day cell not visible");
    await page.mouse.click(dayBox.x + dayBox.width / 2, dayBox.y + dayBox.height / 2);
    await page.getByRole("textbox", {{ name: "hh" }}).fill("08");
    await page.getByRole("textbox", {{ name: "mm" }}).fill("00");
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
        ["playwright-cli", "-s=threads", "run-code", code],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=120,
    )
    if proc.returncode != 0 or "### Error" in proc.stdout:
        raise RuntimeError(f"playwright-cli failed: {proc.stderr}\n{proc.stdout}")
    return proc.stdout


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int)
    parser.add_argument("--start-after")
    args = parser.parse_args()

    files = sorted(BASE.glob("2026-06-*.md"))
    if args.start_after:
        files = [p for p in files if p.name > args.start_after]
    if args.limit:
        files = files[: args.limit]

    existing = []
    if RESULT.exists():
        existing = json.loads(RESULT.read_text(encoding="utf-8"))

    for path in files:
        item = {
            "file": path.name,
            "label": label_for(path),
            "status": "started",
            "started_at": datetime.now().isoformat(timespec="seconds"),
        }
        existing.append(item)
        RESULT.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            stdout = run_code(parse_blocks(path), item["label"])
            item["status"] = "scheduled"
            item["stdout_tail"] = stdout[-1000:]
            item["finished_at"] = datetime.now().isoformat(timespec="seconds")
        except Exception as exc:
            item["status"] = "failed"
            item["error"] = str(exc)
            item["finished_at"] = datetime.now().isoformat(timespec="seconds")
            RESULT.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
            raise
        RESULT.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
        time.sleep(1.5)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
