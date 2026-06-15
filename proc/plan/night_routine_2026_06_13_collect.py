#!/usr/bin/env python3
from __future__ import annotations

import base64
import html
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests


ROOT = Path(__file__).resolve().parents[2]
DAY = os.environ.get("NIGHT_ROUTINE_DAY", "2026-06-13")
KST = timezone(timedelta(hours=9))
START = datetime.fromisoformat(f"{DAY}T00:00:00+09:00")
END = START + timedelta(days=1)
RAW = ROOT / "data" / "daily" / DAY / "raw"
DAILY = ROOT / "data" / "daily" / DAY
RAINDROP_DUMP = ROOT / "data" / "raindrop" / "dump"
RAINDROP_INFER = ROOT / "data" / "raindrop" / "infer"

NOTION_TASK_DB = "71c69a38-772b-4ea0-b9e6-0bb23f64ac7c"
NOTION_JOT_DB = "d16ebd32-1285-43a8-a9c1-355a91ab782b"
NOTION_NOTE_DB = "57fc4d6e-2d7b-4162-8b4e-87c3e45d79cd"
NOTION_AREA_DB = "e71a7b62-a9fa-4a34-b5cf-1e5af5826d8e"

AREA_DESCRIPTIONS = {
    "DOF": "디오에프 현 회사 업무: CRM, 거래원장, 영업/AX, 사내 세미나, 사내 데이터/업무 자동화.",
    "Productivity": "개인 생산성 도구, Notion, 워크스페이스, 루틴, 개인 지식관리.",
    "Lecturing": "외부 강의/강연, 바이브코딩, 벤처경영, 책, 슬라이드, 교육 콘텐츠.",
    "Career": "커리어, 이전 직장/학계 협업/외부 인맥, 장기 커리어 자산.",
    "SelfAdmin": "개인 행정, 건강, 계정, 생활 관리.",
    "Home": "부부 일상, 아내, 자녀/임신 등 집 안의 일.",
    "Family": "본가와 가족 관련 일.",
    "ProgMaster": "프로그래밍 마스터, 개발 학습, 코딩 스킬 훈련.",
    "Kamo": "Kamo 영역.",
    "Musician": "음악/뮤지션 관련 영역.",
    "ProPar": "ProPar 영역.",
    "ConvBoard": "ConvBoard 영역.",
    "Suited": "Suited 영역.",
    "WHYQ": "WHYQ 영역.",
    "TANKMON": "TANKMON 영역.",
    "RealEstate": "부동산 관련 영역.",
    "Artisan": "장인성/창작/제작 관련 영역.",
    "Uncategorizable": "정보가 부족하거나 기존 Area와 의미적으로 맞지 않는 항목.",
}

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "night-routine/2026-06-13"})
ERRORS: dict[str, Any] = {}


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    env_path = ROOT / ".env"
    if not env_path.exists():
        return env
    for raw in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        env[key.strip()] = value
    return env


ENV = load_env()


def ensure_dirs() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    RAINDROP_DUMP.joinpath("raindrops").mkdir(parents=True, exist_ok=True)
    RAINDROP_DUMP.joinpath("collections").mkdir(parents=True, exist_ok=True)
    RAINDROP_INFER.mkdir(parents=True, exist_ok=True)


def write_json(name: str, data: Any) -> None:
    path = RAW / name
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def write_text(name: str, data: str) -> None:
    (RAW / name).write_text(data, encoding="utf-8")


def record_error(source: str, exc: Any) -> None:
    text = str(exc)
    if len(text) > 4000:
        text = text[:4000] + "...<truncated>"
    ERRORS[source] = text
    (RAW / f"{source}.err").write_text(text, encoding="utf-8")


def save_errors() -> None:
    write_json("source-errors.json", ERRORS)


def dt_parse(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def in_day(value: str | None) -> bool:
    parsed = dt_parse(value)
    if not parsed:
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    kst = parsed.astimezone(KST)
    return START <= kst < END


def safe_request(method: str, url: str, **kwargs: Any) -> requests.Response:
    kwargs.setdefault("timeout", 40)
    response = SESSION.request(method, url, **kwargs)
    if response.status_code >= 400:
        body = response.text[:1200]
        raise RuntimeError(f"{method} {url} -> {response.status_code}: {body}")
    return response


def safe_json(method: str, url: str, **kwargs: Any) -> Any:
    return safe_request(method, url, **kwargs).json()


def first_env(*names: str) -> str | None:
    for name in names:
        value = ENV.get(name) or os.environ.get(name)
        if value:
            return value
    return None


def openai_json(messages: list[dict[str, str]], *, temperature: float = 0.2) -> dict[str, Any]:
    key = first_env("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is missing")
    payload = {
        "model": os.environ.get("NIGHT_ROUTINE_OPENAI_MODEL", "gpt-4o-mini"),
        "messages": messages,
        "temperature": temperature,
        "response_format": {"type": "json_object"},
    }
    data = safe_json(
        "POST",
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json=payload,
        timeout=90,
    )
    text = data["choices"][0]["message"]["content"]
    return json.loads(text)


def openai_audio_transcribe(path: Path) -> str:
    key = first_env("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is missing")
    with path.open("rb") as f:
        response = safe_request(
            "POST",
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {key}"},
            data={"model": "whisper-1", "language": "ko"},
            files={"file": (path.name, f)},
            timeout=300,
        )
    return response.json().get("text", "")


def collect_local_audio() -> None:
    candidates: list[str] = []
    for base in [Path.home() / "Downloads", Path.home() / "Desktop", ROOT / "data" / "daily"]:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".m4a", ".mp3", ".wav", ".aac", ".webm"}:
                continue
            try:
                mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=KST)
            except OSError:
                continue
            if START - timedelta(days=1) <= mtime < END + timedelta(days=1):
                candidates.append(str(path))
    write_text("local-audio-candidates.txt", "\n".join(sorted(candidates)) + ("\n" if candidates else ""))
    todays = [Path(p) for p in candidates if in_day(datetime.fromtimestamp(Path(p).stat().st_mtime, tz=KST).isoformat())]
    for idx, audio in enumerate(todays[:5], 1):
        out_audio = RAW / f"audio-local-{idx}{audio.suffix.lower()}"
        if not out_audio.exists():
            out_audio.write_bytes(audio.read_bytes())
        voice_path = RAW / f"voice-local-{idx}.txt"
        if voice_path.exists():
            continue
        try:
            text = openai_audio_transcribe(out_audio)
            voice_path.write_text(text, encoding="utf-8")
        except Exception as exc:
            record_error(f"voice-local-{idx}", exc)


def notion_headers() -> dict[str, str]:
    token = first_env("NOTION_INTEG_ACCESS_TOKEN_GQAUTO01")
    if not token:
        raise RuntimeError("NOTION_INTEG_ACCESS_TOKEN_GQAUTO01 is missing")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }


def notion(method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
    url = f"https://api.notion.com/v1{path}"
    kwargs: dict[str, Any] = {"headers": notion_headers()}
    if payload is not None:
        kwargs["json"] = payload
    return safe_json(method, url, **kwargs)


def rich_plain(items: list[dict[str, Any]] | None) -> str:
    if not items:
        return ""
    return "".join((item.get("plain_text") or "") for item in items)


def page_title(page: dict[str, Any]) -> str:
    props = page.get("properties") or {}
    for prop in props.values():
        if prop.get("type") == "title":
            return rich_plain(prop.get("title")).strip()
    return page.get("title") or page.get("id") or ""


def prop_status(page: dict[str, Any]) -> str:
    props = page.get("properties") or {}
    for key in ["Status", "상태"]:
        prop = props.get(key)
        if prop and prop.get("type") == "status":
            status = prop.get("status") or {}
            return status.get("name") or ""
        if prop and prop.get("type") == "select":
            select = prop.get("select") or {}
            return select.get("name") or ""
    for prop in props.values():
        if prop.get("type") == "status":
            status = prop.get("status") or {}
            return status.get("name") or ""
    for prop in props.values():
        if prop.get("type") == "select":
            select = prop.get("select") or {}
            if select:
                return select.get("name") or ""
    return ""


def prop_date_values(page: dict[str, Any]) -> dict[str, str | None]:
    values: dict[str, str | None] = {}
    for name, prop in (page.get("properties") or {}).items():
        if prop.get("type") == "date":
            values[name] = (prop.get("date") or {}).get("start")
    return values


def prop_relation_len(page: dict[str, Any], name: str = "Areas") -> int | None:
    prop = (page.get("properties") or {}).get(name)
    if not prop or prop.get("type") != "relation":
        return None
    return len(prop.get("relation") or [])


def block_text(block: dict[str, Any]) -> str:
    btype = block.get("type")
    if not btype:
        return ""
    data = block.get(btype) or {}
    parts = [
        rich_plain(data.get("rich_text")),
        rich_plain(data.get("caption")),
    ]
    return " ".join(p for p in parts if p).strip()


def notion_blocks(block_id: str, *, max_blocks: int = 120, depth: int = 0) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    cursor: str | None = None
    while len(blocks) < max_blocks:
        qs = f"?page_size=100"
        if cursor:
            qs += f"&start_cursor={cursor}"
        data = notion("GET", f"/blocks/{block_id}/children{qs}")
        results = data.get("results") or []
        for block in results:
            blocks.append(block)
            if len(blocks) >= max_blocks:
                break
            if depth < 1 and block.get("has_children"):
                try:
                    blocks.extend(notion_blocks(block["id"], max_blocks=max_blocks - len(blocks), depth=depth + 1))
                except Exception:
                    pass
        if not data.get("has_more") or len(blocks) >= max_blocks:
            break
        cursor = data.get("next_cursor")
    return blocks


def page_excerpt(page: dict[str, Any], *, max_chars: int = 1200) -> str:
    try:
        texts = [block_text(block) for block in notion_blocks(page["id"], max_blocks=80)]
    except Exception:
        texts = []
    excerpt = "\n".join(t for t in texts if t).strip()
    return excerpt[:max_chars]


def notion_search(query: str, *, page_size: int = 20) -> list[dict[str, Any]]:
    data = notion(
        "POST",
        "/search",
        {
            "query": query,
            "filter": {"property": "object", "value": "page"},
            "page_size": page_size,
        },
    )
    return data.get("results") or []


def notion_query(object_id: str, payload: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    body = payload or {"page_size": 100}
    paths = [f"/databases/{object_id}/query", f"/data_sources/{object_id}/query"]
    last_error: Exception | None = None
    for path in paths:
        try:
            data = notion("POST", path, body)
            out = data.get("results") or []
            cursor = data.get("next_cursor")
            while data.get("has_more") and cursor and len(out) < 300:
                body2 = dict(body)
                body2["start_cursor"] = cursor
                data = notion("POST", path, body2)
                out.extend(data.get("results") or [])
                cursor = data.get("next_cursor")
            return out
        except Exception as exc:
            last_error = exc
    raise RuntimeError(last_error or f"Notion query failed for {object_id}")


def collect_notion() -> None:
    try:
        pages = notion_search(f"DailyJot {DAY}", page_size=10)
        target = None
        for page in pages:
            title = page_title(page)
            if DAY in title and "DailyJot" in title:
                target = page
                break
        if target:
            data = {"page": target, "title": page_title(target), "blocks": notion_blocks(target["id"])}
        else:
            data = {"page": None, "title": None, "blocks": [], "search_results": pages}
        write_json("notion-jot-live.json", data)
        write_json("notion-jot.json", data)
    except Exception as exc:
        record_error("notion-jot", exc)

    try:
        edited: list[dict[str, Any]] = []
        cursor: str | None = None
        while len(edited) < 200:
            payload: dict[str, Any] = {
                "filter": {"property": "object", "value": "page"},
                "sort": {"direction": "descending", "timestamp": "last_edited_time"},
                "page_size": 100,
            }
            if cursor:
                payload["start_cursor"] = cursor
            data = notion("POST", "/search", payload)
            for page in data.get("results") or []:
                if in_day(page.get("last_edited_time")):
                    edited.append(
                        {
                            "id": page.get("id"),
                            "title": page_title(page),
                            "last_edited_time": page.get("last_edited_time"),
                            "url": page.get("url"),
                            "properties": page.get("properties"),
                            "excerpt": page_excerpt(page, max_chars=800),
                        }
                    )
            if not data.get("has_more") or not data.get("next_cursor"):
                break
            if data.get("results") and not any(in_day(p.get("last_edited_time")) for p in data.get("results")):
                break
            cursor = data.get("next_cursor")
        write_json("notion-edited.json", edited)
    except Exception as exc:
        record_error("notion-edited", exc)

    try:
        tasks_by_id: dict[str, dict[str, Any]] = {}
        filters = [
            {"property": "ActDate", "date": {"equals": DAY}},
            {"property": "DueDate", "date": {"on_or_before": DAY}},
        ]
        for status in ["Doing", "Wait", "Ready", "Schedule"]:
            filters.append({"property": "Status", "status": {"equals": status}})
        for filt in filters:
            try:
                for page in notion_query(NOTION_TASK_DB, {"filter": filt, "page_size": 100}):
                    tasks_by_id[page["id"]] = page
            except Exception:
                pass
        try:
            recent = notion_query(
                NOTION_TASK_DB,
                {
                    "sorts": [{"timestamp": "last_edited_time", "direction": "descending"}],
                    "page_size": 100,
                },
            )
            for page in recent:
                if in_day(page.get("last_edited_time")):
                    tasks_by_id[page["id"]] = page
            write_json(
                "notion-recent-tasks.json",
                [{"id": p.get("id"), "title": page_title(p), "status": prop_status(p), "last_edited_time": p.get("last_edited_time"), "dates": prop_date_values(p), "url": p.get("url")} for p in recent],
            )
        except Exception:
            pass
        tasks = [
            {
                "id": p.get("id"),
                "title": page_title(p),
                "status": prop_status(p),
                "last_edited_time": p.get("last_edited_time"),
                "dates": prop_date_values(p),
                "areas_count": prop_relation_len(p),
                "url": p.get("url"),
                "excerpt": page_excerpt(p, max_chars=800),
                "properties": p.get("properties"),
            }
            for p in tasks_by_id.values()
        ]
        write_json("notion-tasks-live.json", tasks)
        write_json("notion-tasks.json", tasks)
    except Exception as exc:
        record_error("notion-tasks", exc)

    try:
        areas_raw = notion_query(
            NOTION_AREA_DB,
            {
                "page_size": 100,
            },
        )
        areas = []
        for page in areas_raw:
            status = prop_status(page)
            if status == "Closed":
                continue
            name = page_title(page)
            areas.append(
                {
                    "id": page["id"],
                    "name": name,
                    "status": status,
                    "description": AREA_DESCRIPTIONS.get(name, ""),
                    "url": page.get("url"),
                }
            )
        write_json("notion-areas-active.json", areas)
    except Exception as exc:
        record_error("notion-areas-active", exc)


def collect_area_backfill() -> None:
    try:
        areas_path = RAW / "notion-areas-active.json"
        if not areas_path.exists():
            write_json("notion-area-backfill.result.json", {"status": "skipped", "reason": "no active area data"})
            return
        areas = json.loads(areas_path.read_text(encoding="utf-8"))
        candidates: dict[str, list[dict[str, Any]]] = {"tasks": [], "notes": []}
        for label, object_id in [("tasks", NOTION_TASK_DB), ("notes", NOTION_NOTE_DB)]:
            try:
                pages = notion_query(
                    object_id,
                    {"filter": {"property": "Areas", "relation": {"is_empty": True}}, "page_size": 10},
                )
            except Exception as exc:
                candidates[label] = [{"error": str(exc)}]
                continue
            for page in pages[:10]:
                candidates[label].append(
                    {
                        "id": page["id"],
                        "title": page_title(page),
                        "status": prop_status(page),
                        "last_edited_time": page.get("last_edited_time"),
                        "url": page.get("url"),
                        "excerpt": page_excerpt(page, max_chars=900),
                    }
                )
        write_json("notion-area-backfill.discover.json", {"areas": areas, **candidates})
        real_candidates = [c for c in candidates["tasks"] + candidates["notes"] if c.get("id")]
        if not real_candidates:
            write_json("notion-area-backfill.result.json", {"status": "no_candidates", "count": 0})
            return
        mapping = openai_json(
            [
                {
                    "role": "system",
                    "content": (
                        "You assign Notion pages to exactly one Area by semantic judgment. "
                        "Do not use keyword rules. Prefer Uncategorizable when evidence is weak. "
                        "Return JSON with tasks and notes arrays. Each item: id,title,area_page_id,area_name,reason."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "day": DAY,
                            "area_descriptions": AREA_DESCRIPTIONS,
                            "active_areas": areas,
                            "candidates": candidates,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            temperature=0.1,
        )
        mapping["_meta"] = {"act_date": DAY, "area_descriptions": AREA_DESCRIPTIONS}
        write_json("notion-area-backfill.mapping.json", mapping)
        area_by_id = {a["id"]: a for a in areas}
        area_by_name = {a["name"]: a for a in areas}

        def resolve_area_id(item: dict[str, Any]) -> str | None:
            area_id = item.get("area_page_id")
            if area_id in area_by_id:
                return area_id
            for key in [item.get("area_name"), item.get("area_page_id")]:
                if not key:
                    continue
                if key in area_by_name:
                    return area_by_name[key]["id"]
                for area in areas:
                    name = area.get("name") or ""
                    bare = re.sub(r"\(.*?\)", "", name).strip()
                    if key == bare or str(key) in name:
                        return area["id"]
            return None

        result = {"patched": [], "skipped": [], "errors": []}
        for section in ["tasks", "notes"]:
            for item in mapping.get(section, []) or []:
                page_id = item.get("id")
                area_id = resolve_area_id(item)
                if not page_id or not area_id:
                    result["skipped"].append({"item": item, "reason": "missing page or inactive area"})
                    continue
                try:
                    live = notion("GET", f"/pages/{page_id}")
                    current_count = prop_relation_len(live)
                    if current_count is None:
                        result["skipped"].append({"id": page_id, "reason": "Areas property not found"})
                        continue
                    if current_count > 0:
                        result["skipped"].append({"id": page_id, "reason": "skipped_has_area"})
                        continue
                    notion(
                        "PATCH",
                        f"/pages/{page_id}",
                        {"properties": {"Areas": {"relation": [{"id": area_id}]}}},
                    )
                    result["patched"].append(item)
                    time.sleep(0.35)
                except Exception as exc:
                    result["errors"].append({"id": page_id, "error": str(exc)})
        write_json("notion-area-backfill.result.json", result)
    except Exception as exc:
        record_error("notion-area-backfill", exc)


def google_token(account: str) -> str:
    upper = account.upper()
    token_path_value = first_env(f"GOOGLE_{upper}_TOKEN_PATH")
    client_id = first_env(f"GOOGLE_{upper}_CLIENT_ID")
    client_secret = first_env(f"GOOGLE_{upper}_CLIENT_SECRET")
    if not token_path_value or not client_id or not client_secret:
        raise RuntimeError(f"Google config missing for {account}")
    token_path = Path(token_path_value).expanduser()
    if not token_path.is_absolute():
        token_path = ROOT / token_path
    token_data = json.loads(token_path.read_text(encoding="utf-8"))
    refresh_token = token_data.get("refresh_token")
    if refresh_token:
        data = safe_json(
            "POST",
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=40,
        )
        return data["access_token"]
    token = token_data.get("token") or token_data.get("access_token")
    if token:
        return token
    raise RuntimeError(f"No usable Google token for {account}")


def google_headers(account: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {google_token(account)}"}


def collect_gcal(account: str) -> None:
    try:
        params = {
            "timeMin": START.isoformat(),
            "timeMax": END.isoformat(),
            "singleEvents": "true",
            "orderBy": "startTime",
            "maxResults": "100",
        }
        data = safe_json(
            "GET",
            "https://www.googleapis.com/calendar/v3/calendars/primary/events",
            headers=google_headers(account),
            params=params,
        )
        write_json(f"gcal-{account}.json", data.get("items") or [])
    except Exception as exc:
        record_error(f"gcal-{account}", exc)


def b64url_decode(value: str) -> str:
    padded = value + "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(padded.encode()).decode("utf-8", errors="replace")


def gmail_body(payload: dict[str, Any]) -> str:
    chunks: list[str] = []

    def walk(part: dict[str, Any]) -> None:
        mime = part.get("mimeType") or ""
        body = part.get("body") or {}
        data = body.get("data")
        if data and (mime.startswith("text/plain") or mime.startswith("text/html")):
            text = b64url_decode(data)
            if mime.startswith("text/html"):
                text = html_to_text(text)
            chunks.append(text)
        for child in part.get("parts") or []:
            walk(child)

    walk(payload)
    return "\n\n".join(chunks)[:6000]


def selected_headers(headers: list[dict[str, str]]) -> dict[str, str]:
    wanted = {"from", "to", "cc", "subject", "date"}
    return {h["name"]: h.get("value", "") for h in headers if h.get("name", "").lower() in wanted}


def collect_gmail(account: str) -> None:
    try:
        q = f"after:{DAY.replace('-', '/')} before:{(START + timedelta(days=1)).date().isoformat().replace('-', '/')} -category:promotions -category:social"
        data = safe_json(
            "GET",
            "https://gmail.googleapis.com/gmail/v1/users/me/messages",
            headers=google_headers(account),
            params={"q": q, "maxResults": 80},
        )
        messages = []
        for ref in data.get("messages") or []:
            msg = safe_json(
                "GET",
                f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{ref['id']}",
                headers=google_headers(account),
                params={"format": "full"},
            )
            payload = msg.get("payload") or {}
            messages.append(
                {
                    "id": msg.get("id"),
                    "threadId": msg.get("threadId"),
                    "labelIds": msg.get("labelIds"),
                    "snippet": msg.get("snippet"),
                    "internalDate": msg.get("internalDate"),
                    "headers": selected_headers(payload.get("headers") or []),
                    "body": gmail_body(payload),
                }
            )
            time.sleep(0.05)
        write_json(f"gmail-{account}.json", messages)
    except Exception as exc:
        record_error(f"gmail-{account}", exc)


def collect_gdrive(account: str) -> None:
    try:
        q = (
            f"modifiedTime > '{START.isoformat()}' and "
            f"modifiedTime < '{END.isoformat()}' and trashed = false"
        )
        data = safe_json(
            "GET",
            "https://www.googleapis.com/drive/v3/files",
            headers=google_headers(account),
            params={
                "q": q,
                "pageSize": 80,
                "fields": "files(id,name,mimeType,modifiedTime,createdTime,webViewLink,size,owners(displayName,emailAddress))",
                "orderBy": "modifiedTime desc",
            },
        )
        files = data.get("files") or []
        write_json(f"gdrive-{account}.json", files)
        for item in files:
            name = item.get("name") or ""
            mime = item.get("mimeType") or ""
            is_audio = mime.startswith("audio/") or re.search(r"(voice|recording|음성)", name, re.I)
            if not is_audio:
                continue
            ext = Path(name).suffix or ".bin"
            out = RAW / f"audio-gdrive-{account}-{item['id']}{ext}"
            if not out.exists():
                media = safe_request(
                    "GET",
                    f"https://www.googleapis.com/drive/v3/files/{item['id']}",
                    headers=google_headers(account),
                    params={"alt": "media"},
                    timeout=300,
                )
                out.write_bytes(media.content)
            voice = RAW / f"voice-gdrive-{account}-{item['id']}.txt"
            if not voice.exists():
                text = openai_audio_transcribe(out)
                voice.write_text(text, encoding="utf-8")
    except Exception as exc:
        record_error(f"gdrive-{account}", exc)


def graph_token() -> str:
    tenant = first_env("MSFT_TEAMSPEEP_TENANT_ID", "MSFT_SHAREPOINT_TENANT_ID")
    client_id = first_env("MSFT_TEAMSPEEP_CLIENT_ID", "MSFT_SHAREPOINT_CLIENT_ID")
    secret = first_env("MSFT_TEAMSPEEP_CLIENT_SECRET", "MSFT_SHAREPOINT_CLIENT_SECRET")
    if not tenant or not client_id or not secret:
        raise RuntimeError("Microsoft Graph app config missing")
    data = safe_json(
        "POST",
        f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
        data={
            "client_id": client_id,
            "client_secret": secret,
            "grant_type": "client_credentials",
            "scope": "https://graph.microsoft.com/.default",
        },
        timeout=40,
    )
    return data["access_token"]


def graph_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {graph_token()}"}


def collect_teams() -> None:
    headers = graph_headers()
    user_id = first_env("MSFT_TEAMS_PERSONAL_ID") or first_env("MSFT_INFOEMAIL_SENDER_EMAIL")
    if not user_id:
        raise RuntimeError("No Microsoft user id/email configured")
    chats_out = []
    try:
        chats = safe_json(
            "GET",
            f"https://graph.microsoft.com/v1.0/users/{user_id}/chats",
            headers=headers,
            params={"$top": 50},
        ).get("value") or []
        for chat in chats:
            preview = chat.get("lastMessagePreview") or {}
            preview_time = preview.get("createdDateTime")
            if preview_time and not in_day(preview_time):
                continue
            try:
                msgs = safe_json(
                    "GET",
                    f"https://graph.microsoft.com/v1.0/chats/{chat['id']}/messages",
                    headers=headers,
                    params={"$top": 50},
                ).get("value") or []
                msgs = [
                    {
                        "id": m.get("id"),
                        "createdDateTime": m.get("createdDateTime"),
                        "from": m.get("from"),
                        "body": (m.get("body") or {}).get("content"),
                    }
                    for m in msgs
                    if in_day(m.get("createdDateTime"))
                ]
                if msgs:
                    chats_out.append({"chat": chat, "messages": msgs})
            except Exception as exc:
                chats_out.append({"chat": chat, "error": str(exc)})
        write_json("teams-chats.json", chats_out)
    except Exception as exc:
        record_error("teams-chats", exc)

    team_id = first_env("TEAM_ID")
    if not team_id:
        write_json("teams-channel-map.json", [])
        write_json("teams-channels.json", [])
        write_json("teams-standup.json", [])
        return
    try:
        channels = safe_json(
            "GET",
            f"https://graph.microsoft.com/v1.0/teams/{team_id}/channels",
            headers=headers,
            params={"$top": 100},
        ).get("value") or []
        write_json("teams-channel-map.json", channels)
        channel_out = []
        standup_out = []
        for channel in channels:
            display = channel.get("displayName") or ""
            try:
                messages = safe_json(
                    "GET",
                    f"https://graph.microsoft.com/v1.0/teams/{team_id}/channels/{channel['id']}/messages",
                    headers=headers,
                    params={"$top": 30},
                ).get("value") or []
                filtered = [m for m in messages if in_day(m.get("createdDateTime"))]
                if filtered:
                    record = {"channel": channel, "messages": filtered}
                    channel_out.append(record)
                    if "standup" in display.lower() or "daily" in display.lower():
                        standup_out.append(record)
            except Exception as exc:
                if "standup" in display.lower():
                    standup_out.append({"channel": channel, "error": str(exc)})
            time.sleep(0.15)
        write_json("teams-channels.json", channel_out)
        write_json("teams-standup.json", standup_out)
    except Exception as exc:
        record_error("teams-channels", exc)


def collect_outlook() -> None:
    try:
        headers = graph_headers()
        user_id = first_env("MSFT_TEAMS_PERSONAL_ID") or first_env("MSFT_INFOEMAIL_SENDER_EMAIL")
        if not user_id:
            raise RuntimeError("No Outlook user id/email configured")
        data = safe_json(
            "GET",
            f"https://graph.microsoft.com/v1.0/users/{user_id}/messages",
            headers=headers,
            params={
                "$filter": f"receivedDateTime ge {START.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')} and receivedDateTime lt {END.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')}",
                "$select": "id,receivedDateTime,sentDateTime,from,toRecipients,subject,bodyPreview,webLink",
                "$top": 80,
                "$orderby": "receivedDateTime desc",
            },
        )
        write_json("outlook.json", data.get("value") or [])
    except Exception as exc:
        record_error("outlook", exc)


def collect_atlassian() -> None:
    email = first_env("ATLASSIAN_EMAIL")
    token = first_env("ATLASSIAN_TOK")
    if not email or not token:
        raise RuntimeError("Atlassian config missing")
    auth = (email, token)
    out: dict[str, Any] = {"jira": {}, "confluence": {}}
    headers = {"Accept": "application/json"}
    queries = {
        "created": f'creator = currentUser() AND created >= "{DAY}" AND created < "{(START + timedelta(days=1)).date().isoformat()}" ORDER BY created DESC',
        "updated_with_me": f'updated >= "{DAY}" AND updated < "{(START + timedelta(days=1)).date().isoformat()}" AND (assignee = currentUser() OR reporter = currentUser()) ORDER BY updated DESC',
    }
    for name, jql in queries.items():
        try:
            data = safe_json(
                "GET",
                "https://doflab.atlassian.net/rest/api/3/search/jql",
                headers=headers,
                auth=auth,
                params={
                    "jql": jql,
                    "maxResults": 50,
                    "fields": "summary,status,assignee,reporter,creator,updated,created,comment",
                    "expand": "changelog",
                },
                timeout=60,
            )
            out["jira"][name] = data.get("issues") or []
        except Exception as exc:
            out["jira"][name] = {"error": str(exc)}
    try:
        pages = safe_json(
            "GET",
            "https://doflab.atlassian.net/wiki/api/v2/pages",
            headers=headers,
            auth=auth,
            params={"limit": 50, "sort": "-modified-date"},
            timeout=60,
        )
        out["confluence"]["pages"] = [
            p for p in pages.get("results") or [] if in_day(p.get("createdAt")) or in_day((p.get("version") or {}).get("createdAt"))
        ]
    except Exception as exc:
        out["confluence"]["pages"] = {"error": str(exc)}
    write_json("atlassian.json", out)


def raindrop_headers() -> dict[str, str]:
    token = first_env("RAINDROP_TEST_TOKEN")
    if not token:
        raise RuntimeError("RAINDROP_TEST_TOKEN is missing")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def raindrop(method: str, path: str, payload: dict[str, Any] | None = None, params: dict[str, Any] | None = None) -> Any:
    kwargs: dict[str, Any] = {"headers": raindrop_headers()}
    if payload is not None:
        kwargs["json"] = payload
    if params:
        kwargs["params"] = params
    return safe_json(method, f"https://api.raindrop.io/rest/v1{path}", **kwargs)


def html_to_text(value: str) -> str:
    value = re.sub(r"(?is)<(script|style).*?</\1>", " ", value)
    value = re.sub(r"(?s)<[^>]+>", " ", value)
    value = html.unescape(value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def fetch_link_text(url: str) -> str:
    response = safe_request(
        "GET",
        url,
        headers={"User-Agent": "Mozilla/5.0 night-routine"},
        timeout=30,
        allow_redirects=True,
    )
    content = response.text
    return html_to_text(content)[:12000]


def infer_raindrop(item: dict[str, Any]) -> Path | None:
    rid = str(item.get("_id") or item.get("id"))
    if not rid:
        return None
    out = RAINDROP_INFER / f"{rid}.md"
    if out.exists():
        return out
    link = item.get("link") or ""
    content = ""
    status = "ok"
    try:
        if link:
            content = fetch_link_text(link)
    except Exception as exc:
        status = "partial"
        content = f"Fetch failed: {exc}"
    prompt_data = {
        "raindrop": {
            "id": rid,
            "title": item.get("title"),
            "excerpt": item.get("excerpt"),
            "note": item.get("note"),
            "link": item.get("link"),
            "domain": item.get("domain"),
            "tags": item.get("tags") or [],
            "created": item.get("created"),
            "lastUpdate": item.get("lastUpdate"),
        },
        "fetched_text": content[:10000],
    }
    try:
        result = openai_json(
            [
                {
                    "role": "system",
                    "content": (
                        "Read the bookmark metadata and fetched text. Return Korean JSON with keys: "
                        "summary, insights (array), detailed_note, revisit_after_days, revisit_trigger, category, freshness."
                    ),
                },
                {"role": "user", "content": json.dumps(prompt_data, ensure_ascii=False)},
            ],
            temperature=0.2,
        )
    except Exception as exc:
        record_error(f"raindrop-infer-{rid}", exc)
        return None
    md = [
        "---",
        f'id: "{rid}"',
        f'link: "{link}"',
        f'title: "{str(item.get("title") or "").replace(chr(34), chr(39))}"',
        f'domain: "{item.get("domain") or ""}"',
        f"status: \"{status}\"",
        f"raindrop_tags: {json.dumps(item.get('tags') or [], ensure_ascii=False)}",
        f'raindrop_created: "{item.get("created") or ""}"',
        f'raindrop_last_update: "{item.get("lastUpdate") or ""}"',
        f'inferred_at: "{datetime.now(KST).isoformat()}"',
        f"revisit_after_days: {result.get('revisit_after_days', 0)}",
        f'revisit_trigger: "{str(result.get("revisit_trigger") or "").replace(chr(34), chr(39))}"',
        f'category: "{result.get("category") or "other"}"',
        f'freshness: "{result.get("freshness") or "medium"}"',
        "---",
        "",
        f"# {item.get('title') or rid}",
        f"<{link}>",
        "",
        "## 요약",
        str(result.get("summary") or ""),
        "",
        "## 핵심 인사이트",
    ]
    for insight in result.get("insights") or []:
        md.append(f"- {insight}")
    md.extend(["", "## 상세 메모", str(result.get("detailed_note") or ""), "", "## 재방문 가이드", f"- {result.get('revisit_trigger') or ''}"])
    out.write_text("\n".join(md).strip() + "\n", encoding="utf-8")
    return out


def retag_raindrop(item: dict[str, Any], infer_path: Path, top_tags: list[str]) -> dict[str, Any]:
    rid = str(item.get("_id") or item.get("id"))
    infer_md = infer_path.read_text(encoding="utf-8", errors="replace")
    current_note = item.get("note") or ""
    if "--- ai memo ----" in current_note:
        return {"id": rid, "status": "skip-already-tagged"}
    result = openai_json(
        [
            {
                "role": "system",
                "content": (
                    "You retag one Raindrop bookmark after reading the infer markdown. "
                    "Return JSON with exactly keys tags and memo. tags must be exactly 3 concise tags, no duplicates, "
                    "prefer the provided vocabulary when semantically suitable. memo is Korean, under 80 chars, saying when to revisit."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "title": item.get("title"),
                        "link": item.get("link"),
                        "current_tags": item.get("tags") or [],
                        "top_tag_vocabulary": top_tags[:80],
                        "infer_markdown": infer_md[:12000],
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        temperature=0.2,
    )
    tags = [str(t).strip() for t in result.get("tags") or [] if str(t).strip()]
    deduped: list[str] = []
    for tag in tags:
        if tag not in deduped:
            deduped.append(tag)
    if len(deduped) != 3:
        return {"id": rid, "status": "bad-llm-output", "tags": deduped}
    memo = str(result.get("memo") or "").strip()
    if not memo:
        return {"id": rid, "status": "bad-llm-output", "tags": deduped, "memo": memo}
    note = f"{current_note.strip()}\n\n--- ai memo ----\n{memo[:120]}\n----------------".strip()
    raindrop("PUT", f"/raindrop/{rid}", {"tags": deduped, "note": note})
    item["tags"] = deduped
    item["note"] = note
    (RAINDROP_DUMP / "raindrops" / f"{rid}.json").write_text(json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"id": rid, "status": "ok", "tags": deduped, "memo": memo}


def collect_raindrop() -> None:
    try:
        try:
            user = raindrop("GET", "/user")
            (RAINDROP_DUMP / "_user.json").write_text(json.dumps(user, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
        try:
            collections = raindrop("GET", "/collections")
            (RAINDROP_DUMP / "collections" / "_collections.json").write_text(json.dumps(collections, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
        tags_raw = raindrop("GET", "/tags")
        (RAINDROP_DUMP / "tags.json").write_text(json.dumps(tags_raw, ensure_ascii=False, indent=2), encoding="utf-8")
        top_tags = [t.get("_id") or t.get("tag") or t.get("name") for t in tags_raw.get("items", []) or tags_raw.get("tags", []) or []]
        top_tags = [str(t) for t in top_tags if t]
        todays: list[dict[str, Any]] = []
        page = 0
        while page < 5:
            data = raindrop(
                "GET",
                "/raindrops/-1",
                params={"sort": "-lastUpdate", "perpage": 50, "page": page},
            )
            items = data.get("items") or []
            if not items:
                break
            old_seen = False
            for item in items:
                rid = str(item.get("_id") or item.get("id"))
                if rid:
                    (RAINDROP_DUMP / "raindrops" / f"{rid}.json").write_text(json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8")
                if in_day(item.get("lastUpdate")) or in_day(item.get("created")):
                    todays.append(item)
                elif dt_parse(item.get("lastUpdate") or item.get("created")):
                    parsed = dt_parse(item.get("lastUpdate") or item.get("created"))
                    if parsed and parsed.astimezone(KST) < START:
                        old_seen = True
            if old_seen and page > 0:
                break
            page += 1
            time.sleep(0.55)
        todays.sort(key=lambda x: x.get("lastUpdate") or x.get("created") or "", reverse=True)
        write_json("raindrop.json", todays)
        selected = [item for item in todays if not (item.get("tags") or [])][:20]
        write_text("raindrop-untagged-selected-ids.txt", "\n".join(str(i.get("_id") or i.get("id")) for i in selected) + ("\n" if selected else ""))
        retag_results = []
        inferred_ids = []
        for item in selected:
            infer_path = infer_raindrop(item)
            if not infer_path:
                retag_results.append({"id": item.get("_id") or item.get("id"), "status": "no-infer"})
                continue
            inferred_ids.append(str(item.get("_id") or item.get("id")))
            retag_results.append(retag_raindrop(item, infer_path, top_tags))
            time.sleep(0.7)
        write_text("raindrop-untagged-infer-ids.txt", "\n".join(inferred_ids) + ("\n" if inferred_ids else ""))
        write_json("raindrop-retag-result.json", retag_results)
    except Exception as exc:
        record_error("raindrop-dump", exc)


def collect_amaranth_stub() -> None:
    write_json(
        "amaranth-approval.json",
        {
            "status": "skipped",
            "reason": "No reusable Amaranth collector script is available in this workspace for the night routine.",
        },
    )


def collect_kubit_stub() -> None:
    kubit = Path("/Users/gq/works/lecture/kubit/kubit-bitbot-slack-01")
    if not kubit.exists() or not (kubit / "package.json").exists():
        write_json("kubit-slack.json", {"status": "skipped", "reason": "kubit workspace or package.json not available"})
        return
    result: dict[str, Any] = {}
    for name, cmd in {
        "collect:conv": ["npm", "run", "collect:conv"],
        "collect:people": ["npm", "run", "collect:people"],
    }.items():
        try:
            proc = subprocess.run(cmd, cwd=kubit, text=True, capture_output=True, timeout=600)
            result[name] = {"returncode": proc.returncode, "stdout_tail": proc.stdout[-4000:], "stderr_tail": proc.stderr[-4000:]}
        except Exception as exc:
            result[name] = {"error": str(exc)}
    write_json("kubit-slack.json", result)


def main() -> int:
    ensure_dirs()
    write_json(
        "night-routine-run.json",
        {
            "day": DAY,
            "started_at": datetime.now(KST).isoformat(),
            "root": str(ROOT),
        },
    )
    steps = [
        ("voice", collect_local_audio),
        ("notion", collect_notion),
        ("notion-area-backfill", collect_area_backfill),
        ("gcal-bispro89", lambda: collect_gcal("bispro89")),
        ("gcal-sikbrad", lambda: collect_gcal("sikbrad")),
        ("gmail-bispro89", lambda: collect_gmail("bispro89")),
        ("gmail-sikbrad", lambda: collect_gmail("sikbrad")),
        ("gdrive-bispro89", lambda: collect_gdrive("bispro89")),
        ("gdrive-sikbrad", lambda: collect_gdrive("sikbrad")),
        ("teams", collect_teams),
        ("outlook", collect_outlook),
        ("atlassian", collect_atlassian),
        ("raindrop", collect_raindrop),
        ("kubit", collect_kubit_stub),
        ("amaranth", collect_amaranth_stub),
    ]
    status = []
    for name, fn in steps:
        started = datetime.now(KST)
        try:
            fn()
            status.append({"source": name, "status": "done", "seconds": (datetime.now(KST) - started).total_seconds()})
        except Exception as exc:
            record_error(name, exc)
            status.append({"source": name, "status": "failed", "seconds": (datetime.now(KST) - started).total_seconds()})
        save_errors()
    write_json(
        "night-routine-run.json",
        {
            "day": DAY,
            "started_at": status[0]["source"] if status else None,
            "finished_at": datetime.now(KST).isoformat(),
            "steps": status,
            "errors": ERRORS,
        },
    )
    save_errors()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
