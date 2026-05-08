"""Stage C — render hydrated JSON into a tree of Markdown files.

Inputs:
    <hydrated>/pages/<id>.json         hydrated page (page meta + nested blocks)
    <hydrated>/data_sources/<id>.json  data source schema + row index
    <assets>/_index.json (optional)    asset_id → local path map

Output layout (relative to --out):
    <Title-of-Root-Page>.md
    <Title-of-Root-Page>/
        <Sub-Page>.md
        <Sub-Page>/...
        <DB-Title>.md                    # data_source index page
        <DB-Title>/
            <row1-title>.md
            ...

Two-pass: first pass builds id→path map, second pass renders MD with rewritten
internal links and local asset paths.

Block coverage (best-effort): paragraph, heading_1/2/3, bulleted_list_item,
numbered_list_item, to_do, toggle, quote, callout, code, divider, child_page,
child_database, image, file, video, audio, pdf, bookmark, embed, equation,
table+table_row, column_list+column, synced_block, breadcrumb, table_of_contents,
link_preview, link_to_page. Unsupported types emit a `<!-- unsupported -->` marker.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path


# ───────────────────────── helpers ─────────────────────────

INVALID_FNAME = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def _sanitize(name: str, *, max_len: int = 100) -> str:
    name = INVALID_FNAME.sub("-", (name or "").strip()) or "untitled"
    name = re.sub(r"\s+", " ", name)
    name = name.replace("/", "-").strip(". ")
    if len(name) > max_len:
        name = name[:max_len].rstrip()
    return name or "untitled"


def _norm(uid: str) -> str:
    s = (uid or "").replace("-", "")
    if len(s) != 32:
        return uid or ""
    return f"{s[0:8]}-{s[8:12]}-{s[12:16]}-{s[16:20]}-{s[20:32]}"


def _load(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _title_of_page(page: dict) -> str:
    meta_title = (page.get("_meta") or {}).get("title")
    if meta_title:
        return meta_title
    for v in (page.get("properties") or {}).values():
        if v.get("type") == "title":
            parts = v.get("title") or []
            return "".join(p.get("plain_text", "") for p in parts) or "(untitled)"
    return "(untitled)"


def _title_of_ds(ds: dict) -> str:
    meta_title = (ds.get("_meta") or {}).get("title")
    if meta_title:
        return meta_title
    parts = ds.get("title") or []
    return "".join(p.get("plain_text", "") for p in parts) or "(untitled db)"


# ───────────────────────── rich text → MD ─────────────────────────


def _rich_text(rt: list[dict] | None) -> str:
    if not rt:
        return ""
    out: list[str] = []
    for r in rt:
        text = r.get("plain_text", "")
        ann = r.get("annotations") or {}
        if not text:
            continue
        # escape pipes for tables; otherwise leave literal
        if ann.get("code"):
            text = f"`{text}`"
        if ann.get("bold"):
            text = f"**{text}**"
        if ann.get("italic"):
            text = f"*{text}*"
        if ann.get("strikethrough"):
            text = f"~~{text}~~"
        if ann.get("underline"):
            text = f"<u>{text}</u>"
        href = r.get("href")
        if href:
            text = f"[{text}]({href})"
        out.append(text)
    return "".join(out)


# ───────────────────────── renderer ─────────────────────────


class Renderer:
    def __init__(
        self,
        hydrated: Path,
        out: Path,
        assets_index: dict | None = None,
        dump: Path | None = None,
        *,
        verbose: bool = True,
    ):
        self.hyd = hydrated
        self.out = out
        self.dump = dump  # raw dump dir, optional — used to resolve database→page parent edges
        self.verbose = verbose
        self.assets_index = assets_index or {}
        # asset_id → relative path (from hydrated assets/_index.json)
        self.asset_path: dict[str, str] = {}
        for aid, info in self.assets_index.items():
            if info.get("status") == "ok" and info.get("path"):
                self.asset_path[aid] = info["path"]
        self.id2path: dict[str, str] = {}    # uuid (no dashes) → repo-relative MD path
        self.id2title: dict[str, str] = {}
        # database_id → parent_id and block_id → parent_id maps. Bridge tiers so
        # data_sources / pages whose parent chain passes through invisible
        # database / block containers still resolve to the real page hierarchy.
        self.db_parent: dict[str, str | None] = {}
        self.block_parent: dict[str, str | None] = {}
        if self.dump:
            db_dir = self.dump / "databases"
            if db_dir.exists():
                for p in db_dir.iterdir():
                    if p.suffix != ".json": continue
                    obj = _load(p) or {}
                    did = _norm(obj.get("id") or p.stem)
                    self.db_parent[did] = _parent_id(obj.get("parent"))
            block_dir = self.dump / "blocks"
            if block_dir.exists():
                for p in block_dir.iterdir():
                    if p.suffix != ".json": continue
                    bf = _load(p) or {}
                    for blk in bf.get("results", []) or []:
                        bid = _norm(blk.get("id") or "")
                        if not bid: continue
                        self.block_parent[bid] = _parent_id(blk.get("parent"))
        self.errors: list[dict] = []
        self.counts = {"pages_rendered": 0, "data_sources_rendered": 0, "errors": 0}

    def log(self, *a):
        if self.verbose:
            print(*a, flush=True)

    # ── pass 1: build id→path map ──

    def build_paths(self) -> None:
        page_dir = self.hyd / "pages"
        ds_dir = self.hyd / "data_sources"

        # collect titles + parent edges
        nodes: dict[str, dict] = {}  # id_norm → {"kind","title","parent"}
        if page_dir.exists():
            for p in page_dir.iterdir():
                if p.suffix != ".json": continue
                obj = _load(p) or {}
                pid = _norm(obj.get("id") or p.stem)
                nodes[pid] = {
                    "kind": "page",
                    "title": _title_of_page(obj),
                    "parent": _parent_id(obj.get("parent")),
                }
        if ds_dir.exists():
            for p in ds_dir.iterdir():
                if p.suffix != ".json": continue
                obj = _load(p) or {}
                did = _norm(obj.get("id") or p.stem)
                nodes[did] = {
                    "kind": "data_source",
                    "title": _title_of_ds(obj),
                    "parent": _parent_id(obj.get("parent")),
                }

        # rows of a data_source go under its folder
        # — for each ds, attach each row id as child of ds
        if ds_dir.exists():
            for p in ds_dir.iterdir():
                if p.suffix != ".json": continue
                obj = _load(p) or {}
                did = _norm(obj.get("id") or p.stem)
                for row in obj.get("rows") or []:
                    rid = _norm(row.get("id") or "")
                    if rid and rid in nodes:
                        nodes[rid]["parent"] = did

        # Bridge: a parent may be a database_id (Notion invisible container) or
        # a block_id (child_page/child_database block). Walk up until we hit a
        # known node (page or data_source). Cap depth to avoid pathological loops.
        def resolve_parent(par_id: str | None, _seen: set | None = None) -> str | None:
            if par_id is None: return None
            if _seen is None: _seen = set()
            if par_id in _seen: return None
            _seen.add(par_id)
            if par_id in nodes:
                return par_id
            if par_id in self.db_parent:
                return resolve_parent(self.db_parent[par_id], _seen)
            if par_id in self.block_parent:
                return resolve_parent(self.block_parent[par_id], _seen)
            return None  # workspace / unknown

        for nid, n in nodes.items():
            par = n.get("parent")
            if par and par not in nodes:
                resolved = resolve_parent(par)
                if resolved:
                    n["parent"] = resolved

        # compute path by walking up from each node to root
        def path_for(nid: str, _seen: set | None = None) -> str:
            if _seen is None:
                _seen = set()
            if nid in self.id2path:
                return self.id2path[nid]
            if nid in _seen:
                return _sanitize(nodes[nid]["title"]) + ".md"
            _seen.add(nid)
            n = nodes.get(nid)
            if not n:
                return _sanitize(nid) + ".md"
            title = _sanitize(n["title"])
            parent = n.get("parent")
            if parent and parent in nodes:
                parent_path = path_for(parent, _seen)
                folder = parent_path[:-3] if parent_path.endswith(".md") else parent_path
                rel = f"{folder}/{title}.md"
            else:
                rel = f"{title}.md"
            self.id2path[nid] = rel
            self.id2title[nid] = n["title"]
            return rel

        for nid in nodes:
            path_for(nid)

    # ── pass 2: render ──

    def render_all(self) -> None:
        self.build_paths()
        page_dir = self.hyd / "pages"
        ds_dir = self.hyd / "data_sources"
        if page_dir.exists():
            for p in page_dir.iterdir():
                if p.suffix == ".json":
                    self._render_page_file(p)
        if ds_dir.exists():
            for p in ds_dir.iterdir():
                if p.suffix == ".json":
                    self._render_ds_file(p)

    def _render_page_file(self, json_path: Path) -> None:
        page = _load(json_path) or {}
        pid = _norm(page.get("id") or json_path.stem)
        rel = self.id2path.get(pid)
        if not rel:
            self.counts["errors"] += 1
            return
        try:
            md = self._render_page(page)
        except Exception as e:
            self.errors.append({"id": pid, "msg": str(e)})
            self.counts["errors"] += 1
            return
        _save_text(self.out / rel, md)
        self.counts["pages_rendered"] += 1

    def _render_ds_file(self, json_path: Path) -> None:
        ds = _load(json_path) or {}
        did = _norm(ds.get("id") or json_path.stem)
        rel = self.id2path.get(did)
        if not rel:
            self.counts["errors"] += 1
            return
        try:
            md = self._render_data_source(ds)
        except Exception as e:
            self.errors.append({"id": did, "msg": str(e)})
            self.counts["errors"] += 1
            return
        _save_text(self.out / rel, md)
        self.counts["data_sources_rendered"] += 1

    def _frontmatter(self, obj: dict, kind: str) -> str:
        meta = {
            "id": obj.get("id"),
            "kind": kind,
            "title": _title_of_page(obj) if kind == "page" else _title_of_ds(obj),
            "url": obj.get("url"),
            "last_edited_time": obj.get("last_edited_time"),
            "created_time": obj.get("created_time"),
        }
        lines = ["---"]
        for k, v in meta.items():
            if v is None:
                continue
            v = str(v).replace('"', '\\"')
            lines.append(f'{k}: "{v}"')
        lines.append("---\n")
        return "\n".join(lines)

    def _render_page(self, page: dict) -> str:
        title = _title_of_page(page)
        body = self._render_blocks(page.get("blocks") or [], indent=0)
        return self._frontmatter(page, "page") + f"# {title}\n\n" + body.rstrip() + "\n"

    def _render_data_source(self, ds: dict) -> str:
        title = _title_of_ds(ds)
        rows = ds.get("rows") or []
        out: list[str] = [self._frontmatter(ds, "data_source"), f"# {title}\n"]
        desc = ds.get("description")
        if desc:
            out.append(_rich_text(desc) + "\n")
        out.append(f"_{len(rows)} rows_\n")
        # simple table: title + last_edited_time
        out.append("| Title | Last edited |")
        out.append("|---|---|")
        ds_id_norm = _norm(ds.get("id") or "")
        for row in rows:
            rid = _norm(row.get("id") or "")
            row_path = self.id2path.get(rid)
            link_title = (row.get("title") or "(untitled)").replace("|", "\\|")
            if row_path:
                rel_link = self._relative_link(ds_id_norm, rid)
                link = f"[{link_title}]({rel_link})"
            else:
                link = link_title
            out.append(f"| {link} | {row.get('last_edited_time') or ''} |")
        return "\n".join(out) + "\n"

    # ── block dispatch ──

    def _render_blocks(self, blocks: list[dict], *, indent: int) -> str:
        out: list[str] = []
        prev_type: str | None = None
        for blk in blocks:
            t = blk.get("type")
            md = self._render_block(blk, indent=indent)
            if md is None:
                continue
            # blank line between type changes (but list items stay together)
            list_types = {"bulleted_list_item", "numbered_list_item", "to_do"}
            if prev_type and prev_type != t and not (prev_type in list_types and t in list_types):
                out.append("")
            out.append(md)
            prev_type = t
        return "\n".join(out) + ("\n" if out else "")

    def _render_block(self, blk: dict, *, indent: int) -> str | None:
        t = blk.get("type")
        pad = "  " * indent
        rt = lambda key: _rich_text((blk.get(t) or {}).get(key) or [])

        if t == "paragraph":
            txt = rt("rich_text")
            inner = self._render_blocks(blk.get("children") or [], indent=indent)
            return (pad + txt) + (("\n" + inner) if inner else "")
        if t in ("heading_1", "heading_2", "heading_3"):
            level = {"heading_1": "#", "heading_2": "##", "heading_3": "###"}[t]
            return f"{pad}{level} {rt('rich_text')}"
        if t == "bulleted_list_item":
            inner = self._render_blocks(blk.get("children") or [], indent=indent + 1)
            return f"{pad}- {rt('rich_text')}" + (("\n" + inner) if inner else "")
        if t == "numbered_list_item":
            inner = self._render_blocks(blk.get("children") or [], indent=indent + 1)
            return f"{pad}1. {rt('rich_text')}" + (("\n" + inner) if inner else "")
        if t == "to_do":
            check = "[x]" if (blk.get(t) or {}).get("checked") else "[ ]"
            inner = self._render_blocks(blk.get("children") or [], indent=indent + 1)
            return f"{pad}- {check} {rt('rich_text')}" + (("\n" + inner) if inner else "")
        if t == "toggle":
            inner = self._render_blocks(blk.get("children") or [], indent=indent + 1)
            return f"{pad}<details><summary>{rt('rich_text')}</summary>\n\n{inner}\n{pad}</details>"
        if t == "quote":
            inner = self._render_blocks(blk.get("children") or [], indent=indent)
            return f"{pad}> {rt('rich_text')}" + (("\n" + inner) if inner else "")
        if t == "callout":
            payload = blk.get(t) or {}
            icon = payload.get("icon") or {}
            emoji = icon.get("emoji", "💡") if isinstance(icon, dict) else "💡"
            inner = self._render_blocks(blk.get("children") or [], indent=indent)
            return f"{pad}> {emoji} {rt('rich_text')}" + (("\n" + inner) if inner else "")
        if t == "code":
            lang = (blk.get(t) or {}).get("language", "")
            return f"{pad}```{lang}\n{rt('rich_text')}\n{pad}```"
        if t == "divider":
            return f"{pad}---"
        if t == "equation":
            expr = (blk.get(t) or {}).get("expression", "")
            return f"{pad}$$\n{expr}\n$$"
        if t == "child_page":
            child_id = _norm(blk.get("id") or "")
            title = (blk.get(t) or {}).get("title") or self.id2title.get(child_id, "(child page)")
            link = self._relative_link_from_block(child_id, blk)
            return f"{pad}- 📄 [{title}]({link})" if link else f"{pad}- 📄 {title}"
        if t == "child_database":
            child_id = _norm(blk.get("id") or "")
            title = (blk.get(t) or {}).get("title") or self.id2title.get(child_id, "(database)")
            link = self._relative_link_from_block(child_id, blk)
            return f"{pad}- 🗃️ [{title}]({link})" if link else f"{pad}- 🗃️ {title}"
        if t in ("image", "file", "video", "audio", "pdf"):
            return self._render_media(blk, pad)
        if t == "bookmark":
            url = (blk.get(t) or {}).get("url", "")
            cap = rt("caption") or url
            return f"{pad}🔖 [{cap}]({url})"
        if t == "embed":
            url = (blk.get(t) or {}).get("url", "")
            return f"{pad}<iframe src=\"{url}\"></iframe>"
        if t == "table":
            return self._render_table(blk, pad)
        if t == "column_list":
            return self._render_blocks(blk.get("children") or [], indent=indent)
        if t == "column":
            return self._render_blocks(blk.get("children") or [], indent=indent)
        if t == "synced_block":
            return self._render_blocks(blk.get("children") or [], indent=indent)
        if t == "breadcrumb":
            return f"{pad}*[breadcrumb]*"
        if t == "table_of_contents":
            return f"{pad}*[table of contents]*"
        if t == "link_preview":
            url = (blk.get(t) or {}).get("url", "")
            return f"{pad}[{url}]({url})"
        if t == "link_to_page":
            ref = blk.get(t) or {}
            target = ref.get("page_id") or ref.get("database_id") or ref.get("data_source_id")
            if target:
                target_n = _norm(target)
                title = self.id2title.get(target_n, "(linked)")
                rel = self._relative_link(_parent_block_owner(blk), target_n)
                return f"{pad}→ [{title}]({rel})"
            return f"{pad}*[link]*"
        if t == "unsupported":
            return f"{pad}<!-- unsupported block (Notion side) -->"
        # Fallback for any other type
        return f"{pad}<!-- unsupported: type={t} -->"

    def _render_media(self, blk: dict, pad: str) -> str:
        t = blk.get("type")
        payload = blk.get(t) or {}
        url = ""
        kind = "external"
        if "file" in payload and (payload["file"] or {}).get("url"):
            url = payload["file"]["url"]
            kind = "file"
        elif "external" in payload and (payload["external"] or {}).get("url"):
            url = payload["external"]["url"]
        # rewrite to local asset if available
        if kind == "file":
            local = self._asset_for_url(url)
            if local:
                url = local
        cap = _rich_text(payload.get("caption") or [])
        if t == "image":
            return f"{pad}![{cap}]({url})"
        return f"{pad}[{cap or t}]({url})"

    def _render_table(self, blk: dict, pad: str) -> str:
        rows = blk.get("children") or []
        if not rows:
            return f"{pad}<!-- empty table -->"
        out: list[str] = []
        header = ["" for _ in range(len(((rows[0].get("table_row") or {}).get("cells") or [[]])))]
        for i, row in enumerate(rows):
            cells = ((row.get("table_row") or {}).get("cells")) or []
            line = "| " + " | ".join(_rich_text(c).replace("|", "\\|") for c in cells) + " |"
            out.append(pad + line)
            if i == 0:
                out.append(pad + "|" + "|".join("---" for _ in cells) + "|")
        return "\n".join(out)

    def _asset_for_url(self, url: str) -> str | None:
        # The first UUID in a Notion S3 path is workspace_id; the per-file
        # id is the LAST UUID in the path. Strip query string first.
        from urllib.parse import urlparse as _u
        path = _u(url or "").path
        uuids = re.findall(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", path)
        if not uuids:
            return None
        return self.asset_path.get(uuids[-1])

    def _relative_link(self, from_id: str, to_id: str) -> str:
        from_path = self.id2path.get(_norm(from_id))
        to_path = self.id2path.get(_norm(to_id))
        if not to_path:
            return f"#missing-{to_id}"
        if not from_path:
            return to_path
        from_p = Path(from_path)
        to_p = Path(to_path)
        try:
            rel = Path(*self._rel_parts(from_p, to_p))
            return rel.as_posix()
        except Exception:
            return to_path

    @staticmethod
    def _rel_parts(from_p: Path, to_p: Path) -> list[str]:
        # compute relative path from from_p (file) to to_p (file)
        from_dir = list(from_p.parent.parts)
        to_parts = list(to_p.parts)
        common = 0
        for a, b in zip(from_dir, to_parts):
            if a == b:
                common += 1
            else:
                break
        ups = [".."] * (len(from_dir) - common)
        return ups + to_parts[common:]

    def _relative_link_from_block(self, child_id: str, blk: dict) -> str | None:
        # Best effort: assume the parent owner is tracked in id2path; we don't have it here.
        # The renderer level (page) will look right because Notion blocks live within a page,
        # which we do know via the file we are rendering (not threaded here). For now use absolute-from-root.
        to_path = self.id2path.get(_norm(child_id))
        return to_path  # treat as path from out root


def _parent_id(parent: dict | None) -> str | None:
    if not parent:
        return None
    for k in ("page_id", "database_id", "data_source_id", "block_id"):
        v = parent.get(k)
        if v:
            return _norm(v)
    return None


def _parent_block_owner(blk: dict) -> str:
    return _norm(blk.get("id") or "")


def _main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Stage C — render hydrated JSON to MD tree")
    p.add_argument("--hydrated", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--assets", default=None, help="optional: assets dir (uses _index.json for url rewrite)")
    p.add_argument("--dump", default=None, help="optional: raw dump dir (resolves database→page parent edges)")
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args(argv)

    assets_index = None
    if args.assets:
        idx_path = Path(args.assets) / "_index.json"
        if idx_path.exists():
            assets_index = json.loads(idx_path.read_text(encoding="utf-8"))

    r = Renderer(
        Path(args.hydrated),
        Path(args.out),
        assets_index=assets_index,
        dump=Path(args.dump) if args.dump else None,
        verbose=not args.quiet,
    )
    t0 = time.time()
    r.render_all()
    print(f"=== render done in {time.time()-t0:.1f}s ===")
    print(f"  out      {args.out}")
    print(f"  counts   {r.counts}")
    print(f"  errors   {len(r.errors)}")
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
