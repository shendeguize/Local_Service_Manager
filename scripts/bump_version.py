#!/usr/bin/env python3
"""Update the runtime version, npm wrapper, and changelog together."""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "src" / "localsm" / "__init__.py"
NPM_PACKAGE = ROOT / "packages" / "npm" / "package.json"
CHANGELOG = ROOT / "CHANGELOG.md"
VERSION_PATTERN = re.compile(r'(__version__\s*=\s*")[^"]+(")')
SEMVER_PATTERN = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def _read_version() -> str:
    match = re.search(r'^__version__\s*=\s*"([^"]+)"$', VERSION_FILE.read_text(encoding="utf-8"), re.MULTILINE)
    if not match:
        raise SystemExit(f"could not find __version__ in {VERSION_FILE}")
    return match.group(1)


def _validate_version(version: str) -> None:
    if not SEMVER_PATTERN.fullmatch(version):
        raise SystemExit(f"version must be a stable semantic version: {version}")


def _update_runtime_version(version: str) -> None:
    content = VERSION_FILE.read_text(encoding="utf-8")
    updated, count = VERSION_PATTERN.subn(rf"\g<1>{version}\g<2>", content, count=1)
    if count != 1:
        raise SystemExit(f"could not update {VERSION_FILE}")
    VERSION_FILE.write_text(updated, encoding="utf-8")


def _update_npm_version(version: str) -> None:
    if not NPM_PACKAGE.exists():
        return
    package = json.loads(NPM_PACKAGE.read_text(encoding="utf-8"))
    package["version"] = version
    NPM_PACKAGE.write_text(json.dumps(package, indent=2) + "\n", encoding="utf-8")


def _update_changelog(version: str, release_date: str) -> None:
    content = CHANGELOG.read_text(encoding="utf-8")
    heading = f"## [{version}] - {release_date}"
    if heading in content:
        raise SystemExit(f"changelog entry already exists for {version}")
    entry = f"{heading}\n\n### Added\n\n- Describe the user-visible changes in this release.\n\n"
    marker = "\n## ["
    position = content.find(marker)
    if position == -1:
        content = f"{content.rstrip()}\n\n{entry}"
    else:
        content = f"{content[:position].rstrip()}\n\n{entry}{content[position + 1 :]}"
    CHANGELOG.write_text(content, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", help="new stable semantic version, such as 0.1.1")
    parser.add_argument("--date", default=date.today().isoformat(), help="release date in YYYY-MM-DD format")
    args = parser.parse_args()
    _validate_version(args.version)
    current = _read_version()
    if args.version == current:
        raise SystemExit(f"version is already {current}")
    _update_runtime_version(args.version)
    _update_npm_version(args.version)
    _update_changelog(args.version, args.date)
    print(f"updated LocalSM from {current} to {args.version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
