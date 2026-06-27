#!/usr/bin/env python3
"""Publish WIS 2026 visit notes to Outline."""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import re
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from PIL import Image, ImageOps


ROOT = Path("/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04")
ANALYSIS_JSON = ROOT / "output/wis-2026/qwen-vqa/wis_qwen_vendor_analysis.json"
PUBLISH_ROOT = ROOT / "output/wis-2026/outline_publish"
IMAGE_ROOT = PUBLISH_ROOT / "images"
ASSET_CACHE = PUBLISH_ROOT / "outline_assets.json"
DOC_CACHE = PUBLISH_ROOT / "outline_docs.json"
PUBLISH_DATASET = PUBLISH_ROOT / "publish_dataset.json"
FLOOR_IMAGE = ROOT / "output/wis-2026/reference/pdf_pages/wis_participants-1.png"

OUTLINE_BASE = "https://outline.doflab.com"
TARGET_URL_ID = "6oNZMSV1gd"
REQUEST_TIMEOUT = 60
IMAGE_MAX_EDGE = 1600
IMAGE_QUALITY = 84


@dataclass
class OutlineDocument:
    id: str
    url_id: str
    title: str
    url: str


def read_env_key(name: str) -> str:
    env_path = ROOT / ".env"
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{name}="):
            return line.split("=", 1)[1].strip().strip("'\"")
    raise RuntimeError(f"{name} not found")


def compact(value: Any, sep: str = " / ") -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return sep.join(str(v).strip() for v in value if str(v).strip())
    return " ".join(str(value).split())


def md_escape(text: str) -> str:
    return (text or "").replace("|", "\\|").replace("\n", "<br>")


def short_name(name: str) -> str:
    return re.sub(r"\s+", " ", name or "미확인 그룹").strip()


def vendor_key(vendor: dict[str, Any]) -> str:
    return f"{int(vendor.get('group_index') or 0):02d}:{short_name(vendor.get('vendor', ''))}"


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def rotate_image(image: Image.Image, degrees_clockwise: int) -> Image.Image:
    degrees_clockwise %= 360
    if degrees_clockwise == 0:
        return image
    return image.rotate(-degrees_clockwise, expand=True)


def prepare_image(source: Path, role: str, order: int, rotation: int = 0) -> dict[str, Any]:
    IMAGE_ROOT.mkdir(parents=True, exist_ok=True)
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()[:16]
    output_name = f"{role}_{order:03d}_{source.stem}_r{rotation}_{source_hash}.jpg"
    output = IMAGE_ROOT / output_name

    with Image.open(source) as raw:
        image = ImageOps.exif_transpose(raw)
        original_size = list(raw.size)
        transposed_size = list(image.size)
        image = rotate_image(image, rotation)
        image = image.convert("RGB")
        image.thumbnail((IMAGE_MAX_EDGE, IMAGE_MAX_EDGE), Image.Resampling.LANCZOS)
        final_size = list(image.size)
        if not output.exists():
            image.save(output, "JPEG", quality=IMAGE_QUALITY, optimize=True)

    return {
        "source": str(source),
        "published_path": str(output),
        "published_name": output.name,
        "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "role": role,
        "order": order,
        "rotation_applied_clockwise": rotation,
        "original_size": original_size,
        "transposed_size": transposed_size,
        "published_size": final_size,
    }


class OutlineClient:
    def __init__(self, key: str):
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {key}"})

    def api(self, endpoint: str, body: dict[str, Any]) -> dict[str, Any]:
        response = self.session.post(f"{OUTLINE_BASE}/api/{endpoint}", json=body, timeout=REQUEST_TIMEOUT)
        if response.status_code >= 400:
            raise RuntimeError(f"{endpoint} failed {response.status_code}: {response.text[:1000]}")
        return response.json()

    def document_info(self, doc_id: str) -> dict[str, Any]:
        return self.api("documents.info", {"id": doc_id})["data"]

    def documents_list(self, **params: Any) -> list[dict[str, Any]]:
        offset = 0
        docs: list[dict[str, Any]] = []
        while True:
            data = self.api("documents.list", {"limit": 100, "offset": offset, **params})
            batch = data.get("data") or []
            docs.extend(batch)
            pagination = data.get("pagination") or {}
            total = pagination.get("total", len(docs))
            offset += len(batch)
            if not batch or offset >= total:
                return docs

    def create_document(self, title: str, parent_document_id: str, text: str) -> dict[str, Any]:
        return self.api(
            "documents.create",
            {"title": title, "parentDocumentId": parent_document_id, "text": text, "publish": True, "fullWidth": True},
        )["data"]

    def update_document(self, doc_id: str, title: str, text: str) -> dict[str, Any]:
        return self.api("documents.update", {"id": doc_id, "title": title, "text": text, "publish": True, "fullWidth": True})["data"]

    def create_attachment(self, document_id: str, image_path: Path) -> dict[str, Any]:
        content_type = mimetypes.guess_type(image_path.name)[0] or "image/jpeg"
        created = self.api(
            "attachments.create",
            {"name": image_path.name, "documentId": document_id, "contentType": content_type, "size": image_path.stat().st_size},
        )["data"]
        upload_url = created["uploadUrl"]
        if upload_url.startswith("/"):
            upload_url = f"{OUTLINE_BASE}{upload_url}"
        form = created.get("form") or {}
        with image_path.open("rb") as file_obj:
            response = requests.post(
                upload_url,
                data=form,
                files={"file": (image_path.name, file_obj, content_type)},
                headers={"Authorization": self.session.headers["Authorization"]},
                timeout=REQUEST_TIMEOUT,
            )
        if response.status_code >= 400:
            raise RuntimeError(f"attachment upload failed {response.status_code}: {response.text[:1000]}")
        return created["attachment"]


def doc_url(doc: dict[str, Any]) -> str:
    return f"{OUTLINE_BASE}/doc/{doc['urlId']}"


def upload_image(client: OutlineClient, document_id: str, image: dict[str, Any], asset_cache: dict[str, Any]) -> str:
    source = image.get("source")
    published_path = Path(image.get("published_path", ""))
    if not source or not published_path.exists():
        return ""
    cache_key = f"{document_id}:{source}:{image.get('sha256')}"
    cached = asset_cache.get(cache_key)
    if cached and cached.get("url"):
        return cached["url"]
    attachment = client.create_attachment(document_id, published_path)
    asset_cache[cache_key] = {
        "source": source,
        "published_path": str(published_path),
        "document_id": document_id,
        "url": attachment.get("url", ""),
        "name": attachment.get("name", published_path.name),
    }
    save_json(ASSET_CACHE, asset_cache)
    time.sleep(0.05)
    return attachment.get("url", "")


def build_dataset() -> dict[str, Any]:
    data = load_json(ANALYSIS_JSON, {})
    vendors = data.get("vendors") or []
    for vendor in vendors:
        for idx, photo in enumerate(vendor.get("photos") or [], start=1):
            source = Path(photo.get("source", ""))
            if source.exists():
                photo["outline_image"] = prepare_image(source, f"group{vendor.get('group_index', 0):02d}", idx)
    dataset = {
        "generated_at": data.get("generated_at"),
        "counts": data.get("counts") or {},
        "sector_counts": data.get("sector_counts") or [],
        "category_counts": data.get("category_counts") or [],
        "vendors": vendors,
    }
    save_json(PUBLISH_DATASET, dataset)
    return dataset


def build_child_markdown(vendor: dict[str, Any], image_urls: dict[str, str]) -> str:
    lines = ["## 현장 메모", ""]
    notes = vendor.get("user_notes") or []
    if notes:
        for note in notes:
            lines.append(f"- {note}")
    else:
        lines.append("- 별도 메모 없음.")

    lines += ["", "## 한눈에 보기", ""]
    if vendor.get("sector_group"):
        lines.append(f"- 관람 구분: {vendor['sector_group']}")
    if vendor.get("categories"):
        lines.append(f"- 분야: {compact(vendor['categories'], ', ')}")
    if vendor.get("brand_candidates"):
        lines.append(f"- 사진상 브랜드/업체 후보: {compact(vendor['brand_candidates'][:8], ', ')}")
    if vendor.get("booth_candidates"):
        lines.append(f"- 부스 후보: {compact(vendor['booth_candidates'], ', ')}")
    if vendor.get("participant_reference_hits"):
        lines.append(f"- 참가사 리스트 후보: {compact(vendor['participant_reference_hits'][:3], ' / ')}")

    if vendor.get("product_or_service_names"):
        lines += ["", "## 제품/서비스", ""]
        for item in vendor["product_or_service_names"][:14]:
            lines.append(f"- {item}")

    if vendor.get("claims"):
        lines += ["", "## 업체가 강조한 점", ""]
        for claim in vendor["claims"][:14]:
            lines.append(f"- {claim}")

    if vendor.get("price_or_business_terms"):
        lines += ["", "## 가격/도입 조건", ""]
        for item in vendor["price_or_business_terms"][:10]:
            lines.append(f"- {item}")

    lines += ["", "## 정리", "", vendor.get("summary", ""), "", "## 사진", ""]
    for photo in vendor.get("photos") or []:
        image = photo.get("outline_image") or {}
        url = image_urls.get(photo.get("source", ""))
        if not url:
            continue
        caption = f"{photo.get('timestamp') or ''} · {photo.get('filename') or ''}".strip(" ·")
        lines += [f"![{caption}]({url})", "", caption]
        visible = compact((photo.get("visible_text") or [])[:10])
        if visible:
            lines.append(f"사진에서 확인된 문구: {visible}")
        context = compact(photo.get("visual_context", ""))
        if context:
            lines.append(f"사진 맥락: {context}")
        lines.append("")
    lines += ["## 백인식 메모", "", ""]
    return "\n".join(lines).strip() + "\n"


def insight_lines(dataset: dict[str, Any]) -> list[str]:
    vendors = dataset.get("vendors") or []
    by_sector = Counter(v.get("sector_group") or "기타" for v in vendors)
    top_sectors = ", ".join(f"{name} {count}개" for name, count in by_sector.most_common(5))
    return [
        f"- 현장 메모는 총 {len(vendors)}개 관람 그룹과 {sum(len(v.get('photos') or []) for v in vendors)}장 사진을 기준으로 정리했다.",
        f"- 관람 축은 {top_sectors} 순으로 많았다.",
        "- 지식검색·특허·지원사업 추천처럼 문서/정보 탐색을 AI로 감싸는 제품이 많았고, 실제 업무 데이터와 연결되는지 여부가 핵심 평가 포인트다.",
        "- 협업툴, 회의 AI, 마케팅 분석, ERP/업무툴은 기존 SaaS에 AI 기능을 얹는 흐름이 뚜렷했다. 단순 데모보다 조직의 반복 업무에 들어갈 수 있는지가 중요하다.",
        "- 공간정보, 보안, 카메라/센서, AI 반도체·인프라 쪽은 현장 실물과 운영 데이터가 있어 제품성이 상대적으로 분명했다.",
        "- 외주사/개발사 부스는 기술 차별성보다 커뮤니케이션, 납기, 가격, 국내 대응력 같은 실행 리스크를 따로 봐야 한다.",
    ]


def build_parent_markdown(dataset: dict[str, Any], docs: dict[str, OutlineDocument], floor_url: str) -> str:
    lines = ["# WIS 2026 방문 요약", "", "## 핵심 현장 인사이트", ""]
    lines.extend(insight_lines(dataset))
    lines += [
        "",
        "## 방문 기록 개요",
        "",
        "- 서해리 방문: 2026-04-22",
        "- 백인식 방문: 2026-04-24",
        f"- 정리 그룹: {dataset.get('counts', {}).get('groups', len(dataset.get('vendors') or []))}개",
        f"- 정리 사진: {dataset.get('counts', {}).get('vqa_images', 0)}장",
    ]
    if floor_url:
        lines += ["", "## 참가사 리스트/도면", "", f"![WIS 2026 참가사 리스트]({floor_url})", ""]
    lines += ["", "## 분야별 분포", "", "| 분야 | 그룹 수 |", "| --- | ---: |"]
    for sector, count in dataset.get("sector_counts") or []:
        lines.append(f"| {md_escape(sector)} | {count} |")
    lines += ["", "## 업체/주제별 문서", "", "| 그룹 | 관람 구분 | 분야 | 사진 | 문서 |", "| --- | --- | --- | ---: | --- |"]
    for vendor in dataset.get("vendors") or []:
        name = short_name(vendor.get("vendor", ""))
        doc = docs.get(vendor_key(vendor))
        link = f"[열기]({doc.url})" if doc else ""
        lines.append(
            "| "
            + " | ".join(
                [
                    md_escape(name),
                    md_escape(vendor.get("sector_group", "")),
                    md_escape(compact(vendor.get("categories") or [], ", ")),
                    str(len(vendor.get("photos") or [])),
                    link,
                ]
            )
            + " |"
        )
    lines += ["", "## 백인식 메모", ""]
    return "\n".join(lines).strip() + "\n"


def publish(dry_run: bool = False, limit: int | None = None) -> dict[str, Any]:
    dataset = build_dataset()
    vendors = dataset.get("vendors") or []
    if limit:
        vendors = vendors[:limit]
        dataset = {**dataset, "vendors": vendors}
    key = read_env_key("DOF_OUTLINE_KEY")
    client = OutlineClient(key)
    parent = client.document_info(TARGET_URL_ID)
    existing_children = {
        doc["title"]: doc
        for doc in client.documents_list(parentDocumentId=parent["id"])
        if doc.get("title")
    }
    asset_cache = load_json(ASSET_CACHE, {})
    doc_cache = load_json(DOC_CACHE, {})
    published_docs: dict[str, OutlineDocument] = {}

    if dry_run:
        return {"dry_run": True, "parent": parent, "vendors": len(vendors), "dataset": dataset}

    for index, vendor in enumerate(vendors, start=1):
        vendor_name = short_name(vendor.get("vendor", ""))
        title = f"{index:02d}. {vendor_name}"
        if vendor.get("sector_group"):
            title += f" / {vendor['sector_group']}"
        doc = existing_children.get(title)
        if not doc:
            doc = client.create_document(title, parent["id"], "작성 중입니다.")
            time.sleep(0.1)
        image_urls = {}
        for photo in vendor.get("photos") or []:
            image = photo.get("outline_image") or {}
            url = upload_image(client, doc["id"], image, asset_cache)
            if url:
                image_urls[photo.get("source", "")] = url
        body = build_child_markdown(vendor, image_urls)
        updated = client.update_document(doc["id"], title, body)
        child = OutlineDocument(id=updated["id"], url_id=updated["urlId"], title=updated["title"], url=doc_url(updated))
        key = vendor_key(vendor)
        published_docs[key] = child
        doc_cache[key] = child.__dict__
        save_json(DOC_CACHE, doc_cache)
        print(json.dumps({"published": title, "images": len(image_urls), "url": child.url}, ensure_ascii=False), flush=True)
        time.sleep(0.1)

    floor_url = ""
    if FLOOR_IMAGE.exists():
        floor_prepared = prepare_image(FLOOR_IMAGE, "floor", 1)
        floor_url = upload_image(client, parent["id"], floor_prepared, asset_cache)
    parent_title = "WIS 2026 방문 요약"
    parent_body = build_parent_markdown(dataset, published_docs, floor_url)
    updated_parent = client.update_document(parent["id"], parent_title, parent_body)
    result = {
        "parent": {"id": updated_parent["id"], "urlId": updated_parent["urlId"], "title": updated_parent["title"], "url": doc_url(updated_parent)},
        "children": [doc.__dict__ for doc in published_docs.values()],
        "counts": {
            "vendors": len(vendors),
            "photos": sum(len(v.get("photos") or []) for v in vendors),
        },
    }
    save_json(PUBLISH_ROOT / "publish_result.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    result = publish(dry_run=args.dry_run, limit=args.limit)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
