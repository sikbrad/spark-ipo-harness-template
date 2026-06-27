#!/usr/bin/env python3
"""Run local Qwen VQA on SIDEX snap/handout images one by one."""

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

from sidex_build_report import (
    compact,
    has_strong_vendor_evidence,
    load_partners,
    partner_display_name,
    score_partner,
    score_partner_from_vqa,
    sector_tags,
)


ROOT = Path("/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04")
SNAPS_DIR = ROOT / "output/sidex-2026/originals/snaps"
HANDOUTS_DIR = ROOT / "output/sidex-2026/originals/handouts"
OUT_ROOT = ROOT / "output/sidex-2026/qwen-vqa"
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL = "qwen3.6:35b"

MAX_EDGE = 1600
JPEG_QUALITY = 88
MAX_RETRIES = 3

GENERIC_NAMES = {
    "sidex",
    "sidex2026",
    "dental",
    "digital",
    "solution",
    "solutions",
    "scanner",
    "scan",
    "implant",
    "implants",
    "cad",
    "cam",
    "ai",
    "3d",
    "qr",
    "qrcode",
    "new",
    "premium",
    "global",
    "korea",
    "치과",
    "덴탈",
    "디지털",
    "스캐너",
    "임플란트",
    "솔루션",
}


PROMPT = """\
SIDEX 2026 치과 전시회 사진 VQA/OCR.
보이는 원문 텍스트를 최대한 그대로 읽고, 업체/브랜드/제품/주장을 분리해 JSON object 하나만 출력하라.
모르는 글자는 지어내지 말고 uncertainties에 적어라. 설명문/마크다운 금지.

schema:
{
  "visible_text": ["원문 텍스트 조각. 중요 텍스트 우선, 최대 35개"],
  "brand_or_company_candidates": [{"name":"업체/브랜드 후보","evidence":"사진 근거","confidence":0.0}],
  "likely_vendor_from_image": {"name":"가장 그럴듯한 업체명 또는 빈 문자열","confidence":0.0,"evidence":"근거"},
  "booth_candidates": ["부스번호 후보"],
  "product_names": ["제품명 후보"],
  "product_categories": ["scanner|milling|implant_parts|software|cad_cam|robot|imaging|orthodontics|endo|materials|hygiene|idea_product|other"],
  "claims": ["업체가 주장하는 강점/성능/워크플로우"],
  "visual_context": "사진 내용 한국어 1-3문장",
  "confidence": 0.0,
  "uncertainties": ["불확실한 점"]
}
"""

BRIEF_PROMPT = """\
SIDEX 2026 치과 전시회 사진에서 핵심 텍스트만 읽어 JSON object 하나만 출력하라.
긴 설명 금지. 보이는 회사/브랜드/제품명/핵심 문구만 적어라.
schema:
{
  "visible_text": ["핵심 원문 텍스트 최대 18개"],
  "brand_or_company_candidates": [{"name":"업체/브랜드 후보","evidence":"사진 근거","confidence":0.0}],
  "likely_vendor_from_image": {"name":"가장 그럴듯한 업체명 또는 빈 문자열","confidence":0.0,"evidence":"근거"},
  "booth_candidates": ["부스번호 후보"],
  "product_names": ["제품명 후보 최대 8개"],
  "product_categories": ["scanner|milling|implant_parts|software|cad_cam|robot|imaging|orthodontics|endo|materials|hygiene|idea_product|other"],
  "claims": ["핵심 주장 최대 5개"],
  "visual_context": "사진 내용 한 문장",
  "confidence": 0.0,
  "uncertainties": ["불확실한 점 최대 3개"]
}
"""


def norm(s: str) -> str:
    return re.sub(r"[^0-9a-zA-Z가-힣]+", "", (s or "").lower())


def timestamp_from_name(path: Path) -> str:
    m = re.search(r"(20\d{2})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})(\d{0,3})", path.stem)
    if not m:
        return ""
    y, mo, d, h, mi, sec, ms = m.groups()
    suffix = f".{ms}" if ms else ""
    return f"{y}-{mo}-{d} {h}:{mi}:{sec}{suffix}"


def role_dir(role: str) -> Path:
    if role == "snaps":
        return SNAPS_DIR
    if role == "handouts":
        return HANDOUTS_DIR
    raise ValueError(f"unknown role {role}")


def image_files(role: str) -> list[Path]:
    exts = {".jpg", ".jpeg", ".png", ".webp", ".heic"}
    return [p for p in sorted(role_dir(role).iterdir()) if p.is_file() and p.suffix.lower() in exts]


def resize_for_model(src: Path, role: str) -> dict[str, Any]:
    out_dir = OUT_ROOT / "input" / role
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / f"{src.stem}.jpg"
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im)
        original_size = list(im.size)
        im = im.convert("RGB")
        im.thumbnail((MAX_EDGE, MAX_EDGE), Image.Resampling.LANCZOS)
        resized_size = list(im.size)
        if not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime:
            im.save(dst, "JPEG", quality=JPEG_QUALITY, optimize=True)
    return {
        "source": str(src),
        "model_input": str(dst),
        "original_size": original_size,
        "resized_size": resized_size,
        "max_edge": MAX_EDGE,
        "jpeg_quality": JPEG_QUALITY,
    }


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
        return {}, f"{exc}"


def normalize_vqa(vqa: dict[str, Any]) -> dict[str, Any]:
    out = {
        "visible_text": [],
        "text_blocks": [],
        "brand_or_company_candidates": [],
        "likely_vendor_from_image": {"name": "", "confidence": 0, "evidence": ""},
        "booth_candidates": [],
        "product_names": [],
        "product_categories": [],
        "claims": [],
        "visual_context": "",
        "confidence": 0,
        "uncertainties": [],
    }
    out.update({k: v for k, v in vqa.items() if k in out})
    for key in ["visible_text", "booth_candidates", "product_names", "product_categories", "claims", "uncertainties"]:
        if isinstance(out[key], str):
            out[key] = [out[key]]
        elif not isinstance(out[key], list):
            out[key] = []
        out[key] = [compact(str(x)) for x in out[key] if compact(str(x))]
    if not isinstance(out["text_blocks"], list):
        out["text_blocks"] = []
    blocks = []
    for item in out["text_blocks"]:
        if isinstance(item, dict):
            blocks.append(
                {
                    "text": compact(str(item.get("text", ""))),
                    "location": compact(str(item.get("location", "unknown"))) or "unknown",
                    "confidence": safe_float(item.get("confidence"), 0),
                }
            )
        elif compact(str(item)):
            blocks.append({"text": compact(str(item)), "location": "unknown", "confidence": 0.5})
    out["text_blocks"] = [b for b in blocks if b["text"]]
    candidates = []
    raw_candidates = out["brand_or_company_candidates"]
    if isinstance(raw_candidates, dict):
        raw_candidates = [raw_candidates]
    if not isinstance(raw_candidates, list):
        raw_candidates = []
    for item in raw_candidates:
        if isinstance(item, dict):
            name = compact(str(item.get("name", "")))
            if name:
                candidates.append(
                    {
                        "name": name,
                        "evidence": compact(str(item.get("evidence", ""))),
                        "confidence": safe_float(item.get("confidence"), 0.5),
                    }
                )
        elif compact(str(item)):
            candidates.append({"name": compact(str(item)), "evidence": "visible candidate", "confidence": 0.5})
    out["brand_or_company_candidates"] = candidates
    likely = out["likely_vendor_from_image"]
    if isinstance(likely, str):
        likely = {"name": likely, "confidence": 0.5, "evidence": "model output"}
    if not isinstance(likely, dict):
        likely = {"name": "", "confidence": 0, "evidence": ""}
    out["likely_vendor_from_image"] = {
        "name": compact(str(likely.get("name", ""))),
        "confidence": safe_float(likely.get("confidence"), 0),
        "evidence": compact(str(likely.get("evidence", ""))),
    }
    out["visual_context"] = compact(str(out.get("visual_context", "")))
    out["confidence"] = safe_float(out.get("confidence"), 0)
    return out


def safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except Exception:
        return default


def qwen_request(image_path: Path, num_predict: int, brief: bool) -> tuple[dict[str, Any], dict[str, Any], str]:
    body = {
        "model": MODEL,
        "prompt": BRIEF_PROMPT if brief else PROMPT,
        "images": [base64.b64encode(image_path.read_bytes()).decode("ascii")],
        "stream": False,
        "format": "json",
        "think": False,
        "options": {
            "temperature": 0,
            "top_p": 0.2,
            "num_predict": num_predict,
        },
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


def vqa_text_blob(vqa: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ["visible_text", "booth_candidates", "product_names", "product_categories", "claims", "uncertainties"]:
        parts.extend(str(x) for x in vqa.get(key, []) or [])
    for block in vqa.get("text_blocks", []) or []:
        if isinstance(block, dict):
            parts.append(str(block.get("text", "")))
    for item in vqa.get("brand_or_company_candidates", []) or []:
        if isinstance(item, dict):
            parts.append(str(item.get("name", "")))
            parts.append(str(item.get("evidence", "")))
    likely = vqa.get("likely_vendor_from_image", {}) or {}
    if isinstance(likely, dict):
        parts.append(str(likely.get("name", "")))
        parts.append(str(likely.get("evidence", "")))
    parts.append(str(vqa.get("visual_context", "")))
    return compact(" ".join(parts))


def is_generic_name(name: str) -> bool:
    n = norm(name)
    if not n or len(n) < 3:
        return True
    return n in GENERIC_NAMES


def visible_brand_fallback(vqa: dict[str, Any]) -> tuple[str, float, str]:
    likely = vqa.get("likely_vendor_from_image", {}) or {}
    if isinstance(likely, dict):
        name = compact(str(likely.get("name", "")))
        conf = safe_float(likely.get("confidence"), 0)
        if name and conf >= 0.65 and not is_generic_name(name):
            return name, conf, compact(str(likely.get("evidence", ""))) or "qwen likely_vendor_from_image"
    candidates = vqa.get("brand_or_company_candidates", []) or []
    candidates = [c for c in candidates if isinstance(c, dict)]
    candidates.sort(key=lambda c: safe_float(c.get("confidence"), 0), reverse=True)
    for item in candidates:
        name = compact(str(item.get("name", "")))
        conf = safe_float(item.get("confidence"), 0)
        if name and conf >= 0.72 and not is_generic_name(name):
            return name, conf, compact(str(item.get("evidence", ""))) or "qwen brand candidate"
    return "", 0, ""


def analyze_vendor(
    *,
    role: str,
    image_path: Path,
    vqa: dict[str, Any],
    partners: list[dict[str, Any]],
    previous_snap: dict[str, Any] | None,
) -> dict[str, Any]:
    text_blob = vqa_text_blob(vqa)
    scores = []
    wrapper = {"vqa": vqa}
    for partner in partners:
        text_score, text_evidence = score_partner(text_blob, partner)
        vqa_score, vqa_evidence = score_partner_from_vqa(wrapper, partner)
        score = text_score + vqa_score
        evidence = (vqa_evidence + text_evidence)[:10]
        if score > 0:
            scores.append((score, partner, evidence))
    scores.sort(key=lambda item: item[0], reverse=True)

    associated_vendor = ""
    booth = ""
    href = None
    confidence = 0.0
    method = "unidentified"
    needs_user_memo = True
    evidence: list[str] = []
    reference_candidate = None

    if scores:
        score, partner, evidence = scores[0]
        if has_strong_vendor_evidence(score, evidence):
            associated_vendor = partner_display_name(partner)
            booth = partner.get("booth", "") or ""
            href = partner.get("view_url") or partner.get("href")
            confidence = round(min(score / 100, 1.0), 2)
            method = "sidex_reference_match"
            needs_user_memo = False
            reference_candidate = {
                "vendor": associated_vendor,
                "booth": booth,
                "score": round(score, 2),
                "evidence": evidence,
            }

    if not associated_vendor:
        raw_brand, raw_conf, raw_evidence = visible_brand_fallback(vqa)
        if raw_brand:
            associated_vendor = raw_brand
            confidence = round(min(raw_conf, 0.88), 2)
            method = "qwen_visible_brand"
            needs_user_memo = False
            evidence = [f"qwen_visible_brand:{raw_brand}", raw_evidence]

    if role == "snaps" and not associated_vendor and previous_snap:
        prev_analysis = previous_snap.get("agent_analysis", {})
        prev_vendor = prev_analysis.get("associated_vendor", "")
        prev_confidence = safe_float(prev_analysis.get("association_confidence"), 0)
        raw_brand, raw_conf, _ = visible_brand_fallback(vqa)
        if prev_vendor and prev_confidence >= 0.6 and not raw_brand:
            associated_vendor = prev_vendor
            booth = prev_analysis.get("booth", "")
            href = prev_analysis.get("partner_href")
            confidence = round(min(prev_confidence - 0.18, 0.55), 2)
            method = "snap_sequence_inferred"
            needs_user_memo = True
            evidence = [f"previous_snap:{previous_snap.get('filename')}"]

    categories = vqa.get("product_categories", []) or []
    inferred_sectors = sector_tags(text_blob, " ".join(categories), vqa_result={"vqa": vqa})
    if not associated_vendor:
        associated_vendor = "미확인"
        confidence = 0
        method = "unidentified"
        needs_user_memo = True
        evidence = evidence or ["no reliable vendor text"]

    result_check = []
    if method == "sidex_reference_match":
        result_check.append("SIDEX 업체 레퍼런스와 Qwen 판독 텍스트가 직접 매칭됨.")
    elif method == "qwen_visible_brand":
        result_check.append("SIDEX 레퍼런스 직접 매칭은 약하지만 사진에 보이는 브랜드/업체명을 업체명으로 사용함.")
    elif method == "snap_sequence_inferred":
        result_check.append("사진 자체 업체명은 약하고 snaps 경로상 직전 업체 흐름으로 추정함. 확인 필요.")
    else:
        result_check.append("사진에서 신뢰할 수 있는 업체명을 확정하지 못함. 사용자 메모 필요.")

    return {
        "associated_vendor": associated_vendor,
        "booth": booth,
        "partner_href": href,
        "association_confidence": confidence,
        "association_method": method,
        "needs_user_memo": needs_user_memo,
        "reference_candidate": reference_candidate,
        "evidence": [x for x in evidence if x],
        "sectors": inferred_sectors,
        "claims": vqa.get("claims", []) or [],
        "product_names": vqa.get("product_names", []) or [],
        "result_check": result_check,
    }


def output_path(role: str, image_path: Path) -> Path:
    return OUT_ROOT / role / f"{image_path.stem}_qwen_vqa.json"


def process_role(role: str, args: argparse.Namespace, partners: list[dict[str, Any]]) -> list[dict[str, Any]]:
    files = image_files(role)
    if args.limit:
        files = files[: args.limit]
    (OUT_ROOT / role).mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    previous_snap = None

    for index, image_path in enumerate(files, start=1):
        out = output_path(role, image_path)
        if out.exists() and not args.force:
            try:
                existing = json.loads(out.read_text(encoding="utf-8"))
                if not args.retry_errors or not existing.get("qwen", {}).get("error"):
                    records.append(existing)
                    if role == "snaps" and existing.get("agent_analysis", {}).get("associated_vendor") != "미확인":
                        previous_snap = existing
                    print(json.dumps({"status": "skip", "role": role, "index": index, "filename": image_path.name}, ensure_ascii=False), flush=True)
                    continue
            except Exception:
                pass

        image_meta = resize_for_model(image_path, role)
        vqa, raw, error = qwen_request(Path(image_meta["model_input"]), args.num_predict, args.brief)
        if not vqa:
            vqa = normalize_vqa({})
        agent_analysis = analyze_vendor(
            role=role,
            image_path=image_path,
            vqa=vqa,
            partners=partners,
            previous_snap=previous_snap,
        )
        record = {
            "schema_version": 1,
            "generated_at": datetime.now().astimezone().isoformat(),
            "role": role,
            "path_order": index,
            "filename": image_path.name,
            "timestamp": timestamp_from_name(image_path),
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
            "agent_analysis": agent_analysis,
        }
        out.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        records.append(record)
        if role == "snaps" and agent_analysis.get("associated_vendor") != "미확인":
            previous_snap = record
        print(
            json.dumps(
                {
                    "status": "ok" if not error else "partial",
                    "role": role,
                    "index": index,
                    "total": len(files),
                    "filename": image_path.name,
                    "vendor": agent_analysis.get("associated_vendor"),
                    "method": agent_analysis.get("association_method"),
                    "error": error,
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
    return records


def write_manifest(records: list[dict[str, Any]]) -> None:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    by_role: dict[str, int] = {}
    errors = []
    for record in records:
        by_role[record["role"]] = by_role.get(record["role"], 0) + 1
        if record.get("qwen", {}).get("error"):
            errors.append({"role": record["role"], "filename": record["filename"], "error": record["qwen"]["error"]})
    (OUT_ROOT / "qwen_vqa_manifest.json").write_text(
        json.dumps(
            {
                "generated_at": datetime.now().astimezone().isoformat(),
                "model": MODEL,
                "counts": by_role,
                "total": len(records),
                "errors": errors,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", choices=["snaps", "handouts", "all"], default="all")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--retry-errors", action="store_true")
    parser.add_argument("--num-predict", type=int, default=1200)
    parser.add_argument("--brief", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    partners = load_partners()
    roles = ["snaps", "handouts"] if args.role == "all" else [args.role]
    all_records: list[dict[str, Any]] = []
    for role in roles:
        all_records.extend(process_role(role, args, partners))
    write_manifest(all_records)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
