#!/usr/bin/env python3
"""Check the bilingual README sections, the docs tree, and local links.

Chinese is the source language: every page under docs/zh must have an English
counterpart under docs/en with the same heading skeleton. Comparing the sequence
of heading levels rather than their text catches a translation that dropped or
reordered a section, without pretending the titles are comparable.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
SOURCE_LANG = "zh"
TARGET_LANG = "en"
# Maintainer-facing pages live at the top of docs/ and are deliberately
# monolingual: their audience already reads this repository.
MAINTAINER_DOCS = frozenset({"releasing.md"})
README_SECTIONS = (
    "安装",
    "快速上手",
    "CLI 参考",
    "远端扫描与隧道",
    "配置",
    "自检、测试与 smoke",
    "路线图",
)
README_EN_SECTIONS = (
    "Installation",
    "Quick start",
    "CLI reference",
    "Remote scans and tunnels",
    "Configuration",
    "Diagnostics, tests, and smoke",
    "Roadmap",
)
LINK_PATTERN = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
HEADING_PATTERN = re.compile(r"^(#{1,6})\s+\S", re.MULTILINE)
FENCE_PATTERN = re.compile(r"^```.*?^```", re.MULTILINE | re.DOTALL)


def check_sections(path: Path, sections: tuple[str, ...]) -> list[str]:
    content = path.read_text(encoding="utf-8")
    return [section for section in sections if f"## {section}" not in content]


def check_links(path: Path) -> list[str]:
    missing = []
    for target in LINK_PATTERN.findall(path.read_text(encoding="utf-8")):
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        target_path = (path.parent / target.split("#", 1)[0]).resolve()
        if not target_path.exists():
            missing.append(target)
    return missing


def heading_levels(path: Path) -> list[int]:
    """Return the heading depths of a page, ignoring fenced code blocks.

    Fences are stripped first so a `# comment` inside a shell example is not
    mistaken for a section.
    """
    content = FENCE_PATTERN.sub("", path.read_text(encoding="utf-8"))
    return [len(match.group(1)) for match in HEADING_PATTERN.finditer(content)]


def pages(lang: str) -> set[str]:
    directory = DOCS / lang
    if not directory.is_dir():
        return set()
    return {path.name for path in directory.glob("*.md")}


def check_docs_tree() -> list[str]:
    failures = []
    stray = sorted(path.name for path in DOCS.glob("*.md") if path.name not in MAINTAINER_DOCS)
    if stray:
        failures.append(
            f"docs/: {', '.join(stray)} must live under docs/{SOURCE_LANG}/ and docs/{TARGET_LANG}/ "
            f"(only {', '.join(sorted(MAINTAINER_DOCS))} may stay at the top level)"
        )
    source, target = pages(SOURCE_LANG), pages(TARGET_LANG)
    if not source:
        failures.append(f"docs/{SOURCE_LANG}/: no pages found")
        return failures
    for name in sorted(source - target):
        failures.append(f"docs/{TARGET_LANG}/{name}: missing translation of docs/{SOURCE_LANG}/{name}")
    for name in sorted(target - source):
        failures.append(f"docs/{TARGET_LANG}/{name}: has no docs/{SOURCE_LANG}/{name} to translate")
    for name in sorted(source & target):
        expected = heading_levels(DOCS / SOURCE_LANG / name)
        actual = heading_levels(DOCS / TARGET_LANG / name)
        if expected != actual:
            failures.append(
                f"docs/{TARGET_LANG}/{name}: heading structure {actual} does not match "
                f"docs/{SOURCE_LANG}/{name} {expected}"
            )
    for lang in (SOURCE_LANG, TARGET_LANG):
        for name in sorted(pages(lang)):
            missing_links = check_links(DOCS / lang / name)
            if missing_links:
                failures.append(f"docs/{lang}/{name}: missing links: {', '.join(missing_links)}")
    return failures


def main() -> int:
    failures = []
    for path, sections in (
        (ROOT / "README.md", README_SECTIONS),
        (ROOT / "README.en.md", README_EN_SECTIONS),
    ):
        missing = check_sections(path, sections)
        if missing:
            failures.append(f"{path.name}: missing sections: {', '.join(missing)}")
        missing_links = check_links(path)
        if missing_links:
            failures.append(f"{path.name}: missing links: {', '.join(missing_links)}")
    failures.extend(check_docs_tree())
    for path in sorted(DOCS.glob("*.md")):
        missing_links = check_links(path)
        if missing_links:
            failures.append(f"docs/{path.name}: missing links: {', '.join(missing_links)}")
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print(
        f"Documentation check passed: {len(pages(SOURCE_LANG))} pages in both "
        f"docs/{SOURCE_LANG} and docs/{TARGET_LANG}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
