#!/usr/bin/env python3
"""Run group-level OpenAI Vision VQA for WIS 2026 image groups."""

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

from llm import api_key


ROOT = Path("/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04")
GROUPS_JSON = ROOT / "output/wis-2026/reference/confluence_vendor_groups.json"
ORIGINALS_DIR = ROOT / "output/wis-2026/originals"
OUT_ROOT = ROOT / "output/wis-2026/group-vqa"
INPUT_DIR = OUT_ROOT / "input"
RESULT_DIR = OUT_ROOT / "results"
API_URL = "https://api.openai.com/v1/chat/completions"
MODEL = "gpt-4o-mini"
MAX_EDGE = 1200
JPEG_QUALITY = 82
MAX_RETRIES = 5
MIN_INTERVAL_SEC = 0.6


SYSTEM_PROMPT = """\
당신은 WIS 2026 월드IT쇼 방문 사진을 분석하는 한국어 VQA 분석가입니다.
사용자 메모와 여러 장의 사진을 함께 보고, 업체/주제별로 보이는 텍스트, 제품/서비스, 업체 주장, 가격/도입 조건, 현장 맥락을 정리합니다.
사진에 없는 내용은 사용자 메모와 사진 근거를 구분해 쓰고, 불확실한 점은 uncertainties에 남깁니다.
반드시 JSON object 하나만 출력합니다.
"""


def compact(value: Any, sep: str = " / ") -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return sep.join(str(v).strip() for v in value if str(v).strip())
    return " ".join(str(value).split())


def slug(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "-", text or "").strip("-")[:40] or "group"


def resize_image(src: Path, group_index: int) -> dict[str, Any]:
    out_dir = INPUT_DIR / f"group_{group_index:03d}"
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / f"{src.stem}.jpg"
    with Image.open(src) as raw:
        image = ImageOps.exif_transpose(raw)
        original_size = list(raw.size)
        image = image.convert("RGB")
        image.thumbnail((MAX_EDGE, MAX_EDGE), Image.Resampling.LANCZOS)
        resized_size = list(image.size)
        if not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime:
            image.save(dst, "JPEG", quality=JPEG_QUALITY, optimize=True)
    return {"source": str(src), "input": str(dst), "original_size": original_size, "resized_size": resized_size}


def data_url(path: Path) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


class VisionClient:
    def __init__(self, model: str):
        self.model = model
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {api_key()}", "Content-Type": "application/json"})
        self.last_ts = 0.0

    def throttle(self) -> None:
        delta = time.monotonic() - self.last_ts
        if delta < MIN_INTERVAL_SEC:
            time.sleep(MIN_INTERVAL_SEC - delta)
        self.last_ts = time.monotonic()

    def analyze(self, messages_content: list[dict[str, Any]], max_tokens: int) -> dict[str, Any]:
        body = {
            "model": self.model,
            "temperature": 0.1,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": messages_content},
            ],
        }
        for attempt in range(MAX_RETRIES):
            self.throttle()
            response = self.session.post(API_URL, json=body, timeout=240)
            if response.status_code == 429 or 500 <= response.status_code < 600:
                time.sleep(min(2 ** attempt, 30))
                continue
            if response.status_code >= 400:
                raise RuntimeError(f"vision request failed {response.status_code}: {response.text[:700]}")
            data = response.json()
            parsed = json.loads(data["choices"][0]["message"]["content"])
            parsed["_usage"] = data.get("usage", {})
            parsed["_model"] = data.get("model", self.model)
            return parsed
        raise RuntimeError("vision request failed after retries")


def schema_prompt(group: dict[str, Any], images: list[dict[str, Any]]) -> str:
    payload = {
        "event": "WIS 2026 World IT Show, COEX",
        "group_title": group.get("vendor"),
        "sector_group": group.get("sector_group"),
        "user_notes": group.get("notes") or [],
        "image_filenames_in_order": [Path(item["source"]).name for item in images],
        "output_schema": {
            "visible_text_by_image": {"filename.jpg": ["사진별 핵심 원문 텍스트 최대 12개"]},
            "brand_or_company_candidates": [{"name": "업체/브랜드 후보", "evidence": "사진/메모 근거", "confidence": 0.0}],
            "likely_vendor_or_topic": {"name": "그룹 대표 업체/주제명", "confidence": 0.0, "evidence": "근거"},
            "booth_candidates": ["부스번호 후보"],
            "product_or_service_names": ["제품/서비스명 후보 최대 12개"],
            "categories": ["dental|knowledge_search|patent_ai|spatial|security|outsourcing|collaboration|marketing|erp|business_tool|meeting_ai|hardware|robotics|ai_semiconductor|public_sector|healthcare|startup|data|education|other"],
            "claims": ["업체가 주장하는 강점/효과 최대 10개"],
            "price_or_business_terms": ["가격/계약/도입 조건 최대 8개"],
            "image_notes": [{"filename": "filename.jpg", "visual_context": "사진 맥락 한 문장"}],
            "summary": "이 그룹을 3-5문장으로 요약",
            "confidence": 0.0,
            "uncertainties": ["불확실한 점"],
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def load_groups() -> list[dict[str, Any]]:
    return json.loads(GROUPS_JSON.read_text(encoding="utf-8")).get("groups") or []


def result_path(index: int, group: dict[str, Any]) -> Path:
    return RESULT_DIR / f"group_{index:03d}_{slug(group.get('vendor', ''))}.json"


def run(args: argparse.Namespace) -> int:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    client = VisionClient(args.model)
    groups = load_groups()
    if args.limit:
        groups = groups[: args.limit]
    completed = 0
    skipped = 0
    failed = []
    for index, group in enumerate(groups, start=1):
        out = result_path(index, group)
        if out.exists() and not args.force:
            skipped += 1
            continue
        images = []
        for filename in group.get("images") or []:
            src = ORIGINALS_DIR / filename
            if src.exists():
                images.append(resize_image(src, index))
        content: list[dict[str, Any]] = [{"type": "text", "text": schema_prompt(group, images)}]
        for image in images:
            name = Path(image["source"]).name
            content.append({"type": "text", "text": f"IMAGE filename={name}"})
            content.append({"type": "image_url", "image_url": {"url": data_url(Path(image["input"])), "detail": "high"}})
        try:
            vqa = client.analyze(content, args.max_tokens)
            wrapped = {
                "schema_version": 1,
                "generated_at": datetime.now().astimezone().isoformat(),
                "group_index": index,
                "group_title": group.get("vendor"),
                "sector_group": group.get("sector_group"),
                "user_notes": group.get("notes") or [],
                "images": images,
                "vqa": vqa,
            }
            out.write_text(json.dumps(wrapped, ensure_ascii=False, indent=2), encoding="utf-8")
            completed += 1
            print(json.dumps({"status": "ok", "group": group.get("vendor"), "images": len(images), "completed": completed, "skipped": skipped}, ensure_ascii=False), flush=True)
        except Exception as exc:
            failed.append({"group": group.get("vendor"), "error": str(exc)})
            print(json.dumps({"status": "failed", "group": group.get("vendor"), "error": str(exc)[:500]}, ensure_ascii=False), flush=True)
            if args.stop_on_error:
                break
    print(json.dumps({"groups": len(groups), "completed": completed, "skipped": skipped, "failed": failed}, ensure_ascii=False, indent=2))
    return 1 if failed and args.stop_on_error else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--max-tokens", type=int, default=2600)
    parser.add_argument("--stop-on-error", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))
