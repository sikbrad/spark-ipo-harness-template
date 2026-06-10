from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import date, datetime
from pathlib import Path


ROOT = Path("/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04")
DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MONTH_NAMES = {
    6: "June",
    7: "July",
}


def blocks_for(path: Path) -> list[str]:
    blocks = [b.strip() for b in path.read_text(encoding="utf-8").split("---") if b.strip()]
    if len(blocks) != 3:
        raise ValueError(f"{path.name}: expected 3 blocks, got {len(blocks)}")
    for i, block in enumerate(blocks, 1):
        if len(block) > 500:
            raise ValueError(f"{path.name}: block {i} exceeds 500 chars")
    return blocks


def label_for(path: Path) -> str:
    y, m, d = [int(part) for part in path.stem.split("-")]
    dt = date(y, m, d)
    return f"{DAY_NAMES[dt.weekday()]}, {MONTH_NAMES[m]} {d}, {y}"


def split_time(value: str) -> tuple[str, str]:
    hour, minute = value.split(":", 1)
    return f"{int(hour):02d}", f"{int(minute):02d}"


def run_browser(payload: dict, *, schedule: bool) -> str:
    js_payload = json.dumps(payload, ensure_ascii=False)
    schedule_js = """
  async function setSchedule() {
    await clickComposeMore();
    await page.getByRole("menuitem", { name: "Schedule..." }).click({ timeout: 8000 });
    await page.getByRole("gridcell").first().waitFor({ timeout: 8000 });
    await page.waitForTimeout(500);
    async function findDayCell() {
      const cells = await page.getByRole("gridcell").all();
      for (const cell of cells) {
        const text = await cell.innerText().catch(() => "");
        if (text.includes(payload.label)) return cell;
      }
      return null;
    }
    let dayCell = await findDayCell();
    for (let attempt = 0; attempt < 12; attempt++) {
      if (dayCell) break;
      const nextButton = page.getByRole("button", { name: "Next Month" });
      await nextButton.waitFor({ timeout: 8000 });
      await nextButton.evaluate((el) => el.click());
      await page.waitForTimeout(400);
      dayCell = await findDayCell();
    }
    if (!dayCell) throw new Error("schedule day cell not found: " + payload.label);
    await dayCell.evaluate((el) => el.click());
    await page.waitForTimeout(300);
    await page.locator('input[type="text"]').last().waitFor({ timeout: 8000 });
    const inputs = await page.locator('input[type="text"]').all();
    const visible = [];
    for (const input of inputs) {
      const box = await input.boundingBox().catch(() => null);
      if (box && box.width > 10 && box.height > 10) visible.push(input);
    }
    if (visible.length < 2) throw new Error("schedule time inputs not found");
    await visible[visible.length - 2].fill(payload.hour);
    await visible[visible.length - 1].fill(payload.minute);
    await page.getByRole("button", { name: "Done", exact: true }).click({ timeout: 8000, force: true });
    await page.waitForTimeout(700);
  }
""" if schedule else """
  async function setSchedule() {}
"""
    action_js = (
        'await setSchedule(); await clickModalAction("Schedule");'
        if schedule
        else 'await clickModalAction("Post");'
    )
    code = f"""
async page => {{
  const payload = {js_payload};

  async function openComposer() {{
    await page.goto("https://www.threads.com/", {{ waitUntil: "domcontentloaded" }});
    await page.waitForTimeout(1200);
    await page.getByRole("button", {{ name: "Create" }}).last().click({{ timeout: 10000 }});
    await page.getByRole("heading", {{ name: "New thread" }}).waitFor({{ timeout: 10000 }});
  }}

  async function clickComposeMore() {{
    let target = null;
    let targetBox = null;
    for (let attempt = 0; attempt < 10; attempt++) {{
      const buttons = await page.getByRole("button", {{ name: "More" }}).all();
      for (const button of buttons) {{
        const box = await button.boundingBox().catch(() => null);
        if (box && box.x > 1300 && box.y > 100 && box.y < 460 && box.width > 30) {{
          target = button;
          targetBox = box;
        }}
      }}
      if (target) break;
      await page.waitForTimeout(300);
    }}
    if (!target) throw new Error("compose More button not found");
    await page.mouse.click(targetBox.x + targetBox.width / 2, targetBox.y + targetBox.height / 2);
  }}

  async function chooseTopic() {{
    if (!payload.topic) return;
    const topicInput = page.locator('input[placeholder="Community or topic"]').last();
    await topicInput.waitFor({{ timeout: 10000 }});
    await topicInput.fill(payload.topic);
    await page.waitForTimeout(1200);
    const matches = await page.getByText(payload.topic, {{ exact: true }}).all();
    let picked = null;
    let pickedBox = null;
    for (const match of matches) {{
      const box = await match.boundingBox().catch(() => null);
      if (box && box.x > 850 && box.y > 430 && box.y < 820) {{
        if (!pickedBox || box.y > pickedBox.y) {{
          picked = match;
          pickedBox = box;
        }}
      }}
    }}
    if (picked) {{
      await picked.click({{ force: true }});
    }} else {{
      await topicInput.press("Enter");
    }}
    await page.waitForTimeout(500);
  }}

  async function editableLast() {{
    const loc = page.locator('div[contenteditable="true"][role="textbox"]').last();
    await loc.waitFor({{ timeout: 10000 }});
    return loc;
  }}

  async function clickModalAction(name) {{
    const buttons = await page.getByRole("button", {{ name }}).all();
    let target = null;
    let targetBox = null;
    for (const button of buttons) {{
      const box = await button.boundingBox().catch(() => null);
      if (box && box.x > 1200 && box.y > 700 && box.y < 850) {{
        target = button;
        targetBox = box;
      }}
    }}
    if (!target) throw new Error("modal action button not found: " + name);
    await target.click({{ force: true }});
    await page.waitForTimeout(500);
  }}

  async function fillChain() {{
    let textbox = await editableLast();
    await textbox.fill(payload.blocks[0]);
    await chooseTopic();
    await page.waitForTimeout(400);
    for (const block of payload.blocks.slice(1)) {{
      await page.getByRole("button", {{ name: "Add to thread" }}).click({{ timeout: 8000 }});
      await page.waitForTimeout(400);
      textbox = await editableLast();
      await textbox.fill(block);
      await page.waitForTimeout(400);
    }}
  }}

{schedule_js}

  await openComposer();
  await fillChain();
  {action_js}
  await page.waitForTimeout(3500);
  return {{ status: "{'scheduled' if schedule else 'posted'}", file: payload.file, topic: payload.topic, time: payload.time || null }};
}}
"""
    proc = subprocess.run(
        ["playwright-cli", "-s=threads", "run-code", code],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=140,
    )
    if proc.returncode or "### Error" in proc.stdout:
        raise RuntimeError(proc.stdout + proc.stderr)
    return proc.stdout


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--result", required=True)
    parser.add_argument("--post-now", action="store_true")
    parser.add_argument("--schedule", action="store_true")
    parser.add_argument("--start-after")
    parser.add_argument("--until")
    args = parser.parse_args()

    base = Path(args.base)
    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    result_path = Path(args.result)
    results = json.loads(result_path.read_text(encoding="utf-8")) if result_path.exists() else []
    done = {item["file"] for item in results if item.get("status") in {"posted", "scheduled"}}

    for item in plan:
        if item["file"] in done:
            continue
        if args.start_after and item["file"] <= args.start_after:
            continue
        if args.until and item["file"] > args.until:
            continue
        if args.post_now and item["status"] != "post_now":
            continue
        if args.schedule and item["status"] == "post_now":
            continue
        path = base / item["file"]
        payload = {
            "file": item["file"],
            "blocks": blocks_for(path),
            "topic": item.get("topic"),
            "time": item.get("planned_time"),
            "label": label_for(path),
            "hour": None,
            "minute": None,
        }
        schedule = bool(args.schedule)
        if schedule:
            payload["hour"], payload["minute"] = split_time(item["planned_time"])
        row = {
            "file": item["file"],
            "topic": item.get("topic"),
            "time": item.get("planned_time"),
            "status": "started",
            "started_at": datetime.now().isoformat(timespec="seconds"),
        }
        results.append(row)
        result_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            row["stdout_tail"] = run_browser(payload, schedule=schedule)[-1000:]
            row["status"] = "scheduled" if schedule else "posted"
        except Exception as exc:
            row["status"] = "failed"
            row["error"] = str(exc)[-2000:]
            result_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
            raise
        row["finished_at"] = datetime.now().isoformat(timespec="seconds")
        result_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        time.sleep(1.5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
