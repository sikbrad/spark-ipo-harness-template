#!/usr/bin/env python3
"""Build a Markdown/PDF sourcebook from latest vibecoding PPTX files."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import posixpath
import re
import shutil
import sys
import unicodedata
import zipfile
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from lxml import etree


BASE_DIR = Path(
    "/Users/gq/Library/CloudStorage/GoogleDrive-bispro89@gmail.com/"
    "Other computers/내PC백업/Dropbox_local_231107/Working"
)

PPT_SUFFIXES = {".ppt", ".pptx", ".pptm"}
VIBE_KEYWORDS = ("vibe", "vibecoding", "vivecoding", "바이브")

NS = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
RID = f"{{{NS['r']}}}id"


@dataclass
class SourceDeck:
    index: int
    source_path: Path
    copied_path: Path
    slug: str


def clean_ws(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def slugify(value: str, fallback: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_value).strip("-").lower()
    if not slug:
        digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:10]
        slug = f"{fallback}-{digest}"
    return slug[:110].strip("-")


def source_matches(path: Path) -> bool:
    if path.name.startswith("~$"):
        return False
    if path.suffix.lower() not in PPT_SUFFIXES:
        return False
    path_text = str(path).lower()
    return "latest" in path.name.lower() and any(key in path_text for key in VIBE_KEYWORDS)


def discover_sources(base_dir: Path) -> list[Path]:
    return sorted(path for path in base_dir.rglob("*") if path.is_file() and source_matches(path))


def normalize_target(base_file: str, target: str) -> str:
    if target.startswith("/"):
        return target.lstrip("/")
    return posixpath.normpath(posixpath.join(posixpath.dirname(base_file), target))


def parse_relationships(zf: zipfile.ZipFile, rels_path: str) -> dict[str, dict[str, str]]:
    if rels_path not in zf.namelist():
        return {}
    root = etree.fromstring(zf.read(rels_path))
    rels: dict[str, dict[str, str]] = {}
    for rel in root.findall(f"{{{REL_NS}}}Relationship"):
        rels[rel.get("Id", "")] = {
            "type": rel.get("Type", ""),
            "target": rel.get("Target", ""),
            "target_mode": rel.get("TargetMode", ""),
        }
    return rels


def extract_paragraphs(xml_bytes: bytes) -> list[str]:
    root = etree.fromstring(xml_bytes)
    paragraphs: list[str] = []
    for para in root.xpath(".//a:p", namespaces=NS):
        parts = [node.text or "" for node in para.xpath(".//a:t", namespaces=NS)]
        text = clean_ws("".join(parts))
        if text:
            paragraphs.append(text)
    return unique_adjacent(paragraphs)


def unique_adjacent(items: list[str]) -> list[str]:
    out: list[str] = []
    previous = None
    for item in items:
        if item != previous:
            out.append(item)
        previous = item
    return out


def extract_alt_text(xml_bytes: bytes) -> list[dict[str, str]]:
    root = etree.fromstring(xml_bytes)
    items: list[dict[str, str]] = []
    for node in root.xpath(".//p:cNvPr", namespaces=NS):
        title = clean_ws(node.get("title", ""))
        descr = clean_ws(node.get("descr", ""))
        if title or descr:
            items.append({"title": title, "description": descr})
    return items


def get_slide_order(zf: zipfile.ZipFile) -> list[str]:
    presentation_path = "ppt/presentation.xml"
    rels_path = "ppt/_rels/presentation.xml.rels"
    root = etree.fromstring(zf.read(presentation_path))
    rels = parse_relationships(zf, rels_path)
    slide_paths: list[str] = []
    for slide_id in root.xpath(".//p:sldId", namespaces=NS):
        rid = slide_id.get(RID)
        if not rid or rid not in rels:
            continue
        target = rels[rid]["target"]
        slide_paths.append(normalize_target("ppt/presentation.xml", target))
    return slide_paths


def read_core_properties(zf: zipfile.ZipFile) -> dict[str, str]:
    core_path = "docProps/core.xml"
    app_path = "docProps/app.xml"
    props: dict[str, str] = {}
    if core_path in zf.namelist():
        root = etree.fromstring(zf.read(core_path))
        for node in root.iter():
            tag = etree.QName(node).localname
            if tag in {"title", "subject", "creator", "created", "modified", "lastModifiedBy"}:
                text = clean_ws(node.text or "")
                if text:
                    props[tag] = text
    if app_path in zf.namelist():
        root = etree.fromstring(zf.read(app_path))
        for node in root.iter():
            tag = etree.QName(node).localname
            if tag in {"Application", "Slides", "Words"}:
                text = clean_ws(node.text or "")
                if text:
                    props[tag] = text
    return props


def extract_deck(deck: SourceDeck, extracts_dir: Path) -> dict[str, Any]:
    deck_dir = extracts_dir / deck.slug
    deck_dir.mkdir(parents=True, exist_ok=True)
    slide_records: list[dict[str, Any]] = []
    errors: list[str] = []
    props: dict[str, str] = {}

    if deck.copied_path.suffix.lower() not in {".pptx", ".pptm"}:
        return {
            "index": deck.index,
            "slug": deck.slug,
            "file_name": deck.copied_path.name,
            "source_path": str(deck.source_path),
            "copied_path": str(deck.copied_path),
            "supported": False,
            "errors": ["Legacy .ppt extraction is not supported by this pipeline."],
            "slides": [],
        }

    try:
        with zipfile.ZipFile(deck.copied_path) as zf:
            bad_member = zf.testzip()
            if bad_member:
                errors.append(f"Zip CRC check failed at {bad_member}")
            props = read_core_properties(zf)
            slide_paths = get_slide_order(zf)
            for slide_index, slide_path in enumerate(slide_paths, start=1):
                try:
                    slide_xml = zf.read(slide_path)
                    root = etree.fromstring(slide_xml)
                    hidden = root.get("show") == "0"
                    paragraphs = extract_paragraphs(slide_xml)
                    alt_text = extract_alt_text(slide_xml)
                    slide_rels = parse_relationships(
                        zf,
                        f"{posixpath.dirname(slide_path)}/_rels/{posixpath.basename(slide_path)}.rels",
                    )
                    media_refs = []
                    note_text: list[str] = []
                    for rel in slide_rels.values():
                        rel_type = rel["type"]
                        target = rel["target"]
                        if not target:
                            continue
                        target_path = normalize_target(slide_path, target)
                        if rel_type.endswith("/notesSlide") and target_path in zf.namelist():
                            notes = extract_paragraphs(zf.read(target_path))
                            slide_text_set = set(paragraphs)
                            note_text.extend([item for item in notes if item not in slide_text_set])
                        if "/image" in rel_type or "/media" in rel_type or "/video" in rel_type:
                            media_refs.append(
                                {
                                    "type": rel_type.rsplit("/", 1)[-1],
                                    "target": target_path,
                                    "exists": target_path in zf.namelist(),
                                }
                            )
                    title = choose_slide_title(paragraphs, slide_index)
                    slide_records.append(
                        {
                            "slide_number": slide_index,
                            "slide_path": slide_path,
                            "hidden": hidden,
                            "title": title,
                            "paragraphs": paragraphs,
                            "notes": unique_adjacent(note_text),
                            "alt_text": alt_text,
                            "media_refs": media_refs,
                            "text_count": len(paragraphs),
                        }
                    )
                except Exception as exc:  # noqa: BLE001 - preserve per-slide progress
                    errors.append(f"slide {slide_index}: {exc}")
    except Exception as exc:  # noqa: BLE001
        errors.append(str(exc))

    deck_record = {
        "index": deck.index,
        "slug": deck.slug,
        "file_name": deck.copied_path.name,
        "source_path": str(deck.source_path),
        "copied_path": str(deck.copied_path),
        "file_size_bytes": deck.copied_path.stat().st_size,
        "supported": True,
        "properties": props,
        "slide_count": len(slide_records),
        "hidden_slide_count": sum(1 for slide in slide_records if slide["hidden"]),
        "paragraph_count": sum(slide["text_count"] for slide in slide_records),
        "media_ref_count": sum(len(slide["media_refs"]) for slide in slide_records),
        "errors": errors,
        "slides": slide_records,
    }

    (deck_dir / "slides.json").write_text(
        json.dumps(deck_record, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (deck_dir / "slides.md").write_text(render_deck_markdown(deck_record), encoding="utf-8")
    return deck_record


def choose_slide_title(paragraphs: list[str], slide_index: int) -> str:
    for text in paragraphs:
        compact = clean_ws(text)
        if not compact:
            continue
        if re.fullmatch(r"\d{1,3}", compact):
            continue
        if len(compact) > 120:
            return compact[:117].rstrip() + "..."
        return compact
    return f"Slide {slide_index}"


def markdown_safe(text: str) -> str:
    text = clean_ws(text)
    text = text.replace("\\", "\\\\")
    return text


def render_deck_markdown(deck: dict[str, Any]) -> str:
    lines = [
        f"# {deck['index']:02d}. {deck['file_name']}",
        "",
        f"- 원본: `{deck['source_path']}`",
        f"- 복사본: `{deck['copied_path']}`",
        f"- 슬라이드: {deck.get('slide_count', 0)}장",
        f"- 숨김 슬라이드: {deck.get('hidden_slide_count', 0)}장",
        f"- 텍스트 단락: {deck.get('paragraph_count', 0)}개",
        "",
    ]
    for slide in deck.get("slides", []):
        hidden = " _(hidden)_" if slide.get("hidden") else ""
        lines.extend([f"## {slide['slide_number']}. {markdown_safe(slide['title'])}{hidden}", ""])
        body = slide.get("paragraphs", [])
        for paragraph in body:
            lines.append(f"- {markdown_safe(paragraph)}")
        if slide.get("notes"):
            lines.extend(["", "**Speaker notes**"])
            for note in slide["notes"]:
                lines.append(f"- {markdown_safe(note)}")
        if slide.get("media_refs"):
            lines.extend(["", f"_Media refs: {len(slide['media_refs'])}_"])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def copy_sources(sources: list[Path], source_dir: Path) -> list[SourceDeck]:
    source_dir.mkdir(parents=True, exist_ok=True)
    decks: list[SourceDeck] = []
    used_slugs: Counter[str] = Counter()
    for index, source_path in enumerate(sources, start=1):
        base_slug = slugify(source_path.stem, f"deck-{index:02d}")
        used_slugs[base_slug] += 1
        suffix = f"-{used_slugs[base_slug]}" if used_slugs[base_slug] > 1 else ""
        slug = f"{index:02d}-{base_slug}{suffix}"
        copied_path = source_dir / f"{slug}{source_path.suffix.lower()}"
        needs_copy = (
            not copied_path.exists()
            or copied_path.stat().st_size != source_path.stat().st_size
            or int(copied_path.stat().st_mtime) < int(source_path.stat().st_mtime)
        )
        if needs_copy:
            print(f"[copy] {index:02d}/{len(sources)} {source_path.name}", flush=True)
            shutil.copy2(source_path, copied_path)
        else:
            print(f"[copy] {index:02d}/{len(sources)} skip existing {source_path.name}", flush=True)
        decks.append(SourceDeck(index=index, source_path=source_path, copied_path=copied_path, slug=slug))
    return decks


def render_manifest(decks: list[SourceDeck]) -> list[dict[str, Any]]:
    manifest: list[dict[str, Any]] = []
    for deck in decks:
        stat = deck.copied_path.stat()
        manifest.append(
            {
                "index": deck.index,
                "slug": deck.slug,
                "source_path": str(deck.source_path),
                "copied_path": str(deck.copied_path),
                "file_name": deck.copied_path.name,
                "size_bytes": stat.st_size,
                "modified_time": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
            }
        )
    return manifest


def build_book(decks: list[dict[str, Any]], book_dir: Path) -> dict[str, Path]:
    book_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    total_slides = sum(deck.get("slide_count", 0) for deck in decks)
    hidden_slides = sum(deck.get("hidden_slide_count", 0) for deck in decks)
    total_paragraphs = sum(deck.get("paragraph_count", 0) for deck in decks)

    lines = [
        '<div class="cover">',
        "",
        "# 바이브코딩 최신 PPT 소스북",
        "",
        f"**생성일:** {generated_at}",
        "",
        f"**대상:** `latest`가 파일명에 포함된 바이브코딩 관련 PPT/PPTX {len(decks)}개",
        "",
        f"**범위:** 슬라이드 {total_slides}장, 숨김 {hidden_slides}장, 추출 단락 {total_paragraphs}개",
        "",
        "</div>",
        "",
        "\\newpage",
        "",
        "# 읽는 법",
        "",
        "이 문서는 원본 PPTX를 로컬로 복사한 뒤 슬라이드 XML에서 텍스트, 발표자 노트, 미디어 참조를 추출해 엮은 소스북이다. "
        "문장 재작성보다 원자료 보존을 우선했고, 각 장은 원본 덱 하나에 대응한다.",
        "",
        "# 원본 덱 목록",
        "",
        "| # | 파일 | 슬라이드 | 숨김 | 단락 |",
        "|---:|---|---:|---:|---:|",
    ]
    for deck in decks:
        lines.append(
            f"| {deck['index']:02d} | {markdown_safe(deck['file_name'])} | "
            f"{deck.get('slide_count', 0)} | {deck.get('hidden_slide_count', 0)} | "
            f"{deck.get('paragraph_count', 0)} |"
        )

    for deck in decks:
        chapter_title = deck_title(deck)
        lines.extend(
            [
                "",
                "\\newpage",
                "",
                f"# {deck['index']:02d}. {markdown_safe(chapter_title)}",
                "",
                f"- 파일: `{deck['file_name']}`",
                f"- 원본 경로: `{deck['source_path']}`",
                f"- 슬라이드: {deck.get('slide_count', 0)}장",
                f"- 숨김 슬라이드: {deck.get('hidden_slide_count', 0)}장",
                f"- 추출 단락: {deck.get('paragraph_count', 0)}개",
                "",
            ]
        )
        if deck.get("errors"):
            lines.extend(["**추출 경고**"])
            for error in deck["errors"]:
                lines.append(f"- {markdown_safe(error)}")
            lines.append("")
        for slide in deck.get("slides", []):
            hidden = " · hidden" if slide.get("hidden") else ""
            lines.extend(
                [
                    f"## Slide {slide['slide_number']}: {markdown_safe(slide['title'])}",
                    "",
                    f"<div class=\"slide-meta\">{deck['index']:02d}-{slide['slide_number']:03d}{hidden}</div>",
                    "",
                ]
            )
            body = slide.get("paragraphs", [])
            if body:
                for paragraph in body:
                    lines.append(f"- {markdown_safe(paragraph)}")
            else:
                lines.append("_텍스트 없음_")
            if slide.get("notes"):
                lines.extend(["", "**발표자 노트**"])
                for note in slide["notes"]:
                    lines.append(f"- {markdown_safe(note)}")
            if slide.get("media_refs"):
                lines.extend(["", f"<div class=\"media-note\">미디어 참조 {len(slide['media_refs'])}개</div>"])
            lines.append("")

    md_path = book_dir / "book.md"
    html_path = book_dir / "book.html"
    css_path = book_dir / "book.css"
    pdf_path = book_dir / "vibecoding-latest-ppt-sourcebook.pdf"

    md_text = "\n".join(lines).replace("\\newpage", '<div class="page-break"></div>')
    md_path.write_text(md_text, encoding="utf-8")
    css_path.write_text(book_css(), encoding="utf-8")
    write_html_and_pdf(md_text, css_path, html_path, pdf_path)
    return {"markdown": md_path, "html": html_path, "css": css_path, "pdf": pdf_path}


def deck_title(deck: dict[str, Any]) -> str:
    props = deck.get("properties") or {}
    title = clean_ws(props.get("title", ""))
    if title:
        return title
    return Path(deck["file_name"]).stem


def write_html_and_pdf(md_text: str, css_path: Path, html_path: Path, pdf_path: Path) -> None:
    try:
        import markdown
        from weasyprint import HTML
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("markdown and weasyprint packages are required for PDF rendering") from exc

    html_body = markdown.markdown(
        md_text,
        extensions=["extra", "tables", "sane_lists", "toc"],
        output_format="html5",
    )
    html_text = f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <title>바이브코딩 최신 PPT 소스북</title>
  <link rel="stylesheet" href="{html.escape(css_path.name)}">
</head>
<body>
{html_body}
</body>
</html>
"""
    html_path.write_text(html_text, encoding="utf-8")
    HTML(filename=str(html_path)).write_pdf(str(pdf_path), stylesheets=[str(css_path)])


def book_css() -> str:
    return """
@page {
  size: A4;
  margin: 18mm 17mm 20mm 17mm;
  @bottom-right {
    content: counter(page);
    color: #6b7280;
    font-size: 8.5pt;
  }
}

html {
  font-family: "Apple SD Gothic Neo", "Noto Sans CJK KR", "Pretendard", sans-serif;
  color: #15171a;
  line-height: 1.55;
  font-size: 10.4pt;
}

body {
  margin: 0;
}

.cover {
  min-height: 235mm;
  display: flex;
  flex-direction: column;
  justify-content: center;
  border-left: 7mm solid #111827;
  padding-left: 16mm;
}

.cover h1 {
  font-size: 34pt;
  line-height: 1.08;
  margin: 0 0 12mm 0;
  color: #111827;
}

h1 {
  break-before: page;
  font-size: 23pt;
  line-height: 1.18;
  margin: 0 0 9mm 0;
  padding-bottom: 4mm;
  border-bottom: 1.2pt solid #111827;
  color: #111827;
}

h2 {
  font-size: 14pt;
  margin: 8mm 0 3mm;
  line-height: 1.25;
  color: #1f2937;
  break-after: avoid;
}

p {
  margin: 0 0 3.5mm;
}

ul {
  margin: 0 0 4mm 5mm;
  padding: 0;
}

li {
  margin: 0 0 1.7mm;
  break-inside: avoid;
}

table {
  width: 100%;
  border-collapse: collapse;
  margin: 3mm 0 8mm;
  font-size: 8.3pt;
}

th {
  background: #111827;
  color: #fff;
  text-align: left;
}

th, td {
  border: 0.6pt solid #d1d5db;
  padding: 2mm;
  vertical-align: top;
}

code {
  font-family: "SF Mono", Menlo, monospace;
  font-size: 8.1pt;
  background: #f3f4f6;
  padding: 0.3mm 0.8mm;
  border-radius: 1mm;
}

.slide-meta,
.media-note {
  color: #6b7280;
  font-size: 8.2pt;
  margin: -1.5mm 0 2.5mm;
}

.page-break {
  break-before: page;
}
"""


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-dir", type=Path, default=BASE_DIR)
    parser.add_argument("--out-dir", type=Path, default=Path("data/vibecoding-book"))
    parser.add_argument("--skip-copy", action="store_true")
    args = parser.parse_args(argv)

    base_dir = args.base_dir.expanduser().resolve()
    out_dir = args.out_dir.expanduser().resolve()
    source_dir = out_dir / "source-ppts"
    extracts_dir = out_dir / "extracts"
    book_dir = out_dir / "book"
    logs_dir = out_dir / "logs"
    for directory in (source_dir, extracts_dir, book_dir, logs_dir):
        directory.mkdir(parents=True, exist_ok=True)

    print(f"[discover] base={base_dir}", flush=True)
    sources = discover_sources(base_dir)
    if not sources:
        print("[error] no matching PPT/PPTX files found", file=sys.stderr)
        return 1
    print(f"[discover] found {len(sources)} files", flush=True)

    if args.skip_copy:
        copied = sorted(source_dir.glob("*.ppt*"))
        decks = [
            SourceDeck(index=i, source_path=path, copied_path=path, slug=path.stem)
            for i, path in enumerate(copied, start=1)
        ]
    else:
        decks = copy_sources(sources, source_dir)

    manifest = render_manifest(decks)
    write_json(out_dir / "manifest.json", manifest)
    write_json(logs_dir / "source-paths.json", [str(path) for path in sources])

    deck_records = []
    all_slides = []
    for deck in decks:
        print(f"[extract] {deck.index:02d}/{len(decks)} {deck.copied_path.name}", flush=True)
        record = extract_deck(deck, extracts_dir)
        deck_records.append(record)
        for slide in record.get("slides", []):
            item = dict(slide)
            item["deck_index"] = record["index"]
            item["deck_slug"] = record["slug"]
            item["deck_file_name"] = record["file_name"]
            all_slides.append(item)

    write_json(extracts_dir / "decks.json", deck_records)
    write_json(extracts_dir / "all-slides.json", all_slides)
    write_json(
        extracts_dir / "slide-inventory.json",
        [
            {
                "deck_index": deck["index"],
                "file_name": deck["file_name"],
                "slide_count": deck.get("slide_count", 0),
                "hidden_slide_count": deck.get("hidden_slide_count", 0),
                "paragraph_count": deck.get("paragraph_count", 0),
                "errors": deck.get("errors", []),
            }
            for deck in deck_records
        ],
    )

    print("[book] render markdown/html/pdf", flush=True)
    book_paths = build_book(deck_records, book_dir)
    write_json(
        out_dir / "summary.json",
        {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "base_dir": str(base_dir),
            "output_dir": str(out_dir),
            "deck_count": len(deck_records),
            "total_size_bytes": sum(item["size_bytes"] for item in manifest),
            "slide_count": sum(deck.get("slide_count", 0) for deck in deck_records),
            "hidden_slide_count": sum(deck.get("hidden_slide_count", 0) for deck in deck_records),
            "paragraph_count": sum(deck.get("paragraph_count", 0) for deck in deck_records),
            "errors": {
                deck["file_name"]: deck.get("errors", [])
                for deck in deck_records
                if deck.get("errors")
            },
            "book_paths": {key: str(value) for key, value in book_paths.items()},
        },
    )
    print(f"[done] {book_paths['pdf']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
