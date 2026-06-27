from __future__ import annotations

import importlib.util
from pathlib import Path


BASE = Path(__file__).resolve().parent
SRC = BASE / "backfill_areas_2026-05-19_discover.py"

spec = importlib.util.spec_from_file_location("backfill_discover_base", SRC)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
mod.OUT = BASE / "backfill_areas_2026-06-22.candidates.json"

if __name__ == "__main__":
    raise SystemExit(mod.main())
