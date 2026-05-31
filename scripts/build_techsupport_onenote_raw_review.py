#!/usr/bin/env python3
"""Build local OneNote-like raw HTML review pages with local resource paths."""

from __future__ import annotations

import html
import json
import os
import re
import shutil
from pathlib import Path
from urllib.parse import quote, urlparse

from bs4 import BeautifulSoup, Tag


ROOT = Path(__file__).resolve().parents[1]
BASE_OUT = ROOT / "data" / "techsupport" / "onenote"
RAW_DIR = BASE_OUT / "raw"
OUT_DIR = BASE_OUT / "raw_review"
PAGES_DIR = OUT_DIR / "pages"


def read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def rel_path(target: Path, start: Path) -> str:
    return quote(os.path.relpath(target, start).replace(os.sep, "/"), safe="/")


def px_from_style(style: str | None, prop: str) -> float:
    if not style:
        return 0.0
    match = re.search(rf"{re.escape(prop)}\s*:\s*(-?\d+(?:\.\d+)?)px", style)
    return float(match.group(1)) if match else 0.0


def number_attr(tag: Tag, name: str) -> float:
    value = tag.get(name)
    if value is None:
        return 0.0
    match = re.match(r"\s*(-?\d+(?:\.\d+)?)", str(value))
    return float(match.group(1)) if match else 0.0


def image_resource_url_and_type(img: Tag) -> tuple[str | None, str | None]:
    src = img.get("src")
    src_type = img.get("data-src-type")
    fullres = img.get("data-fullres-src")
    fullres_type = img.get("data-fullres-src-type")
    if fullres and (fullres_type or "").lower().startswith("image/"):
        return fullres, fullres_type
    return src or fullres, src_type or fullres_type


def resource_key(url: str | None) -> str:
    if not url:
        return ""
    match = re.search(r"/onenote/resources/([^/?#]+)(/[^?#]+)?", url)
    if match:
        return f"{match.group(1)}{match.group(2) or '/$value'}"
    parsed = urlparse(url)
    return parsed.path + (f"?{parsed.query}" if parsed.query else "")


def resource_maps(resources: list[dict]) -> tuple[dict[str, dict], dict[str, dict]]:
    by_url: dict[str, dict] = {}
    by_key: dict[str, dict] = {}
    for item in resources:
        url = item.get("url")
        if not url:
            continue
        by_url[url] = item
        by_key[resource_key(url)] = item
    return by_url, by_key


def local_resource_path(item: dict | None) -> Path | None:
    if not item or item.get("status") != "ok":
        return None
    for key in ("raw_path", "md_path"):
        value = item.get(key)
        if value:
            path = BASE_OUT / value
            if path.exists():
                return path
    return None


def lookup_resource(url: str | None, by_url: dict[str, dict], by_key: dict[str, dict]) -> dict | None:
    if not url:
        return None
    return by_url.get(url) or by_key.get(resource_key(url))


def replace_image_with_placeholder(soup: BeautifulSoup, img: Tag, reason: str, css_class: str = "onenote-missing-image") -> None:
    placeholder = soup.new_tag("div")
    placeholder["class"] = css_class
    width = number_attr(img, "width") or 320
    height = number_attr(img, "height") or 180
    placeholder["style"] = f"width:{int(width)}px;min-height:{int(height)}px"
    placeholder["data-original-img-id"] = img.get("id") or ""
    placeholder.string = reason
    img.replace_with(placeholder)


def direct_node_height(tag: Tag) -> float:
    style = tag.get("style")
    height = px_from_style(style, "height") or number_attr(tag, "height")
    if height:
        return height
    max_child_bottom = 0.0
    for child in tag.find_all(["img", "table", "div", "p"], recursive=True):
        child_style = child.get("style")
        child_top = px_from_style(child_style, "top")
        child_height = px_from_style(child_style, "height") or number_attr(child, "height")
        if not child_height and child.name == "p":
            text = child.get_text(" ", strip=True)
            child_height = 24.0 + (len(text) // 90) * 20.0 if text else 0.0
        max_child_bottom = max(max_child_bottom, child_top + child_height)
    if max_child_bottom:
        return max_child_bottom
    text = tag.get_text(" ", strip=True)
    return 32.0 + (len(text) // 90) * 20.0 if text else 0.0


def estimate_min_height(body: Tag) -> int:
    max_bottom = 0.0
    for child in body.find_all(recursive=False):
        if not isinstance(child, Tag):
            continue
        top = px_from_style(child.get("style"), "top")
        max_bottom = max(max_bottom, top + direct_node_height(child))
    return max(720, int(max_bottom + 96))


def rewrite_images(soup: BeautifulSoup, page_dir: Path, by_url: dict[str, dict], by_key: dict[str, dict]) -> dict:
    stats = {
        "images": 0,
        "local_images": 0,
        "missing_images": 0,
        "remote_images": 0,
        "non_previewable_images": 0,
        "source_missing_images": 0,
        "unavailable_images": 0,
    }
    for img in soup.find_all("img"):
        stats["images"] += 1
        url, mime_type = image_resource_url_and_type(img)
        if not url:
            stats["source_missing_images"] += 1
            alt = img.get("alt") or "OneNote source image has no URL."
            replace_image_with_placeholder(soup, img, f"원본 OneNote에서 이미지 링크 없음: {alt}")
            continue
        item = lookup_resource(url, by_url, by_key)
        local_path = local_resource_path(item)
        if local_path:
            img["data-original-src"] = url or ""
            img["src"] = rel_path(local_path, page_dir)
            stats["local_images"] += 1
            suffix = local_path.suffix.lower()
            if suffix not in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}:
                stats["non_previewable_images"] += 1
                img["data-non-previewable"] = "true"
        elif item:
            stats["unavailable_images"] += 1
            reason = item.get("error") or "downloaded resource is unavailable"
            replace_image_with_placeholder(soup, img, f"Graph 이미지 본문 비어 있음: {reason}", "onenote-missing-image unavailable")
        elif url and url.startswith("http"):
            stats["missing_images"] += 1
            replace_image_with_placeholder(soup, img, "로컬에 저장된 이미지 리소스가 없습니다.", "onenote-missing-image unavailable")
        else:
            stats["missing_images"] += 1
            replace_image_with_placeholder(soup, img, "이미지 리소스 경로가 없습니다.", "onenote-missing-image unavailable")
        if mime_type:
            img["data-resource-type"] = mime_type
    return stats


def rewrite_attachments(soup: BeautifulSoup, page_dir: Path, by_url: dict[str, dict], by_key: dict[str, dict]) -> dict:
    stats = {"attachments": 0, "local_attachments": 0, "missing_attachments": 0}
    for obj in list(soup.find_all("object")):
        stats["attachments"] += 1
        url = obj.get("data")
        item = lookup_resource(url, by_url, by_key)
        local_path = local_resource_path(item)
        label = obj.get("data-attachment") or (item or {}).get("attachment_name") or "attachment"
        link = soup.new_tag("a")
        link["class"] = "onenote-attachment"
        link.string = label
        if local_path:
            link["href"] = rel_path(local_path, page_dir)
            stats["local_attachments"] += 1
        else:
            link["href"] = url or "#"
            link["data-missing-resource"] = "true"
            stats["missing_attachments"] += 1
        obj.replace_with(link)
    return stats


def render_page(page: dict) -> dict:
    page_key = page["_pageKey"]
    raw_page_dir = RAW_DIR / page["_rawRelDir"]
    content_path = raw_page_dir / "content.html"
    resources_path = raw_page_dir / "resources.json"
    out_path = PAGES_DIR / f"{page_key}.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    meta_title = page.get("title") or "(untitled)"
    section_path = " / ".join(page.get("_sectionPath") or [])
    resources = read_json(resources_path) if resources_path.exists() else []
    by_url, by_key = resource_maps(resources if isinstance(resources, list) else [])

    if not content_path.exists():
        error_path = raw_page_dir / "error.json"
        error = read_json(error_path) if error_path.exists() else {}
        message = error.get("error") if isinstance(error, dict) else "content.html missing"
        out_path.write_text(
            raw_shell(
                meta_title,
                section_path,
                f'<div class="missing-page"><h1>{html.escape(meta_title)}</h1>'
                f"<p>OneNote content endpoint error: {html.escape(str(message))}</p></div>",
                body_attrs="",
            ),
            encoding="utf-8",
        )
        return {
            "page_key": page_key,
            "title": meta_title,
            "section_path": section_path,
            "status": "missing_content",
            "html_path": str(out_path.relative_to(BASE_OUT)),
            "source_content": str(content_path.relative_to(BASE_OUT)),
            "images": 0,
            "local_images": 0,
            "missing_images": 0,
            "remote_images": 0,
            "non_previewable_images": 0,
            "source_missing_images": 0,
            "unavailable_images": 0,
            "attachments": 0,
            "local_attachments": 0,
            "missing_attachments": 0,
        }

    soup = BeautifulSoup(content_path.read_text(encoding="utf-8"), "lxml")
    body = soup.body or soup
    img_stats = rewrite_images(soup, out_path.parent, by_url, by_key)
    attachment_stats = rewrite_attachments(soup, out_path.parent, by_url, by_key)
    body_style = body.get("style") or ""
    absolute = body.get("data-absolute-enabled") == "true"
    min_height = estimate_min_height(body) if absolute else 0
    attrs = f'data-absolute-enabled="{str(absolute).lower()}"'
    styles = [body_style.strip()] if body_style.strip() else []
    if min_height:
        styles.append(f"min-height:{min_height}px")
    if styles:
        attrs += f' style="{html.escape(";".join(styles), quote=True)}"'
    if min_height:
        attrs += f' data-min-height="{min_height}"'
    inner_html = "".join(str(child) for child in body.children)
    out_path.write_text(raw_shell(meta_title, section_path, inner_html, attrs), encoding="utf-8")
    return {
        "page_key": page_key,
        "title": meta_title,
        "section_path": section_path,
        "status": "ok",
        "html_path": str(out_path.relative_to(BASE_OUT)),
        "source_content": str(content_path.relative_to(BASE_OUT)),
        **img_stats,
        **attachment_stats,
    }


def raw_shell(title: str, section_path: str, body_html: str, body_attrs: str) -> str:
    css = rel_path(OUT_DIR / "raw_review.css", PAGES_DIR)
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <link rel="stylesheet" href="{css}">
</head>
<body class="raw-review">
  <header class="raw-header">
    <h1>{html.escape(title)}</h1>
    <p>{html.escape(section_path)}</p>
  </header>
  <main class="raw-canvas">
    <article class="onenote-body" {body_attrs}>
{body_html}
    </article>
  </main>
</body>
</html>
"""


def write_css() -> None:
    css = """
:root {
  color-scheme: light;
  --page-bg: #f5f7fa;
  --paper: #fff;
  --line: #d6dde7;
  --ink: #172033;
  --muted: #5e6d82;
}
* { box-sizing: border-box; }
body.raw-review {
  margin: 0;
  background: var(--page-bg);
  color: var(--ink);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Malgun Gothic", sans-serif;
  letter-spacing: 0;
}
.raw-header {
  position: sticky;
  top: 0;
  z-index: 5;
  padding: 12px 18px;
  border-bottom: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.96);
}
.raw-header h1 {
  margin: 0;
  font-size: 18px;
  line-height: 1.25;
}
.raw-header p {
  margin: 6px 0 0;
  color: var(--muted);
  font-size: 12px;
}
.raw-canvas {
  padding: 20px;
  overflow: auto;
}
.onenote-body {
  position: relative;
  min-width: 980px;
  max-width: none;
  padding: 20px;
  border: 1px solid var(--line);
  background: var(--paper);
  box-shadow: 0 1px 2px rgba(22, 32, 51, 0.08);
}
.onenote-body[data-absolute-enabled="true"] {
  position: relative;
}
.onenote-body img {
  max-width: 100%;
  height: auto;
}
.onenote-body[data-absolute-enabled="true"] img {
  max-width: none;
}
.onenote-body p {
  line-height: 1.45;
}
.onenote-body table {
  border-collapse: collapse;
}
.onenote-body td,
.onenote-body th {
  border: 1px solid #cfd6e2;
  padding: 4px 6px;
}
.onenote-attachment {
  display: inline-flex;
  align-items: center;
  min-height: 30px;
  margin: 4px 0;
  padding: 5px 9px;
  border: 1px solid var(--line);
  border-radius: 4px;
  background: #f7fafb;
  color: #0b6b5a;
  text-decoration: none;
}
.onenote-missing-image {
  display: flex;
  align-items: center;
  justify-content: center;
  max-width: 100%;
  margin: 6px 0;
  padding: 12px;
  border: 1px dashed #d97706;
  background: #fff7ed;
  color: #9a3412;
  font-size: 13px;
  text-align: center;
}
.onenote-missing-image.unavailable {
  border-style: solid;
  background: #fef2f2;
  color: #991b1b;
}
.missing-page {
  padding: 24px;
  border: 1px solid #e3c0a1;
  background: #fff2dd;
}
img[data-missing-resource="true"],
a[data-missing-resource="true"] {
  outline: 3px solid #d97706;
}
"""
    (OUT_DIR / "raw_review.css").write_text(css.strip() + "\n", encoding="utf-8")


def write_index(page_rows: list[dict]) -> None:
    ok_count = sum(1 for row in page_rows if row["status"] == "ok")
    image_count = sum(row["images"] for row in page_rows)
    missing_images = sum(row["missing_images"] for row in page_rows)
    source_missing_images = sum(row["source_missing_images"] for row in page_rows)
    unavailable_images = sum(row["unavailable_images"] for row in page_rows)
    rows = "\n".join(
        f"<tr><td>{idx}</td><td><a href=\"{html.escape(rel_path(BASE_OUT / row['html_path'], OUT_DIR))}\">{html.escape(row['title'])}</a></td>"
        f"<td>{html.escape(row['section_path'])}</td><td>{html.escape(row['status'])}</td>"
        f"<td>{row['images']}</td><td>{row['missing_images']}</td><td>{row['source_missing_images']}</td><td>{row['unavailable_images']}</td></tr>"
        for idx, row in enumerate(page_rows, start=1)
    )
    (OUT_DIR / "index.html").write_text(
        f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Techsupport OneNote Raw Review</title>
  <style>
    body {{ margin: 0; padding: 24px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Malgun Gothic", sans-serif; color: #172033; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ border-bottom: 1px solid #d6dde7; padding: 8px; text-align: left; vertical-align: top; }}
    th {{ background: #f5f7fa; position: sticky; top: 0; }}
    a {{ color: #0b6b5a; }}
  </style>
</head>
<body>
  <h1>Techsupport OneNote Raw Review</h1>
  <p>{len(page_rows)} pages / {ok_count} content pages / {image_count} image slots / {missing_images} missing local image refs / {source_missing_images} source-missing image slots / {unavailable_images} unavailable Graph image bodies</p>
  <table>
    <thead><tr><th>#</th><th>Title</th><th>Section</th><th>Status</th><th>Images</th><th>Missing</th><th>Source Missing</th><th>Unavailable</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</body>
</html>
""",
        encoding="utf-8",
    )


def main() -> int:
    pages = read_json(RAW_DIR / "pages_index.json")
    if not isinstance(pages, list):
        raise TypeError("raw/pages_index.json must be a list")
    if PAGES_DIR.exists():
        shutil.rmtree(PAGES_DIR)
    PAGES_DIR.mkdir(parents=True, exist_ok=True)
    write_css()
    page_rows = [render_page(page) for page in pages]
    summary = {
        "pages": len(page_rows),
        "ok_pages": sum(1 for row in page_rows if row["status"] == "ok"),
        "missing_content_pages": sum(1 for row in page_rows if row["status"] != "ok"),
        "images": sum(row["images"] for row in page_rows),
        "local_images": sum(row["local_images"] for row in page_rows),
        "missing_images": sum(row["missing_images"] for row in page_rows),
        "remote_images": sum(row["remote_images"] for row in page_rows),
        "non_previewable_images": sum(row["non_previewable_images"] for row in page_rows),
        "source_missing_images": sum(row["source_missing_images"] for row in page_rows),
        "unavailable_images": sum(row["unavailable_images"] for row in page_rows),
        "attachments": sum(row["attachments"] for row in page_rows),
        "local_attachments": sum(row["local_attachments"] for row in page_rows),
        "missing_attachments": sum(row["missing_attachments"] for row in page_rows),
        "pages_detail": page_rows,
    }
    write_json(OUT_DIR / "summary.json", summary)
    write_index(page_rows)
    print(json.dumps({key: summary[key] for key in summary if key != "pages_detail"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
