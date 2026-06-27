#!/usr/bin/env python3
"""Suggest clockwise rotations for SIDEX published images using OCR confidence."""

from __future__ import annotations

import csv
import io
import json
import re
import subprocess
import tempfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from PIL import Image, ImageOps


ROOT = Path("/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04")
ANALYSIS_JSON = ROOT / "output/sidex-2026/qwen-vqa/sidex_qwen_vendor_analysis.json"
OUT = ROOT / "output/sidex-2026/outline_publish/rotation_suggestions.json"
TESSERACT = "/opt/homebrew/bin/tesseract"


def all_sources() -> list[Path]:
    data = json.loads(ANALYSIS_JSON.read_text(encoding="utf-8"))
    paths: list[Path] = []
    for vendor in data.get("vendors") or []:
        for photo in [*(vendor.get("snaps") or []), *(vendor.get("handouts") or [])]:
            if photo.get("role") == "handouts":
                paths.append(Path(photo["source"]))
    return paths


def score_image(path: Path, rotation: int) -> tuple[float, str]:
    image = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    image = image.rotate(-rotation, expand=True)
    image.thumbnail((900, 900), Image.Resampling.LANCZOS)
    with tempfile.NamedTemporaryFile(suffix=".png") as tmp:
        image.save(tmp.name)
        result = subprocess.run(
            [TESSERACT, tmp.name, "stdout", "-l", "kor+eng", "--psm", "6", "tsv"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=20,
        )
    rows = csv.DictReader(io.StringIO(result.stdout), delimiter="\t")
    score = 0.0
    texts: list[str] = []
    for row in rows:
        text = (row.get("text") or "").strip()
        if not text:
            continue
        try:
            conf = float(row.get("conf") or -1)
        except ValueError:
            conf = -1
        meaningful = sum(1 for ch in text if re.match(r"[A-Za-z0-9가-힣]", ch))
        if conf > 25 and meaningful >= 2:
            score += (conf + 20) * meaningful
            texts.append(text)
    return score, " ".join(texts[:16])


def suggest(path: Path) -> dict:
    scores = {}
    samples = {}
    for rotation in [0, 90, 180, 270]:
        try:
            score, sample = score_image(path, rotation)
        except Exception as exc:  # noqa: BLE001
            score, sample = 0.0, f"ERROR {type(exc).__name__}: {exc}"
        scores[str(rotation)] = round(score, 2)
        samples[str(rotation)] = sample
    best = max(scores, key=lambda k: scores[k])
    best_score = scores[best]
    current = scores["0"]
    ratio = best_score / max(current, 1.0)
    return {
        "filename": path.name,
        "path": str(path),
        "suggested_clockwise": int(best),
        "current_score": current,
        "best_score": best_score,
        "ratio": round(ratio, 2),
        "scores": scores,
        "samples": samples,
    }


def main() -> None:
    paths = all_sources()
    results = []
    with ProcessPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(suggest, path) for path in paths]
        for index, future in enumerate(as_completed(futures), start=1):
            item = future.result()
            results.append(item)
            print(index, item["filename"], item["suggested_clockwise"], item["ratio"], item["scores"], flush=True)
    results.sort(key=lambda x: x["filename"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
