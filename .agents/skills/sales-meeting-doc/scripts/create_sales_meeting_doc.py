#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup


FOLDER_ID = "724271123"
FORBIDDEN = ("kubit", "slack", "슬랙", "고려대", "고려대학교", "카카오", "카톡", "kmsg")
KST = timezone(timedelta(hours=9))
SITE = "doflab.atlassian.net"
CONF_V2 = f"https://{SITE}/wiki/api/v2"


def find_repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / ".env").exists() and (parent / "proc/lib").exists():
            return parent
    raise RuntimeError("repo root not found")


ROOT = find_repo_root()


def load_env() -> tuple[str, str]:
    env_path = ROOT / ".env"
    vals: dict[str, str] = {}
    if env_path.exists():
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            vals[k.strip()] = v.strip().strip("'\"")
    email = vals.get("ATLASSIAN_EMAIL", "")
    token = vals.get("ATLASSIAN_TOK", "")
    if not (email and token):
        raise RuntimeError("ATLASSIAN_EMAIL / ATLASSIAN_TOK not set in .env")
    return email, token


class Confluence:
    def __init__(self) -> None:
        self.email, self.token = load_env()

    def auth(self) -> str:
        raw = f"{self.email}:{self.token}".encode()
        return "Basic " + base64.b64encode(raw).decode()

    def request(self, method: str, url: str, body: dict | None = None) -> Any:
        data = None if body is None else json.dumps(body).encode("utf-8")
        headers = {
            "Authorization": self.auth(),
            "Accept": "application/json",
        }
        if body is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                raw = resp.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:1000]
            raise RuntimeError(f"Confluence {method} {url} failed: HTTP {e.code} {detail}") from e

    def folder_children(self, folder_id: str) -> list[dict]:
        out: list[dict] = []
        url = f"{CONF_V2}/folders/{folder_id}/direct-children?limit=250"
        while url:
            data = self.request("GET", url)
            out.extend(data.get("results", []))
            nxt = (data.get("_links") or {}).get("next")
            if nxt and nxt.startswith("http"):
                url = nxt
            elif nxt:
                url = f"https://{SITE}/wiki{nxt}"
            else:
                url = ""
        return out

    def page(self, page_id: str) -> dict:
        return self.request("GET", f"{CONF_V2}/pages/{page_id}?body-format=storage")

    def create_page(self, *, space_id: str, parent_id: str, title: str, body: str) -> dict:
        payload = {
            "spaceId": space_id,
            "status": "current",
            "title": title,
            "parentId": parent_id,
            "body": {"representation": "storage", "value": body},
            "subtype": "live",
        }
        return self.request("POST", f"{CONF_V2}/pages", payload)

    def copy_page(
        self,
        *,
        source_id: str,
        destination_type: str,
        destination_value: str,
        title: str,
        body: str,
    ) -> dict:
        payload = {
            "copyAttachments": True,
            "copyPermissions": True,
            "copyProperties": True,
            "copyLabels": True,
            "copyCustomContents": True,
            "destination": {
                "type": destination_type,
                "value": destination_value,
            },
            "pageTitle": title,
            "body": {
                "storage": {
                    "value": body,
                    "representation": "storage",
                }
            },
        }
        return self.request(
            "POST",
            f"https://{SITE}/wiki/rest/api/content/{source_id}/copy",
            payload,
        )


def parse_day(value: str | None) -> date:
    if not value:
        return datetime.now(KST).date()
    text = value.strip()
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%y%m%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"unsupported date: {value}")


def title_date(title: str) -> tuple[date, str] | None:
    patterns = [
        (r"(?<!\d)(\d{6})(?!\d)", "%y%m%d"),
        (r"(?<!\d)(\d{8})(?!\d)", "%Y%m%d"),
        (r"(?<!\d)(\d{4}-\d{2}-\d{2})(?!\d)", "%Y-%m-%d"),
        (r"(?<!\d)(\d{4}\.\d{2}\.\d{2})(?!\d)", "%Y.%m.%d"),
    ]
    for pat, fmt in patterns:
        m = re.search(pat, title)
        if not m:
            continue
        return datetime.strptime(m.group(1), fmt).date(), m.group(1)
    return None


def target_title(latest_title: str, target: date) -> str:
    parsed = title_date(latest_title)
    if not parsed:
        return f"{target:%y%m%d} {latest_title}"
    _, token = parsed
    if re.fullmatch(r"\d{6}", token):
        replacement = target.strftime("%y%m%d")
    elif re.fullmatch(r"\d{8}", token):
        replacement = target.strftime("%Y%m%d")
    elif "-" in token:
        replacement = target.strftime("%Y-%m-%d")
    elif "." in token:
        replacement = target.strftime("%Y.%m.%d")
    else:
        replacement = target.strftime("%y%m%d")
    return latest_title.replace(token, replacement, 1)


def latest_page(children: list[dict], before: date | None = None) -> dict:
    dated: list[tuple[date, dict]] = []
    for child in children:
        if child.get("type") != "page":
            continue
        parsed = title_date(child.get("title", ""))
        if parsed and (before is None or parsed[0] < before):
            dated.append((parsed[0], child))
    if not dated:
        if before is not None:
            return latest_page(children)
        raise RuntimeError("no dated page children found")
    return sorted(dated, key=lambda x: x[0])[-1][1]


def _normalize_bullet(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return {"text": text, "children": []} if text else None
    if isinstance(value, dict):
        text = str(
            value.get("text")
            or value.get("title")
            or value.get("label")
            or value.get("item")
            or ""
        ).strip()
        child_values = value.get("children") or value.get("items") or value.get("bullets") or []
        children = _normalize_bullets(child_values)
        if not text and not children:
            return None
        return {"text": text, "children": children}
    text = str(value).strip()
    return {"text": text, "children": []} if text else None


def _normalize_bullets(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, (str, dict)):
        one = _normalize_bullet(value)
        return [one] if one else []
    if isinstance(value, list):
        out: list[dict[str, Any]] = []
        for item in value:
            one = _normalize_bullet(item)
            if one:
                out.append(one)
        return out
    one = _normalize_bullet(value)
    return [one] if one else []


def load_discussion(path: Path | None) -> dict[str, list[dict[str, Any]]]:
    if path is None:
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))

    if isinstance(raw, dict):
        return {str(k): _normalize_bullets(v) for k, v in raw.items()}
    if isinstance(raw, list):
        out: dict[str, list[dict[str, Any]]] = {}
        for item in raw:
            topic = str(item.get("topic", "")).strip()
            items = item.get("items") or item.get("bullets") or []
            if topic:
                out[topic] = _normalize_bullets(items)
        return out
    raise ValueError("discussion JSON must be an object or list")


def find_discussion_table(soup: BeautifulSoup):
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue
        header_cells = rows[0].find_all(["th", "td"], recursive=False)
        headers = [cell.get_text(" ", strip=True) for cell in header_cells]
        if "주제" in headers and "논의항목" in headers:
            return table, headers.index("주제"), headers.index("논의항목")
    raise RuntimeError("table with headers '주제' and '논의항목' not found")


def _build_bullet_list(soup: BeautifulSoup, bullets: list[dict[str, Any]]):
    ul = soup.new_tag("ul")
    for bullet in bullets:
        li = soup.new_tag("li")
        p = soup.new_tag("p")
        p.append(str(bullet.get("text") or ""))
        li.append(p)
        children = bullet.get("children") or []
        if children:
            li.append(_build_bullet_list(soup, children))
        ul.append(li)
    return ul


def set_cell_bullets(soup: BeautifulSoup, cell, bullets: list[dict[str, Any]]) -> None:
    cell.clear()
    if not bullets:
        cell.append(soup.new_tag("p"))
        return
    ul = _build_bullet_list(soup, bullets)
    cell.append(ul)


def update_discussion_table(body: str, discussion: dict[str, list[dict[str, Any]]], preserve_unmapped: bool) -> tuple[str, list[str], list[str]]:
    soup = BeautifulSoup(body, "html.parser")
    table, topic_col, discussion_col = find_discussion_table(soup)
    rows = table.find_all("tr")[1:]
    topics: list[str] = []
    touched: list[str] = []
    for row in rows:
        cells = row.find_all(["th", "td"], recursive=False)
        if max(topic_col, discussion_col) >= len(cells):
            continue
        topic = " ".join(cells[topic_col].get_text(" ", strip=True).split())
        if topic:
            topics.append(topic)
        if topic in discussion:
            set_cell_bullets(soup, cells[discussion_col], discussion[topic])
            touched.append(topic)
        elif not preserve_unmapped:
            set_cell_bullets(soup, cells[discussion_col], [])
    unknown = sorted(set(discussion) - set(topics))
    if unknown:
        raise RuntimeError(f"discussion topics not in Confluence table: {unknown}")
    return str(soup), topics, touched


def _bullet_texts(bullets: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for bullet in bullets:
        out.append(str(bullet.get("text") or ""))
        out.extend(_bullet_texts(bullet.get("children") or []))
    return out


def validate_discussion(discussion: dict[str, list[dict[str, Any]]]) -> None:
    violations: list[str] = []
    for topic, bullets in discussion.items():
        haystack = " ".join([topic, *_bullet_texts(bullets)]).lower()
        for term in FORBIDDEN:
            if term.lower() in haystack:
                violations.append(term)
    if violations:
        raise RuntimeError(f"forbidden terms in discussion bullets: {sorted(set(violations))}")


def write_outputs(target: date, payload: dict, body: str, discussion_template: dict[str, list[str]]) -> Path:
    out_dir = ROOT / f"output/sales-meeting-doc/{target.isoformat()}"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "preview.html").write_text(body, encoding="utf-8")
    (out_dir / "summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if discussion_template:
        (out_dir / "discussion-template.json").write_text(
            json.dumps(discussion_template, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return out_dir


def page_url(page: dict) -> str:
    links = page.get("_links") or {}
    if links.get("base") and links.get("webui"):
        return f"{links['base']}{links['webui']}"
    if links.get("webui"):
        return f"https://{SITE}/wiki{links['webui']}"
    return f"https://{SITE}/wiki/spaces/AX/pages/{page.get('id')}"


def main() -> None:
    ap = argparse.ArgumentParser(description="Create a Confluence sales regular meeting page from the latest folder page.")
    ap.add_argument("--date", help="target date, default Asia/Seoul today")
    ap.add_argument("--folder-id", default=FOLDER_ID)
    ap.add_argument("--discussion-json", type=Path)
    ap.add_argument("--preserve-unmapped", action="store_true", help="leave previous discussion cells untouched when missing in JSON")
    ap.add_argument("--dry-run", action="store_true", help="write local preview only")
    ap.add_argument("--write", action="store_true", help="create the Confluence page")
    ap.add_argument("--replace-existing", action="store_true", help="if target title exists, replace that page using Confluence native copy")
    args = ap.parse_args()

    if args.write == args.dry_run:
        raise SystemExit("choose exactly one of --dry-run or --write")

    target = parse_day(args.date)
    c = Confluence()
    children = c.folder_children(args.folder_id)
    latest = latest_page(children, before=target)
    latest_date, _ = title_date(latest["title"]) or (None, "")
    target_name = target_title(latest["title"], target)
    existing = [x for x in children if x.get("type") == "page" and x.get("title") == target_name]
    if existing and args.write and not args.replace_existing:
        raise SystemExit(f"target page already exists: {target_name} ({existing[0].get('id')})")

    page = c.page(latest["id"])
    body = (((page.get("body") or {}).get("storage") or {}).get("value") or "")
    discussion = load_discussion(args.discussion_json)
    validate_discussion(discussion)
    updated_body, topics, touched = update_discussion_table(body, discussion, args.preserve_unmapped)
    template = {topic: [] for topic in topics} if not discussion else {}

    summary = {
        "folder_id": args.folder_id,
        "latest": {"id": latest.get("id"), "title": latest.get("title"), "date": latest_date.isoformat() if latest_date else ""},
        "target": {"date": target.isoformat(), "title": target_name},
        "topics": topics,
        "touched_topics": touched,
        "mode": "write" if args.write else "dry-run",
    }
    out_dir = write_outputs(target, summary, updated_body, template)

    if args.write:
        if existing and args.replace_existing:
            created = c.copy_page(
                source_id=latest["id"],
                destination_type="existing_page",
                destination_value=existing[0]["id"],
                title=target_name,
                body=updated_body,
            )
            summary["replaced"] = {"id": existing[0].get("id"), "url": page_url(created)}
        else:
            created = c.copy_page(
                source_id=latest["id"],
                destination_type="parent_content",
                destination_value=args.folder_id,
                title=target_name,
                body=updated_body,
            )
            summary["created"] = {"id": created.get("id"), "url": page_url(created)}
        (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return

    print(json.dumps(summary | {"out_dir": str(out_dir.relative_to(ROOT))}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        raise SystemExit(f"ERROR: {exc}") from None
