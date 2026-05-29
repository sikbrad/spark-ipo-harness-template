#!/usr/bin/env python3
"""Build a polished SIDEX 2026 HTML/PDF report from the published visit dataset."""

from __future__ import annotations

import html
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import fitz
from PIL import Image, ImageOps
from weasyprint import HTML

ROOT = Path("/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04")
sys.path.insert(0, str(ROOT / "proc/lib"))

from sidex_outline_publish import all_photos, build_dataset, compact  # noqa: E402


OUT_ROOT = ROOT / "output/sidex-2026/pdf_report"
PDF_IMAGE_ROOT = OUT_ROOT / "images"
HTML_OUT = OUT_ROOT / "SIDEX_2026_visit_report.html"
PDF_OUT = OUT_ROOT / "SIDEX_2026_visit_report.pdf"
MANIFEST_OUT = OUT_ROOT / "SIDEX_2026_visit_report_manifest.json"
PREVIEW_DIR = OUT_ROOT / "preview"

IMAGE_MAX_EDGE = 1100
IMAGE_QUALITY = 78
INTERNAL_TERM_RE = re.compile(r"\b(qwen|vqa|ocr|snaps|handouts|originals)\b", re.I)

SECTOR_COLORS = [
    "#185a9d",
    "#2a9d8f",
    "#e76f51",
    "#6a4c93",
    "#bc6c25",
    "#3a86ff",
    "#7f5539",
    "#588157",
    "#d62828",
    "#4d908e",
    "#7209b7",
    "#577590",
]


def esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def clean_vendor_name(value: str) -> str:
    return re.sub(r"\s+", " ", value or "미확인 업체").strip()


def uniq(values: list[str], limit: int | None = None) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        text = re.sub(r"\s+", " ", str(value or "")).strip()
        if INTERNAL_TERM_RE.search(text):
            continue
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
        if limit and len(out) >= limit:
            break
    return out


def short_text(text: str, limit: int = 180) -> str:
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"


def sector_counts(vendors: list[dict[str, Any]]) -> list[tuple[str, int]]:
    counter: Counter[str] = Counter()
    for vendor in vendors:
        for sector in vendor.get("sectors") or []:
            counter[sector] += 1
    return counter.most_common()


def memo_vendors(vendors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [vendor for vendor in vendors if str(vendor.get("feedback_memo") or "").strip()]


def prepare_pdf_image(photo: dict[str, Any]) -> Path | None:
    image = photo.get("outline_image") or {}
    source = Path(image.get("published_path") or photo.get("source") or "")
    if not source.exists():
        return None
    PDF_IMAGE_ROOT.mkdir(parents=True, exist_ok=True)
    role = photo.get("role") or "photo"
    order = int(photo.get("path_order") or 0)
    output = PDF_IMAGE_ROOT / f"{role}_{order:03d}_{Path(photo.get('filename') or source.name).stem}.jpg"
    if output.exists() and output.stat().st_mtime >= source.stat().st_mtime:
        return output
    with Image.open(source) as raw:
        image_obj = ImageOps.exif_transpose(raw).convert("RGB")
        image_obj.thumbnail((IMAGE_MAX_EDGE, IMAGE_MAX_EDGE), Image.Resampling.LANCZOS)
        image_obj.save(output, "JPEG", quality=IMAGE_QUALITY, optimize=True)
    return output


def photo_cards(vendor: dict[str, Any]) -> tuple[str, int]:
    cards: list[str] = []
    count = 0
    for photo in all_photos(vendor):
        image_path = prepare_pdf_image(photo)
        if not image_path:
            continue
        count += 1
        role = "현장" if photo.get("role") == "snaps" else "자료"
        caption = " · ".join(
            part
            for part in [role, photo.get("timestamp"), photo.get("filename")]
            if part
        )
        cards.append(
            f"""
            <figure class="photo">
              <img src="{image_path.as_uri()}" alt="{esc(caption)}">
              <figcaption>{esc(caption)}</figcaption>
            </figure>
            """
        )
    return "\n".join(cards), count


def chip_list(values: list[str], *, limit: int = 10, css_class: str = "chip") -> str:
    items = uniq(values, limit)
    if not items:
        return '<span class="muted">-</span>'
    return "".join(f'<span class="{css_class}">{esc(item)}</span>' for item in items)


def bullet_list(values: list[str], *, limit: int = 7) -> str:
    items = uniq(values, limit)
    if not items:
        return '<p class="muted">확인된 강조 문구 없음</p>'
    return "<ul>" + "".join(f"<li>{esc(short_text(item, 150))}</li>" for item in items) + "</ul>"


def cover_images(vendors: list[dict[str, Any]], limit: int = 8) -> str:
    selected: list[dict[str, Any]] = []
    for vendor in vendors:
        photos = all_photos(vendor)
        if photos:
            selected.append(photos[0])
        if len(selected) >= limit:
            break
    cells = []
    for photo in selected:
        image_path = prepare_pdf_image(photo)
        if image_path:
            cells.append(f'<img src="{image_path.as_uri()}" alt="">')
    return "".join(cells)


def stats_cards(vendors: list[dict[str, Any]]) -> str:
    total_photos = sum(len(all_photos(vendor)) for vendor in vendors)
    memos = len(memo_vendors(vendors))
    sectors = len({sector for vendor in vendors for sector in (vendor.get("sectors") or [])})
    return f"""
    <section class="stats">
      <div><b>{len(vendors)}</b><span>정리 업체</span></div>
      <div><b>{total_photos}</b><span>사진/자료</span></div>
      <div><b>{memos}</b><span>현장 메모</span></div>
      <div><b>{sectors}</b><span>분야 분류</span></div>
    </section>
    """


def sector_bars(vendors: list[dict[str, Any]]) -> str:
    counts = sector_counts(vendors)
    if not counts:
        return ""
    max_count = max(count for _, count in counts)
    rows = []
    for index, (sector, count) in enumerate(counts):
        color = SECTOR_COLORS[index % len(SECTOR_COLORS)]
        width = max(5, round(count / max_count * 100, 1))
        rows.append(
            f"""
            <div class="bar-row">
              <div class="bar-label">{esc(sector)}</div>
              <div class="bar-track"><div class="bar-fill" style="width:{width}%; background:{color};"></div></div>
              <div class="bar-count">{count}</div>
            </div>
            """
        )
    return "\n".join(rows)


def memo_section(vendors: list[dict[str, Any]]) -> str:
    cards = []
    for vendor in memo_vendors(vendors):
        name = clean_vendor_name(vendor.get("vendor") or "")
        booth = vendor.get("booth") or ""
        memo = vendor.get("feedback_memo") or ""
        cards.append(
            f"""
            <article class="memo-card">
              <h3>{esc(name)}</h3>
              <div class="meta">{esc(booth)}</div>
              <p>{esc(memo)}</p>
            </article>
            """
        )
    return "\n".join(cards)


def vendor_section(vendors: list[dict[str, Any]]) -> tuple[str, int]:
    blocks = []
    image_count = 0
    for index, vendor in enumerate(vendors, start=1):
        name = clean_vendor_name(vendor.get("vendor") or "")
        booth = vendor.get("booth") or ""
        photos_html, count = photo_cards(vendor)
        image_count += count
        memo = str(vendor.get("feedback_memo") or "").strip()
        visible_texts: list[str] = []
        contexts: list[str] = []
        for photo in all_photos(vendor):
            visible_texts.extend(photo.get("visible_text") or [])
            if photo.get("visual_context"):
                contexts.append(photo["visual_context"])
        blocks.append(
            f"""
            <article class="vendor">
              <div class="vendor-head">
                <div class="vendor-index">{index:02d}</div>
                <div>
                  <h2>{esc(name)}</h2>
                  <p>{esc(booth)}</p>
                </div>
              </div>
              <div class="vendor-grid">
                <section>
                  <h3>분야</h3>
                  <div class="chips">{chip_list(vendor.get("sectors") or [], limit=12)}</div>
                </section>
                <section>
                  <h3>제품/브랜드</h3>
                  <div class="chips subtle">{chip_list(vendor.get("product_names") or [], limit=9, css_class="chip light")}</div>
                </section>
              </div>
              {f'<section class="memo-inline"><h3>백인식 메모</h3><p>{esc(memo)}</p></section>' if memo else ''}
              <section>
                <h3>회사가 강조한 점</h3>
                {bullet_list(vendor.get("claims") or [], limit=8)}
              </section>
              <section>
                <h3>현장에서 읽힌 문구</h3>
                <div class="chips textchips">{chip_list(visible_texts, limit=12, css_class="chip text")}</div>
              </section>
              <section>
                <h3>사진상 맥락</h3>
                {bullet_list(contexts, limit=4)}
              </section>
              <section>
                <h3>사진</h3>
                <div class="photos">{photos_html}</div>
              </section>
            </article>
            """
        )
    return "\n".join(blocks), image_count


def build_html(vendors: list[dict[str, Any]]) -> tuple[str, int]:
    now = datetime.now().strftime("%Y-%m-%d")
    vendor_html, image_count = vendor_section(vendors)
    html_doc = f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <title>SIDEX 2026 방문 인사이트 리포트</title>
  <style>
    @page {{
      size: A4;
      margin: 13mm 12mm 15mm;
      @bottom-center {{
        color: #7b8492;
        font-size: 8.5pt;
        content: "SIDEX 2026 방문 인사이트 리포트 · " counter(page) " / " counter(pages);
      }}
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: #18212f;
      font-family: "Apple SD Gothic Neo", "Nanum Gothic", sans-serif;
      font-size: 9.4pt;
      line-height: 1.46;
      background: #f5f7fb;
      word-break: keep-all;
      overflow-wrap: break-word;
    }}
    h1, h2, h3, p {{ margin: 0; }}
    ul {{ margin: 5px 0 0 17px; padding: 0; }}
    li {{ margin: 2px 0; }}
    .cover {{
      min-height: 252mm;
      padding: 26mm 15mm 13mm;
      color: #fff;
      background: linear-gradient(140deg, #10253f 0%, #153f55 48%, #1d665b 100%);
      page-break-after: always;
      position: relative;
      overflow: hidden;
    }}
    .cover:after {{
      content: "";
      position: absolute;
      inset: auto -20mm -28mm auto;
      width: 95mm;
      height: 95mm;
      border-radius: 50%;
      background: rgba(255,255,255,.08);
    }}
    .eyebrow {{
      letter-spacing: .08em;
      font-size: 9pt;
      font-weight: 800;
      color: #a8e6d7;
      text-transform: uppercase;
    }}
    .cover h1 {{
      margin-top: 9mm;
      max-width: 176mm;
      font-size: 31pt;
      line-height: 1.12;
      letter-spacing: 0;
    }}
    .cover .subtitle {{
      margin-top: 7mm;
      max-width: 148mm;
      color: #dcebf0;
      font-size: 12.2pt;
      line-height: 1.55;
    }}
    .cover-strip {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 3mm;
      margin-top: 17mm;
    }}
    .cover-strip img {{
      width: 100%;
      height: 37mm;
      object-fit: cover;
      border-radius: 4px;
      border: 1px solid rgba(255,255,255,.28);
    }}
    .cover-date {{
      margin-top: 11mm;
      color: #b7d0d8;
      font-size: 10pt;
    }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 4mm;
      margin-top: 15mm;
    }}
    .stats div {{
      padding: 5mm 4mm;
      background: rgba(255,255,255,.12);
      border: 1px solid rgba(255,255,255,.18);
      border-radius: 6px;
    }}
    .stats b {{
      display: block;
      font-size: 20pt;
      line-height: 1;
    }}
    .stats span {{
      display: block;
      margin-top: 2mm;
      color: #d9edf0;
      font-size: 8.7pt;
    }}
    .page {{
      background: #fff;
      padding: 6mm 5mm;
      page-break-after: always;
    }}
    .page h2 {{
      font-size: 19pt;
      line-height: 1.2;
      margin-bottom: 5mm;
      color: #10253f;
    }}
    .page-intro {{
      margin: -2mm 0 6mm;
      color: #5b6675;
      font-size: 10pt;
    }}
    .memo-grid {{
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 3.6mm;
    }}
    .memo-card {{
      padding: 4.3mm;
      border: 1px solid #dde5ee;
      border-left: 4px solid #2a9d8f;
      border-radius: 5px;
      background: #fbfdff;
      break-inside: avoid;
    }}
    .memo-card h3 {{
      font-size: 10.5pt;
      color: #17243a;
    }}
    .memo-card .meta {{
      margin-top: 1mm;
      color: #758293;
      font-size: 8pt;
    }}
    .memo-card p {{
      margin-top: 2.5mm;
      color: #263241;
    }}
    .insight-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 6mm;
      align-items: start;
    }}
    .insight-list {{
      padding: 5mm;
      border-radius: 6px;
      background: #f7fafc;
      border: 1px solid #e4eaf1;
    }}
    .insight-list h3, .bars h3 {{
      margin-bottom: 3mm;
      font-size: 12pt;
      color: #10253f;
    }}
    .bars {{
      padding: 5mm;
      border-radius: 6px;
      background: #fff;
      border: 1px solid #e4eaf1;
    }}
    .bar-row {{
      display: grid;
      grid-template-columns: 28mm 1fr 8mm;
      gap: 3mm;
      align-items: center;
      margin: 2.2mm 0;
      font-size: 8.2pt;
    }}
    .bar-track {{
      height: 3.4mm;
      background: #e7ecf3;
      border-radius: 99px;
      overflow: hidden;
    }}
    .bar-fill {{
      height: 100%;
      border-radius: 99px;
    }}
    .bar-count {{
      text-align: right;
      color: #405066;
      font-weight: 800;
    }}
    .vendor {{
      background: #fff;
      padding: 5.5mm 5mm 6mm;
      border-top: 1px solid #dfe6ef;
      page-break-inside: avoid;
    }}
    .vendor + .vendor {{ margin-top: 4mm; }}
    .vendor-head {{
      display: grid;
      grid-template-columns: 14mm 1fr;
      gap: 3.5mm;
      align-items: start;
      margin-bottom: 3.5mm;
    }}
    .vendor-index {{
      width: 12mm;
      height: 12mm;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      background: #10253f;
      color: #fff;
      font-weight: 800;
      font-size: 8.5pt;
    }}
    .vendor h2 {{
      font-size: 14.4pt;
      line-height: 1.22;
      color: #10253f;
    }}
    .vendor-head p {{
      color: #68768a;
      font-size: 8.5pt;
      margin-top: 1mm;
    }}
    .vendor h3 {{
      margin: 2.5mm 0 1.5mm;
      color: #2a3647;
      font-size: 9.2pt;
    }}
    .vendor-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 3.5mm;
    }}
    .chips {{
      display: flex;
      flex-wrap: wrap;
      gap: 1.5mm;
    }}
    .chip {{
      display: inline-block;
      padding: 1.2mm 2.2mm;
      border-radius: 99px;
      color: #0d3b38;
      background: #dff4ef;
      font-size: 7.7pt;
      font-weight: 700;
    }}
    .chip.light {{
      color: #233244;
      background: #eef2f7;
      font-weight: 650;
    }}
    .chip.text {{
      color: #4b5566;
      background: #f4f6f9;
      border: 1px solid #e0e6ee;
      font-weight: 500;
    }}
    .memo-inline {{
      margin: 3mm 0 1mm;
      padding: 3.5mm;
      background: #fff8e8;
      border: 1px solid #f0d38b;
      border-left: 4px solid #e09f3e;
      border-radius: 4px;
    }}
    .memo-inline h3 {{ margin: 0 0 1.2mm; color: #603d00; }}
    .photos {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 2.8mm;
      align-items: start;
    }}
    .photo {{
      margin: 0;
      break-inside: avoid;
      border: 1px solid #dfe6ef;
      border-radius: 4px;
      overflow: hidden;
      background: #fbfcfe;
    }}
    .photo img {{
      display: block;
      width: 100%;
      height: 39mm;
      object-fit: contain;
      background: #eef2f7;
    }}
    .photo figcaption {{
      min-height: 9mm;
      padding: 1.6mm 2mm;
      color: #667386;
      font-size: 7pt;
      line-height: 1.25;
    }}
    .muted {{ color: #8a95a5; }}
  </style>
</head>
<body>
  <section class="cover">
    <div class="eyebrow">SIDEX 2026 FIELD REPORT</div>
    <h1>SIDEX 2026 방문 인사이트 리포트</h1>
    <p class="subtitle">현장에서 촬영한 부스와 자료를 업체별로 묶어 분야, 제품, 주장, 백인식 메모를 한 번에 볼 수 있도록 정리했습니다.</p>
    {stats_cards(vendors)}
    <div class="cover-strip">{cover_images(vendors)}</div>
    <p class="cover-date">작성일 {esc(now)}</p>
  </section>

  <section class="page">
    <h2>백인식 현장 메모</h2>
    <p class="page-intro">현장에서 직접 남긴 판단과 코멘트를 우선 배치했습니다.</p>
    <div class="memo-grid">{memo_section(vendors)}</div>
  </section>

  <section class="page">
    <h2>전체 요약</h2>
    <div class="insight-grid">
      <div class="insight-list">
        <h3>전시장에서 읽힌 큰 흐름</h3>
        <ul>
          <li>디지털 워크플로우가 웹 기반 공유와 상담 도구로 확장되고 있습니다.</li>
          <li>중국 장비와 OEM 공급을 활용한 저가형 스캐너·밀링·퍼네스 패키지 경쟁이 강해졌습니다.</li>
          <li>대형 임플란트사는 장비, 소모품, 진단, 이벤트 운영까지 묶은 수직계열화 모습을 보였습니다.</li>
          <li>구강스캐너는 고성능 브랜드, 저가형 OEM, 모바일 연동형 제품이 동시에 경쟁하는 구도입니다.</li>
          <li>로봇, 상담 솔루션, 미용 장비, 산업디자인처럼 진료 주변 영역의 제품화도 눈에 띕니다.</li>
        </ul>
      </div>
      <div class="bars">
        <h3>분야별 업체 수</h3>
        {sector_bars(vendors)}
      </div>
    </div>
  </section>

  <section class="page">
    <h2>업체별 정리</h2>
    <p class="page-intro">업체별 분야, 주력 주장, 현장 메모와 이미지를 함께 묶었습니다.</p>
    {vendor_html}
  </section>
</body>
</html>
"""
    return html_doc, image_count


def render_preview(pdf_path: Path) -> list[str]:
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)
    outputs: list[str] = []
    try:
        for index in range(min(5, len(doc))):
            page = doc[index]
            pix = page.get_pixmap(matrix=fitz.Matrix(0.55, 0.55), alpha=False)
            out = PREVIEW_DIR / f"page_{index + 1:02d}.jpg"
            pix.save(out)
            outputs.append(str(out))
    finally:
        doc.close()
    return outputs


def pdf_stats(pdf_path: Path) -> dict[str, Any]:
    doc = fitz.open(pdf_path)
    try:
        image_refs = sum(len(page.get_images(full=True)) for page in doc)
        return {
            "pages": len(doc),
            "embedded_image_refs": image_refs,
            "size_bytes": pdf_path.stat().st_size,
        }
    finally:
        doc.close()


def main() -> None:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    vendors, _feedback, dataset = build_dataset()
    html_doc, image_count = build_html(vendors)
    HTML_OUT.write_text(html_doc, encoding="utf-8")
    HTML(filename=str(HTML_OUT), base_url=str(OUT_ROOT)).write_pdf(str(PDF_OUT))
    preview_paths = render_preview(PDF_OUT)
    stats = pdf_stats(PDF_OUT)
    manifest = {
        "html": str(HTML_OUT),
        "pdf": str(PDF_OUT),
        "preview": preview_paths,
        "vendors": len(vendors),
        "photos_in_report": image_count,
        "feedback_memos": len(memo_vendors(vendors)),
        "dataset_counts": dataset.get("counts") or {},
        "pdf": stats,
    }
    MANIFEST_OUT.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
