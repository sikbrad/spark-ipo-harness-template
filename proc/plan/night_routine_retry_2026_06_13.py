#!/usr/bin/env python3
"""Retry the 2026-06-13 night-routine sources that failed on remote Linux.

This script writes separate local retry artifacts under
data/daily/2026-06-13/raw/local-retry/ so the remote-collected raw files are not
overwritten while validating whether the Mac has the missing credentials/tools.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


DAY = "2026-06-13"
NEXT_DAY = "2026-06-14"
RAW = Path(f"data/daily/{DAY}/raw/local-retry")
RAW.mkdir(parents=True, exist_ok=True)


def json_ready(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_ready(v) for v in value]
    return value


def write_json(name: str, payload: Any) -> None:
    (RAW / name).write_text(
        json.dumps(json_ready(payload), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def run_cmd(name: str, cmd: list[str], *, cwd: Path | None = None, timeout: int = 120) -> dict:
    record: dict[str, Any] = {
        "source": name,
        "cmd": cmd,
        "cwd": str(cwd or Path.cwd()),
        "status": "unknown",
    }
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd or Path.cwd(),
            text=True,
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        (RAW / f"{name}.log").write_text(to_text(exc.stdout), encoding="utf-8")
        (RAW / f"{name}.err").write_text(to_text(exc.stderr), encoding="utf-8")
        record.update({"status": "timeout", "detail": f"Timed out after {timeout}s"})
        return record

    (RAW / f"{name}.log").write_text(proc.stdout or "", encoding="utf-8")
    (RAW / f"{name}.err").write_text(proc.stderr or "", encoding="utf-8")
    if proc.returncode == 0:
        record.update({"status": "ok", "returncode": proc.returncode})
    else:
        detail = (proc.stderr or proc.stdout or "").strip()[:1000]
        record.update({"status": "failed", "returncode": proc.returncode, "detail": detail})
    return record


def load_base_collector():
    path = Path("proc/plan/night_routine_collect_2026_06_10.py")
    spec = importlib.util.spec_from_file_location("night_collect_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.DAY = DAY
    module.NEXT_DAY = NEXT_DAY
    module.RAW = RAW
    module.ERRORS = []
    return module


def main() -> int:
    statuses: list[dict[str, Any]] = []

    for account in ["bispro89", "sikbrad"]:
        statuses.append(run_cmd(
            f"gcal-{account}",
            [
                sys.executable,
                "proc/lib/gcal_api.py",
                "events",
                "--account",
                account,
                "--since",
                DAY,
                "--until",
                DAY,
                "--out",
                str(RAW / f"gcal-{account}.json"),
            ],
            timeout=120,
        ))
        statuses.append(run_cmd(
            f"gmail-{account}",
            [
                sys.executable,
                "proc/lib/gmail_api.py",
                "search",
                "--account",
                account,
                "--q",
                f"after:{DAY.replace('-', '/')} before:{NEXT_DAY.replace('-', '/')} -category:promotions -category:social",
                "--max",
                "80",
                "--out",
                str(RAW / f"gmail-{account}.json"),
            ],
            timeout=180,
        ))
        statuses.append(run_cmd(
            f"gdrive-{account}",
            [
                sys.executable,
                "proc/lib/gdrive_api.py",
                "search",
                "--account",
                account,
                "--q",
                f"modifiedTime > '{DAY}T00:00:00+09:00' and modifiedTime < '{NEXT_DAY}T00:00:00+09:00' and trashed = false",
                "--max",
                "80",
                "--out",
                str(RAW / f"gdrive-{account}.json"),
            ],
            timeout=180,
        ))

    try:
        base = load_base_collector()
        try:
            base.collect_outlook()
            statuses.append({"source": "outlook", "status": "ok"})
        except Exception as exc:
            write_json("outlook.json", [])
            write_json("outlook-errors.json", [{"error": repr(exc)}])
            statuses.append({"source": "outlook", "status": "failed", "detail": repr(exc)})

        try:
            base.collect_teams()
            statuses.append({"source": "teams", "status": "ok", "base_errors": base.ERRORS})
        except Exception as exc:
            write_json("teams-chats.json", [])
            write_json("teams-channels.json", [])
            write_json("teams-standup.json", {"day": DAY, "threads": [], "error": repr(exc)})
            write_json("teams-errors.json", [{"error": repr(exc)}])
            statuses.append({"source": "teams", "status": "failed", "detail": repr(exc)})
    except Exception as exc:
        statuses.append({"source": "msgraph-base-loader", "status": "failed", "detail": repr(exc)})

    kubit = Path("/Users/gq/works/lecture/kubit/kubit-bitbot-slack-01")
    statuses.append(run_cmd("kubit-collect-conv", ["npm", "run", "collect:conv"], cwd=kubit, timeout=300))
    statuses.append(run_cmd("kubit-collect-people", ["npm", "run", "collect:people"], cwd=kubit, timeout=300))

    write_json("source-status.json", statuses)
    print(json.dumps({"day": DAY, "raw": str(RAW), "statuses": statuses}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
