#!/usr/bin/env python3
"""Date-scoped collector wrapper for the 2026-06-22 night routine."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


DAY = "2026-06-22"
NEXT_DAY = "2026-06-23"
RAW = Path(f"data/daily/{DAY}/raw")


def load_base():
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
    RAW.mkdir(parents=True, exist_ok=True)
    return module


def main() -> int:
    module = load_base()
    sys.argv = [str(Path(__file__)), "--skip-notion-dump"]
    return module.main()


if __name__ == "__main__":
    raise SystemExit(main())
