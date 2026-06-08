from __future__ import annotations

import argparse
import base64
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from dotenv import dotenv_values
except Exception:  # pragma: no cover
    dotenv_values = None


SITE = "doflab.atlassian.net"
BASE = f"https://{SITE}/wiki"
CONF_V1 = f"{BASE}/rest/api"
CONF_V2 = f"{BASE}/api/v2"
SPACE_ID = "611057699"
OUT_DIR = Path("output/confluence-ax-reorg")
OUT_DIR.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class MoveSpec:
    page_id: str
    title: str
    target_id: str
    target_path: str
    reason: str


MOVES: list[MoveSpec] = [
    MoveSpec(
        "755597315",
        "핑거의 현행 요구사항 다시파악",
        "613941421",
        "AX / 프로젝트(보안) / ING 프로젝트 (보안)",
        "루트 직속 예외를 보안 프로젝트 하위로 이동",
    ),
    MoveSpec(
        "724729899",
        "주문앱 개발로그 모음",
        "711622712",
        "AX / 프로젝트(협업) / ING 프로젝트 (협업) / [AX-129] 주문앱",
        "본문에 [AX-129] 주문앱 하위 편입 의도가 명시됨",
    ),
    MoveSpec(
        "762183703",
        "[AX-183] 주문앱 현장테스트",
        "711622712",
        "AX / 프로젝트(협업) / ING 프로젝트 (협업) / [AX-129] 주문앱",
        "주문앱 현장테스트 subtree",
    ),
    MoveSpec(
        "826277897",
        "[AX-190] SF 데이터 이관 문서 작성",
        "723255336",
        "AX / 프로젝트(협업) / ING 프로젝트 (협업)",
        "AX 프로젝트 산출물",
    ),
    MoveSpec(
        "831717485",
        "[AX-191] 거래원장 새로만들기 업무",
        "723255336",
        "AX / 프로젝트(협업) / ING 프로젝트 (협업)",
        "프로젝트성 업무 문서",
    ),
    MoveSpec(
        "847872005",
        "[AX-193] 입출금 자동화 관련 조사",
        "711983125",
        "AX / 리서치(보안)",
        "입출금/자동화 조사 문서",
    ),
    MoveSpec(
        "852721703",
        "[AX-194] 포탈 할일탭 기획",
        "722960415",
        "AX / 프로젝트(협업) / ING 프로젝트 (협업) / [AX-129] 주문앱 / 주문웹 기획",
        "포탈/주문웹 기획 문서",
    ),
    MoveSpec(
        "868909093",
        "파일 고객에 직접 전송관련 리서치",
        "711983125",
        "AX / 리서치(보안)",
        "고객 전달 내용과 금액이 포함됨",
    ),
    MoveSpec(
        "824180818",
        "계약업무 관련 리서치",
        "711983125",
        "AX / 리서치(보안)",
        "장기 참고성 리서치",
    ),
    MoveSpec(
        "821133343",
        "기술지원 및 계약서관련 인터뷰",
        "711983125",
        "AX / 리서치(보안)",
        "인터뷰/계약/기술지원 리서치",
    ),
    MoveSpec(
        "830144513",
        "거래처원장 ERP데이터 보는방법",
        "614007091",
        "AX / 지식(보안)",
        "재사용 가능한 ERP 참고 지식",
    ),
]


def load_auth() -> tuple[str, str]:
    env_path = Path(".env")
    if env_path.exists() and dotenv_values is not None:
        values = dotenv_values(str(env_path))
        email = values.get("ATLASSIAN_EMAIL")
        token = values.get("ATLASSIAN_TOK")
        if email and token:
            return email, token
    raise RuntimeError("ATLASSIAN_EMAIL / ATLASSIAN_TOK not found in .env")


class Client:
    def __init__(self) -> None:
        email, token = load_auth()
        self.auth = "Basic " + base64.b64encode(f"{email}:{token}".encode()).decode()

    def request(
        self,
        method: str,
        url: str,
        body: dict[str, Any] | None = None,
        retries: int = 4,
    ) -> tuple[int, Any]:
        data = None
        headers = {
            "Authorization": self.auth,
            "Accept": "application/json",
        }
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode()
            headers["Content-Type"] = "application/json"
        last_error: Exception | None = None
        for attempt in range(retries):
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            try:
                with urllib.request.urlopen(req, timeout=30) as response:
                    raw = response.read().decode("utf-8", "replace")
                    if not raw:
                        return response.status, ""
                    try:
                        return response.status, json.loads(raw)
                    except json.JSONDecodeError:
                        return response.status, raw
            except urllib.error.HTTPError as exc:
                raw = exc.read().decode("utf-8", "replace")
                if exc.code in (429, 502, 503, 504):
                    last_error = RuntimeError(f"HTTP {exc.code}: {raw[:500]}")
                    time.sleep(2**attempt)
                    continue
                return exc.code, {"error": raw[:1200]}
            except Exception as exc:  # pragma: no cover
                last_error = exc
                time.sleep(2**attempt)
        raise RuntimeError(f"{method} {url} failed after retries: {last_error}")

    def get_page(self, page_id: str) -> dict[str, Any]:
        status, data = self.request("GET", f"{CONF_V2}/pages/{page_id}")
        if status != 200 or not isinstance(data, dict):
            raise RuntimeError(f"page read failed {page_id}: {status} {data}")
        return data

    def get_folder(self, folder_id: str) -> dict[str, Any]:
        status, data = self.request("GET", f"{CONF_V2}/folders/{folder_id}")
        if status != 200 or not isinstance(data, dict):
            raise RuntimeError(f"folder read failed {folder_id}: {status} {data}")
        return data

    def read_target(self, target_id: str) -> dict[str, Any]:
        status, data = self.request("GET", f"{CONF_V2}/pages/{target_id}")
        if status == 200 and isinstance(data, dict):
            data["_kind"] = "page"
            return data
        status, data = self.request("GET", f"{CONF_V2}/folders/{target_id}")
        if status == 200 and isinstance(data, dict):
            data["_kind"] = "folder"
            return data
        raise RuntimeError(f"target read failed {target_id}: {status} {data}")

    def move_append(self, page_id: str, target_id: str) -> tuple[int, Any]:
        url = f"{CONF_V1}/content/{page_id}/move/append/{target_id}"
        return self.request("PUT", url)


def web_url(page: dict[str, Any]) -> str:
    links = page.get("_links") or {}
    link = links.get("webui") or f"/spaces/AX/pages/{page.get('id')}"
    if link.startswith("http"):
        return link
    if link.startswith("/wiki/"):
        return f"https://{SITE}{link}"
    return f"{BASE}{link}"


def make_record(client: Client, spec: MoveSpec, before: dict[str, Any] | None = None) -> dict[str, Any]:
    page = before or client.get_page(spec.page_id)
    target = client.read_target(spec.target_id)
    return {
        "page_id": spec.page_id,
        "title_expected": spec.title,
        "title_actual": page.get("title"),
        "current_parent_id": page.get("parentId"),
        "current_parent_type": page.get("parentType"),
        "current_url": web_url(page),
        "target_id": spec.target_id,
        "target_title": target.get("title"),
        "target_kind": target.get("_kind"),
        "target_path": spec.target_path,
        "reason": spec.reason,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--out", default=str(OUT_DIR / "2026-06-08_move_results.json"))
    args = parser.parse_args()

    client = Client()
    results: list[dict[str, Any]] = []
    mode = "verify" if args.verify_only else "write" if args.write else "dry-run"
    for index, spec in enumerate(MOVES, start=1):
        before = client.get_page(spec.page_id)
        record = make_record(client, spec, before=before)
        record["index"] = index
        record["mode"] = mode
        record["skipped"] = False
        if record["title_actual"] != spec.title:
            record["error"] = f"title mismatch: {record['title_actual']!r}"
            results.append(record)
            print(f"[{index:02}] ERROR title mismatch {spec.page_id}: {record['title_actual']!r}")
            continue
        if before.get("parentId") == spec.target_id:
            record["skipped"] = True
            record["move_status"] = "already-at-target"
            print(f"[{index:02}] SKIP already at target: {spec.title}")
        elif args.write:
            status, payload = client.move_append(spec.page_id, spec.target_id)
            record["move_status_code"] = status
            record["move_response"] = payload
            print(f"[{index:02}] MOVE {status}: {spec.title} -> {spec.target_path}")
            if status not in (200, 202, 204):
                results.append(record)
                continue
            time.sleep(0.7)
        else:
            print(
                f"[{index:02}] DRY {spec.title}: parent {before.get('parentId')} "
                f"-> {spec.target_id} ({record['target_title']})"
            )

        after = client.get_page(spec.page_id)
        record["after_parent_id"] = after.get("parentId")
        record["after_parent_type"] = after.get("parentType")
        record["after_url"] = web_url(after)
        record["verified"] = after.get("parentId") == spec.target_id
        results.append(record)

    summary = {
        "mode": mode,
        "write": bool(args.write),
        "total": len(results),
        "verified_count": sum(1 for r in results if r.get("verified")),
        "skipped_count": sum(1 for r in results if r.get("skipped")),
        "error_count": sum(1 for r in results if r.get("error") or (r.get("move_status_code") not in (None, 200, 202, 204))),
        "results": results,
    }
    Path(args.out).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("saved", args.out)
    print(
        "summary",
        json.dumps({k: summary[k] for k in ["mode", "total", "verified_count", "skipped_count", "error_count"]}, ensure_ascii=False),
    )


if __name__ == "__main__":
    main()
