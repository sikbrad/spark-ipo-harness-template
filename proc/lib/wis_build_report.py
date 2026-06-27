#!/usr/bin/env python3
"""Build WIS 2026 grouped analysis from Confluence notes and image VQA."""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps


ROOT = Path("/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04")
GROUPS_JSON = ROOT / "output/wis-2026/reference/confluence_vendor_groups.json"
PARTICIPANTS_OCR = ROOT / "output/wis-2026/reference/wis_participants_ocr.txt"
VQA_DIR = ROOT / "output/wis-2026/qwen-vqa/images"
GROUP_VQA_DIR = ROOT / "output/wis-2026/group-vqa/results"
OUT_ROOT = ROOT / "output/wis-2026/qwen-vqa"
OUT_JSON = OUT_ROOT / "wis_qwen_vendor_analysis.json"
OUT_MD = OUT_ROOT / "WIS_2026_vendor_report.md"
THUMBS_DIR = OUT_ROOT / "thumbs"


CATEGORY_LABELS = {
    "dental": "치과/헬스케어",
    "knowledge_search": "지식검색",
    "patent_ai": "특허/기술검색",
    "spatial": "공간정보",
    "security": "보안",
    "outsourcing": "외주/개발사",
    "collaboration": "협업툴",
    "marketing": "마케팅/분석",
    "erp": "ERP/업무시스템",
    "business_tool": "업무툴/SaaS",
    "meeting_ai": "회의/통역 AI",
    "hardware": "하드웨어/디바이스",
    "robotics": "로봇/자동화",
    "ai_semiconductor": "AI 반도체/인프라",
    "public_sector": "공공/지원사업",
    "healthcare": "헬스케어",
    "startup": "스타트업",
    "data": "데이터/검색",
    "education": "교육/HR",
    "other": "기타",
    "saas": "업무툴/SaaS",
    "blockchain": "블록체인",
}


def compact(value: Any, sep: str = " / ") -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return sep.join(str(v).strip() for v in value if str(v).strip())
    return " ".join(str(value).split())


def norm(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "", value or "").lower()


def unique_extend(base: list[str], more: list[Any], limit: int = 40) -> list[str]:
    seen = set(base)
    for item in more or []:
        text = compact(item)
        if text and text not in seen:
            base.append(text)
            seen.add(text)
        if len(base) >= limit:
            break
    return base


def load_vqa(filename: str) -> dict[str, Any]:
    path = VQA_DIR / f"{Path(filename).stem}_qwen_vqa.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_group_vqa(group_index: int) -> dict[str, Any]:
    matches = sorted(GROUP_VQA_DIR.glob(f"group_{group_index:03d}_*.json"))
    if not matches:
        return {}
    return json.loads(matches[0].read_text(encoding="utf-8"))


def thumb_for(source: str) -> str:
    src = Path(source)
    THUMBS_DIR.mkdir(parents=True, exist_ok=True)
    dst = THUMBS_DIR / f"{src.stem}_thumb.jpg"
    if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
        return str(dst)
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        im.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
        im.save(dst, "JPEG", quality=84, optimize=True)
    return str(dst)


def participant_hits(vendor: str, brands: list[str], ocr_text: str) -> list[str]:
    needles = [vendor, *brands]
    hits = []
    lines = [compact(line) for line in ocr_text.splitlines() if compact(line)]
    for needle in needles:
        n = norm(needle)
        if len(n) < 3:
            continue
        for line in lines:
            if n in norm(line) and line not in hits:
                hits.append(line)
                break
        if len(hits) >= 4:
            break
    return hits


def summarize_photo(record: dict[str, Any]) -> dict[str, Any]:
    vqa = record.get("vqa") or {}
    source = record.get("image", {}).get("source", "")
    brands = []
    for item in vqa.get("brand_or_company_candidates") or []:
        if isinstance(item, dict) and item.get("name"):
            brands.append(item["name"])
    likely = vqa.get("likely_vendor_from_image") or {}
    if isinstance(likely, dict) and likely.get("name"):
        brands.append(likely["name"])
    return {
        "filename": record.get("filename"),
        "timestamp": record.get("timestamp"),
        "source": source,
        "thumb": thumb_for(source) if source else "",
        "visible_text": vqa.get("visible_text") or [],
        "brand_candidates": brands,
        "booth_candidates": vqa.get("booth_candidates") or [],
        "product_or_service_names": vqa.get("product_or_service_names") or [],
        "categories": vqa.get("categories") or [],
        "claims": vqa.get("claims") or [],
        "price_or_business_terms": vqa.get("price_or_business_terms") or [],
        "visual_context": vqa.get("visual_context") or "",
        "confidence": vqa.get("confidence") or 0,
        "uncertainties": vqa.get("uncertainties") or [],
        "vqa_error": record.get("qwen", {}).get("error", ""),
    }


def summarize_photo_from_group(filename: str, source: str, group_vqa: dict[str, Any]) -> dict[str, Any]:
    vqa = group_vqa.get("vqa") or {}
    visible_by_image = vqa.get("visible_text_by_image") or {}
    visible = visible_by_image.get(filename) or visible_by_image.get(Path(filename).name) or []
    image_notes = vqa.get("image_notes") or []
    visual_context = ""
    for note in image_notes:
        if isinstance(note, dict) and note.get("filename") == filename:
            visual_context = note.get("visual_context") or ""
            break
    return {
        "filename": filename,
        "timestamp": timestamp_from_filename(filename),
        "source": source,
        "thumb": thumb_for(source) if source else "",
        "visible_text": visible,
        "brand_candidates": [
            item.get("name")
            for item in vqa.get("brand_or_company_candidates", []) or []
            if isinstance(item, dict) and item.get("name")
        ],
        "booth_candidates": vqa.get("booth_candidates") or [],
        "product_or_service_names": vqa.get("product_or_service_names") or [],
        "categories": vqa.get("categories") or [],
        "claims": vqa.get("claims") or [],
        "price_or_business_terms": vqa.get("price_or_business_terms") or [],
        "visual_context": visual_context,
        "confidence": vqa.get("confidence") or 0,
        "uncertainties": vqa.get("uncertainties") or [],
        "vqa_error": "",
    }


def timestamp_from_filename(filename: str) -> str:
    stem = Path(filename).stem
    m = re.search(r"(20\d{2})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})(\d{0,3})", stem)
    if not m:
        return ""
    y, mo, d, h, mi, sec, ms = m.groups()
    suffix = f".{ms}" if ms else ""
    return f"{y}-{mo}-{d} {h}:{mi}:{sec}{suffix}"


def group_summary(group: dict[str, Any]) -> str:
    if group.get("group_vqa_summary"):
        return group["group_vqa_summary"]
    notes = group.get("user_notes") or []
    claims = group.get("claims") or []
    products = group.get("product_or_service_names") or []
    pieces = []
    if notes:
        pieces.append("현장 메모상 " + compact(notes[:3], " "))
    if products:
        pieces.append("사진에서는 " + compact(products[:5]) + "가 확인됩니다.")
    if claims:
        pieces.append("강조 메시지는 " + compact(claims[:4]) + "입니다.")
    if not pieces:
        pieces.append("사진과 메모에서 추가 확인이 필요한 그룹입니다.")
    return " ".join(pieces)


def build() -> dict[str, Any]:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    groups_payload = json.loads(GROUPS_JSON.read_text(encoding="utf-8"))
    ocr_text = PARTICIPANTS_OCR.read_text(encoding="utf-8") if PARTICIPANTS_OCR.exists() else ""
    groups = []
    missing_vqa = []

    for group_index, raw in enumerate(groups_payload.get("groups") or [], start=1):
        group_vqa = load_group_vqa(group_index)
        group_vqa_payload = group_vqa.get("vqa") or {}
        photos = []
        brand_pool: list[str] = []
        products: list[str] = []
        claims: list[str] = []
        categories: list[str] = []
        prices: list[str] = []
        booths: list[str] = []
        visible: list[str] = []
        unique_extend(
            brand_pool,
            [
                item.get("name")
                for item in group_vqa_payload.get("brand_or_company_candidates", []) or []
                if isinstance(item, dict) and item.get("name")
            ],
            20,
        )
        unique_extend(products, group_vqa_payload.get("product_or_service_names") or [], 25)
        unique_extend(claims, group_vqa_payload.get("claims") or [], 30)
        unique_extend(categories, group_vqa_payload.get("categories") or [], 20)
        unique_extend(prices, group_vqa_payload.get("price_or_business_terms") or [], 15)
        unique_extend(booths, group_vqa_payload.get("booth_candidates") or [], 10)
        visible_by_image = group_vqa_payload.get("visible_text_by_image") or {}
        if isinstance(visible_by_image, dict):
            for values in visible_by_image.values():
                unique_extend(visible, values if isinstance(values, list) else [values], 40)

        for filename in raw.get("images") or []:
            record = load_vqa(filename)
            source = str(ROOT / "output/wis-2026/originals" / filename)
            if not record and group_vqa:
                photo = summarize_photo_from_group(filename, source, group_vqa)
                photos.append(photo)
                continue
            if not record:
                missing_vqa.append(filename)
                continue
            photo = summarize_photo(record)
            photos.append(photo)
            unique_extend(brand_pool, photo["brand_candidates"], 20)
            unique_extend(products, photo["product_or_service_names"], 25)
            unique_extend(claims, photo["claims"], 30)
            unique_extend(categories, photo["categories"], 20)
            unique_extend(prices, photo["price_or_business_terms"], 15)
            unique_extend(booths, photo["booth_candidates"], 10)
            unique_extend(visible, photo["visible_text"], 40)

        labeled_categories = []
        for category in categories:
            label = CATEGORY_LABELS.get(category, category)
            if label not in labeled_categories:
                labeled_categories.append(label)

        group = {
            "group_index": group_index,
            "vendor": raw.get("vendor"),
            "sector_group": raw.get("sector_group") or "",
            "user_notes": raw.get("notes") or [],
            "image_count": len(raw.get("images") or []),
            "vqa_image_count": len(photos),
            "photos": photos,
            "brand_candidates": brand_pool,
            "booth_candidates": booths,
            "participant_reference_hits": participant_hits(raw.get("vendor", ""), brand_pool, ocr_text),
            "product_or_service_names": products,
            "categories": labeled_categories,
            "claims": claims,
            "price_or_business_terms": prices,
            "visible_text": visible,
            "group_vqa_summary": group_vqa_payload.get("summary", ""),
            "summary": "",
        }
        group["summary"] = group_summary(group)
        groups.append(group)

    category_counter = Counter()
    sector_counter = Counter()
    for group in groups:
        if group.get("sector_group"):
            sector_counter[group["sector_group"]] += 1
        for category in group.get("categories") or []:
            category_counter[category] += 1

    payload = {
        "schema_version": 1,
        "generated_at": datetime.now().astimezone().isoformat(),
        "source": {
            "confluence_page": "https://doflab.atlassian.net/wiki/spaces/AX/pages/823984130/WIS2026",
            "participant_pdf": "/Users/gq/Downloads/2026 WIS 참가사 리스트 (국문).pdf",
            "outline_target": "https://outline.doflab.com/doc/wis-2026-6oNZMSV1gd",
            "image_analysis": "group-level vision analysis with local fallback artifacts",
        },
        "counts": {
            "groups": len(groups),
            "image_refs": sum(g["image_count"] for g in groups),
            "vqa_images": sum(g["vqa_image_count"] for g in groups),
            "missing_vqa": len(missing_vqa),
        },
        "sector_counts": sector_counter.most_common(),
        "category_counts": category_counter.most_common(),
        "vendors": groups,
        "missing_vqa": missing_vqa,
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(payload)
    return payload


def write_markdown(payload: dict[str, Any]) -> None:
    lines = [
        "# WIS 2026 방문 사진/메모 기반 업체별 정리",
        "",
        f"- 생성 시각: {payload['generated_at']}",
        f"- 그룹: {payload['counts']['groups']}개",
        f"- 사진: {payload['counts']['vqa_images']} / {payload['counts']['image_refs']}장 판독",
        "",
        "## 방문 요약",
        "",
        "- Confluence에 정리된 현장 메모를 기준으로 업체/주제 그룹을 유지하고, 각 사진에서 보이는 문구·제품·주장을 보강했다.",
        "- WIS 현장에서는 지식검색/특허 AI, 공간정보, 협업툴, 마케팅 분석, ERP/업무툴, 회의 AI, 외주/개발사, AI 인프라가 반복적으로 등장했다.",
        "- 단순 AI 래핑과 실제 업무 프로세스에 들어갈 수 있는 제품을 구분해 볼 필요가 있다. 사용자의 원메모에서 '특별한 기술 없어보임', '활용도 있어보임', '비싸다' 같은 현장 판단이 중요한 필터로 작동한다.",
        "",
        "## 분야별 분포",
        "",
        "| 분야 | 그룹 수 |",
        "| --- | ---: |",
    ]
    for sector, count in payload.get("sector_counts") or []:
        lines.append(f"| {sector} | {count} |")
    lines.extend(["", "## 업체/주제별 정리", ""])

    for group in payload["vendors"]:
        sector = f" / {group['sector_group']}" if group.get("sector_group") else ""
        lines.extend(
            [
                f"### {group['vendor']}{sector}",
                "",
                f"- 사진: {group['vqa_image_count']}장",
                f"- 카테고리: {compact(group.get('categories') or [], ', ') or '미분류'}",
            ]
        )
        if group.get("booth_candidates"):
            lines.append(f"- 부스 후보: {compact(group['booth_candidates'], ', ')}")
        if group.get("participant_reference_hits"):
            lines.append(f"- 참가사 리스트 후보: {compact(group['participant_reference_hits'][:3], ' / ')}")
        if group.get("brand_candidates"):
            lines.append(f"- 사진상 브랜드/업체 후보: {compact(group['brand_candidates'][:8], ', ')}")
        lines.extend(["", "**백인식/서해리 현장 메모**", ""])
        if group.get("user_notes"):
            for note in group["user_notes"]:
                lines.append(f"- {note}")
        else:
            lines.append("- 별도 메모 없음.")
        lines.extend(["", "**제품/서비스**", ""])
        for item in (group.get("product_or_service_names") or [])[:12]:
            lines.append(f"- {item}")
        if not group.get("product_or_service_names"):
            lines.append("- 사진 판독에서 명확한 제품/서비스명이 충분히 잡히지 않음.")
        lines.extend(["", "**업체가 강조한 점**", ""])
        for item in (group.get("claims") or [])[:12]:
            lines.append(f"- {item}")
        if not group.get("claims"):
            lines.append("- 사진 판독에서 명확한 주장 문구가 충분히 잡히지 않음.")
        if group.get("price_or_business_terms"):
            lines.extend(["", "**가격/계약/도입 조건**", ""])
            for item in group["price_or_business_terms"][:8]:
                lines.append(f"- {item}")
        lines.extend(["", "**정리**", "", group.get("summary", ""), "", "**사진**", ""])
        for photo in group.get("photos") or []:
            lines.append(f"- `{photo.get('timestamp')}` [{photo['filename']}]({photo['source']})")
            if photo.get("thumb"):
                lines.append(f"  ![{photo['filename']}]({photo['thumb']})")
            visible = compact((photo.get("visible_text") or [])[:10])
            if visible:
                lines.append(f"  - 보이는 문구: {visible}")
            context = compact(photo.get("visual_context", ""))
            if context:
                lines.append(f"  - 사진 맥락: {context}")
        lines.extend(["", "백인식 메모:", "", "", ""])

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    payload = build()
    print(json.dumps({"json": str(OUT_JSON), "markdown": str(OUT_MD), "counts": payload["counts"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
