from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


DEFAULT_PATTERNS = [
    r"DOF",
    r"디오에프",
    r"KUBIT",
    r"WhyQ",
    r"PKNU",
    r"KU",
    r"고려대",
    r"부경",
    r"백인식",
    r"박현수",
    r"gmail",
    r"bispro",
    r"doflab",
    r"atlassian",
    r"Teams",
    r"Slack",
    r"Jira",
    r"Confluence",
    r"CRM",
    r"ERP",
    r"Salesforce",
    r"세일즈포스",
    r"거래원장",
    r"고객명",
    r"회사명",
    r"https?://",
]


def split_blocks(path: Path) -> list[str]:
    return [block.strip() for block in path.read_text(encoding="utf-8").split("---") if block.strip()]


def validate_file(path: Path, max_chars: int, block_count: int, patterns: list[re.Pattern[str]]) -> list[str]:
    errors: list[str] = []
    blocks = split_blocks(path)
    if len(blocks) != block_count:
        errors.append(f"expected {block_count} blocks, got {len(blocks)}")
    for index, block in enumerate(blocks, 1):
        if len(block) > max_chars:
            errors.append(f"block {index} exceeds {max_chars} chars ({len(block)})")
    text = path.read_text(encoding="utf-8")
    for pattern in patterns:
        if pattern.search(text):
            errors.append(f"sensitive-pattern match: {pattern.pattern}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Threads chain markdown files.")
    parser.add_argument("path", help="Markdown file or directory containing YYYY-MM-DD.md files")
    parser.add_argument("--max-chars", type=int, default=500)
    parser.add_argument("--block-count", type=int, default=3)
    parser.add_argument("--allow-pattern", action="append", default=[], help="Remove a default sensitive regex")
    args = parser.parse_args()

    root = Path(args.path)
    files = [root] if root.is_file() else sorted(root.glob("*.md"))
    if not files:
        print("No markdown files found", file=sys.stderr)
        return 2

    raw_patterns = [p for p in DEFAULT_PATTERNS if p not in set(args.allow_pattern)]
    patterns = [re.compile(p, re.IGNORECASE) for p in raw_patterns]

    failed = False
    for path in files:
        errors = validate_file(path, args.max_chars, args.block_count, patterns)
        blocks = split_blocks(path)
        lengths = [len(block) for block in blocks]
        if errors:
            failed = True
            print(f"{path.name} BAD blocks={len(blocks)} lengths={lengths}")
            for error in errors:
                print(f"  - {error}")
        else:
            print(f"{path.name} OK blocks={len(blocks)} lengths={lengths}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
