#!/usr/bin/env python3
"""Build SIDEX vendor report from local Qwen VQA JSON files."""

from __future__ import annotations

import json
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps


ROOT = Path("/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04")
QWEN_ROOT = ROOT / "output/sidex-2026/qwen-vqa"
OUT_JSON = QWEN_ROOT / "sidex_qwen_vendor_analysis.json"
OUT_MD = QWEN_ROOT / "SIDEX_2026_qwen_vendor_report.md"
THUMBS_DIR = QWEN_ROOT / "thumbs"

PHOTO_VENDOR_OVERRIDES = {
    # This handout is an INNO3D/Densflo Codi brochure. Its visual text is close
    # to DENTIS's digital-dentistry vocabulary, so keep the correction explicit.
    "20260529_144007637.jpg": "(주)이노디 INOD",
}


def compact(s: str) -> str:
    return " ".join((s or "").split())


def read_records(role: str) -> list[dict[str, Any]]:
    rows = []
    for path in sorted((QWEN_ROOT / role).glob("*_qwen_vqa.json")):
        try:
            rows.append(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            continue
    rows.sort(key=lambda r: (int(r.get("path_order") or 0), r.get("filename", "")))
    return rows


def thumb_for(record: dict[str, Any]) -> str:
    src = Path(record["image"]["source"])
    role = record["role"]
    out_dir = THUMBS_DIR / role
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / f"{src.stem}_thumb.jpg"
    if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
        return str(dst)
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        im.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
        im.save(dst, "JPEG", quality=84, optimize=True)
    return str(dst)


def vendor_key(record: dict[str, Any]) -> str:
    filename = record.get("filename", "")
    if filename in PHOTO_VENDOR_OVERRIDES:
        return PHOTO_VENDOR_OVERRIDES[filename]
    vendor = compact(record.get("agent_analysis", {}).get("associated_vendor", ""))
    if not vendor or vendor == "미확인":
        return ""
    return vendor


def merge_unique(items: list[str], more: list[str], limit: int = 30) -> list[str]:
    seen = set(items)
    for item in more:
        item = compact(str(item))
        if item and item not in seen:
            items.append(item)
            seen.add(item)
        if len(items) >= limit:
            break
    return items


def photo_summary(record: dict[str, Any]) -> dict[str, Any]:
    analysis = record.get("agent_analysis", {})
    vqa = record.get("vqa", {})
    return {
        "role": record.get("role"),
        "path_order": record.get("path_order"),
        "filename": record.get("filename"),
        "timestamp": record.get("timestamp"),
        "source": record.get("image", {}).get("source"),
        "thumb": thumb_for(record),
        "association_method": analysis.get("association_method"),
        "association_confidence": analysis.get("association_confidence"),
        "needs_user_memo": analysis.get("needs_user_memo"),
        "visible_text": vqa.get("visible_text", []) or [],
        "brand_or_company_candidates": vqa.get("brand_or_company_candidates", []) or [],
        "product_names": analysis.get("product_names", []) or vqa.get("product_names", []) or [],
        "claims": analysis.get("claims", []) or vqa.get("claims", []) or [],
        "visual_context": vqa.get("visual_context", ""),
        "uncertainties": vqa.get("uncertainties", []) or [],
        "result_check": analysis.get("result_check", []) or [],
    }


def build_groups(snaps: list[dict[str, Any]], handouts: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    groups: OrderedDict[str, dict[str, Any]] = OrderedDict()
    unknown: list[dict[str, Any]] = []

    def ensure_group(vendor: str, record: dict[str, Any], source: str) -> dict[str, Any]:
        if vendor not in groups:
            analysis = record.get("agent_analysis", {})
            groups[vendor] = {
                "vendor": vendor,
                "booth": analysis.get("booth", ""),
                "partner_href": analysis.get("partner_href"),
                "first_seen_role": record.get("role"),
                "first_path_order": record.get("path_order"),
                "group_source": source,
                "needs_user_memo": False,
                "sectors": [],
                "claims": [],
                "product_names": [],
                "photos": [],
                "snaps": [],
                "handouts": [],
            }
        return groups[vendor]

    for record in snaps:
        vendor = vendor_key(record)
        if not vendor:
            unknown.append(photo_summary(record))
            continue
        group = ensure_group(vendor, record, "snaps")
        append_record(group, record)

    for record in handouts:
        vendor = vendor_key(record)
        if not vendor:
            unknown.append(photo_summary(record))
            continue
        source = "snaps+handouts" if vendor in groups else "handouts_only"
        group = ensure_group(vendor, record, source)
        if group["group_source"] == "snaps":
            group["group_source"] = "snaps+handouts"
        append_record(group, record)

    return list(groups.values()), unknown


def append_record(group: dict[str, Any], record: dict[str, Any]) -> None:
    analysis = record.get("agent_analysis", {})
    summary = photo_summary(record)
    group["photos"].append(summary)
    group[record["role"]].append(summary)
    group["needs_user_memo"] = (
        group["needs_user_memo"]
        or bool(analysis.get("needs_user_memo"))
        or analysis.get("association_method") == "qwen_visible_brand"
    )
    group["sectors"] = merge_unique(group["sectors"], analysis.get("sectors", []) or [], limit=20)
    group["claims"] = merge_unique(group["claims"], summary.get("claims", []) or [], limit=30)
    group["product_names"] = merge_unique(group["product_names"], summary.get("product_names", []) or [], limit=30)
    if not group.get("booth") and analysis.get("booth"):
        group["booth"] = analysis.get("booth")
    if not group.get("partner_href") and analysis.get("partner_href"):
        group["partner_href"] = analysis.get("partner_href")


def write_outputs(groups: list[dict[str, Any]], unknown: list[dict[str, Any]], snaps: list[dict[str, Any]], handouts: list[dict[str, Any]]) -> None:
    QWEN_ROOT.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "generated_at": datetime.now().astimezone().isoformat(),
        "source": {
            "snaps_dir": str(ROOT / "output/sidex-2026/originals/snaps"),
            "handouts_dir": str(ROOT / "output/sidex-2026/originals/handouts"),
            "model": "qwen3.6:35b",
        },
        "counts": {
            "snaps": len(snaps),
            "handouts": len(handouts),
            "vendor_groups": len(groups),
            "unknown_photos": len(unknown),
        },
        "vendors": groups,
        "unknown_photos": unknown,
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines: list[str] = [
        "# SIDEX 2026 Qwen VQA 업체별 정리",
        "",
        f"- 생성 시각: {payload['generated_at']}",
        f"- snaps: {len(snaps)}장",
        f"- handouts: {len(handouts)}장",
        f"- 업체 그룹: {len(groups)}개",
        f"- 미확인 사진: {len(unknown)}장",
        "- 기준: `originals/snaps`는 시간순/동선순으로 업체 그룹의 기본 흐름을 만들고, `originals/handouts`는 같은 업체에 끼우거나 별도 업체 그룹으로 분리.",
        "",
        "## 업체별 정리",
        "",
    ]
    for group in groups:
        booth = f" / {group['booth']}" if group.get("booth") else ""
        lines.extend(
            [
                f"### {group['vendor']}{booth}",
                "",
                "**사진**",
                "",
            ]
        )
        if group["snaps"]:
            lines.append("- snaps")
            for photo in group["snaps"]:
                append_photo_lines(lines, photo)
        if group["handouts"]:
            lines.append("- handouts")
            for photo in group["handouts"]:
                append_photo_lines(lines, photo)
        lines.extend(
            [
                "",
                f"섹터: {', '.join(group['sectors']) if group['sectors'] else '미분류'}",
                "",
                "이 회사가 주장하는 것:",
            ]
        )
        if group["claims"]:
            for claim in group["claims"][:12]:
                lines.append(f"- {claim}")
        else:
            lines.append("- Qwen VQA에서 명확한 주장 문구를 충분히 추출하지 못함.")
        if group["product_names"]:
            lines.extend(["", "제품/브랜드 후보:"])
            for product in group["product_names"][:12]:
                lines.append(f"- {product}")
        if group.get("partner_href"):
            lines.extend(["", f"SIDEX 업체 페이지: {group['partner_href']}"])
        if group.get("needs_user_memo"):
            lines.extend(["", "입력필요 백인식 메모:", "", ""])
        else:
            lines.extend(["", "백인식 메모:", "", ""])
        lines.append("")

    lines.extend(["## 미확인 사진", ""])
    if not unknown:
        lines.append("- 없음")
    for photo in unknown:
        lines.extend(
            [
                f"### 미확인 - {photo['filename']}",
                "",
            ]
        )
        append_photo_lines(lines, photo)
        lines.extend(["", "입력필요 백인식 메모: 업체명 / 부스 / 내가 본 제품 / 추가 맥락", "", "", ""])

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def append_photo_lines(lines: list[str], photo: dict[str, Any]) -> None:
    lines.append(
        f"  - `{photo.get('timestamp')}` [{photo['filename']}]({photo['source']}) "
        f"(method {photo.get('association_method')}, confidence {photo.get('association_confidence')})"
    )
    lines.append(f"    ![{photo['filename']}]({photo['thumb']})")
    visible = " / ".join(str(x) for x in (photo.get("visible_text") or [])[:12])
    if visible:
        lines.append(f"    - Qwen text: {visible}")
    context = compact(photo.get("visual_context", ""))
    if context:
        lines.append(f"    - 맥락: {context}")
    checks = photo.get("result_check") or []
    if checks:
        lines.append(f"    - 분석: {compact(' '.join(map(str, checks)))}")


def main() -> int:
    snaps = read_records("snaps")
    handouts = read_records("handouts")
    groups, unknown = build_groups(snaps, handouts)
    write_outputs(groups, unknown, snaps, handouts)
    print(json.dumps({"markdown": str(OUT_MD), "json": str(OUT_JSON), "groups": len(groups), "unknown": len(unknown)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
