#!/usr/bin/env python3
"""Run local Qwen VQA on WIS 2026 Confluence-grouped images."""

from __future__ import annotations

import argparse
import base64
import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from PIL import Image, ImageOps


ROOT = Path("/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04")
GROUPS_JSON = ROOT / "output/wis-2026/reference/confluence_vendor_groups.json"
ORIGINALS_DIR = ROOT / "output/wis-2026/originals"
OUT_ROOT = ROOT / "output/wis-2026/qwen-vqa"
INPUT_DIR = OUT_ROOT / "input"
RESULT_DIR = OUT_ROOT / "images"
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL = "qwen3.6:35b"
MAX_EDGE = 1600
JPEG_QUALITY = 88
MAX_RETRIES = 3


PROMPT_TEMPLATE = """\
WIS 2026 월드IT쇼 현장 사진 VQA/OCR.
아래 사용자 메모는 같은 그룹의 현장 메모다. 사진에 보이는 원문 텍스트를 우선 읽고,
업체/브랜드/제품/서비스/주장/가격/카테고리를 JSON object 하나로 정리하라.
모르는 글자는 지어내지 말고 uncertainties에 적어라. 마크다운 금지.

group_title: {group_title}
sector_group: {sector_group}
user_notes:
{user_notes}

schema:
{{
  "visible_text": ["사진에서 보이는 핵심 원문 텍스트 최대 15개"],
  "brand_or_company_candidates": [{{"name":"업체/브랜드 후보","evidence":"사진 근거","confidence":0.0}}],
  "likely_vendor_from_image": {{"name":"가장 그럴듯한 업체명 또는 빈 문자열","confidence":0.0,"evidence":"근거"}},
  "booth_candidates": ["부스번호 후보"],
  "product_or_service_names": ["제품/서비스명 후보 최대 8개"],
  "categories": ["dental|knowledge_search|patent_ai|spatial|security|outsourcing|collaboration|marketing|erp|business_tool|meeting_ai|hardware|robotics|ai_semiconductor|public_sector|healthcare|startup|data|education|other"],
  "claims": ["업체가 주장하는 강점/성능/효과 최대 6개"],
  "price_or_business_terms": ["가격/계약/도입 조건이 보이면 최대 4개"],
  "visual_context": "사진 내용과 부스 상황을 한국어 1문장",
  "confidence": 0.0,
  "uncertainties": ["불확실한 점"]
}}
"""


def compact(value: Any, sep: str = " / ") -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return sep.join(str(v).strip() for v in value if str(v).strip())
    return " ".join(str(value).split())


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def timestamp_from_name(path: Path) -> str:
    m = re.search(r"(20\d{2})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})(\d{0,3})", path.stem)
    if not m:
        return ""
    y, mo, d, h, mi, sec, ms = m.groups()
    suffix = f".{ms}" if ms else ""
    return f"{y}-{mo}-{d} {h}:{mi}:{sec}{suffix}"


def parse_json_response(text: str) -> tuple[dict[str, Any], str]:
    raw = text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw), ""
    except json.JSONDecodeError as exc:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(raw[start : end + 1]), ""
            except json.JSONDecodeError:
                pass
        return {}, str(exc)


def listify(value: Any) -> list[str]:
    if isinstance(value, str):
        return [compact(value)] if compact(value) else []
    if isinstance(value, list):
        return [compact(v) for v in value if compact(v)]
    return []


def normalize_vqa(vqa: dict[str, Any]) -> dict[str, Any]:
    out = {
        "visible_text": [],
        "brand_or_company_candidates": [],
        "likely_vendor_from_image": {"name": "", "confidence": 0, "evidence": ""},
        "booth_candidates": [],
        "product_or_service_names": [],
        "categories": [],
        "claims": [],
        "price_or_business_terms": [],
        "visual_context": "",
        "confidence": 0,
        "uncertainties": [],
    }
    out.update({k: v for k, v in vqa.items() if k in out})
    for key in [
        "visible_text",
        "booth_candidates",
        "product_or_service_names",
        "categories",
        "claims",
        "price_or_business_terms",
        "uncertainties",
    ]:
        out[key] = listify(out.get(key))
    candidates = out.get("brand_or_company_candidates")
    if isinstance(candidates, dict):
        candidates = [candidates]
    if not isinstance(candidates, list):
        candidates = []
    normalized_candidates = []
    for item in candidates:
        if isinstance(item, dict):
            name = compact(item.get("name"))
            if name:
                normalized_candidates.append(
                    {
                        "name": name,
                        "evidence": compact(item.get("evidence")),
                        "confidence": safe_float(item.get("confidence"), 0.5),
                    }
                )
        elif compact(item):
            normalized_candidates.append({"name": compact(item), "evidence": "visible candidate", "confidence": 0.5})
    out["brand_or_company_candidates"] = normalized_candidates
    likely = out.get("likely_vendor_from_image")
    if isinstance(likely, str):
        likely = {"name": likely, "confidence": 0.5, "evidence": "model output"}
    if not isinstance(likely, dict):
        likely = {"name": "", "confidence": 0, "evidence": ""}
    out["likely_vendor_from_image"] = {
        "name": compact(likely.get("name")),
        "confidence": safe_float(likely.get("confidence"), 0),
        "evidence": compact(likely.get("evidence")),
    }
    out["visual_context"] = compact(out.get("visual_context"))
    out["confidence"] = safe_float(out.get("confidence"), 0)
    return out


def resize_for_model(src: Path) -> dict[str, Any]:
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    dst = INPUT_DIR / f"{src.stem}.jpg"
    with Image.open(src) as raw:
        image = ImageOps.exif_transpose(raw)
        original_size = list(raw.size)
        transposed_size = list(image.size)
        image = image.convert("RGB")
        image.thumbnail((MAX_EDGE, MAX_EDGE), Image.Resampling.LANCZOS)
        resized_size = list(image.size)
        if not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime:
            image.save(dst, "JPEG", quality=JPEG_QUALITY, optimize=True)
    return {
        "source": str(src),
        "model_input": str(dst),
        "original_size": original_size,
        "transposed_size": transposed_size,
        "resized_size": resized_size,
        "max_edge": MAX_EDGE,
        "jpeg_quality": JPEG_QUALITY,
    }


def qwen_request(image_path: Path, prompt: str, num_predict: int) -> tuple[dict[str, Any], dict[str, Any], str]:
    body = {
        "model": MODEL,
        "prompt": prompt,
        "images": [base64.b64encode(image_path.read_bytes()).decode("ascii")],
        "stream": False,
        "format": "json",
        "think": False,
        "options": {"temperature": 0, "top_p": 0.2, "num_predict": num_predict},
    }
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.post(OLLAMA_URL, json=body, timeout=240)
            if response.status_code >= 500:
                time.sleep(2 + attempt * 3)
                continue
            if response.status_code >= 400:
                return {}, {}, f"ollama_http_{response.status_code}: {response.text[:500]}"
            data = response.json()
            parsed, parse_error = parse_json_response(data.get("response", ""))
            if parse_error:
                data["parse_error"] = parse_error
            return normalize_vqa(parsed), data, parse_error
        except Exception as exc:
            if attempt + 1 >= MAX_RETRIES:
                return {}, {}, str(exc)
            time.sleep(2 + attempt * 3)
    return {}, {}, "max retries exceeded"


def load_tasks() -> list[dict[str, Any]]:
    payload = json.loads(GROUPS_JSON.read_text(encoding="utf-8"))
    tasks = []
    for group_index, group in enumerate(payload.get("groups") or [], start=1):
        for image_index, filename in enumerate(group.get("images") or [], start=1):
            src = ORIGINALS_DIR / filename
            if not src.exists():
                tasks.append({"missing": True, "group_index": group_index, "image_index": image_index, "filename": filename, **group})
                continue
            tasks.append(
                {
                    "missing": False,
                    "group_index": group_index,
                    "image_index": image_index,
                    "filename": filename,
                    "source": str(src),
                    "vendor": group.get("vendor"),
                    "sector_group": group.get("sector_group"),
                    "notes": group.get("notes") or [],
                }
            )
    return tasks


def output_path(filename: str) -> Path:
    return RESULT_DIR / f"{Path(filename).stem}_qwen_vqa.json"


def run(args: argparse.Namespace) -> int:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    tasks = [t for t in load_tasks() if not t.get("missing")]
    if args.limit:
        tasks = tasks[: args.limit]
    completed = 0
    skipped = 0
    failed = []
    for task in tasks:
        out = output_path(task["filename"])
        if out.exists() and not args.force:
            existing = json.loads(out.read_text(encoding="utf-8"))
            if not args.retry_errors or not existing.get("qwen", {}).get("error"):
                skipped += 1
                continue
        image_meta = resize_for_model(Path(task["source"]))
        prompt = PROMPT_TEMPLATE.format(
            group_title=task.get("vendor") or "",
            sector_group=task.get("sector_group") or "",
            user_notes="\n".join(f"- {note}" for note in task.get("notes") or []) or "- 없음",
        )
        vqa, raw, error = qwen_request(Path(image_meta["model_input"]), prompt, args.num_predict)
        if not vqa:
            vqa = normalize_vqa({})
        record = {
            "schema_version": 1,
            "generated_at": datetime.now().astimezone().isoformat(),
            "group_index": task["group_index"],
            "image_index": task["image_index"],
            "group_title": task.get("vendor"),
            "sector_group": task.get("sector_group"),
            "user_notes": task.get("notes") or [],
            "filename": task["filename"],
            "timestamp": timestamp_from_name(Path(task["filename"])),
            "image": image_meta,
            "qwen": {
                "model": MODEL,
                "ollama_url": OLLAMA_URL,
                "error": error,
                "raw_response_metadata": {
                    key: raw.get(key)
                    for key in [
                        "model",
                        "created_at",
                        "done",
                        "done_reason",
                        "total_duration",
                        "load_duration",
                        "prompt_eval_count",
                        "eval_count",
                        "parse_error",
                    ]
                    if isinstance(raw, dict) and key in raw
                },
            },
            "vqa": vqa,
        }
        out.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        if error:
            failed.append({"filename": task["filename"], "error": error})
        else:
            completed += 1
        print(
            json.dumps(
                {
                    "status": "ok" if not error else "partial",
                    "index": task["image_index"],
                    "group": task.get("vendor"),
                    "filename": task["filename"],
                    "completed": completed,
                    "skipped": skipped,
                    "error": error,
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
    print(json.dumps({"tasks": len(tasks), "completed": completed, "skipped": skipped, "failed": failed}, ensure_ascii=False, indent=2))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--retry-errors", action="store_true")
    parser.add_argument("--num-predict", type=int, default=900)
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))
