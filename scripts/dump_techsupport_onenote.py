#!/usr/bin/env python3
"""Dump DOFSupport OneNote notebooks to raw files, Markdown, and review HTML."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import mimetypes
import os
import re
import shutil
import sys
import time
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import markdown
import requests
from bs4 import BeautifulSoup, NavigableString, Tag

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "proc" / "lib"))

from msgraph import GRAPH, GraphClient  # noqa: E402

BASE_OUT = ROOT / "data" / "techsupport" / "onenote"
RAW_DIR = BASE_OUT / "raw"
MD_DIR = BASE_OUT / "mdfiles"
REVIEW_DIR = BASE_OUT / "review"
SITE_HOST = "doflab.sharepoint.com"
SITE_PATH = "/sites/DOFSupport"


def log(message: str) -> None:
    print(message, flush=True)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def safe_name(value: str | None, fallback: str = "untitled", max_len: int = 90) -> str:
    text = unicodedata.normalize("NFC", value or "").strip() or fallback
    text = re.sub(r"[\\/:*?\"<>|\u0000-\u001f]", "_", text)
    text = re.sub(r"\s+", " ", text).strip(" .")
    text = text or fallback
    if len(text) > max_len:
        digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]
        text = text[: max_len - 9].rstrip() + "-" + digest
    return text


def stable_key(prefix: str, title: str | None, identifier: str) -> str:
    digest = hashlib.sha1(identifier.encode("utf-8")).hexdigest()[:10]
    return f"{prefix}_{safe_name(title, max_len=60)}_{digest}"


def url_to_graph_path(url: str) -> str:
    if url.startswith(GRAPH):
        return url[len(GRAPH) :]
    parsed = urlparse(url)
    return parsed.path + (("?" + parsed.query) if parsed.query else "")


def style_px(style: str | None, prop: str) -> float:
    if not style:
        return 0.0
    match = re.search(rf"{re.escape(prop)}\s*:\s*(-?\d+(?:\.\d+)?)px", style)
    return float(match.group(1)) if match else 0.0


def body_children_in_visual_order(body: Tag) -> list[Tag | NavigableString]:
    children = [child for child in body.children if not is_blank_node(child)]
    if body.get("data-absolute-enabled") != "true":
        return children

    def key(node: Tag | NavigableString) -> tuple[float, float, int]:
        if isinstance(node, Tag):
            return (style_px(node.get("style"), "top"), style_px(node.get("style"), "left"), 0)
        return (0.0, 0.0, 1)

    return sorted(children, key=key)


def is_blank_node(node: Tag | NavigableString) -> bool:
    if isinstance(node, NavigableString):
        return not str(node).strip()
    if isinstance(node, Tag):
        if node.name in {"img", "object", "table"}:
            return False
        return node.name in {"script", "style"} or not node.get_text(strip=True) and not node.find(["img", "object", "table"])
    return True


def clean_inline_text(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return text


def trim_blank_lines(lines: list[str]) -> list[str]:
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def md_target(target: str) -> str:
    if re.search(r"[\s()]", target):
        return "<" + target.replace(">", "%3E") + ">"
    return target


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    for idx in range(2, 10000):
        candidate = path.with_name(f"{stem}-{idx}{suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"could not allocate unique path for {path}")


def mime_extension(mime_type: str | None, fallback: str = ".bin") -> str:
    if not mime_type:
        return fallback
    ext = mimetypes.guess_extension(mime_type.split(";")[0].strip())
    if ext == ".jpe":
        return ".jpg"
    return ext or fallback


@dataclass
class ResourceRef:
    url: str
    kind: str
    mime_type: str | None = None
    attachment_name: str | None = None
    alt: str | None = None
    raw_path: Path | None = None
    md_path: Path | None = None
    rel_md_path: str | None = None
    status: str = "pending"
    error: str | None = None
    bytes: int = 0


@dataclass
class DumpStats:
    notebooks: int = 0
    section_groups: int = 0
    sections: int = 0
    pages: int = 0
    pages_with_content: int = 0
    resources: int = 0
    resource_errors: int = 0
    page_errors: int = 0
    md_files: int = 0
    review_pages: int = 0
    started_at: float = field(default_factory=time.time)


class OneNoteDumper:
    def __init__(self, clean: bool = False, sleep: float = 0.0, resume: bool = False, rebuild_md: bool = False):
        self.g = GraphClient()
        self.sleep = sleep
        self.resume = resume
        self.rebuild_md = rebuild_md
        self.stats = DumpStats()
        self.site: dict[str, Any] = {}
        self.notebooks: list[dict[str, Any]] = []
        self.section_groups: list[dict[str, Any]] = []
        self.sections: list[dict[str, Any]] = []
        self.pages: list[dict[str, Any]] = []
        self.group_by_id: dict[str, dict[str, Any]] = {}
        self.section_by_id: dict[str, dict[str, Any]] = {}
        self.notebook_by_id: dict[str, dict[str, Any]] = {}
        self.resource_cache: dict[str, ResourceRef] = {}
        if clean:
            for path in [RAW_DIR, MD_DIR, REVIEW_DIR]:
                if path.exists():
                    shutil.rmtree(path)

    def graph_get_json(self, path_or_url: str, params: dict[str, Any] | None = None) -> Any:
        response = self.graph_request_bytes(path_or_url, params=params, timeout=90)
        if not response.ok:
            raise RuntimeError(f"GET {path_or_url} failed [{response.status_code}]: {response.text[:300]}")
        return response.json()

    def graph_paged(self, path_or_url: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        url: str | None = path_or_url
        first = True
        while url:
            data = self.graph_get_json(url, params=params if first else None)
            out.extend(data.get("value", []))
            url = data.get("@odata.nextLink")
            first = False
        return out

    def graph_request_bytes(self, url: str, params: dict[str, Any] | None = None, timeout: int = 180) -> requests.Response:
        url = self.normalize_resource_url(url)
        full_url = url if url.startswith("http") else GRAPH + (url if url.startswith("/") else "/" + url)
        last_error: Exception | None = None
        response: requests.Response | None = None
        for attempt in range(8):
            try:
                response = requests.get(
                    full_url,
                    params=params,
                    headers={"Authorization": "Bearer " + self.g.token()},
                    timeout=timeout,
                )
                if response.status_code == 429:
                    delay = int(response.headers.get("Retry-After") or 0) or min(45 * (attempt + 1), 300)
                    log(f"throttled 429; sleeping {delay}s before retry {attempt + 1}/8")
                    time.sleep(delay)
                    continue
                if response.status_code in {500, 502, 503, 504}:
                    delay = int(response.headers.get("Retry-After") or 0) or min(2**attempt, 30)
                    time.sleep(delay)
                    continue
                if self.sleep:
                    time.sleep(self.sleep)
                return response
            except requests.RequestException as exc:
                last_error = exc
                time.sleep(min(2**attempt, 30))
        if last_error:
            raise last_error
        assert response is not None
        return response

    def normalize_resource_url(self, url: str) -> str:
        if "/siteCollections/" not in url or "/onenote/resources/" not in url:
            return url
        match = re.search(r"/onenote/resources/([^/?#]+)(/[^?#]+)?", url)
        if not match:
            return url
        resource_id = match.group(1)
        suffix = match.group(2) or "/$value"
        return f"/sites/{self.site['id']}/onenote/resources/{resource_id}{suffix}"

    def collect_structure(self) -> None:
        cached = [RAW_DIR / name for name in ["site.json", "notebooks.json", "section_groups.json", "sections.json"]]
        if self.resume and all(path.exists() for path in cached):
            self.site = read_json(RAW_DIR / "site.json")
            self.notebooks = read_json(RAW_DIR / "notebooks.json")
            self.section_groups = read_json(RAW_DIR / "section_groups.json")
            self.sections = read_json(RAW_DIR / "sections.json")
            self.notebook_by_id = {item["id"]: item for item in self.notebooks}
            self.group_by_id = {item["id"]: item for item in self.section_groups}
            self.section_by_id = {item["id"]: item for item in self.sections}
            self.stats.notebooks = len(self.notebooks)
            self.stats.section_groups = len(self.section_groups)
            self.stats.sections = len(self.sections)
            log("loaded cached structure")
            return
        self.site = self.graph_get_json(f"/sites/{SITE_HOST}:{SITE_PATH}")
        base = f"/sites/{self.site['id']}/onenote"
        self.notebooks = self.graph_paged(base + "/notebooks", params={"$top": 100})
        self.section_groups = self.graph_paged(
                base + "/sectionGroups",
                params={
                    "$top": 100,
                    "$filter": "parentNotebook ne null",
                    "$expand": "parentNotebook,parentSectionGroup",
                },
        )
        self.sections = self.graph_paged(
                base + "/sections",
                params={"$top": 100, "$expand": "parentNotebook,parentSectionGroup"},
        )
        self.notebook_by_id = {item["id"]: item for item in self.notebooks}
        self.group_by_id = {item["id"]: item for item in self.section_groups}
        self.section_by_id = {item["id"]: item for item in self.sections}
        self.stats.notebooks = len(self.notebooks)
        self.stats.section_groups = len(self.section_groups)
        self.stats.sections = len(self.sections)
        write_json(RAW_DIR / "site.json", self.site)
        write_json(RAW_DIR / "notebooks.json", self.notebooks)
        write_json(RAW_DIR / "section_groups.json", self.section_groups)
        write_json(RAW_DIR / "sections.json", self.sections)

    def group_path_parts(self, group: dict[str, Any] | None) -> list[str]:
        if not group:
            return []
        parent = group.get("parentSectionGroup") or {}
        parts = self.group_path_parts(self.group_by_id.get(parent.get("id"))) if parent.get("id") else []
        parts.append(safe_name(group.get("displayName"), "section-group"))
        return parts

    def section_path_parts(self, section: dict[str, Any]) -> list[str]:
        notebook = section.get("parentNotebook") or {}
        group = section.get("parentSectionGroup") or {}
        parts = [safe_name(notebook.get("displayName"), "notebook")]
        parts.extend(self.group_path_parts(self.group_by_id.get(group.get("id"))))
        parts.append(safe_name(section.get("displayName"), "section"))
        return parts

    def page_path_parts(self, section: dict[str, Any], page: dict[str, Any], index: int) -> tuple[list[str], str, str]:
        section_parts = self.section_path_parts(section)
        page_key = stable_key(f"p{index:04d}", page.get("title"), page["id"])
        filename = safe_name(f"{index:04d} {page.get('title') or 'Untitled'}", max_len=110) + ".md"
        return section_parts, page_key, filename

    def collect_pages(self) -> None:
        if self.resume and (RAW_DIR / "pages_index.json").exists():
            self.pages = read_json(RAW_DIR / "pages_index.json")
            self.stats.pages = len(self.pages)
            log("loaded cached pages_index")
            return
        base = f"/sites/{self.site['id']}/onenote"
        pages: list[dict[str, Any]] = []
        for idx, section in enumerate(self.sections, start=1):
            if idx % 10 == 0 or idx == 1:
                log(f"sections {idx}/{len(self.sections)} pages_so_far={len(pages)}")
            section_pages = self.graph_paged(
                    base + f"/sections/{section['id']}/pages",
                    params={
                        "$top": 100,
                        "$select": "id,title,createdDateTime,lastModifiedDateTime,level,order,links",
                    },
            )
            for page in section_pages:
                page["_sectionId"] = section["id"]
                page["_sectionName"] = section.get("displayName")
                page["_sectionPath"] = self.section_path_parts(section)
                pages.append(page)
            if self.sleep:
                time.sleep(self.sleep)
        pages.sort(key=lambda p: ("/".join(p.get("_sectionPath") or []), p.get("order") or 0, p.get("title") or ""))
        for idx, page in enumerate(pages, start=1):
            section = self.section_by_id[page["_sectionId"]]
            parts, page_key, filename = self.page_path_parts(section, page, idx)
            page["_index"] = idx
            page["_pageKey"] = page_key
            page["_mdRelPath"] = str(Path(*parts) / filename)
            page["_rawRelDir"] = str(Path("pages") / page_key)
        self.pages = pages
        self.stats.pages = len(pages)
        write_json(RAW_DIR / "pages_index.json", pages)

    def collect_page_content(self) -> None:
        base = f"/sites/{self.site['id']}/onenote"
        for idx, page in enumerate(self.pages, start=1):
            if idx % 25 == 0 or idx == 1:
                log(f"content {idx}/{len(self.pages)} resources={self.stats.resources} errors={self.stats.resource_errors}")
            raw_page_dir = RAW_DIR / page["_rawRelDir"]
            raw_page_dir.mkdir(parents=True, exist_ok=True)
            write_json(raw_page_dir / "metadata.json", page)
            try:
                content_path = raw_page_dir / "content.html"
                resources_path = raw_page_dir / "resources.json"
                md_path = MD_DIR / page["_mdRelPath"]
                if self.resume and (raw_page_dir / "error.json").exists() and not content_path.exists():
                    error_payload = read_json(raw_page_dir / "error.json")
                    page["_error"] = error_payload.get("error")
                    self.write_error_markdown(page, page["_error"] or "content unavailable")
                    self.stats.page_errors += 1
                    continue
                if self.rebuild_md and content_path.exists() and resources_path.exists():
                    content = content_path.read_text(encoding="utf-8")
                    page["_contentBytes"] = content_path.stat().st_size
                    resource_refs = self.extract_resource_refs(content)
                    self.apply_saved_resource_paths(md_path, resource_refs, read_json(resources_path))
                    page["_resources"] = read_json(resources_path)
                    self.stats.pages_with_content += 1
                    self.write_markdown(page, content, resource_refs)
                    self.stats.resources += sum(1 for item in page["_resources"] if item.get("status") == "ok")
                    continue
                if self.resume and content_path.exists() and resources_path.exists() and md_path.exists():
                    resources = read_json(resources_path)
                    if all(item.get("status") == "ok" for item in resources):
                        page["_resources"] = resources
                        self.stats.pages_with_content += 1
                        self.stats.md_files += 1
                        self.stats.resources += sum(1 for item in resources if item.get("status") == "ok")
                        continue
                if self.resume and content_path.exists():
                    content = content_path.read_text(encoding="utf-8")
                    page["_contentBytes"] = content_path.stat().st_size
                else:
                    response = self.graph_request_bytes(base + f"/pages/{page['id']}/content", params={"includeIDs": "true"})
                    if not response.ok:
                        raise RuntimeError(f"content fetch failed [{response.status_code}]: {response.text[:300]}")
                    content = response.text
                    content_path.write_text(content, encoding="utf-8")
                    page["_contentBytes"] = len(response.content)
                self.stats.pages_with_content += 1
                resource_refs = self.extract_resource_refs(content)
                self.download_resources(page, resource_refs)
                self.write_markdown(page, content, resource_refs)
            except Exception as exc:
                self.stats.page_errors += 1
                page["_error"] = f"{type(exc).__name__}: {exc}"
                write_json(raw_page_dir / "error.json", {"error": page["_error"], "page": page})
                self.write_error_markdown(page, page["_error"])
            if self.sleep:
                time.sleep(self.sleep)
        write_json(RAW_DIR / "pages_index.json", self.pages)

    def extract_resource_refs(self, content: str) -> list[ResourceRef]:
        soup = BeautifulSoup(content, "lxml")
        refs: list[ResourceRef] = []
        for img in soup.find_all("img"):
            url = img.get("data-fullres-src") or img.get("src")
            if not url:
                continue
            refs.append(
                ResourceRef(
                    url=url,
                    kind="image",
                    mime_type=img.get("data-fullres-src-type") or img.get("data-src-type"),
                    alt=img.get("alt"),
                )
            )
        for obj in soup.find_all("object"):
            url = obj.get("data")
            if not url:
                continue
            refs.append(
                ResourceRef(
                    url=url,
                    kind="attachment",
                    mime_type=obj.get("type"),
                    attachment_name=obj.get("data-attachment"),
                )
            )
        return refs

    def download_resources(self, page: dict[str, Any], refs: list[ResourceRef]) -> None:
        seen: set[str] = set()
        unique_refs = []
        for ref in refs:
            if ref.url in seen:
                continue
            seen.add(ref.url)
            unique_refs.append(ref)
        raw_res_dir = RAW_DIR / page["_rawRelDir"] / "resources"
        md_path = MD_DIR / page["_mdRelPath"]
        md_assets_dir = md_path.with_suffix("").with_name(md_path.stem + "_assets")
        raw_res_dir.mkdir(parents=True, exist_ok=True)
        md_assets_dir.mkdir(parents=True, exist_ok=True)
        for idx, ref in enumerate(unique_refs, start=1):
            cached = self.resource_cache.get(ref.url)
            if cached and cached.status == "ok" and cached.raw_path and cached.raw_path.exists():
                local_name = cached.raw_path.name
                raw_dest = raw_res_dir / local_name
                md_dest = md_assets_dir / local_name
                if not raw_dest.exists():
                    shutil.copy2(cached.raw_path, raw_dest)
                if not md_dest.exists():
                    shutil.copy2(cached.raw_path, md_dest)
                ref.raw_path = raw_dest
                ref.md_path = md_dest
                ref.rel_md_path = os.path.relpath(md_dest, md_path.parent).replace(os.sep, "/")
                ref.status = "ok"
                ref.bytes = cached.bytes
                continue
            ext = self.resource_extension(ref)
            base_name = ref.attachment_name or f"{ref.kind}-{idx:03d}{ext}"
            if "." not in Path(base_name).name:
                base_name += ext
            base_name = safe_name(unquote(base_name), fallback=f"{ref.kind}-{idx:03d}{ext}", max_len=100)
            raw_dest = unique_path(raw_res_dir / base_name)
            md_dest = md_assets_dir / raw_dest.name
            try:
                response = self.graph_request_bytes(ref.url)
                if not response.ok:
                    raise RuntimeError(f"resource fetch failed [{response.status_code}]: {response.text[:200]}")
                raw_dest.write_bytes(response.content)
                shutil.copy2(raw_dest, md_dest)
                ref.raw_path = raw_dest
                ref.md_path = md_dest
                ref.rel_md_path = os.path.relpath(md_dest, md_path.parent).replace(os.sep, "/")
                ref.status = "ok"
                ref.bytes = len(response.content)
                self.resource_cache[ref.url] = ref
                self.stats.resources += 1
            except Exception as exc:
                ref.status = "error"
                ref.error = f"{type(exc).__name__}: {exc}"
                self.stats.resource_errors += 1
        page["_resources"] = [
            {
                "url": ref.url,
                "kind": ref.kind,
                "mime_type": ref.mime_type,
                "attachment_name": ref.attachment_name,
                "raw_path": str(ref.raw_path.relative_to(BASE_OUT)) if ref.raw_path else None,
                "md_path": str(ref.md_path.relative_to(BASE_OUT)) if ref.md_path else None,
                "bytes": ref.bytes,
                "status": ref.status,
                "error": ref.error,
            }
            for ref in unique_refs
        ]
        write_json(RAW_DIR / page["_rawRelDir"] / "resources.json", page["_resources"])

    def apply_saved_resource_paths(self, md_path: Path, refs: list[ResourceRef], saved_resources: list[dict[str, Any]]) -> None:
        by_url = {item.get("url"): item for item in saved_resources}
        for ref in refs:
            saved = by_url.get(ref.url)
            if not saved:
                continue
            ref.status = saved.get("status") or "ok"
            ref.error = saved.get("error")
            ref.bytes = saved.get("bytes") or 0
            if saved.get("raw_path"):
                ref.raw_path = BASE_OUT / saved["raw_path"]
            if saved.get("md_path"):
                ref.md_path = BASE_OUT / saved["md_path"]
                ref.rel_md_path = os.path.relpath(ref.md_path, md_path.parent).replace(os.sep, "/")

    def resource_extension(self, ref: ResourceRef) -> str:
        ext = mime_extension(ref.mime_type)
        if ext != ".bin":
            return ext
        parsed_ext = Path(urlparse(ref.url).path).suffix
        return parsed_ext if parsed_ext else ".bin"

    def write_markdown(self, page: dict[str, Any], content: str, refs: list[ResourceRef]) -> None:
        md_path = MD_DIR / page["_mdRelPath"]
        md_path.parent.mkdir(parents=True, exist_ok=True)
        resources_by_url = {ref.url: ref for ref in refs}
        soup = BeautifulSoup(content, "lxml")
        title = page.get("title") or (soup.title.get_text(strip=True) if soup.title else "Untitled")
        lines = [
            f"# {title}",
            "",
            f"- Notebook: {page.get('_sectionPath', [''])[0] if page.get('_sectionPath') else ''}",
            f"- Section path: {' / '.join(page.get('_sectionPath') or [])}",
            f"- Created: {page.get('createdDateTime') or ''}",
            f"- Modified: {page.get('lastModifiedDateTime') or ''}",
        ]
        web_url = (((page.get("links") or {}).get("oneNoteWebUrl") or {}).get("href"))
        if web_url:
            lines.append(f"- OneNote: [{title}]({web_url})")
        lines.extend(["", "---", ""])
        body = soup.body
        if body:
            for child in body_children_in_visual_order(body):
                block = self.block_to_markdown(child, resources_by_url, md_path.parent)
                if block.strip():
                    lines.extend(trim_blank_lines(block.splitlines()))
                    lines.append("")
        body_text = "\n".join(trim_blank_lines(lines)).rstrip() + "\n"
        md_path.write_text(body_text, encoding="utf-8")
        self.stats.md_files += 1

    def write_error_markdown(self, page: dict[str, Any], error: str) -> None:
        md_path = MD_DIR / page["_mdRelPath"]
        md_path.parent.mkdir(parents=True, exist_ok=True)
        title = page.get("title") or "Untitled"
        web_url = (((page.get("links") or {}).get("oneNoteWebUrl") or {}).get("href"))
        section_file = self.original_section_link(page, md_path.parent)
        lines = [
            f"# {title}",
            "",
            f"- Notebook: {page.get('_sectionPath', [''])[0] if page.get('_sectionPath') else ''}",
            f"- Section path: {' / '.join(page.get('_sectionPath') or [])}",
            f"- Created: {page.get('createdDateTime') or ''}",
            f"- Modified: {page.get('lastModifiedDateTime') or ''}",
        ]
        if web_url:
            lines.append(f"- OneNote: [{title}]({web_url})")
        if section_file:
            lines.append(f"- Original section file: [{section_file['label']}]({md_target(section_file['href'])})")
        lines.extend(
            [
                "",
                "---",
                "",
                "> Graph returned page metadata, but the page content endpoint returned an error.",
                "",
                "```text",
                error,
                "```",
            ]
        )
        md_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        self.stats.md_files += 1

    def original_section_link(self, page: dict[str, Any], md_parent: Path) -> dict[str, str] | None:
        href = (((page.get("links") or {}).get("oneNoteClientUrl") or {}).get("href"))
        if not href:
            return None
        href = href.removeprefix("onenote:")
        path = unquote(urlparse(href).path)
        marker = "/SiteAssets/"
        if marker not in path:
            return None
        rel = path.split(marker, 1)[1].split("#", 1)[0]
        original = BASE_OUT / "raw" / "original_section_files" / rel
        if not original.exists():
            return None
        return {
            "label": Path(rel).name,
            "href": os.path.relpath(original, md_parent).replace(os.sep, "/"),
        }

    def inline_to_markdown(self, node: Tag | NavigableString, resources: dict[str, ResourceRef], md_parent: Path) -> str:
        if isinstance(node, NavigableString):
            return clean_inline_text(str(node))
        if not isinstance(node, Tag):
            return ""
        name = node.name.lower()
        if name == "br":
            return "\n"
        if name == "img":
            url = node.get("data-fullres-src") or node.get("src")
            ref = resources.get(url or "")
            alt = clean_inline_text(node.get("alt") or "").replace("\n", " ").strip()
            if len(alt) > 80:
                alt = alt[:77].rstrip() + "..."
            alt = alt or "image"
            target = ref.rel_md_path if ref and ref.rel_md_path else url or ""
            return f"\n![{alt}]({md_target(target)})\n"
        if name == "object":
            url = node.get("data")
            ref = resources.get(url or "")
            label = ref.attachment_name if ref and ref.attachment_name else node.get("data-attachment") or "attachment"
            target = ref.rel_md_path if ref and ref.rel_md_path else url or ""
            return f"\n[{label}]({md_target(target)})\n"
        if name == "a":
            label = "".join(self.inline_to_markdown(child, resources, md_parent) for child in node.children).strip()
            href = node.get("href") or ""
            return f"[{label or href}]({href})" if href else label
        if name in {"strong", "b"}:
            text = "".join(self.inline_to_markdown(child, resources, md_parent) for child in node.children).strip()
            return f"**{text}**" if text else ""
        if name in {"em", "i"}:
            text = "".join(self.inline_to_markdown(child, resources, md_parent) for child in node.children).strip()
            return f"*{text}*" if text else ""
        if name == "u":
            text = "".join(self.inline_to_markdown(child, resources, md_parent) for child in node.children).strip()
            return f"<u>{html.escape(text)}</u>" if text else ""
        return "".join(self.inline_to_markdown(child, resources, md_parent) for child in node.children)

    def block_to_markdown(self, node: Tag | NavigableString, resources: dict[str, ResourceRef], md_parent: Path) -> str:
        if isinstance(node, NavigableString):
            return clean_inline_text(str(node)).strip()
        if not isinstance(node, Tag):
            return ""
        name = node.name.lower()
        if name in {"script", "style"}:
            return ""
        if name in {"p", "span"}:
            return self.inline_to_markdown(node, resources, md_parent).strip()
        if name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            level = int(name[1])
            text = self.inline_to_markdown(node, resources, md_parent).strip()
            return f"{'#' * level} {text}" if text else ""
        if name in {"img", "object"}:
            return self.inline_to_markdown(node, resources, md_parent).strip()
        if name == "br":
            return ""
        if name in {"ul", "ol"}:
            ordered = name == "ol"
            lines: list[str] = []
            for idx, li in enumerate(node.find_all("li", recursive=False), start=1):
                text = self.inline_to_markdown(li, resources, md_parent).strip()
                if text:
                    prefix = f"{idx}. " if ordered else "- "
                    lines.append(prefix + text.replace("\n", "\n  "))
            return "\n".join(lines)
        if name == "table":
            return self.table_to_markdown(node, resources, md_parent)
        if name in {"div", "body", "article", "section"}:
            lines: list[str] = []
            children = body_children_in_visual_order(node) if name == "body" else [c for c in node.children if not is_blank_node(c)]
            for child in children:
                block = self.block_to_markdown(child, resources, md_parent)
                if block.strip():
                    lines.extend(trim_blank_lines(block.splitlines()))
                    lines.append("")
            return "\n".join(trim_blank_lines(lines))
        return self.inline_to_markdown(node, resources, md_parent).strip()

    def table_to_markdown(self, table: Tag, resources: dict[str, ResourceRef], md_parent: Path) -> str:
        rows: list[list[str]] = []
        for tr in table.find_all("tr"):
            cells = []
            for cell in tr.find_all(["th", "td"], recursive=False):
                text = self.inline_to_markdown(cell, resources, md_parent)
                text = re.sub(r"\s*\n\s*", "<br>", text.strip())
                cells.append(text.replace("|", "\\|"))
            if cells:
                rows.append(cells)
        if not rows:
            return ""
        width = max(len(row) for row in rows)
        rows = [row + [""] * (width - len(row)) for row in rows]
        header = rows[0]
        out = ["| " + " | ".join(header) + " |", "| " + " | ".join(["---"] * width) + " |"]
        for row in rows[1:]:
            out.append("| " + " | ".join(row) + " |")
        return "\n".join(out)

    def build_review(self) -> None:
        REVIEW_DIR.mkdir(parents=True, exist_ok=True)
        review_pages_dir = REVIEW_DIR / "pages"
        review_pages_dir.mkdir(parents=True, exist_ok=True)
        page_entries: list[dict[str, Any]] = []
        for page in self.pages:
            md_path = MD_DIR / page["_mdRelPath"]
            if not md_path.exists():
                continue
            review_page = review_pages_dir / (page["_pageKey"] + ".html")
            rendered = markdown.markdown(
                md_path.read_text(encoding="utf-8"),
                extensions=["extra", "sane_lists", "tables"],
                output_format="html5",
            )
            rendered = self.rewrite_rendered_paths(rendered, md_path.parent, review_page.parent)
            review_page.write_text(self.wrap_page_html(page, rendered), encoding="utf-8")
            self.stats.review_pages += 1
            page_entries.append(
                {
                    "title": page.get("title") or "Untitled",
                    "section": " / ".join(page.get("_sectionPath") or []),
                    "md": str(md_path.relative_to(BASE_OUT)),
                    "html": str(review_page.relative_to(REVIEW_DIR)),
                    "modified": page.get("lastModifiedDateTime"),
                    "resources": len(page.get("_resources") or []),
                }
            )
        write_json(REVIEW_DIR / "review_index.json", page_entries)
        (REVIEW_DIR / "index.html").write_text(self.wrap_index_html(page_entries), encoding="utf-8")

    def rewrite_rendered_paths(self, rendered: str, md_parent: Path, html_parent: Path) -> str:
        soup = BeautifulSoup(rendered, "lxml")
        for tag in soup.find_all(["img", "a"]):
            attr = "src" if tag.name == "img" else "href"
            value = tag.get(attr)
            if not value or re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", value) or value.startswith("#"):
                continue
            absolute = (md_parent / value).resolve()
            if absolute.exists():
                tag[attr] = os.path.relpath(absolute, html_parent).replace(os.sep, "/")
        body = soup.body
        return "".join(str(child) for child in body.children) if body else str(soup)

    def wrap_page_html(self, page: dict[str, Any], rendered: str) -> str:
        title = html.escape(page.get("title") or "Untitled")
        section = html.escape(" / ".join(page.get("_sectionPath") or []))
        md_rel = html.escape(page.get("_mdRelPath") or "")
        return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <link rel="stylesheet" href="../review.css">
</head>
<body>
  <main class="page">
    <nav><a href="../index.html">Index</a></nav>
    <header>
      <p class="eyebrow">{section}</p>
      <h1>{title}</h1>
      <p class="path">{md_rel}</p>
    </header>
    <article class="markdown-body">
{rendered}
    </article>
  </main>
</body>
</html>
"""

    def wrap_index_html(self, entries: list[dict[str, Any]]) -> str:
        rows = "\n".join(
            f"""<tr>
  <td><a href="{html.escape(entry['html'])}">{html.escape(entry['title'])}</a></td>
  <td>{html.escape(entry['section'])}</td>
  <td>{html.escape(str(entry['resources']))}</td>
  <td>{html.escape(entry.get('modified') or '')}</td>
  <td><code>{html.escape(entry['md'])}</code></td>
</tr>"""
            for entry in entries
        )
        stats = {
            "notebooks": self.stats.notebooks,
            "section_groups": self.stats.section_groups,
            "sections": self.stats.sections,
            "pages": self.stats.pages,
            "review_pages": self.stats.review_pages,
            "resource_errors": self.stats.resource_errors,
            "page_errors": self.stats.page_errors,
        }
        write_json(REVIEW_DIR / "summary.json", {**stats, "elapsed_seconds": round(time.time() - self.stats.started_at, 2)})
        (REVIEW_DIR / "review.css").write_text(REVIEW_CSS, encoding="utf-8")
        return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>DOFSupport OneNote Markdown Review</title>
  <link rel="stylesheet" href="review.css">
</head>
<body>
  <main class="index">
    <header>
      <p class="eyebrow">DOFSupport OneNote dump</p>
      <h1>Markdown Review</h1>
      <p class="path">data/techsupport/onenote/mdfiles</p>
    </header>
    <section class="stats">
      <div><strong>{stats['notebooks']}</strong><span>notebooks</span></div>
      <div><strong>{stats['section_groups']}</strong><span>section groups</span></div>
      <div><strong>{stats['sections']}</strong><span>sections</span></div>
      <div><strong>{stats['pages']}</strong><span>pages</span></div>
      <div><strong>{stats['resource_errors']}</strong><span>resource errors</span></div>
      <div><strong>{stats['page_errors']}</strong><span>page errors</span></div>
    </section>
    <div class="toolbar">
      <input id="q" type="search" placeholder="Filter title, section, path">
      <span id="count">{len(entries)} pages</span>
    </div>
    <table id="pages">
      <thead><tr><th>Title</th><th>Section</th><th>Assets</th><th>Modified</th><th>Markdown</th></tr></thead>
      <tbody>
{rows}
      </tbody>
    </table>
  </main>
  <script>
    const q = document.getElementById('q');
    const rows = [...document.querySelectorAll('#pages tbody tr')];
    const count = document.getElementById('count');
    q.addEventListener('input', () => {{
      const needle = q.value.toLowerCase();
      let shown = 0;
      for (const row of rows) {{
        const hit = row.textContent.toLowerCase().includes(needle);
        row.hidden = !hit;
        if (hit) shown++;
      }}
      count.textContent = shown.toLocaleString() + ' pages';
    }});
  </script>
</body>
</html>
"""

    def write_drive_index(self) -> None:
        notebooks = []
        for nb in self.notebooks:
            href = (((nb.get("links") or {}).get("oneNoteWebUrl") or {}).get("href"))
            if not href:
                continue
            try:
                share = "u!" + __import__("base64").urlsafe_b64encode(href.encode()).decode().rstrip("=")
                item = self.graph_get_json(f"/shares/{share}/driveItem")
                notebooks.append(item)
            except Exception as exc:
                notebooks.append({"notebook": nb.get("displayName"), "webUrl": href, "error": f"{type(exc).__name__}: {exc}"})
        write_json(RAW_DIR / "notebook_drive_items.json", notebooks)

    def run(self) -> None:
        log("collect structure")
        self.collect_structure()
        self.write_drive_index()
        log(
            f"structure notebooks={self.stats.notebooks} "
            f"groups={self.stats.section_groups} sections={self.stats.sections}"
        )
        self.collect_pages()
        log(f"pages={self.stats.pages}")
        self.collect_page_content()
        self.build_review()
        write_json(RAW_DIR / "summary.json", {**self.stats.__dict__, "elapsed_seconds": round(time.time() - self.stats.started_at, 2)})
        log(
            f"DONE pages={self.stats.pages} md={self.stats.md_files} "
            f"resources={self.stats.resources} page_errors={self.stats.page_errors} "
            f"resource_errors={self.stats.resource_errors}"
        )


REVIEW_CSS = """
:root {
  color-scheme: light;
  --bg: #f6f7f9;
  --surface: #ffffff;
  --line: #d8dee8;
  --ink: #172033;
  --muted: #607086;
  --accent: #1e6f5c;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Malgun Gothic", sans-serif;
  background: var(--bg);
  color: var(--ink);
}
a { color: var(--accent); }
.index, .page { max-width: 1180px; margin: 0 auto; padding: 32px 24px 72px; }
header { margin-bottom: 22px; }
.eyebrow { margin: 0 0 6px; color: var(--accent); font-weight: 700; font-size: 13px; }
h1 { margin: 0; font-size: 30px; line-height: 1.25; letter-spacing: 0; }
.path { color: var(--muted); font-size: 13px; overflow-wrap: anywhere; }
.stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
  gap: 10px;
  margin: 20px 0;
}
.stats div {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 14px;
}
.stats strong { display: block; font-size: 24px; line-height: 1; }
.stats span { color: var(--muted); font-size: 12px; }
.toolbar { display: flex; align-items: center; gap: 12px; margin: 20px 0 12px; }
input[type="search"] {
  width: min(560px, 100%);
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 10px 12px;
  font: inherit;
}
table {
  width: 100%;
  border-collapse: collapse;
  background: var(--surface);
  border: 1px solid var(--line);
}
th, td { padding: 10px 12px; border-bottom: 1px solid var(--line); vertical-align: top; text-align: left; }
th { background: #eef2f6; font-size: 13px; }
td { font-size: 14px; }
code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
  overflow-wrap: anywhere;
}
nav { margin-bottom: 18px; }
.markdown-body {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 28px;
  overflow-wrap: anywhere;
}
.markdown-body h1:first-child { margin-top: 0; }
.markdown-body img {
  display: block;
  max-width: 100%;
  height: auto;
  margin: 14px 0;
  border: 1px solid var(--line);
}
.markdown-body table { margin: 16px 0; }
.markdown-body pre {
  padding: 12px;
  overflow: auto;
  background: #f1f4f8;
  border-radius: 6px;
}
@media (max-width: 760px) {
  .index, .page { padding: 20px 12px 48px; }
  table, thead, tbody, tr, th, td { display: block; }
  thead { display: none; }
  tr { border-bottom: 1px solid var(--line); padding: 10px 0; }
  td { border: 0; padding: 5px 10px; }
  .markdown-body { padding: 16px; }
}
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clean", action="store_true", help="remove prior raw/md/review outputs first")
    parser.add_argument("--resume", action="store_true", help="reuse existing raw/md outputs and retry missing or failed pages")
    parser.add_argument("--rebuild-md", action="store_true", help="rebuild Markdown/review from existing raw content and resources")
    parser.add_argument("--sleep", type=float, default=0.0, help="optional delay between Graph calls")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dumper = OneNoteDumper(clean=args.clean, sleep=args.sleep, resume=args.resume, rebuild_md=args.rebuild_md)
    dumper.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
