#!/usr/bin/env python3
"""Retry blocked recommended-report web enrichment targets with playwright-cli."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dof_prospect_outline_publish as publish  # noqa: E402
import dof_recommended_report_web_enrich as enrich  # noqa: E402


BASE = publish.BASE
OUT_DIR = publish.PUBLISH_ROOT / "recommended_report_web_enrichment_260605"
RESEARCH_JSONL = OUT_DIR / "recommended_report_web_research.jsonl"
BROWSER_RETRY_JSON = OUT_DIR / "browser_retry_results.json"
BROWSER_RETRY_SUMMARY = OUT_DIR / "browser_retry_summary.json"
RESULT_JSON = BASE / "recommended_overseas_dental_distributors_260604_result.json"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def save_json(path: Path, data: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def needs_retry(row: dict[str, Any]) -> bool:
    website_status = str(row.get("website_status") or "")
    source_status = str(row.get("source_status") or "")
    return not website_status.startswith("200") or not source_status.startswith("200") or row.get("confidence") == "낮음"


def js_code(targets: list[dict[str, Any]]) -> str:
    target_json = json.dumps(targets, ensure_ascii=False)
    return f"""
async page => {{
  const targets = {target_json};
  const brandPatterns = [
    ["DOF", /\\bDOF\\b|freedom\\s*hd|craft\\s*5x|edge\\s*e/i],
    ["Medit", /\\bMedit\\b|i700|i900/i],
    ["Shining3D\\/Aoralscan", /Shining\\s*3D|Aoralscan/i],
    ["3Shape\\/TRIOS", /3Shape|TRIOS/i],
    ["exocad", /exocad|DentalCAD/i],
    ["vhf", /\\bvhf\\b|R5\\b|E5\\b|K5\\b|N4\\+?/i],
    ["DGSHAPE\\/Roland", /DGSHAPE|Roland/i],
    ["imes-icore", /imes[- ]?icore/i],
    ["Amann Girrbach\\/Ceramill", /Amann\\s*Girrbach|Ceramill/i],
    ["Zirkonzahn", /Zirkonzahn/i],
    ["Ivoclar", /Ivoclar|Vivadent/i],
    ["GC Dental", /\\bGC\\s*Dental\\b|GC\\s+Europe|GC\\s+Orthodontics/i],
    ["DETAX", /\\bDETAX\\b/i],
    ["Bredent", /\\bbredent\\b/i],
    ["Dentsply Sirona", /Dentsply|Sirona|CEREC|Primescan/i],
    ["Planmeca", /Planmeca|Emerald/i],
    ["Carestream", /Carestream|CS\\s*3\\d{{3}}/i],
    ["iTero", /iTero|Align\\s+Technology/i],
    ["Milling\\/CAD-CAM", /CAD\\s*\\/?\\s*CAM|milling|fresadora|fresage|Fräs|zirconia|zirkon/i],
    ["Intraoral scanner", /intraoral\\s+scanner|scanner\\s+intraoral|escaner\\s+intraoral|escáner\\s+intraoral|scanner intraorale|口腔扫描|口腔スキャ/i]
  ];
  function compact(text, limit = 220) {{
    text = String(text || "").replace(/\\s+/g, " ").trim();
    return text.length > limit ? text.slice(0, limit - 1).trimEnd() + "…" : text;
  }}
  function statusLabel(status, finalUrl, originalUrl) {{
    if (!status) return "browser unknown";
    let label = status < 400 ? `${{status}} OK (browser)` : `${{status}} (browser)`;
    if (status === 403) label += " blocked";
    if (status === 404) label += " not found";
    try {{
      const f = new URL(finalUrl || "").hostname.replace(/^www\\./, "");
      const o = new URL(originalUrl || "").hostname.replace(/^www\\./, "");
      if (f && o && f !== o) label += ` -> ${{f}}`;
    }} catch {{}}
    return label;
  }}
  function detectBrands(text) {{
    const found = [];
    for (const [label, rx] of brandPatterns) if (rx.test(text) && !found.includes(label)) found.push(label);
    return found.slice(0, 7);
  }}
  function recentSnippets(text) {{
    const out = [];
    const rx = /\\b(2026|2025|2024)\\b/g;
    let m;
    while ((m = rx.exec(text)) && out.length < 2) {{
      const start = Math.max(0, m.index - 55);
      const end = Math.min(text.length, m.index + 95);
      const snip = compact(text.slice(start, end), 170);
      if (snip && !out.includes(snip)) out.push(snip);
    }}
    return out;
  }}
  function socials(text, links) {{
    const combined = `${{text}} ${{links.map(l => l.href).join(" ")}}`;
    const out = [];
    for (const [label, rx] of [["LinkedIn", /linkedin\\.com/i], ["Facebook", /facebook\\.com/i], ["Instagram", /instagram\\.com/i], ["YouTube", /youtube\\.com/i], ["X/Twitter", /(x\\.com|twitter\\.com)/i]]) {{
      if (rx.test(combined)) out.push(label);
    }}
    return out.slice(0, 4);
  }}
  function extraLinks(currentUrl, links) {{
    const hints = /(news|blog|press|media|event|events|expo|ids|aeedc|webinar|seminar|brand|product|cad|cam|scanner|milling)/i;
    const out = [];
    let baseHost = "";
    try {{ baseHost = new URL(currentUrl).hostname.replace(/^www\\./, ""); }} catch {{}}
    for (const link of links) {{
      if (!hints.test(`${{link.href}} ${{link.text}}`)) continue;
      let host = "";
      try {{ host = new URL(link.href).hostname.replace(/^www\\./, ""); }} catch {{ continue; }}
      if (baseHost && host !== baseHost) continue;
      if (!out.find(x => x.url === link.href)) out.push({{url: link.href, title: compact(link.text || link.href, 90), status: "browser discovered"}});
      if (out.length >= 2) break;
    }}
    return out;
  }}
  async function checkUrl(context, url) {{
    if (!url) return {{url: "", ok: false, status: null, status_label: "no link", final_url: "", title: "", text: "", brands: [], recent: [], social: [], extra_pages: []}};
    const p = await context.newPage();
    await p.setViewportSize({{ width: 1365, height: 900 }});
    let response = null;
    try {{
      response = await p.goto(url, {{ waitUntil: "domcontentloaded", timeout: 18000 }});
      await p.waitForTimeout(1400);
    }} catch (err) {{
      try {{ await p.waitForTimeout(1000); }} catch {{}}
      const finalUrl = p.url();
      const title = await p.title().catch(() => "");
      const text = await p.locator("body").innerText({{ timeout: 1500 }}).catch(() => "");
      const links = await p.evaluate(() => Array.from(document.querySelectorAll("a[href]")).slice(0, 160).map(a => ({{href: a.href, text: (a.textContent || "").trim().slice(0, 100)}}))).catch(() => []);
      await p.close().catch(() => {{}});
      const meaningful = title || text.length > 80;
      const brands = detectBrands(`${{title}} ${{text}}`);
      return {{
        url, ok: meaningful, status: response ? response.status() : null,
        status_label: meaningful ? "browser rendered after navigation error" : "browser error",
        final_url: finalUrl, title: compact(title, 160), text: compact(text, 4500),
        brands, recent: recentSnippets(text), social: socials(text, links), extra_pages: extraLinks(finalUrl, links),
        error: String(err).slice(0, 220)
      }};
    }}
    const status = response ? response.status() : null;
    const finalUrl = p.url();
    const title = await p.title().catch(() => "");
    const text = await p.locator("body").innerText({{ timeout: 4000 }}).catch(() => "");
    const links = await p.evaluate(() => Array.from(document.querySelectorAll("a[href]")).slice(0, 220).map(a => ({{href: a.href, text: (a.textContent || "").trim().slice(0, 100)}}))).catch(() => []);
    await p.close().catch(() => {{}});
    const brands = detectBrands(`${{title}} ${{text}}`);
    return {{
      url, ok: !!(status && status < 400) || text.length > 80, status,
      status_label: statusLabel(status, finalUrl, url),
      final_url: finalUrl, title: compact(title, 160), text: compact(text, 4500),
      brands, recent: recentSnippets(text), social: socials(text, links), extra_pages: extraLinks(finalUrl, links)
    }};
  }}
  async function worker(queue, results, context) {{
    while (queue.length) {{
      const target = queue.shift();
      const website = await checkUrl(context, target.website);
      const source = target.source_url ? await checkUrl(context, target.source_url) : {{status_label: "no link", ok: false}};
      results.push({{...target, website_browser: website, source_browser: source}});
    }}
  }}
  const context = page.context();
  const queue = [...targets];
  const results = [];
  await Promise.all(Array.from({{length: Math.min(4, queue.length)}}, () => worker(queue, results, context)));
  results.sort((a, b) => a.index - b.index);
  return {{checked: results.length, results}};
}}
"""


def run_playwright(targets: list[dict[str, Any]], timeout: int) -> dict[str, Any]:
    code = js_code(targets)
    proc = subprocess.run(
        ["playwright-cli", "--raw", "run-code", code],
        cwd=publish.ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"playwright-cli failed {proc.returncode}: {proc.stderr[:1000]} {proc.stdout[:1000]}")
    stdout = proc.stdout.strip()
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"playwright-cli returned non-json: {stdout[:1000]}") from exc


def merge_browser_result(row: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    row = dict(row)
    web = result.get("website_browser") or {}
    source = result.get("source_browser") or {}
    changed = False
    if web.get("ok"):
        row["website_status"] = web.get("status_label") or row.get("website_status")
        row["website_final_url"] = web.get("final_url") or row.get("website_final_url")
        row["website_title"] = web.get("title") or row.get("website_title")
        changed = True
    if source.get("ok"):
        row["source_status"] = source.get("status_label") or row.get("source_status")
        row["source_final_url"] = source.get("final_url") or row.get("source_final_url")
        changed = True
    brands = list(dict.fromkeys((row.get("brands") or []) + (web.get("brands") or []) + (source.get("brands") or [])))[:7]
    recent = list(dict.fromkeys((row.get("recent_snippets") or []) + (web.get("recent") or []) + (source.get("recent") or [])))[:2]
    social = list(dict.fromkeys((row.get("social") or []) + (web.get("social") or []) + (source.get("social") or [])))[:4]
    extra_pages = (row.get("extra_pages") or []) + (web.get("extra_pages") or []) + (source.get("extra_pages") or [])
    if brands != (row.get("brands") or []) or recent != (row.get("recent_snippets") or []) or social != (row.get("social") or []) or extra_pages != (row.get("extra_pages") or []):
        changed = True
    row["brands"] = brands
    row["recent_snippets"] = recent
    row["social"] = social
    row["extra_pages"] = extra_pages[:2]
    if (str(row.get("website_status") or "").startswith(("200", "browser")) or web.get("ok")) and brands:
        row["confidence"] = "높음"
    elif web.get("ok") or source.get("ok") or brands or row.get("search_results"):
        row["confidence"] = "중간"
    else:
        row["confidence"] = "낮음"
    row["browser_retry"] = {
        "checked_at": datetime.now().isoformat(timespec="seconds"),
        "changed": changed,
        "website_status": web.get("status_label"),
        "source_status": source.get("status_label"),
        "website_title": web.get("title"),
        "website_error": web.get("error"),
        "source_error": source.get("error"),
    }
    return row


def rerender_and_publish(research_rows: list[dict[str, Any]]) -> dict[str, Any]:
    markdown = enrich.REPORT_MD.read_text(encoding="utf-8")
    prefix, report_rows, suffix = enrich.load_report_rows(markdown)
    research_by_index = {int(row["index"]): row for row in research_rows}
    next_text = enrich.render_report(prefix, report_rows, suffix, research_by_index)
    enrich.REPORT_MD.write_text(next_text, encoding="utf-8")
    client = publish.OutlineClient(publish.read_env_key("DOF_OUTLINE_KEY"))
    updated = client.update_document(enrich.DOC_ID, enrich.DOC_TITLE, next_text)
    check = client.document_info(enrich.DOC_ID)
    check_text = check.get("text") or ""
    return {
        "outline_url_returned": f"https://outline.doflab.com/doc/{updated.get('urlId') or check.get('urlId')}",
        "row_count": sum(1 for line in check_text.splitlines() if line.startswith("| A-") or line.startswith("| B-") or line.startswith("| C-")),
        "has_new_columns": all(col in check_text for col in enrich.NEW_COLS),
        "text_len": len(check_text),
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    research_rows = read_jsonl(RESEARCH_JSONL)
    targets = [
        {
            "index": int(row["index"]),
            "company": row.get("company"),
            "website": row.get("website"),
            "source_url": row.get("source_url"),
            "website_status": row.get("website_status"),
            "source_status": row.get("source_status"),
            "confidence": row.get("confidence"),
        }
        for row in research_rows
        if needs_retry(row)
    ]
    if args.limit:
        targets = targets[: args.limit]
    browser_result = run_playwright(targets, args.timeout) if targets else {"checked": 0, "results": []}
    save_json(BROWSER_RETRY_JSON, browser_result)
    result_by_index = {int(row["index"]): row for row in browser_result.get("results", [])}
    merged_rows = [merge_browser_result(row, result_by_index[int(row["index"])]) if int(row["index"]) in result_by_index else row for row in research_rows]
    write_jsonl(RESEARCH_JSONL, merged_rows)
    publish_result = rerender_and_publish(merged_rows)
    trust_counts = Counter(row.get("confidence") for row in merged_rows)
    website_status_counts = Counter(str(row.get("website_status") or "").split()[0] for row in merged_rows)
    source_status_counts = Counter(str(row.get("source_status") or "").split()[0] for row in merged_rows)
    changed = sum(1 for row in merged_rows if (row.get("browser_retry") or {}).get("changed"))
    fixed_web = sum(
        1
        for row in merged_rows
        if row.get("browser_retry") and str(row.get("website_status") or "").startswith(("200", "browser"))
    )
    fixed_source = sum(
        1
        for row in merged_rows
        if row.get("browser_retry") and str(row.get("source_status") or "").startswith(("200", "browser"))
    )
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "targets": len(targets),
        "checked": browser_result.get("checked", 0),
        "changed_rows": changed,
        "fixed_or_rendered_websites": fixed_web,
        "fixed_or_rendered_sources": fixed_source,
        "trust_counts_after": dict(trust_counts),
        "website_status_counts_after": dict(website_status_counts),
        "source_status_counts_after": dict(source_status_counts),
        "with_brands_after": sum(1 for row in merged_rows if row.get("brands")),
        "with_recent_or_social_or_media_after": sum(
            1 for row in merged_rows if row.get("recent_snippets") or row.get("social") or row.get("media_results")
        ),
        "browser_retry_json": str(BROWSER_RETRY_JSON),
        "research_jsonl": str(RESEARCH_JSONL),
        "publish": publish_result,
    }
    save_json(BROWSER_RETRY_SUMMARY, summary)
    result_json = json.loads(RESULT_JSON.read_text(encoding="utf-8")) if RESULT_JSON.exists() else {}
    result_json["playwright_browser_retry"] = summary
    result_json["row_count"] = publish_result["row_count"]
    result_json["text_len"] = publish_result["text_len"]
    result_json["updated_at_epoch"] = int(time.time())
    enrich.save_json(RESULT_JSON, result_json)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int)
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()
    print(json.dumps(run(args), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
