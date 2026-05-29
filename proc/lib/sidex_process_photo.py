#!/usr/bin/env python3
"""Normalize one SIDEX photo and write OCR sidecar JSON."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageOps
import pytesseract


TIMESTAMP_RE = re.compile(r"(20\d{2})[-_]?(\d{2})[-_]?(\d{2})[-_]?(\d{2})(\d{2})(\d{2})(\d{0,3})")


def timestamp_from_filename(path: Path) -> str | None:
    m = TIMESTAMP_RE.search(path.stem)
    if not m:
        return None
    year, month, day, hour, minute, second, ms = m.groups()
    suffix = f".{ms}" if ms else ""
    return f"{year}-{month}-{day}T{hour}:{minute}:{second}{suffix}+09:00"


def sanitize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def run_osd(path: Path) -> dict:
    try:
        output = pytesseract.image_to_osd(str(path), config="--psm 0")
    except Exception as exc:
        return {"ok": False, "error": str(exc), "rotate_degrees": 0}

    data: dict[str, object] = {"ok": True, "raw": output, "rotate_degrees": 0}
    for line in output.splitlines():
        if ":" not in line:
            continue
        key, value = [part.strip() for part in line.split(":", 1)]
        if key == "Rotate":
            try:
                data["rotate_degrees"] = int(value)
            except ValueError:
                pass
        elif key == "Orientation confidence":
            try:
                data["orientation_confidence"] = float(value)
            except ValueError:
                pass
        elif key == "Script":
            data["script"] = value
        elif key == "Script confidence":
            try:
                data["script_confidence"] = float(value)
            except ValueError:
                pass
    return data


def normalize_image(src: Path, dest: Path) -> dict:
    with Image.open(src) as image:
        original_size = {"width": image.width, "height": image.height}
        original_format = image.format
        exif_orientation = None
        try:
            exif_orientation = image.getexif().get(274)
        except Exception:
            pass

        normalized = ImageOps.exif_transpose(image)
        exif_transposed_size = {"width": normalized.width, "height": normalized.height}

        dest.parent.mkdir(parents=True, exist_ok=True)
        save_kwargs = {}
        if dest.suffix.lower() in {".jpg", ".jpeg"}:
            normalized = normalized.convert("RGB")
            save_kwargs = {"quality": 95, "optimize": True}
        normalized.save(dest, **save_kwargs)

    osd = run_osd(dest)
    rotate_degrees = int(osd.get("rotate_degrees") or 0)
    applied_osd_rotation = 0
    if rotate_degrees in {90, 180, 270}:
        # Tesseract's Rotate value is the clockwise correction needed.
        with Image.open(dest) as image:
            rotated = image.rotate(-rotate_degrees, expand=True)
            if dest.suffix.lower() in {".jpg", ".jpeg"}:
                rotated = rotated.convert("RGB")
                rotated.save(dest, quality=95, optimize=True)
            else:
                rotated.save(dest)
        applied_osd_rotation = rotate_degrees

    with Image.open(dest) as image:
        final_size = {"width": image.width, "height": image.height}

    return {
        "original_format": original_format,
        "original_size": original_size,
        "exif_orientation": exif_orientation,
        "exif_transposed_size": exif_transposed_size,
        "osd": osd,
        "applied_osd_rotation_degrees": applied_osd_rotation,
        "final_size": final_size,
    }


def ocr_image(path: Path) -> dict:
    data = pytesseract.image_to_data(
        str(path),
        lang="kor+eng",
        output_type=pytesseract.Output.DICT,
        config="--psm 6",
    )

    words = []
    line_buckets: dict[tuple[int, int, int], list[dict]] = {}
    for i, text in enumerate(data.get("text", [])):
        clean = sanitize_text(text)
        if not clean:
            continue
        try:
            conf = float(data["conf"][i])
        except Exception:
            conf = -1.0
        if conf < 20:
            continue

        word = {
            "text": clean,
            "confidence": conf,
            "bbox": {
                "x": int(data["left"][i]),
                "y": int(data["top"][i]),
                "width": int(data["width"][i]),
                "height": int(data["height"][i]),
            },
            "block_num": int(data["block_num"][i]),
            "par_num": int(data["par_num"][i]),
            "line_num": int(data["line_num"][i]),
        }
        words.append(word)
        key = (word["block_num"], word["par_num"], word["line_num"])
        line_buckets.setdefault(key, []).append(word)

    lines = []
    for key, line_words in sorted(line_buckets.items()):
        xs = [w["bbox"]["x"] for w in line_words]
        ys = [w["bbox"]["y"] for w in line_words]
        rights = [w["bbox"]["x"] + w["bbox"]["width"] for w in line_words]
        bottoms = [w["bbox"]["y"] + w["bbox"]["height"] for w in line_words]
        lines.append(
            {
                "text": sanitize_text(" ".join(w["text"] for w in line_words)),
                "mean_confidence": round(
                    sum(w["confidence"] for w in line_words) / len(line_words), 2
                ),
                "bbox": {
                    "x": min(xs),
                    "y": min(ys),
                    "width": max(rights) - min(xs),
                    "height": max(bottoms) - min(ys),
                },
                "block_num": key[0],
                "par_num": key[1],
                "line_num": key[2],
            }
        )

    raw_text = "\n".join(line["text"] for line in lines)
    return {
        "engine": "tesseract",
        "languages": ["kor", "eng"],
        "raw_text": raw_text,
        "lines": lines,
        "words": words,
        "line_count": len(lines),
        "word_count": len(words),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, type=Path)
    ap.add_argument("--output-dir", required=True, type=Path)
    ap.add_argument("--source-href")
    ap.add_argument("--source-label")
    ap.add_argument("--google-stamp")
    args = ap.parse_args()

    src = args.input
    out_dir = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    processed = out_dir / src.name
    sidecar = out_dir / f"{processed.stem}_text.json"

    try:
        orientation = normalize_image(src, processed)
        ocr = ocr_image(processed)
        status = "ok"
        error = None
    except Exception as exc:
        status = "error"
        error = str(exc)
        if not processed.exists():
            shutil.copy2(src, processed)
        orientation = {}
        ocr = {
            "engine": "tesseract",
            "languages": ["kor", "eng"],
            "raw_text": "",
            "lines": [],
            "words": [],
            "line_count": 0,
            "word_count": 0,
        }

    payload = {
        "schema_version": 1,
        "file": str(processed),
        "original_file": str(src),
        "filename": processed.name,
        "file_stem": processed.stem,
        "timestamp_from_filename": timestamp_from_filename(processed),
        "google_photos": {
            "href": args.source_href,
            "label": args.source_label,
            "stamp": args.google_stamp,
        },
        "status": status,
        "error": error,
        "processed_at": datetime.now().astimezone().isoformat(),
        "orientation": orientation,
        "ocr": ocr,
        "analysis": {
            "candidate_vendor": None,
            "confidence": None,
            "evidence": [],
            "observed_products_or_claims": [],
            "sector_tags": [],
            "nearby_or_sequence_context": [],
        },
    }
    sidecar.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": status, "processed": str(processed), "sidecar": str(sidecar)}, ensure_ascii=False))
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
