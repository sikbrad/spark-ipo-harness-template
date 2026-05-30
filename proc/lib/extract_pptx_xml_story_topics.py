#!/usr/bin/env python3
"""Extract slide/notes text from PPTX packages using XML only.

This intentionally avoids python-pptx so image-heavy decks do not get fully
materialized in memory. It is an evidence-generation helper for the
vibecoding story-topic inventory.
"""

from __future__ import annotations

import json
import multiprocessing as mp
import re
import sys
import traceback
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


NS = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}


def safe_name(name: str) -> str:
    stem = name.rsplit(".", 1)[0]
    stem = re.sub(r"[^0-9A-Za-z가-힣._-]+", "-", stem).strip("-")
    stem = re.sub(r"-+", "-", stem)
    return (stem or "deck")[:120]


def text_runs(xml_bytes: bytes) -> list[str]:
    try:
        root = ET.fromstring(xml_bytes)
    except Exception:
        return []

    values: list[str] = []
    for node in root.findall(".//a:t", NS):
        if node.text:
            text = node.text.replace("\u000b", " ").strip()
            if text and (not values or values[-1] != text):
                values.append(text)
    return values


def extract_one(idx: int, source: str, output: str, queue: mp.Queue) -> None:
    path = Path(source)
    out_path = Path(output)
    try:
        with zipfile.ZipFile(path) as deck:
            names = set(deck.namelist())
            hidden = 0
            slide_order: list[str] = []

            try:
                presentation = ET.fromstring(deck.read("ppt/presentation.xml"))
                rels = ET.fromstring(deck.read("ppt/_rels/presentation.xml.rels"))
                rel_targets: dict[str, str] = {}
                for rel in rels.findall(".//rel:Relationship", NS):
                    rid = rel.attrib.get("Id")
                    target = rel.attrib.get("Target", "")
                    if rid and target.startswith("slides/"):
                        rel_targets[rid] = "ppt/" + target

                for slide in presentation.findall(".//p:sldId", NS):
                    rid = slide.attrib.get(f"{{{NS['r']}}}id")
                    target = rel_targets.get(rid or "")
                    if not target:
                        continue
                    if slide.attrib.get("show") == "0":
                        hidden += 1
                    else:
                        slide_order.append(target)
            except Exception:
                slide_order = sorted(
                    [
                        name
                        for name in names
                        if re.match(r"ppt/slides/slide\d+\.xml$", name)
                    ],
                    key=lambda name: int(re.search(r"(\d+)", name).group(1)),
                )

            lines: list[str] = [
                f"# {path.name}",
                "",
                f"- source: `{path}`",
                f"- active_slides: {len(slide_order)}",
                f"- hidden: {hidden}",
                "- extractor: pptx-xml-text-only",
                "",
            ]
            total_chars = 0
            for target in slide_order:
                match = re.search(r"slide(\d+)\.xml$", target)
                slide_number = int(match.group(1)) if match else len(lines)
                slide_text = text_runs(deck.read(target)) if target in names else []
                notes_name = f"ppt/notesSlides/notesSlide{slide_number}.xml"
                note_text = text_runs(deck.read(notes_name)) if notes_name in names else []

                lines.append(f"## Slide {slide_number}")
                lines.append("")
                if slide_text:
                    body = "\n".join(slide_text)
                    lines.append(body)
                    total_chars += len(body)
                else:
                    lines.append("(no extractable text)")
                if note_text:
                    notes_body = "\n".join(note_text)
                    lines.append("")
                    lines.append("[speaker notes]")
                    lines.append(notes_body)
                    total_chars += len(notes_body)
                lines.append("")

            out_path.write_text("\n".join(lines), encoding="utf-8")

        queue.put(
            {
                "ok": True,
                "idx": idx,
                "name": path.name,
                "source": str(path),
                "active": len(slide_order),
                "hidden": hidden,
                "chars": total_chars,
                "out": str(out_path),
            }
        )
    except Exception as exc:  # noqa: BLE001 - diagnostic artifact
        queue.put(
            {
                "ok": False,
                "idx": idx,
                "name": path.name,
                "source": str(path),
                "error": repr(exc),
                "trace": traceback.format_exc()[-1200:],
            }
        )


def main() -> int:
    base = Path("data/vibecoding-book/story-topics-2026-05-30")
    paths_file = base / "ppt-paths.all.txt"
    out_dir = base / "extracted-slides-xml"
    out_dir.mkdir(exist_ok=True)

    paths = [Path(line) for line in paths_file.read_text().splitlines() if line.strip()]
    records: list[dict[str, object]] = []
    candidates: list[Path] = []
    for path in paths:
        lower = str(path).lower()
        if "designprep/copy of en " in lower or "designprep/copy of elegant" in lower:
            records.append(
                {
                    "name": path.name,
                    "source": str(path),
                    "skipped": "generic_slidesgo_template",
                }
            )
        else:
            candidates.append(path)

    timeout_seconds = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    for idx, path in enumerate(candidates, 1):
        out_path = out_dir / f"{idx:03d}-{safe_name(path.name)}.md"
        queue: mp.Queue = mp.Queue()
        proc = mp.Process(target=extract_one, args=(idx, str(path), str(out_path), queue))
        proc.start()
        proc.join(timeout_seconds)

        if proc.is_alive():
            proc.terminate()
            proc.join(5)
            record = {
                "ok": False,
                "idx": idx,
                "name": path.name,
                "source": str(path),
                "error": f"timeout_{timeout_seconds}s_probably_cloud_hydration_or_huge_deck",
            }
            print(f"[{idx}/{len(candidates)}] TIMEOUT {path.name}", flush=True)
        else:
            record = (
                queue.get()
                if not queue.empty()
                else {
                    "ok": False,
                    "idx": idx,
                    "name": path.name,
                    "source": str(path),
                    "error": "no_result",
                }
            )
            if record.get("ok"):
                print(
                    f"[{idx}/{len(candidates)}] OK active={record['active']} "
                    f"hidden={record['hidden']} chars={record['chars']} {path.name}",
                    flush=True,
                )
            else:
                print(f"[{idx}/{len(candidates)}] ERR {path.name}: {record.get('error')}", flush=True)

        records.append(record)

    (base / "ppt-inventory-xml.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    lines = ["# PPT XML extraction inventory", ""]
    for record in records:
        if record.get("skipped"):
            lines.append(f"- SKIP `{record['name']}`: {record['skipped']}")
        elif record.get("ok"):
            lines.append(
                f"- OK `{record['name']}`: active={record.get('active')}, "
                f"hidden={record.get('hidden')}, chars={record.get('chars')}, "
                f"out=`{record.get('out')}`"
            )
        else:
            lines.append(f"- ERR `{record.get('name')}`: {record.get('error')}")
    (base / "ppt-inventory-xml.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"DONE records={len(records)} outdir={out_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
