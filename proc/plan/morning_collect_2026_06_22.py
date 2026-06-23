#!/usr/bin/env python3
"""Collect morning live sources for 2026-06-22.

This reuses the date-scoped night routine collector functions, but writes into
the 2026-06-22 daily raw directory and skips the heavy Notion dump step.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
SRC = BASE / "night_routine_collect_2026_06_10.py"

spec = importlib.util.spec_from_file_location("night_collect_base", SRC)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

mod.DAY = "2026-06-22"
mod.NEXT_DAY = "2026-06-23"
mod.RAW = Path("data/daily/2026-06-22/raw")
mod.RAW.mkdir(parents=True, exist_ok=True)
mod.ERRORS.clear()

if "--skip-notion-dump" not in sys.argv:
    sys.argv.append("--skip-notion-dump")

if __name__ == "__main__":
    raise SystemExit(mod.main())
