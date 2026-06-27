#!/usr/bin/env python3
"""Build customer-support knowledge entities from dumped DOFSupport OneNote Markdown."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data" / "techsupport" / "onenote"
MD_ROOT = BASE / "mdfiles"
RAW_ROOT = BASE / "raw"
REVIEW_ROOT = BASE / "review"
OUT_ROOT = BASE / "entities"


INCLUDE_SECTION_KEYWORDS = [
    "Scanner",
    "01. Scanner",
    "02. Milling machine",
    "03. CAD",
    "04. CAM",
    "05. 기타",
    "06. 세일즈",
    "07. 3D 프린터",
    "02-1. Sintering machine",
    "헬프센터",
    "Finger sales",
    "Sales",
]

INTERNAL_SECTION_KEYWORDS = [
    "다오우오피스",
    "통장사본",
    "로보틱스 간담회",
    "/ TEST/",
    "TEST/",
]

INTERNAL_TITLE_KEYWORDS = [
    "자산관리",
    "일일보고",
    "쏘카",
    "비품",
    "물건구매",
    "국내배송",
    "해외배송",
    "지출품의서",
    "지출결의서",
    "10만원",
    "통장사본",
    "간담회",
    "주차등록",
    "저장공간 구매",
    "ID _ PASS",
    "ID / PASS",
    "ID/PASS",
    "ID_PASS",
    "계정",
    "password",
    "pass :",
    "비밀번호",
    "AJ파크",
    "테스트 보고서 작성",
]

CUSTOMER_TITLE_KEYWORDS = [
    "문의",
    "대응",
    "조치",
    "증상",
    "오류",
    "에러",
    "알람",
    "불량",
    "설정",
    "설치",
    "방법",
    "매뉴얼",
    "메뉴얼",
    "체크",
    "가이드",
    "지원",
    "트러블",
    "문제",
    "고장",
    "소음",
    "누수",
    "캘리브레이션",
    "calibration",
    "download",
    "link",
    "주문",
    "출고",
    "Trade in",
    "Forwarder",
]

PRODUCT_RULES = [
    ("scanner", ["Scanner", "스캐너", "ScanApp", "FREEDOM", "EDGE", "SWING", "PRIME", "카메라", "NVT", "uEye"]),
    ("milling_machine", ["Milling machine", "밀링", "CRAFT", "SHARP", "MotionApp", "스핀들", "집진기", "모션앱"]),
    ("cad", ["03. CAD", "exocad", "3shape", "엑소", "CAD"]),
    ("cam", ["04. CAM", "hyperDENT", "하이퍼덴트", "밀박스", "MillBox", "CAM"]),
    ("printer_3d", ["3D 프린터", "RAYSHAPE", "프린터"]),
    ("sintering_machine", ["02-1. Sintering machine", "Sintering", "700SF", "소결"]),
    ("pc_network", ["00. PC", "공유폴더", "네트워크", "윈도우", "Windows", "PC"]),
    ("sales_customer_ops", ["06. 세일즈", "Sales", "Trade in", "Forwarder", "주문", "출고", "송금수수료"]),
    ("implant_misc", ["기타 임플란트", "임플란트"]),
]

TYPE_RULES = [
    ("troubleshooting", ["이슈", "증상", "오류", "에러", "알람", "불량", "문제", "고장", "소음", "누수", "미인식", "안됨", "안 열", "멈", "실패"]),
    ("how_to", ["방법", "가이드", "메뉴얼", "매뉴얼", "설정", "설치", "활용법", "추가", "download", "link"]),
    ("customer_response", ["문의", "대응", "유저 조치", "고객", "전달", "촬영", "확인사항"]),
    ("warranty_policy", ["워런티", "warranty", "무상", "A/S", "AS"]),
    ("training_material", ["교육", "워크플로우", "템플릿", "자료"]),
    ("release_reference", ["릴리즈", "release", "공지사항", "Download Link"]),
    ("sales_procedure", ["Trade in", "주문", "출고", "Forwarder", "송금수수료"]),
]


@dataclass
class PageDoc:
    path: Path
    rel_path: str
    title: str
    notebook: str
    section_path: str
    created: str
    modified: str
    onenote_url: str | None
    body: str
    text: str
    local_links: list[str]
    remote_links: list[str]
    images: list[str]
    attachments: list[str]


def safe_slug(value: str, max_len: int = 70) -> str:
    text = unicodedata.normalize("NFC", value).strip() or "untitled"
    text = re.sub(r"[\\/:*?\"<>|\u0000-\u001f]", "_", text)
    text = re.sub(r"\s+", " ", text).strip(" .")
    if len(text) > max_len:
        text = text[:max_len].rstrip()
    return text or "untitled"


def json_dump(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def jsonl_write(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def clean_output_root() -> None:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    for child in OUT_ROOT.iterdir():
        if child.name == "viewer":
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def parse_markdown(path: Path) -> PageDoc:
    raw = path.read_text(encoding="utf-8")
    lines = raw.splitlines()
    title = lines[0].removeprefix("#").strip() if lines else path.stem
    meta: dict[str, str] = {}
    body_start = 0
    for idx, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            body_start = idx + 1
            break
        m = re.match(r"-\s+([^:]+):\s*(.*)$", line)
        if m:
            meta[m.group(1).strip()] = m.group(2).strip()
    body = "\n".join(lines[body_start:]).strip()
    notebook = meta.get("Notebook", "")
    section_path = meta.get("Section path", "")
    created = meta.get("Created", "")
    modified = meta.get("Modified", "")
    onenote_url = None
    m = re.search(r"-\s+OneNote:\s+\[[^\]]+\]\(([^)]+)\)", raw)
    if m:
        onenote_url = m.group(1)

    links = extract_links(raw)
    local_links = []
    remote_links = []
    images = []
    attachments = []
    for link in links:
        href = link["href"]
        if not href or re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", href) or href.startswith("#"):
            remote_links.append(href)
            continue
        local_links.append(href)
        if link["is_image"]:
            images.append(href)
        else:
            attachments.append(href)

    text = markdown_to_text(body)
    return PageDoc(
        path=path,
        rel_path=str(path.relative_to(MD_ROOT)),
        title=title,
        notebook=notebook,
        section_path=section_path,
        created=created,
        modified=modified,
        onenote_url=onenote_url,
        body=body,
        text=text,
        local_links=local_links,
        remote_links=remote_links,
        images=images,
        attachments=attachments,
    )


def extract_links(markdown_text: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    pattern = re.compile(r"(!?)\[[^\]]*\]\((?:<([^>]+)>|([^)]*))\)")
    for m in pattern.finditer(markdown_text):
        out.append({"is_image": bool(m.group(1)), "href": (m.group(2) or m.group(3) or "").strip()})
    return out


def markdown_to_text(markdown_text: str) -> str:
    text = re.sub(r"!\[[^\]]*\]\((?:<[^>]+>|[^)]*)\)", " ", markdown_text)
    text = re.sub(r"\[([^\]]+)\]\((?:<[^>]+>|[^)]*)\)", r"\1", text)
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.M)
    text = text.replace("|", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def contains_any(haystack: str, needles: list[str]) -> bool:
    lower = haystack.lower()
    return any(needle.lower() in lower for needle in needles)


def classify(doc: PageDoc) -> tuple[bool, str, list[str]]:
    haystack = f"{doc.rel_path}\n{doc.title}\n{doc.section_path}\n{doc.text[:2000]}"
    reasons: list[str] = []
    if doc.rel_path.startswith("TEST/"):
        return False, "test_notebook", ["TEST notebook is not customer-support knowledge"]
    if contains_any(doc.section_path, INTERNAL_SECTION_KEYWORDS) or contains_any(doc.rel_path, INTERNAL_SECTION_KEYWORDS):
        return False, "internal_company_ops", ["internal section path"]
    if contains_any(doc.title, INTERNAL_TITLE_KEYWORDS):
        return False, "internal_company_ops", ["internal/admin title keyword"]
    if contains_any(doc.text[:1200], ["ID :", "Pass :", "PW :", "password", "비밀번호"]):
        return False, "internal_credentials_or_it_resource", ["credential-like body text"]
    if (
        "05. 기타 / Zoom" in doc.section_path
        or "05. 기타 / Sync" in doc.section_path
        or "05. 기타 / 주차등록" in doc.section_path
        or "05. 기타 / 테스트 보고서 작성" in doc.section_path
        or "05. 기타 / MatchApp" in doc.section_path
        or "05. 기타 / SmileApp" in doc.section_path
    ):
        return False, "internal_credentials_or_it_resource", ["internal account/storage resource section"]
    if "헬프센터 / 0. 마스터" in doc.section_path:
        return False, "internal_knowledgebase_structure", ["help-center taxonomy/template"]

    section_included = contains_any(doc.section_path, INCLUDE_SECTION_KEYWORDS) or contains_any(doc.rel_path, INCLUDE_SECTION_KEYWORDS)
    title_included = contains_any(doc.title, CUSTOMER_TITLE_KEYWORDS)
    text_included = contains_any(doc.text[:1500], CUSTOMER_TITLE_KEYWORDS)
    if section_included:
        reasons.append("customer-support product/support section")
    if title_included:
        reasons.append("customer-response title signal")
    if text_included:
        reasons.append("customer-response body signal")
    if "DOF Support Notebook / 00. PC / 00. PC" in doc.section_path and doc.title.strip():
        reasons.append("PC/customer environment support section")
        return True, "customer_support_knowledge", reasons
    if section_included or title_included or text_included:
        return True, "customer_support_knowledge", reasons
    return False, "not_customer_response_knowledge", ["no customer-support signal"]


def pick_rule(value: str, rules: list[tuple[str, list[str]]], default: str) -> str:
    for label, needles in rules:
        if contains_any(value, needles):
            return label
    return default


def extract_tags(doc: PageDoc, product_area: str, support_type: str) -> list[str]:
    candidates: list[str] = [product_area, support_type]
    text = f"{doc.section_path} {doc.title} {doc.text[:1200]}"
    token_patterns = [
        r"\bCRAFT(?:\s?[A-Z0-9]+)?\b",
        r"\bSHARP(?:2)?(?:\s?PLUS)?\b",
        r"\bFREEDOM(?:\s?X5)?\b",
        r"\bEDGE\b",
        r"\bSWING\b",
        r"\bPRIME\b",
        r"\bScanApp(?:\s?3\.0)?\b",
        r"\bhyperDENT\b",
        r"\bMillBox\b",
        r"\bexocad\b",
        r"\b3shape\b",
        r"\bMotionApp(?:\s?3\.0)?\b",
        r"\bRAYSHAPE\b",
        r"\bWD40\b",
        r"\bNC\b",
        r"\bRPM\b",
        r"\bA/S\b",
        r"\bAS\b",
        r"\bTool\b",
        r"\bSpindle\b",
    ]
    for pat in token_patterns:
        candidates.extend(m.group(0) for m in re.finditer(pat, text, flags=re.I))
    korean_terms = [
        "스핀들",
        "집진기",
        "공유폴더",
        "네트워크",
        "캘리브레이션",
        "오토캘",
        "절삭유",
        "누수",
        "소음",
        "미인식",
        "카메라",
        "바운더리",
        "교합",
        "홀",
        "툴",
        "동글",
        "워런티",
        "유저 조치",
    ]
    for term in korean_terms:
        if term in text:
            candidates.append(term)
    seen = set()
    out = []
    for c in candidates:
        c = re.sub(r"\s+", " ", c).strip()
        key = c.lower()
        if not c or key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out[:18]


def split_steps(text: str) -> list[str]:
    lines = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        line = re.sub(r"^[\-•*]\s*", "", line)
        line = re.sub(r"^\d+[.)]\s*", "", line)
        if len(line) < 4:
            continue
        if re.match(r"^-+$", line):
            continue
        lines.append(line)
    return lines[:60]


def make_entity(doc: PageDoc, category: str, reasons: list[str]) -> dict[str, Any]:
    product_area = pick_rule(f"{doc.section_path} {doc.title}", PRODUCT_RULES, "general_support")
    support_type = pick_rule(f"{doc.section_path} {doc.title} {doc.text[:1200]}", TYPE_RULES, "reference")
    digest = hashlib.sha1(doc.rel_path.encode("utf-8")).hexdigest()[:10]
    page_no = re.match(r"(\d{4})", Path(doc.rel_path).name)
    entity_id = f"ts_onenote_{page_no.group(1) if page_no else digest}_{digest}"
    review_html = REVIEW_ROOT / "pages" / raw_page_key_to_html_name(doc.rel_path)
    source_raw_dir = raw_page_dir_for_md(doc.rel_path)
    summary = first_sentences(doc.text, max_chars=600)
    record = {
        "id": entity_id,
        "kind": "customer_support_knowledge",
        "title": doc.title,
        "product_area": product_area,
        "support_type": support_type,
        "section_path": doc.section_path,
        "tags": extract_tags(doc, product_area, support_type),
        "customer_relevance": {
            "included": True,
            "category": category,
            "reasons": reasons,
        },
        "source": {
            "markdown": str(doc.path.relative_to(ROOT)),
            "review_html": str(review_html.relative_to(ROOT)) if review_html.exists() else None,
            "raw_page_dir": str(source_raw_dir.relative_to(ROOT)) if source_raw_dir and source_raw_dir.exists() else None,
            "onenote_url": doc.onenote_url,
            "created": doc.created,
            "modified": doc.modified,
        },
        "assets": {
            "images": doc.images,
            "attachments": doc.attachments,
            "local_link_count": len(doc.local_links),
            "remote_link_count": len(doc.remote_links),
        },
        "summary": summary,
        "steps_or_notes": split_steps(doc.text),
        "full_text": doc.text,
    }
    return record


def first_sentences(text: str, max_chars: int = 600) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    last = max(cut.rfind("."), cut.rfind("다."), cut.rfind("?"), cut.rfind("!"))
    if last > 180:
        return cut[: last + 1].strip()
    return cut.rstrip() + "..."


def raw_page_key_to_html_name(rel_path: str) -> str:
    pages = json.loads((RAW_ROOT / "pages_index.json").read_text(encoding="utf-8"))
    by_md = {page.get("_mdRelPath"): page.get("_pageKey") for page in pages}
    key = by_md.get(rel_path)
    return f"{key}.html" if key else ""


def raw_page_dir_for_md(rel_path: str) -> Path | None:
    pages = json.loads((RAW_ROOT / "pages_index.json").read_text(encoding="utf-8"))
    by_md = {page.get("_mdRelPath"): page.get("_rawRelDir") for page in pages}
    rel = by_md.get(rel_path)
    return RAW_ROOT / rel if rel else None


def write_entity_markdown(record: dict[str, Any]) -> None:
    product = safe_slug(record["product_area"])
    filename = safe_slug(f"{record['id']} {record['title']}", max_len=120) + ".md"
    path = OUT_ROOT / "records" / product / filename
    source = record["source"]
    assets = record["assets"]
    lines = [
        "---",
        f"id: {json.dumps(record['id'], ensure_ascii=False)}",
        f"kind: {json.dumps(record['kind'], ensure_ascii=False)}",
        f"product_area: {json.dumps(record['product_area'], ensure_ascii=False)}",
        f"support_type: {json.dumps(record['support_type'], ensure_ascii=False)}",
        f"tags: {json.dumps(record['tags'], ensure_ascii=False)}",
        "---",
        "",
        f"# {record['title']}",
        "",
        f"- Section: {record['section_path']}",
        f"- Source Markdown: `{source['markdown']}`",
        f"- Review HTML: `{source['review_html']}`",
        f"- Raw page dir: `{source['raw_page_dir']}`",
        f"- Images: {len(assets['images'])}",
        f"- Attachments: {len(assets['attachments'])}",
    ]
    if source.get("onenote_url"):
        lines.append(f"- OneNote: {source['onenote_url']}")
    lines.extend(["", "## 요약", "", record["summary"] or "(요약할 텍스트 없음)", "", "## 고객응대 메모", ""])
    for item in record["steps_or_notes"]:
        lines.append(f"- {item}")
    lines.extend(["", "## 원문 텍스트", "", record["full_text"]])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    record["entity_markdown"] = str(path.relative_to(ROOT))


def build_indexes(included: list[dict[str, Any]], excluded: list[dict[str, Any]]) -> None:
    by_product: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in included:
        by_product[item["product_area"]].append(item)
        by_type[item["support_type"]].append(item)

    json_dump(OUT_ROOT / "indexes" / "by_product_area.json", {k: [x["id"] for x in v] for k, v in sorted(by_product.items())})
    json_dump(OUT_ROOT / "indexes" / "by_support_type.json", {k: [x["id"] for x in v] for k, v in sorted(by_type.items())})

    lines = [
        "# 기술지원 OneNote 고객응대 지식 엔티티",
        "",
        "이 디렉터리는 OneNote Markdown에서 고객응대/기술지원에 해당하는 지식만 추린 구조화 산출물이다.",
        "회사 전산자원관리규칙, 사내 행정/운영 규칙, 계정/비밀번호성 문서는 제외했다.",
        "",
        "## 요약",
        "",
        f"- Included entities: {len(included)}",
        f"- Excluded source pages: {len(excluded)}",
        f"- Product areas: {len(by_product)}",
        f"- Support types: {len(by_type)}",
        "",
        "## 제품/영역별",
        "",
    ]
    for product, rows in sorted(by_product.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        lines.append(f"- {product}: {len(rows)}")
    lines.extend(["", "## 유형별", ""])
    for support_type, rows in sorted(by_type.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        lines.append(f"- {support_type}: {len(rows)}")
    lines.extend(["", "## 파일", ""])
    lines.extend(
        [
            "- `entities.jsonl`: 포함된 고객응대 지식 전체",
            "- `excluded.jsonl`: 제외한 원본 페이지와 제외 이유",
            "- `records/`: 엔티티별 Markdown",
            "- `indexes/`: 제품/유형별 id 목록",
            "- `summary.json`: 통계",
        ]
    )
    (OUT_ROOT / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    summary = {
        "included_entities": len(included),
        "excluded_pages": len(excluded),
        "source_markdown_pages": len(included) + len(excluded),
        "product_area_counts": dict(Counter(item["product_area"] for item in included).most_common()),
        "support_type_counts": dict(Counter(item["support_type"] for item in included).most_common()),
        "excluded_reason_counts": dict(Counter(item["exclude_reason"] for item in excluded).most_common()),
    }
    json_dump(OUT_ROOT / "summary.json", summary)


def main() -> int:
    clean_output_root()

    docs = [parse_markdown(path) for path in sorted(MD_ROOT.glob("**/*.md"))]
    included: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for doc in docs:
        is_included, category_or_reason, reasons = classify(doc)
        if is_included:
            record = make_entity(doc, category_or_reason, reasons)
            write_entity_markdown(record)
            included.append(record)
        else:
            excluded.append(
                {
                    "title": doc.title,
                    "source_markdown": str(doc.path.relative_to(ROOT)),
                    "section_path": doc.section_path,
                    "exclude_reason": category_or_reason,
                    "details": reasons,
                }
            )

    jsonl_write(OUT_ROOT / "entities.jsonl", included)
    json_dump(OUT_ROOT / "entities.json", included)
    jsonl_write(OUT_ROOT / "excluded.jsonl", excluded)
    json_dump(OUT_ROOT / "excluded.json", excluded)
    build_indexes(included, excluded)
    print(json.dumps(json.loads((OUT_ROOT / "summary.json").read_text(encoding="utf-8")), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
