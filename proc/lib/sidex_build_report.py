#!/usr/bin/env python3
"""Build vendor matching JSON and Markdown report from SIDEX photo OCR sidecars."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from difflib import SequenceMatcher

from PIL import Image, ImageOps


ROOT = Path("/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04")
PHOTOS_DIR = ROOT / "output/sidex-2026/photos"
REFERENCE_DIR = ROOT / "output/sidex-2026/reference"
PARTNERS_JSON = REFERENCE_DIR / "sidex_partners.json"
EXHIBITORS_JSON = REFERENCE_DIR / "sidex2026_exhibitors.json"
OUT_JSON = ROOT / "output/sidex-2026/sidex_photo_analysis.json"
OUT_MD = ROOT / "output/sidex-2026/SIDEX_2026_photo_report.md"
VQA_RESULT_DIR = ROOT / "output/sidex-2026/vqa/results"
THUMBS_DIR = ROOT / "output/sidex-2026/thumbs"


SECTOR_KEYWORDS = {
    "스캐너": ["scanner", "scan", "intraoral", "구강스캐너", "스캔", "스캐너", "3d scan"],
    "밀링": ["milling", "mill", "cnc", "cam", "밀링", "가공"],
    "임플란트/부품": ["implant", "abutment", "임플란트", "어버트먼트", "fixture", "ti-base", "tibase"],
    "전산솔루션": ["software", "solution", "workflow", "platform", "cloud", "ai", "sw", "소프트웨어", "솔루션", "플랫폼", "워크플로우", "전산"],
    "CAD/CAM": ["cad", "cam", "exocad", "3d printing", "printer", "printing", "cad/cam", "프린팅", "프린터"],
    "아이디어제품": ["innovative", "idea", "new", "easy", "simple", "편리", "간편", "아이디어", "혁신"],
    "영상/진단": ["x-ray", "ct", "cbct", "imaging", "진단", "영상", "엑스레이", "구강카메라", "camera"],
    "교정": ["ortho", "aligner", "교정", "align"],
    "근관/보존": ["endo", "root canal", "근관", "레진", "bonding", "resin", "gutta", "paper point"],
    "수술/로봇": ["robot", "surgery", "surgical", "로봇", "수술", "autonomy", "자율주행"],
    "소모품/재료": ["material", "소재", "재료", "cement", "시멘트", "composite", "tip", "bur"],
    "위생/멸균": ["steril", "autoclave", "멸균", "소독", "위생"],
}

VQA_CATEGORY_TO_SECTOR = {
    "scanner": "스캐너",
    "milling": "밀링",
    "implant_parts": "임플란트/부품",
    "software": "전산솔루션",
    "cad_cam": "CAD/CAM",
    "robot": "수술/로봇",
    "imaging": "영상/진단",
    "orthodontics": "교정",
    "endo": "근관/보존",
    "materials": "소모품/재료",
    "hygiene": "위생/멸균",
    "idea_product": "아이디어제품",
}

MANUAL_VENDOR_ALIASES = [
    ("GENORAY", "제노레이"),
    ("VATECH", "바텍엠시스"),
    ("바텍", "바텍엠시스"),
    ("OSSTEM", "오스템임플란트"),
    ("OSTEIM", "오스템임플란트"),
    ("MagicPlan", "오스템임플란트"),
    ("MagicAlign", "오스템임플란트"),
    ("Alliedstar", "Alliedstar Medical Equipment"),
    ("Alliedstart", "Alliedstar Medical Equipment"),
    ("Aoralscan", "Shining 3D"),
    ("MetiSmile", "Shining 3D"),
    ("SHINING DENT", "Shining 3D"),
    ("SHINING 3D", "Shining 3D"),
    ("FUSSEN", "신원덴탈"),
    ("B&E", "비엔이코리아"),
]


def compact(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def norm(s: str) -> str:
    return re.sub(r"[^0-9a-zA-Z가-힣]+", "", (s or "").lower())


def ensure_thumb(image_path: str) -> str:
    src = Path(image_path)
    THUMBS_DIR.mkdir(parents=True, exist_ok=True)
    dst = THUMBS_DIR / f"{src.stem}_thumb.jpg"
    if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
        return str(dst)
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        im.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
        im.save(dst, "JPEG", quality=84, optimize=True)
    return str(dst)


def timestamp_from_stem(stem: str) -> str:
    m = re.search(r"(20\d{2})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})(\d{0,3})", stem)
    if not m:
        return ""
    y, mo, d, h, mi, sec, ms = m.groups()
    suffix = f".{ms}" if ms else ""
    return f"{y}-{mo}-{d} {h}:{mi}:{sec}{suffix}"


def aliases_for_partner(partner: dict) -> list[str]:
    name_chunks = []
    for key in [
        "name_logo_alt",
        "exhibitor_name",
        "name_ko",
        "name_alias",
        "logo_alt",
    ]:
        value = compact(partner.get(key, ""))
        if value:
            name_chunks.append(value)

    aliases = set()
    first = compact(
        partner.get("name_logo_alt", "")
        or partner.get("exhibitor_name", "")
        or partner.get("name_ko", "")
        or partner.get("logo_alt", "")
    )
    if first:
        aliases.add(first)
        aliases.add(re.sub(r"^\(?주\)?\s*", "", first))
        aliases.add(first.replace("(주)", "").replace("㈜", "").strip())

    # Pull obvious English/Korean company-name phrases from name fields only.
    front = " ".join(name_chunks)
    for m in re.finditer(r"[A-Z][A-Za-z0-9&.\- ]{2,45}", front):
        aliases.add(compact(m.group(0)))
        stripped = re.sub(
            r"\b(Co\.?|Ltd\.?|Inc\.?|Corporation|Corp\.?|Gmbh|LLC)\b",
            "",
            m.group(0),
            flags=re.I,
        )
        stripped = compact(stripped.replace(",", " "))
        if len(norm(stripped)) >= 4:
            aliases.add(stripped)
    for m in re.finditer(r"[가-힣㈜()]{2,30}", front):
        aliases.add(compact(m.group(0)))

    cleaned = []
    for alias in aliases:
        alias = compact(alias)
        n = norm(alias)
        generic = {
            "dental",
            "medical",
            "solution",
            "solutions",
            "system",
            "systems",
            "field",
            "implant",
            "implants",
            "scanner",
            "scan",
            "tech",
            "bio",
            "코리아",
            "임플란트",
            "스캐너",
            "테크",
            "바이오",
            "digital",
            "덴탈",
            "메디칼",
            "솔루션",
            "시스템",
            "치과",
            "주식회사",
        }
        if len(n) >= 3 and n not in generic and alias not in cleaned:
            cleaned.append(alias)
    return cleaned[:20]


def load_partners() -> list[dict]:
    if EXHIBITORS_JSON.exists():
        data = json.loads(EXHIBITORS_JSON.read_text(encoding="utf-8"))
        partners = data.get("records", [])
        reference_kind = "sidex2026_exhibitors"
    else:
        data = json.loads(PARTNERS_JSON.read_text(encoding="utf-8"))
        partners = data["exhibitors"]
        reference_kind = "sidex_partners"
    for p in partners:
        p["aliases"] = aliases_for_partner(p)
        p["search_text"] = compact(
            " ".join(
                str(part or "")
                for part in [
                    p.get("name_logo_alt"),
                    p.get("name_and_description"),
                    p.get("exhibitor_name"),
                    p.get("name_ko"),
                    p.get("name_alias"),
                    p.get("raw_text"),
                    p.get("description"),
                    " ".join(p.get("product_hints", []) or []),
                    p.get("booth"),
                ]
            )
        )
        p["reference_kind"] = reference_kind
    return partners


def score_partner(text: str, partner: dict) -> tuple[float, list[str]]:
    ntext = norm(text)
    lower_text = (text or "").lower()
    evidence = []
    score = 0.0

    partner_name_blob = " ".join(
        str(partner.get(key, "") or "")
        for key in ["exhibitor_name", "name_ko", "name_alias", "logo_alt", "name_logo_alt"]
    ).lower()

    if "덴탈로보틱스" in partner_name_blob or "dental robotics" in partner_name_blob:
        if any(
            marker in lower_text
            for marker in ["dentvla", "dental robotics", "수술 보조 로봇", "석션 로봇", "자율주행 수술"]
        ):
            score += 85
            evidence.append("domain:DentVLA/Dental Robotics")

    booth = partner.get("booth", "")
    if booth and norm(booth) in ntext:
        score += 40
        evidence.append(f"booth:{booth}")

    for alias in partner.get("aliases", []):
        nalias = norm(alias)
        if len(nalias) < 3:
            continue
        if nalias in ntext:
            if len(nalias) <= 4 and re.fullmatch(r"[a-z0-9]+", nalias):
                if not re.search(rf"(?<![a-z0-9]){re.escape(nalias)}(?![a-z0-9])", lower_text):
                    continue
            points = min(60, 18 + len(nalias) * 1.5)
            score += points
            evidence.append(f"name:{alias}")
        elif len(nalias) >= 5:
            # OCR often drops spaces or confuses romanized brand names.
            ratio = SequenceMatcher(None, nalias, ntext[: max(len(nalias) * 6, 80)]).ratio()
            if ratio > 0.55:
                points = min(18, ratio * 30)
                score += points
                evidence.append(f"fuzzy:{alias}:{ratio:.2f}")

    # Product/description token overlap.
    partner_tokens = {
        token
        for token in re.findall(r"[A-Za-z가-힣0-9]{3,}", partner.get("search_text", "").lower())
        if token not in {"ltd", "co", "주식회사", "company", "medical", "dental"}
    }
    text_tokens = set(re.findall(r"[A-Za-z가-힣0-9]{3,}", text.lower()))
    overlap = partner_tokens & text_tokens
    if overlap:
        score += min(18, len(overlap) * 2.5)
        evidence.append("tokens:" + ",".join(sorted(list(overlap))[:8]))

    if evidence and all(item.startswith("tokens:") for item in evidence):
        score = min(score, 12)

    return score, evidence[:8]


def load_vqa(stem: str) -> dict:
    path = VQA_RESULT_DIR / f"{stem}_vqa.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def vqa_payload(vqa_result: dict) -> dict:
    if not vqa_result:
        return {}
    return vqa_result.get("vqa", {}) or {}


def vqa_text_blob(vqa_result: dict) -> str:
    vqa = vqa_payload(vqa_result)
    parts = []
    for key in ["visible_text", "product_names", "product_categories", "claims", "uncertainties"]:
        value = vqa.get(key)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    parts.extend(str(v or "") for v in item.values())
    for item in vqa.get("brand_or_company_candidates", []) or []:
        if isinstance(item, dict):
            parts.append(item.get("name", ""))
            parts.append(item.get("evidence", ""))
        else:
            parts.append(str(item))
    parts.append(vqa.get("visual_context", ""))
    return compact(" ".join(parts))


def alias_in_text(alias: str, text: str) -> bool:
    if not alias or not text:
        return False
    nalias = norm(alias)
    ntext = norm(text)
    if len(nalias) >= 3:
        return nalias in ntext
    return bool(re.search(rf"(?<![A-Za-z0-9]){re.escape(alias)}(?![A-Za-z0-9])", text, flags=re.I))


def candidate_name_in_partner_blob(name: str, partner: dict) -> bool:
    nname = norm(name)
    if not nname:
        return False
    raw_blob = partner.get("search_text", "")
    partner_blob = norm(raw_blob)
    if re.fullmatch(r"[a-z0-9]+", nname) and len(nname) <= 5:
        return bool(re.search(rf"(?<![a-z0-9]){re.escape(nname)}(?![a-z0-9])", raw_blob.lower()))
    return nname in partner_blob


def candidate_name_in_partner_names(name: str, partner_names: str, alias_norms: list[tuple[str, str]]) -> bool:
    nname = norm(name)
    if not nname:
        return False
    if re.fullmatch(r"[a-z0-9]+", nname) and len(nname) <= 5:
        if re.search(rf"(?<![a-z0-9]){re.escape(nname)}(?![a-z0-9])", partner_names.lower()):
            return True
        return any(nname == nalias for _, nalias in alias_norms)
    partner_name_blob = norm(partner_names)
    return nname in partner_name_blob or any(nname == n or nname in n for _, n in alias_norms)


def partner_display_name(partner: dict) -> str:
    return compact(
        partner.get("exhibitor_name")
        or partner.get("name_logo_alt", "")
        or partner.get("name_ko", "")
        or partner.get("logo_alt", "")
    )


def score_partner_from_vqa(vqa_result: dict, partner: dict) -> tuple[float, list[str]]:
    vqa = vqa_payload(vqa_result)
    if not vqa:
        return 0, []

    score = 0.0
    evidence = []
    partner_blob = norm(partner.get("search_text", ""))
    raw_vqa_text = vqa_text_blob(vqa_result)
    partner_names = " ".join(
        str(partner.get(key, "") or "")
        for key in ["exhibitor_name", "name_ko", "name_alias", "logo_alt", "name_logo_alt"]
    )
    partner_name_blob = norm(partner_names)
    alias_norms = [(alias, norm(alias)) for alias in partner.get("aliases", []) if norm(alias)]

    for alias, target in MANUAL_VENDOR_ALIASES:
        if alias_in_text(alias, raw_vqa_text) and alias_in_text(target, partner_names + " " + partner.get("search_text", "")):
            score += 88
            evidence.append(f"vqa_manual_alias:{alias}->{target}")

    booth = norm(partner.get("booth", ""))
    for candidate in vqa.get("booth_candidates", []) or []:
        if booth and norm(str(candidate)) == booth:
            score += 25
            evidence.append(f"vqa_booth:{candidate}")

    for item in vqa.get("brand_or_company_candidates", []) or []:
        if isinstance(item, dict):
            name = compact(item.get("name", ""))
            vqa_conf = float(item.get("confidence") or 0)
        else:
            name = compact(str(item))
            vqa_conf = 0.5
        nname = norm(name)
        if len(nname) < 3:
            continue
        if candidate_name_in_partner_names(name, partner_names, alias_norms):
            score += 75 * max(vqa_conf, 0.6)
            evidence.append(f"vqa_company:{name}")
        elif candidate_name_in_partner_blob(name, partner):
            # Often the photographed brand is a represented product line rather than the Korean distributor name.
            score += 52 * max(vqa_conf, 0.5)
            evidence.append(f"vqa_partner_text:{name}")

    for product in vqa.get("product_names", []) or []:
        nproduct = norm(str(product))
        if len(nproduct) >= 4 and nproduct in partner_blob:
            score += 22
            evidence.append(f"vqa_product:{product}")

    visible_hits = 0
    for text in vqa.get("visible_text", []) or []:
        ntext = norm(str(text))
        if len(ntext) >= 4 and ntext in partner_blob:
            visible_hits += 1
    if visible_hits:
        score += min(24, visible_hits * 6)
        evidence.append(f"vqa_visible_text_hits:{visible_hits}")

    return score, evidence[:8]


def has_strong_vendor_evidence(score: float, evidence: list[str]) -> bool:
    if any(item.startswith(("booth:", "name:", "domain:", "vqa_company:", "vqa_manual_alias:")) for item in evidence):
        return score >= 30
    if any(item.startswith("vqa_booth:") for item in evidence):
        return score >= 70
    if any(item.startswith("vqa_partner_text:") for item in evidence):
        return score >= 42
    if any(item.startswith("vqa_product:") for item in evidence):
        return score >= 55
    return score >= 55


def sector_tags(*texts: str, vqa_result: dict | None = None) -> list[str]:
    haystack = " ".join(texts).lower()
    tags = []
    for tag, words in SECTOR_KEYWORDS.items():
        if any(word.lower() in haystack for word in words):
            tags.append(tag)
    if vqa_result:
        for category in vqa_payload(vqa_result).get("product_categories", []) or []:
            mapped = VQA_CATEGORY_TO_SECTOR.get(str(category))
            if mapped and mapped not in tags:
                tags.append(mapped)
    return tags


def claim_lines(lines: list[dict], vqa_result: dict | None = None) -> list[str]:
    picked = []
    if vqa_result:
        vqa = vqa_payload(vqa_result)
        for claim in vqa.get("claims", []) or []:
            claim = compact(str(claim))
            if claim and claim not in picked:
                picked.append(claim)
        for product in vqa.get("product_names", []) or []:
            product = compact(str(product))
            if product and product not in picked:
                picked.append(product)
    keywords = [
        "ai",
        "3d",
        "scan",
        "scanner",
        "cad",
        "cam",
        "implant",
        "robot",
        "solution",
        "workflow",
        "정확",
        "정밀",
        "안전",
        "자율",
        "스캔",
        "솔루션",
        "임플란트",
        "로봇",
        "세계",
        "최초",
        "실시간",
    ]
    for line in lines:
        text = compact(line.get("text", ""))
        if len(text) < 4:
            continue
        lower = text.lower()
        if any(k in lower for k in keywords):
            picked.append(text)
        if len(picked) >= 8:
            break
    if not picked:
        picked = [compact(line.get("text", "")) for line in lines[:5] if compact(line.get("text", ""))]
    return picked[:10]


def main() -> int:
    partners = load_partners()
    sidecars = sorted(PHOTOS_DIR.glob("20260529*_text.json"))
    photo_records = []

    for sidecar in sidecars:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        text = data.get("ocr", {}).get("raw_text", "")
        vqa_result = load_vqa(data["file_stem"])
        vqa_text = vqa_text_blob(vqa_result)
        match_text = compact("\n".join([text, vqa_text]))
        scores = []
        for partner in partners:
            text_score, text_evidence = score_partner(match_text, partner)
            vqa_score, vqa_evidence = score_partner_from_vqa(vqa_result, partner)
            score = text_score + vqa_score
            evidence = (vqa_evidence + text_evidence)[:10]
            if score > 0:
                scores.append((score, partner, evidence))
        scores.sort(key=lambda item: item[0], reverse=True)

        best = scores[0] if scores else (0, None, [])
        score, partner, evidence = best
        if not partner or not has_strong_vendor_evidence(score, evidence):
            partner = None
            evidence = evidence[:3] + ["needs_user_memo_for_vendor_name"] if evidence else ["needs_user_memo_for_vendor_name"]
            score = 0

        partner_text = partner.get("search_text", "") if partner else ""
        tags = sector_tags(text, partner_text, vqa_text, vqa_result=vqa_result)
        claims = claim_lines(data.get("ocr", {}).get("lines", []), vqa_result=vqa_result)
        vqa = vqa_payload(vqa_result)
        vqa_summary = {
            key: value
            for key, value in vqa.items()
            if key in [
                "visible_text",
                "brand_or_company_candidates",
                "booth_candidates",
                "product_names",
                "product_categories",
                "claims",
                "visual_context",
                "is_floor_map_or_booth_overview",
                "confidence",
                "uncertainties",
            ]
        }
        association_method = "none"
        if partner:
            association_method = "vqa_visual" if any(str(item).startswith("vqa_") for item in evidence) else "ocr_text"

        analysis = {
            "candidate_vendor": partner_display_name(partner) if partner else "미확인",
            "booth": partner.get("booth", "") if partner else "",
            "partner_href": (partner.get("view_url") or partner.get("href")) if partner else None,
            "confidence": round(min(score / 100, 1.0), 2) if partner else 0,
            "match_score": round(score, 2),
            "evidence": evidence,
            "association_method": association_method,
            "inferred_by_sequence": False,
            "memo_needed": partner is None,
            "needs_confirmation": partner is None,
            "memo_prompt": "업체명/부스/제품 맥락을 백인식 메모에 입력 필요" if partner is None else "",
            "observed_products_or_claims": claims,
            "sector_tags": tags,
            "nearby_or_sequence_context": [],
            "vqa_available": bool(vqa_result),
            "vqa_confidence": vqa.get("confidence") if vqa else None,
            "vqa_summary": vqa_summary,
        }
        data["analysis"] = analysis
        if vqa_result:
            data["vqa"] = vqa_result
        sidecar.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        photo_records.append(
            {
                "filename": data["filename"],
                "file": data["file"],
                "sidecar": str(sidecar),
                "timestamp": timestamp_from_stem(data["file_stem"]),
                "ocr_text": text,
                "ocr_lines": data.get("ocr", {}).get("lines", []),
                "analysis": analysis,
                "vqa_summary": vqa_summary,
            }
        )

    for idx, photo in enumerate(photo_records):
        analysis = photo["analysis"]
        if analysis.get("candidate_vendor") != "미확인":
            continue

        neighbors = []
        try:
            cur_t = datetime.strptime(photo["timestamp"][:19], "%Y-%m-%d %H:%M:%S")
        except Exception:
            cur_t = None
        if cur_t:
            for offset in [-1, 1, -2, 2, -3, 3]:
                ni = idx + offset
                if ni < 0 or ni >= len(photo_records):
                    continue
                other = photo_records[ni]
                other_analysis = other["analysis"]
                if other_analysis.get("candidate_vendor") == "미확인":
                    continue
                if (other_analysis.get("confidence") or 0) < 0.52:
                    continue
                try:
                    other_t = datetime.strptime(other["timestamp"][:19], "%Y-%m-%d %H:%M:%S")
                except Exception:
                    continue
                gap = abs((cur_t - other_t).total_seconds())
                if gap <= 180:
                    neighbors.append((gap, other))
        if not neighbors:
            continue

        neighbors.sort(key=lambda item: item[0])
        selected = neighbors[0][1]
        selected_analysis = selected["analysis"]
        conflict_candidates = [
            item.get("name")
            for item in analysis.get("vqa_summary", {}).get("brand_or_company_candidates", []) or []
            if isinstance(item, dict) and item.get("confidence", 0) >= 0.65
        ]
        if conflict_candidates:
            continue

        analysis["candidate_vendor"] = selected_analysis.get("candidate_vendor")
        analysis["booth"] = selected_analysis.get("booth", "")
        analysis["partner_href"] = selected_analysis.get("partner_href")
        analysis["confidence"] = round(min((selected_analysis.get("confidence") or 0.55) - 0.12, 0.58), 2)
        analysis["match_score"] = 0
        analysis["association_method"] = "walk_path_inferred"
        analysis["inferred_by_sequence"] = True
        analysis["memo_needed"] = True
        analysis["needs_confirmation"] = True
        analysis["memo_prompt"] = "전후 사진의 시간/동선으로 업체 연결을 추정함. 백인식 메모로 확인 필요"
        analysis["evidence"] = [
            f"walk_path_nearby:{selected['timestamp']}:{selected_analysis.get('candidate_vendor')}",
            *analysis.get("evidence", [])[:4],
        ]
        analysis["nearby_or_sequence_context"] = [
            {
                "timestamp": selected["timestamp"],
                "filename": selected["filename"],
                "candidate_vendor": selected_analysis.get("candidate_vendor"),
                "confidence": selected_analysis.get("confidence"),
                "gap_seconds": neighbors[0][0],
            }
        ]
        if not analysis.get("sector_tags"):
            analysis["sector_tags"] = selected_analysis.get("sector_tags", [])

    for photo in photo_records:
        sidecar = Path(photo["sidecar"])
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        data["analysis"] = photo["analysis"]
        sidecar.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    grouped = defaultdict(list)
    unknown_group_index = 0
    last_unknown_key = None
    for photo in photo_records:
        candidate_vendor = photo["analysis"].get("candidate_vendor") or "미확인"
        if candidate_vendor == "미확인":
            prev = grouped[last_unknown_key][-1] if last_unknown_key and grouped[last_unknown_key] else None
            same_unknown_run = False
            if prev:
                try:
                    cur_t = datetime.strptime(photo["timestamp"][:19], "%Y-%m-%d %H:%M:%S")
                    prev_t = datetime.strptime(prev["timestamp"][:19], "%Y-%m-%d %H:%M:%S")
                    same_unknown_run = (cur_t - prev_t).total_seconds() <= 180
                except Exception:
                    same_unknown_run = False
            if not same_unknown_run:
                unknown_group_index += 1
                last_unknown_key = f"업체명 미확인 {unknown_group_index:02d}"
            key = last_unknown_key
        else:
            key = candidate_vendor
            last_unknown_key = None
        grouped[key].append(photo)

    vendors = []
    for vendor, photos in grouped.items():
        first = photos[0]
        tags = sorted({tag for p in photos for tag in p["analysis"]["sector_tags"]})
        claim_pool = []
        for p in photos:
            for claim in p["analysis"]["observed_products_or_claims"]:
                if claim not in claim_pool:
                    claim_pool.append(claim)
        vendors.append(
            {
                "vendor": vendor,
                "memo_needed": any(p["analysis"].get("memo_needed") for p in photos),
                "unknown_vendor": vendor.startswith("업체명 미확인"),
                "booth": first["analysis"].get("booth", ""),
                "partner_href": first["analysis"].get("partner_href"),
                "photo_count": len(photos),
                "first_timestamp": first["timestamp"],
                "last_timestamp": photos[-1]["timestamp"],
                "sector_tags": tags,
                "key_observed_claims": claim_pool[:12],
                "photos": photos,
            }
        )
    vendors.sort(key=lambda v: v["first_timestamp"])

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "generated_at": datetime.now().astimezone().isoformat(),
                "photo_count": len(photo_records),
                "vendor_count": len(vendors),
                "vendors": vendors,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    lines = [
        "# SIDEX 2026 사진 기반 업체 관찰 리포트",
        "",
        f"- 생성 시각: {datetime.now().astimezone().isoformat()}",
        f"- 사진 수: {len(photo_records)}",
        f"- 업체 그룹 수: {len(vendors)}",
        f"- 업체 검색 레퍼런스: `{EXHIBITORS_JSON if EXHIBITORS_JSON.exists() else PARTNERS_JSON}`",
        f"- 전시 도면: `/Users/gq/Downloads/SIDEX2026_v3.pdf`",
        "",
        "## 전시회 인사이트",
        "",
        "- 현장 사진은 디지털 덴티스트리, AI/로봇, 구강스캐너, CAD/CAM, 임플란트/부품, 소재/소모품 영역이 반복적으로 등장한다.",
        "- 업체들은 단순 장비보다 `워크플로우`, `정확도`, `자동화`, `안전성`, `실시간 처리`, `진료/기공 효율`을 전면 주장하는 경향이 강하다.",
        "- 시간순 사진 묶음상 같은 부스에서 제품 패널, 장비 실물, 데모 화면을 연속 촬영한 구간이 많아, 단일 제품보다 업체의 포지셔닝을 함께 읽는 방식이 유효하다.",
        "- 낮은 신뢰도 사진은 축소 JPEG를 별도로 만들어 VQA로 재판독했다. OCR이 놓친 로고/제품명은 VQA 결과를 우선 반영하고, 그래도 직접 근거가 약한 경우에는 전후 3분 동선으로만 낮은 신뢰도 연결을 표시했다.",
        "- 업체명이 여전히 명확히 잡히지 않는 사진 묶음은 `업체명 미확인`으로 두었다. 해당 구간은 `백인식 메모:`에 업체명/부스/현장 기억을 보강하면 후속 정리에 반영하기 쉽다.",
        "",
        "## 업체별 정리",
        "",
    ]

    for vendor in vendors:
        booth = f" / {vendor['booth']}" if vendor.get("booth") else ""
        lines.extend(
            [
                f"### {vendor['vendor']}{booth}",
                "",
                f"- 사진: {vendor['photo_count']}장 (`{vendor['first_timestamp']}` ~ `{vendor['last_timestamp']}`)",
                f"- 섹터: {', '.join(vendor['sector_tags']) if vendor['sector_tags'] else '미분류'}",
            ]
        )
        if vendor.get("unknown_vendor"):
            lines.append("- 입력필요: 업체명 미확인. 아래 `백인식 메모:`에 업체명/부스/맥락 입력 필요.")
        elif vendor.get("memo_needed"):
            lines.append("- 입력필요: 업체 연결에 VQA/동선 기반 추정 포함. 아래 `백인식 메모:`에서 확인 필요.")
        if vendor.get("partner_href"):
            lines.append(f"- SIDEX 업체 페이지: {vendor['partner_href']}")
        lines.extend(["", "**관찰/주장 후보**", ""])
        for claim in vendor["key_observed_claims"][:8]:
            lines.append(f"- {claim}")
        if not vendor["key_observed_claims"]:
            lines.append("- OCR에서 뚜렷한 제품/주장 문구를 충분히 추출하지 못함.")
        lines.extend(["", "**사진 목록**", ""])
        for photo in vendor["photos"]:
            confidence = photo["analysis"].get("confidence", 0)
            method = photo["analysis"].get("association_method", "none")
            thumb = ensure_thumb(photo["file"])
            lines.append(
                f"- `{photo['timestamp']}` [{photo['filename']}]({photo['file']}) "
                f"(confidence {confidence}, method {method})"
            )
            lines.append(f"  ![{photo['filename']}]({thumb})")
            vqa_visible = photo.get("vqa_summary", {}).get("visible_text", []) or []
            if vqa_visible:
                lines.append(f"  - VQA: {compact(' / '.join(map(str, vqa_visible[:8])))}")
            brief = compact(photo["ocr_text"].replace("\n", " "))[:220]
            if brief:
                lines.append(f"  - OCR: {brief}")
        if vendor.get("unknown_vendor"):
            lines.extend(["", "입력필요 백인식 메모: 업체명 / 부스 / 내가 본 제품 / 추가 맥락:", "", "", ""])
        elif vendor.get("memo_needed"):
            lines.extend(["", "입력필요 백인식 메모: 업체 연결 확인 / 부스 / 내가 본 제품 / 추가 맥락:", "", "", ""])
        else:
            lines.extend(["", "백인식 메모:", "", "", ""])

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"json": str(OUT_JSON), "markdown": str(OUT_MD), "photos": len(photo_records), "vendors": len(vendors)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
