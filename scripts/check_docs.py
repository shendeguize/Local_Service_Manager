#!/usr/bin/env python3
"""Check the required bilingual README sections and local links."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
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


def main() -> int:
    failures = []
    for path, sections in (
        (ROOT / "README.md", README_SECTIONS),
        (ROOT / "README.en.md", README_EN_SECTIONS),
    ):
        missing = check_sections(path, sections)
        if missing:
            failures.append(f"{path}: missing sections: {', '.join(missing)}")
        missing_links = check_links(path)
        if missing_links:
            failures.append(f"{path}: missing links: {', '.join(missing_links)}")
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print("Documentation structure and links check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
