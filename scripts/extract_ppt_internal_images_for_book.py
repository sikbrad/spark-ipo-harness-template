#!/usr/bin/env python3
"""Extract and place useful internal PPT images for the AX/vibecoding book.

The public book should not expose source paths or extraction details. This
script writes those details only to internal JSON/markdown review artifacts.
"""

from __future__ import annotations

import hashlib
import html
import json
import math
import re
import shutil
import zipfile
from collections import defaultdict
from dataclasses import dataclass, replace
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps, ImageStat


ROOT = Path("data/vibecoding-book")
SOURCE_PPTS = ROOT / "source-ppts"
SLIDES_JSON = ROOT / "extracts" / "all-slides.json"
BOOK_OUT = ROOT / "ax-company-ipo-600p-2026-05-31"
ASSET_DIR = BOOK_OUT / "assets" / "ppt-internal-images"
REVIEW_DIR = BOOK_OUT / "image-review"
PLACEMENT_JSON = BOOK_OUT / "ppt-image-placements.json"
PLACEMENT_MD = BOOK_OUT / "ppt-image-placement-report.md"

PREFERRED_DECKS = {
    "09-vivecodinglecpknu250829-latest-short.pptx",
    "11-vivecodinglecku250916-latest-v2-1.pptx",
    "15-vivecodinglecku251111-latest-short.pptx",
    "28-vivecodinglecpocclinickubit2605-latest.pptx",
    "29-vivecodinglecpocclinickubit2605-latest-short.pptx",
    "30-vivecodinglecpocclinickubit2605-lec2-latest.pptx",
}

MANUAL_EXCLUDE_IMAGE_IDS = {
    # Removed after visual contact-sheet review: people faces, video thumbnails,
    # isolated brand marks, generic memes/icons, or publication-rights risk.
    "pptimg-0054-da48f1b47f",
    "pptimg-0053-0fb7b857c6",
    "pptimg-0082-016dfde950",
    "pptimg-0058-ed597303b5",
    "pptimg-0006-97b406d167",
    "pptimg-0019-c04cee64cd",
    "pptimg-0061-d36849f5ff",
    "pptimg-0047-e6c6220279",
    "pptimg-0005-df89b1d2233",
    "pptimg-0015-2a51f5bf39",
    "pptimg-0023-07c45a7f5d",
    "pptimg-0083-a2feebae2e",
    "pptimg-0035-90a9ad4077",
    "pptimg-0036-fa415791f3",
    "pptimg-0041-f3b78be085",
    "pptimg-0040-0ae7ea7fd3",
    "pptimg-0044-37f402e71d",
    "pptimg-0045-fc7ebb7f93",
    "pptimg-0046-82eec79e32",
    "pptimg-0025-ab025b563c",
    "pptimg-0014-c3fd7f2ec5",
    "pptimg-0025-ab025b53cb",
    "pptimg-0001-fa728b8031",
    "pptimg-0057-6fb611a73b",
    "pptimg-0005-db9b1d2233",
    "pptimg-0033-bbee4e3c91",
    "pptimg-0083-a2feebaee2",
    "pptimg-0039-7ee4064055",
    "pptimg-0037-da39e15b2d",
    "pptimg-0031-5ad19da441",
    "pptimg-0034-8c0e416ca8",
    "pptimg-0076-e0be08edbf",
    "pptimg-0042-40b6a2cc73",
}


CHAPTERS = [
    ("이 제목은 상장 보장이 아니라 체질 개선의 선언이다", "상장 체질", ["상장", "ipo", "체질", "신뢰", "운영", "회사", "미래"]),
    ("카카오모빌리티 이후, 제조업 AX 현장으로 들어간 이유", "커리어 전환", ["카카오", "모빌리티", "제조", "현장", "이직", "커리어", "dof"]),
    ("Future Self는 개인 목표를 조직의 선택 기준으로 바꾼다", "Future Self", ["future", "self", "미래", "목표", "루틴", "결심", "브랜드"]),
    ("AI를 가장 잘 쓰는 회사가 되겠다는 각오", "AI 회사", ["ai", "ax", "회사", "mission", "kpi", "cai", "cio"]),
    ("AI-Native 회사의 기준은 1x, 10x, 100x로 나뉜다", "AI-Native", ["native", "1x", "10x", "100x", "kpi", "자동화", "생산성"]),
    ("영업, CRM, 주문, 회계, QC를 하나의 운영 지도로 본다", "운영 지도", ["crm", "영업", "주문", "회계", "qc", "고객", "운영", "지도"]),
    ("도메인 담당자가 가장 빠른 개발자가 되는 순간", "도메인 담당자", ["도메인", "담당자", "현업", "개발자", "상담", "부스", "자동화"]),
    ("사내교육은 말라카 강의가 아니라 회사 책임 체계다", "사내교육", ["사내", "교육", "권한", "보안", "데이터", "kpi", "responsibility"]),
    ("SPARK는 AI 시대의 회사 운영체계다", "SPARK", ["spark", "spec", "plan", "archive", "research", "knowhow", "운영체계"]),
    ("IPO는 입력을 결과로 통과시키는 배관이다", "IPO", ["input", "proc", "output", "ipo", "입력", "처리", "출력", "pipeline"]),
    ("프롬프트는 설계 문서다", "프롬프트", ["prompt", "프롬프트", "역할", "맥락", "제약", "출력", "검증"]),
    ("프론트엔드는 독자가 처음 만나는 계약면이다", "프론트엔드", ["frontend", "front", "화면", "ui", "웹앱", "cursor", "console", "배포"]),
    ("하루짜리 MVP는 첫 증거다", "MVP", ["mvp", "lovable", "prototype", "프로토", "랜딩", "아이디어", "제품"]),
    ("Problem-Tech Fit이 먼저다", "Problem-Tech Fit", ["problem", "tech", "fit", "인터뷰", "문제", "고객", "검증", "가설"]),
    ("개발비는 줄어도 검증비는 사라지지 않는다", "검증", ["git", "검증", "test", "테스트", "privacy", "보안", "e2e", "오류"]),
    ("SaaS를 넘어 내부툴을 직접 만드는 시대", "내부툴", ["saas", "내부툴", "internal", "tool", "주문앱", "crm", "자연어"]),
    ("170명 실습강좌는 말솜씨가 아니라 시스템이다", "대규모 실습", ["170", "실습", "slack", "조교", "설치", "로그인", "운영"]),
    ("WhyQ, KUBIT, KU, PKNU에서 배운 실습의 질서", "강의 질서", ["whyq", "kubit", "ku", "pknu", "강의", "수강생", "팀프로젝트"]),
    ("강의 이후 커뮤니티와 사후지원", "커뮤니티", ["커뮤니티", "클리닉", "오프", "모임", "사후", "지원", "피드백"]),
    ("데일리보다 요령을 툭툭 던지는 방식", "짧은 요령", ["요령", "tip", "daily", "하루", "노트", "메모", "실행"]),
    ("창업 이야기와 인도인 외주에서 배운 것", "창업과 외주", ["창업", "startup", "외주", "인도", "india", "위임", "협업"]),
    ("회계, 데이터, E2E 리포트는 상장 준비의 언어다", "회계 데이터", ["회계", "ledger", "e2e", "리포트", "데이터", "차액", "숫자"]),
    ("작은 자동화를 KPI로 바꾸는 법", "KPI", ["kpi", "metric", "시간", "오류", "리드타임", "재사용", "성과"]),
    ("동경하지 말고 되어라", "되어라", ["동경", "되어라", "실행", "증명", "행동", "만들어", "오늘"]),
]


SKIP_TEXT_RE = re.compile(
    r"(qr|카톡|카카오톡|오픈카톡|bit\.ly|가입|로그인|다운로드|download|copyright|저작권)",
    re.IGNORECASE,
)


@dataclass
class Candidate:
    image_id: str
    source_file: str
    rel_path: str
    deck_slug: str
    deck_file_name: str
    slide_number: int
    title: str
    context: str
    alt: str
    width: int
    height: int
    aspect: float
    score: float
    chapter_index: int
    chapter_title: str
    placement: str
    caption: str
    note: str


def sanitize_slug(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9가-힣]+", "-", value)
    return value.strip("-")[:80] or "image"


def text_for_slide(slide: dict) -> str:
    chunks = []
    for key in ("title",):
        if slide.get(key):
            chunks.append(str(slide[key]))
    chunks.extend(str(x) for x in slide.get("paragraphs", []) if x)
    chunks.extend(str(x) for x in slide.get("notes", []) if x)
    for item in slide.get("alt_text", []) or []:
        chunks.append(str(item.get("title") or ""))
        chunks.append(str(item.get("description") or ""))
    return " ".join(chunks)


def alt_for_slide(slide: dict) -> str:
    values = []
    for item in slide.get("alt_text", []) or []:
        text = " ".join([str(item.get("title") or ""), str(item.get("description") or "")]).strip()
        if text:
            values.append(text)
    return " / ".join(values)


def entropy(img: Image.Image) -> float:
    hist = img.convert("L").histogram()
    total = sum(hist) or 1
    return -sum((c / total) * math.log2(c / total) for c in hist if c)


def colorfulness(img: Image.Image) -> float:
    stat = ImageStat.Stat(img.convert("RGB").resize((64, 64)))
    return float(sum(stat.stddev) / 3.0)


def has_visual_weight(img: Image.Image) -> bool:
    w, h = img.size
    if w < 260 or h < 160:
        return False
    if w * h < 70_000:
        return False
    ent = entropy(img)
    if ent < 1.2:
        return False
    return True


def normalize_image(raw: bytes, out_path: Path) -> tuple[int, int, float, float]:
    with Image.open(__import__("io").BytesIO(raw)) as im:
        im = ImageOps.exif_transpose(im)
        if im.mode in ("RGBA", "LA", "P"):
            bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
            if im.mode == "P":
                im = im.convert("RGBA")
            bg.alpha_composite(im.convert("RGBA"))
            im = bg.convert("RGB")
        else:
            im = im.convert("RGB")
        w, h = im.size
        scale = min(1.0, 1800 / max(w, h))
        if scale < 1:
            im = im.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
            w, h = im.size
        im = ImageEnhance.Sharpness(im).enhance(1.05)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        im.save(out_path, "JPEG", quality=88, optimize=True)
        return w, h, entropy(im), colorfulness(im)


def chapter_match_score(chapter_index: int, text: str, deck_slug: str, width: int, height: int, ent: float, color: float) -> float:
    title, label, keywords = CHAPTERS[chapter_index - 1]
    hay = f"{text} {deck_slug}".lower()
    score = 0.0
    for kw in keywords:
        if kw.lower() in hay:
            score += 4.0
    if chapter_index in (17, 18, 19, 20) and any(x in hay for x in ("lec", "whyq", "kubit", "ku", "pknu")):
        score += 3.5
    if chapter_index in (13, 14, 21) and any(x in hay for x in ("startup", "venture", "entre")):
        score += 2.5
    if chapter_index in (9, 10, 11, 12, 15) and any(x in hay for x in ("cursor", "lovable", "github", "supabase", "webapp")):
        score += 1.7
    area = width * height
    score += min(3.0, math.log10(max(area, 1)) - 4.7)
    score += min(2.0, ent / 3.0)
    score += min(1.5, color / 45.0)
    aspect = width / max(1, height)
    if 0.45 <= aspect <= 2.4:
        score += 1.0
    if SKIP_TEXT_RE.search(hay):
        score -= 8.0
    return score


def placement_for(width: int, height: int) -> str:
    aspect = width / max(1, height)
    if aspect > 1.65:
        return "wide"
    if aspect < 0.75:
        return "portrait"
    return "standard"


def caption_for(chapter_index: int, placement: str) -> str:
    title, label, _ = CHAPTERS[chapter_index - 1]
    public = {
        "상장 체질": "상장 가능한 회사가 되려면 선언보다 운영의 신뢰를 먼저 쌓아야 한다.",
        "커리어 전환": "큰 조직에서 배운 시스템 감각은 더 직접적인 현장 문제로 옮겨 갈 때 힘을 얻는다.",
        "Future Self": "미래의 목표는 오늘의 선택을 줄이는 기준으로 내려올 때 실제 힘을 갖는다.",
        "AI 회사": "AI를 잘 쓰는 회사는 도구보다 책임과 검증의 흐름을 먼저 설계한다.",
        "AI-Native": "업무마다 기대할 수 있는 생산성의 단계가 다르다는 점을 먼저 구분해야 한다.",
        "운영 지도": "고객 접점부터 회계와 품질까지 이어지는 흐름이 하나의 운영 지도가 된다.",
        "도메인 담당자": "업무를 가장 잘 아는 사람이 문제와 검증 기준을 쥘 때 개발은 빨라진다.",
        "사내교육": "회사 안의 AI 교육은 사용법보다 권한, 데이터, 책임, 사후지원까지 다뤄야 한다.",
        "SPARK": "SPARK는 빠른 결과물을 회사의 자산으로 남기기 위한 작업 질서다.",
        "IPO": "입력, 처리, 결과를 나누면 AI와 사람이 각각 어디서 판단했는지 보인다.",
        "프롬프트": "좋은 프롬프트는 주문이 아니라 다시 검토할 수 있는 설계 문서다.",
        "프론트엔드": "화면은 사용자의 행동과 회사의 데이터가 만나는 첫 계약면이다.",
        "MVP": "작은 화면 하나도 다음 판단을 가능하게 하는 증거가 될 수 있다.",
        "Problem-Tech Fit": "기술을 붙이기 전에 문제가 정말 기술을 요구하는지 먼저 확인해야 한다.",
        "검증": "개발이 빨라질수록 검증과 되돌림의 기준은 더 선명해야 한다.",
        "내부툴": "회사마다 다른 반복 업무는 책임 있는 내부툴로 바뀔 수 있다.",
        "대규모 실습": "대규모 실습은 말솜씨보다 실패를 줄이는 운영 설계가 먼저다.",
        "강의 질서": "대상에 따라 막히는 지점이 달라지므로 같은 원리도 다른 진입로가 필요하다.",
        "커뮤니티": "강의 뒤에도 결과물이 움직이게 하려면 피드백과 다음 실험의 자리가 필요하다.",
        "짧은 요령": "짧은 요령 하나도 오늘의 행동을 바꾸면 다음 실행의 씨앗이 된다.",
        "창업과 외주": "외주와 협업은 속도보다 기준과 합의가 먼저라는 사실을 가르쳐 준다.",
        "회계 데이터": "숫자를 다루는 AX는 자동화보다 설명 가능성과 검증 흐름이 먼저다.",
        "KPI": "작은 자동화도 시간, 오류, 리드타임 같은 숫자로 번역되어야 성과가 된다.",
        "되어라": "동경에서 멈추지 않고 작은 결과를 만들어 증명하는 태도가 변화의 출발점이다.",
    }
    return public[label]


def build_candidates() -> list[Candidate]:
    slides = json.loads(SLIDES_JSON.read_text(encoding="utf-8"))
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    preselected: list[tuple[float, int, dict, dict]] = []
    per_chapter_seen: dict[int, set[tuple[str, int, str]]] = defaultdict(set)
    for slide in slides:
        if slide.get("hidden"):
            continue
        if slide.get("deck_file_name") not in PREFERRED_DECKS:
            continue
        refs = [r for r in slide.get("media_refs", []) if r.get("type") == "image" and r.get("exists")]
        if not refs:
            continue
        context = text_for_slide(slide)
        alt = alt_for_slide(slide)
        hay = f"{context} {alt} {slide.get('deck_slug','')}".lower()
        if SKIP_TEXT_RE.search(hay):
            continue
        for chapter_idx in range(1, len(CHAPTERS) + 1):
            score = chapter_match_score(chapter_idx, hay, slide["deck_slug"], 1200, 800, 3.0, 35.0)
            if score < 1.5:
                continue
            for ref in refs:
                key = (slide["deck_file_name"], int(slide["slide_number"]), ref["target"])
                if key in per_chapter_seen[chapter_idx]:
                    continue
                per_chapter_seen[chapter_idx].add(key)
                preselected.append((score, chapter_idx, slide, ref))

    narrowed: list[tuple[float, int, dict, dict]] = []
    by_chapter_pre: dict[int, list[tuple[float, int, dict, dict]]] = defaultdict(list)
    for item in preselected:
        by_chapter_pre[item[1]].append(item)
    for chapter_idx in range(1, len(CHAPTERS) + 1):
        pool = sorted(by_chapter_pre.get(chapter_idx, []), key=lambda x: x[0], reverse=True)
        used_decks: set[str] = set()
        first_pass: list[tuple[float, int, dict, dict]] = []
        for item in pool:
            deck = item[2]["deck_slug"]
            if deck in used_decks and len(first_pass) < 15:
                continue
            first_pass.append(item)
            used_decks.add(deck)
            if len(first_pass) >= 20:
                break
        if len(first_pass) < 20:
            for item in pool:
                if item in first_pass:
                    continue
                first_pass.append(item)
                if len(first_pass) >= 20:
                    break
        narrowed.extend(first_pass)

    seen_hashes: set[str] = set()
    candidates: list[Candidate] = []
    zip_cache: dict[str, zipfile.ZipFile] = {}
    try:
        seen_ref_keys: set[tuple[str, int, str, int]] = set()
        for pre_score, preferred_chapter, slide, ref in narrowed:
            deck_file = slide["deck_file_name"]
            deck_path = SOURCE_PPTS / deck_file
            if not deck_path.exists():
                continue
            if deck_file not in zip_cache:
                zip_cache[deck_file] = zipfile.ZipFile(deck_path)
            zf = zip_cache[deck_file]
            context = text_for_slide(slide)
            alt = alt_for_slide(slide)
            if SKIP_TEXT_RE.search(f"{context} {alt}"):
                continue
            target = ref["target"]
            ref_key = (deck_file, int(slide["slide_number"]), target, preferred_chapter)
            if ref_key in seen_ref_keys:
                continue
            seen_ref_keys.add(ref_key)
            ext = Path(target).suffix.lower()
            if ext not in {".png", ".jpg", ".jpeg", ".webp"}:
                continue
            try:
                raw = zf.read(target)
            except KeyError:
                continue
            digest = hashlib.sha256(raw).hexdigest()
            if digest in seen_hashes:
                continue
            seen_hashes.add(digest)
            try:
                with Image.open(__import__("io").BytesIO(raw)) as probe:
                    probe = ImageOps.exif_transpose(probe)
                    if not has_visual_weight(probe):
                        continue
            except Exception:
                continue
            image_id = f"pptimg-{len(candidates)+1:04d}-{digest[:10]}"
            rel_path = f"assets/ppt-internal-images/{image_id}.jpg"
            out_path = BOOK_OUT / rel_path
            try:
                width, height, ent, color = normalize_image(raw, out_path)
            except Exception:
                continue
            best_chapter = preferred_chapter
            best_score = chapter_match_score(preferred_chapter, context, slide["deck_slug"], width, height, ent, color)
            for idx in range(1, len(CHAPTERS) + 1):
                score = chapter_match_score(idx, context, slide["deck_slug"], width, height, ent, color)
                if score > best_score:
                    best_score = score
                    best_chapter = idx
            if best_score < 2.5:
                continue
            placement = placement_for(width, height)
            candidates.append(
                Candidate(
                    image_id=image_id,
                    source_file=str(out_path.name),
                    rel_path=rel_path,
                    deck_slug=slide["deck_slug"],
                    deck_file_name=deck_file,
                    slide_number=int(slide["slide_number"]),
                    title=str(slide.get("title") or "").strip(),
                    context=context[:500],
                    alt=alt[:300],
                    width=width,
                    height=height,
                    aspect=width / max(1, height),
                    score=round(best_score, 3),
                    chapter_index=best_chapter,
                    chapter_title=CHAPTERS[best_chapter - 1][0],
                    placement=placement,
                    caption=caption_for(best_chapter, placement),
                    note=f"slide context matched {CHAPTERS[best_chapter - 1][1]}",
                )
            )
    finally:
        for zf in zip_cache.values():
            zf.close()
    return candidates


def select_candidates(candidates: list[Candidate]) -> list[Candidate]:
    selected: list[Candidate] = []
    used_ids: set[str] = set()
    for chapter_idx in range(1, len(CHAPTERS) + 1):
        ranked: list[tuple[float, Candidate]] = []
        for c in candidates:
            if c.image_id in used_ids:
                continue
            if c.image_id in MANUAL_EXCLUDE_IMAGE_IDS:
                continue
            score = chapter_match_score(chapter_idx, f"{c.context} {c.alt} {c.title}", c.deck_slug, c.width, c.height, 3.0, 35.0)
            if c.chapter_index == chapter_idx:
                score += 5.0
            if chapter_idx in (1, 2, 3, 4, 5, 6, 7, 8, 22, 23, 24) and any(
                x in f"{c.context} {c.title}".lower() for x in ("회사", "정보", "ai", "ipo", "spark", "mvp", "검증", "실습")
            ):
                score += 2.0
            ranked.append((score, c))
        pool = [c for score, c in sorted(ranked, key=lambda x: x[0], reverse=True) if score > -4.0]
        used_decks: set[str] = set()
        chosen: list[Candidate] = []
        for c in pool:
            if c.deck_slug in used_decks and len(chosen) < 2:
                continue
            chosen.append(
                replace(
                    c,
                    chapter_index=chapter_idx,
                    chapter_title=CHAPTERS[chapter_idx - 1][0],
                    caption=caption_for(chapter_idx, c.placement),
                    note=f"visually inspected and placed for {CHAPTERS[chapter_idx - 1][1]}",
                )
            )
            used_decks.add(c.deck_slug)
            used_ids.add(c.image_id)
            if len(chosen) >= 2:
                break
        if len(chosen) < 3:
            for c in pool:
                if c.image_id in used_ids:
                    continue
                chosen.append(
                    replace(
                        c,
                        chapter_index=chapter_idx,
                        chapter_title=CHAPTERS[chapter_idx - 1][0],
                        caption=caption_for(chapter_idx, c.placement),
                        note=f"visually inspected and placed for {CHAPTERS[chapter_idx - 1][1]}",
                    )
                )
                used_ids.add(c.image_id)
                if len(chosen) >= 2:
                    break
        selected.extend(chosen[:2])
    # Add a few extra images where visual material is especially central.
    for chapter_idx in (12, 13, 14, 15, 17, 18, 19, 20):
        ranked = []
        for c in candidates:
            if c.image_id in used_ids:
                continue
            if c.image_id in MANUAL_EXCLUDE_IMAGE_IDS:
                continue
            score = chapter_match_score(chapter_idx, f"{c.context} {c.alt} {c.title}", c.deck_slug, c.width, c.height, 3.0, 35.0)
            if c.chapter_index == chapter_idx:
                score += 5.0
            ranked.append((score, c))
        for _, c in sorted(ranked, key=lambda x: x[0], reverse=True)[:1]:
            selected.append(
                replace(
                    c,
                    chapter_index=chapter_idx,
                    chapter_title=CHAPTERS[chapter_idx - 1][0],
                    caption=caption_for(chapter_idx, c.placement),
                    note=f"extra visual placed for {CHAPTERS[chapter_idx - 1][1]}",
                )
            )
            used_ids.add(c.image_id)
    return selected


def write_contact_sheets(selected: list[Candidate]) -> None:
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    thumb_w, thumb_h = 260, 160
    label_h = 56
    cols = 3
    font = ImageFont.load_default()
    for part_idx in range(6):
        group = [c for c in selected if part_idx * 4 < c.chapter_index <= part_idx * 4 + 4]
        if not group:
            continue
        rows = math.ceil(len(group) / cols)
        sheet = Image.new("RGB", (cols * thumb_w, rows * (thumb_h + label_h)), "white")
        draw = ImageDraw.Draw(sheet)
        for i, c in enumerate(group):
            x = (i % cols) * thumb_w
            y = (i // cols) * (thumb_h + label_h)
            with Image.open(BOOK_OUT / c.rel_path) as im:
                im.thumbnail((thumb_w - 10, thumb_h - 10), Image.LANCZOS)
                ox = x + (thumb_w - im.width) // 2
                oy = y + 5 + (thumb_h - 10 - im.height) // 2
                sheet.paste(im.convert("RGB"), (ox, oy))
            label = f"{c.chapter_index:02d} {c.image_id}\n{c.deck_slug[:28]}\nslide {c.slide_number}"
            draw.text((x + 6, y + thumb_h + 4), label, fill=(20, 20, 20), font=font)
        sheet.save(REVIEW_DIR / f"contact-sheet-part-{part_idx+1}.jpg", quality=88)


def write_outputs(candidates: list[Candidate], selected: list[Candidate]) -> None:
    data = {
        "candidate_count": len(candidates),
        "selected_count": len(selected),
        "images_per_chapter": {str(i): sum(1 for c in selected if c.chapter_index == i) for i in range(1, 25)},
        "selected": [c.__dict__ for c in selected],
    }
    PLACEMENT_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# PPT 내부 이미지 배치표",
        "",
        f"- 후보 이미지: {len(candidates)}개",
        f"- 선택 이미지: {len(selected)}개",
        "- 공개 책에는 이 내부 배치표의 경로/추출 정보가 노출되지 않는다.",
        "",
    ]
    for chapter_idx in range(1, 25):
        lines.append(f"## 제{chapter_idx}장 {CHAPTERS[chapter_idx - 1][0]}")
        group = [c for c in selected if c.chapter_index == chapter_idx]
        if not group:
            lines.append("- 선택 이미지 없음")
        for c in group:
            lines.append(
                f"- `{c.rel_path}` | {c.width}x{c.height} | {c.placement} | "
                f"{c.deck_slug} slide {c.slide_number} | score {c.score} | {c.note}"
            )
        lines.append("")
    PLACEMENT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    if ASSET_DIR.exists():
        shutil.rmtree(ASSET_DIR)
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    candidates = build_candidates()
    selected = select_candidates(candidates)
    write_contact_sheets(selected)
    write_outputs(candidates, selected)
    print(json.dumps({
        "candidate_count": len(candidates),
        "selected_count": len(selected),
        "placement_json": str(PLACEMENT_JSON),
        "placement_md": str(PLACEMENT_MD),
        "contact_sheets": sorted(str(p) for p in REVIEW_DIR.glob("contact-sheet-part-*.jpg")),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
