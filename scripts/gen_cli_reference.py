#!/usr/bin/env python3
"""Write docs/cli-reference.md from the argparse parser, or verify it is current."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from localsm.cli import build_parser  # noqa: E402
from localsm.cli_model import describe, missing_help  # noqa: E402
from localsm.reference import LANGUAGES, render_markdown  # noqa: E402


def target_for(lang: str) -> Path:
    return ROOT / "docs" / lang / "cli-reference.md"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail when a committed reference is stale")
    args = parser.parse_args()

    root = describe(build_parser())
    gaps = missing_help(root)
    if gaps:
        print("Commands or arguments are missing help text:", file=sys.stderr)
        print("\n".join(f"  {gap}" for gap in gaps), file=sys.stderr)
        return 1

    stale = []
    for lang in LANGUAGES:
        target = target_for(lang)
        rendered = render_markdown(root, lang)
        if not args.check:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(rendered, encoding="utf-8")
            print(f"Wrote {target.relative_to(ROOT)}")
            continue
        current = target.read_text(encoding="utf-8") if target.exists() else ""
        if current != rendered:
            stale.append(str(target.relative_to(ROOT)))
    if stale:
        print(f"Out of date with the parser: {', '.join(stale)}. Run `make docs-cli`.", file=sys.stderr)
        return 1
    if args.check:
        print("CLI reference matches the parser.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
