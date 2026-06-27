#!/usr/bin/env python3
"""Run visual VQA on low-confidence SIDEX photos and save per-photo JSON."""

from __future__ import annotations

import argparse
import base64
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from PIL import Image, ImageOps

from llm import api_key


ROOT = Path("/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04")
PHOTOS_DIR = ROOT / "output/sidex-2026/photos"
ANALYSIS_JSON = ROOT / "output/sidex-2026/sidex_photo_analysis.json"
VQA_DIR = ROOT / "output/sidex-2026/vqa"
VQA_INPUT_DIR = VQA_DIR / "input"
VQA_RESULT_DIR = VQA_DIR / "results"
TARGETS_JSON = VQA_DIR / "low_confidence_targets.json"

API_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_MODEL = "gpt-4o-mini"
MAX_IMAGE_EDGE = 1536
JPEG_QUALITY = 86
MIN_INTERVAL_SEC = 0.7
MAX_RETRIES = 5


SYSTEM_PROMPT = """\
당신은 SIDEX 2026 치과 전시회 현장 사진을 판독하는 VQA 분석가입니다.
사진 안의 실제 텍스트, 부스/브랜드/제품명, 전시 패널의 주장, 제품 종류를 식별합니다.
확실하지 않으면 추정과 근거를 분리하고 confidence를 낮게 둡니다.

출력은 반드시 JSON object 하나만 반환합니다. 마크다운 금지.
스키마:
{
  "visible_text": ["사진에서 읽히는 원문 텍스트 조각. 최대 20개"],
  "brand_or_company_candidates": [
    {"name": "후보명", "evidence": "사진에서 보인 글자/로고/맥락", "confidence": 0.0}
  ],
  "booth_candidates": ["C-123 같은 부스번호 후보"],
  "product_names": ["제품명/브랜드명 후보"],
  "product_categories": ["scanner|milling|implant_parts|software|cad_cam|robot|imaging|orthodontics|endo|materials|hygiene|idea_product|other 중 복수"],
  "claims": ["업체가 잘한다고 주장하는 문구나 메시지"],
  "visual_context": "사진 속 장비/패널/화면/부스 상황을 한국어로 2-4문장",
  "is_floor_map_or_booth_overview": false,
  "confidence": 0.0,
  "uncertainties": ["불확실한 점"]
}
"""


def compact(s: str) -> str:
    return " ".join((s or "").split())


def timestamp_from_stem(stem: str) -> str:
    if len(stem) < 15:
        return ""
    date, clock = stem.split("_", 1)
    return f"{date[:4]}-{date[4:6]}-{date[6:8]} {clock[:2]}:{clock[2:4]}:{clock[4:6]}"


def load_sidecars() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for p in sorted(PHOTOS_DIR.glob("20260529*_text.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        analysis = data.get("analysis", {})
        rows.append(
            {
                "sidecar": p,
                "file": Path(data["file"]),
                "filename": data["filename"],
                "stem": data["file_stem"],
                "timestamp": data.get("timestamp_from_filename") or timestamp_from_stem(data["file_stem"]),
                "confidence": float(analysis.get("confidence") or 0),
                "memo_needed": bool(analysis.get("memo_needed")),
                "candidate_vendor": analysis.get("candidate_vendor") or "",
                "ocr_text": data.get("ocr", {}).get("raw_text", ""),
                "analysis": analysis,
            }
        )
    return rows


def select_targets(sidecars: list[dict[str, Any]], threshold: float) -> list[dict[str, Any]]:
    targets = [
        row
        for row in sidecars
        if row["memo_needed"] or row["confidence"] < threshold
    ]
    targets.sort(key=lambda row: row["timestamp"])
    by_stem = {row["stem"]: row for row in targets}
    return list(by_stem.values())


def resize_for_vqa(src: Path, dst: Path) -> dict[str, Any]:
    dst.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im)
        original_size = im.size
        im = im.convert("RGB")
        im.thumbnail((MAX_IMAGE_EDGE, MAX_IMAGE_EDGE), Image.Resampling.LANCZOS)
        resized_size = im.size
        im.save(dst, "JPEG", quality=JPEG_QUALITY, optimize=True)
    return {
        "source": str(src),
        "vqa_input": str(dst),
        "original_size": list(original_size),
        "resized_size": list(resized_size),
        "max_edge": MAX_IMAGE_EDGE,
        "jpeg_quality": JPEG_QUALITY,
    }


def image_data_url(path: Path) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def neighbor_context(sidecars: list[dict[str, Any]], row: dict[str, Any]) -> dict[str, Any]:
    idx = next(i for i, item in enumerate(sidecars) if item["stem"] == row["stem"])
    around = []
    for item in sidecars[max(0, idx - 3): min(len(sidecars), idx + 4)]:
        if item["stem"] == row["stem"]:
            continue
        around.append(
            {
                "timestamp": item["timestamp"],
                "filename": item["filename"],
                "candidate_vendor": item["candidate_vendor"],
                "confidence": item["confidence"],
                "memo_needed": item["memo_needed"],
                "ocr_excerpt": compact(item["ocr_text"])[:220],
            }
        )
    return {"nearby_photos": around}


def make_user_prompt(row: dict[str, Any], context: dict[str, Any]) -> str:
    payload = {
        "task": "SIDEX 2026 현장 사진 VQA. 업체명/제품/부스/주장/섹터를 사진에서 직접 판독.",
        "photo": {
            "filename": row["filename"],
            "timestamp": row["timestamp"],
            "previous_ocr_match": row["candidate_vendor"],
            "previous_confidence": row["confidence"],
            "ocr_excerpt": compact(row["ocr_text"])[:1400],
        },
        "walk_path_context": context,
        "notes": [
            "사진 텍스트가 OCR보다 더 잘 보이면 visible_text에 직접 적는다.",
            "업체명은 로고/부스명/브랜드명이 보일 때만 높은 confidence를 준다.",
            "시간상 가까운 사진은 같은 부스 또는 근처 부스일 수 있으나, 사진 근거와 분리한다.",
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


class VisionClient:
    def __init__(self, model: str):
        self.model = model
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {api_key()}",
                "Content-Type": "application/json",
            }
        )
        self._last_ts = 0.0

    def _throttle(self) -> None:
        delta = time.monotonic() - self._last_ts
        if delta < MIN_INTERVAL_SEC:
            time.sleep(MIN_INTERVAL_SEC - delta)
        self._last_ts = time.monotonic()

    def analyze(self, image_path: Path, prompt: str) -> dict[str, Any]:
        body = {
            "model": self.model,
            "temperature": 0.1,
            "max_tokens": 1600,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": image_data_url(image_path), "detail": "high"},
                        },
                    ],
                },
            ],
        }
        for attempt in range(MAX_RETRIES):
            self._throttle()
            response = self.session.post(API_URL, json=body, timeout=180)
            if response.status_code == 429 or 500 <= response.status_code < 600:
                time.sleep(min(2 ** attempt, 30))
                continue
            if response.status_code >= 400:
                raise RuntimeError(f"OpenAI vision request failed: {response.status_code} {response.text[:600]}")
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            parsed["_usage"] = data.get("usage", {})
            parsed["_model"] = data.get("model", self.model)
            return parsed
        raise RuntimeError("OpenAI vision request failed after retries")


def run(args: argparse.Namespace) -> int:
    sidecars = load_sidecars()
    targets = select_targets(sidecars, args.threshold)
    VQA_INPUT_DIR.mkdir(parents=True, exist_ok=True)
    VQA_RESULT_DIR.mkdir(parents=True, exist_ok=True)
    TARGETS_JSON.write_text(
        json.dumps(
            {
                "generated_at": datetime.now().astimezone().isoformat(),
                "threshold": args.threshold,
                "total_sidecars": len(sidecars),
                "target_count": len(targets),
                "targets": [
                    {
                        "filename": row["filename"],
                        "timestamp": row["timestamp"],
                        "confidence": row["confidence"],
                        "memo_needed": row["memo_needed"],
                    }
                    for row in targets
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    if args.dry_run:
        print(json.dumps({"targets": len(targets), "target_manifest": str(TARGETS_JSON)}, ensure_ascii=False))
        return 0

    client = VisionClient(args.model)
    completed = 0
    skipped = 0
    failed: list[dict[str, Any]] = []
    run_targets = targets[: args.limit] if args.limit else targets

    for row in run_targets:
        out_json = VQA_RESULT_DIR / f"{row['stem']}_vqa.json"
        resized = VQA_INPUT_DIR / f"{row['stem']}.jpg"
        if out_json.exists() and not args.force:
            skipped += 1
            continue
        try:
            image_meta = resize_for_vqa(row["file"], resized)
            context = neighbor_context(sidecars, row)
            prompt = make_user_prompt(row, context)
            result = client.analyze(resized, prompt)
            wrapped = {
                "schema_version": 1,
                "generated_at": datetime.now().astimezone().isoformat(),
                "filename": row["filename"],
                "timestamp": row["timestamp"],
                "previous_confidence": row["confidence"],
                "previous_candidate_vendor": row["candidate_vendor"],
                "image": image_meta,
                "walk_path_context": context,
                "vqa": result,
            }
            out_json.write_text(json.dumps(wrapped, ensure_ascii=False, indent=2), encoding="utf-8")
            completed += 1
            print(json.dumps({"status": "ok", "filename": row["filename"], "completed": completed, "skipped": skipped}, ensure_ascii=False), flush=True)
        except Exception as exc:
            failed.append({"filename": row["filename"], "error": str(exc)})
            print(json.dumps({"status": "failed", "filename": row["filename"], "error": str(exc)[:500]}, ensure_ascii=False), flush=True)
            if args.stop_on_error:
                break

    summary = {
        "targets": len(targets),
        "attempted": len(run_targets),
        "completed": completed,
        "skipped": skipped,
        "failed": failed,
        "results_dir": str(VQA_RESULT_DIR),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if failed and args.stop_on_error else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--threshold", type=float, default=0.65)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--stop-on-error", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))
