#!/usr/bin/env python3
"""Copy docs/ into the Starlight content collection, adapting it for the web.

The documentation has one source: docs/zh and docs/en. The website reads a
generated copy rather than a second set of files, so a page can never say one
thing in the repository and another on the site.

Three adaptations are needed on the way in:

- Starlight renders the title from frontmatter, so the H1 is lifted out of the
  body and into a `title` field.
- Markdown links between pages end in `.md`, which Starlight serves as
  extensionless routes.
- Links into the source tree only resolve inside a checkout, so they are
  rewritten to point at GitHub.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
TARGET = ROOT / "site" / "src" / "content" / "docs"
LANGUAGES = ("zh", "en")
BLOB = "https://github.com/shendeguize/Local_Service_Manager/blob/main"

# Sidebar order, and the reason each page exists. Pages are numbered so the
# reading order on the site matches the order a newcomer needs them in, rather
# than alphabetically.
ORDER = (
    "install",
    "quickstart",
    "configuration",
    "services",
    "launchd",
    "tunnels",
    "remote",
    "web",
    "cli-reference",
    "cli-contract",
    "architecture",
    "troubleshooting",
)
# The docs index is a navigation page for people reading the repository. On the
# site that job belongs to the sidebar and the landing page, and keeping it would
# also claim the `/en/` route the English landing page needs.
SITE_EXCLUDED = frozenset({"index"})
DESCRIPTIONS = {
    "zh": {
        "install": "在 macOS 上安装 LocalSM：npm 直接安装、uv 全局安装或从源码运行。",
        "quickstart": "五分钟从零跑起第一个服务和 Web 面板。",
        "configuration": "配置文件位置、全部字段与环境变量优先级。",
        "services": "服务的启停、端口分配、日志与状态判定。",
        "launchd": "把服务交给 launchd 实现开机自启，以及端口为何要冻结。",
        "tunnels": "显式 SSH 转发规则、ssh 参数选择与自愈。",
        "remote": "并行探测远端主机的监听端口，并对上隧道覆盖情况。",
        "web": "Web 面板的分区、安全模型与 HTTP API。",
        "cli-reference": "全部命令与参数，由 argparse parser 自动生成。",
        "cli-contract": "JSON 输出形态与退出码约定。",
        "architecture": "模块关系、进程模型与路径解析。",
        "troubleshooting": "常见症状、定位方法与修复步骤。",
    },
    "en": {
        "install": "Install LocalSM on macOS through npm, a global uv install, or from source.",
        "quickstart": "From nothing to a running service and dashboard in five minutes.",
        "configuration": "File locations, every field, and environment variable precedence.",
        "services": "Starting and stopping services, port allocation, logs, and state.",
        "launchd": "Hand a service to launchd for start at login, and why the port is frozen.",
        "tunnels": "Explicit SSH forwarding rules, the ssh options chosen, and self-healing.",
        "remote": "Probe remote listening ports in parallel and match them against tunnels.",
        "web": "The dashboard's sections, security model, and HTTP API.",
        "cli-reference": "Every command and argument, generated from the argparse parser.",
        "cli-contract": "JSON output shapes and the exit-code convention.",
        "architecture": "Module relationships, the process model, and path resolution.",
        "troubleshooting": "Symptoms, how to narrow them down, and how to fix them.",
    },
}

H1_PATTERN = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
COMMENT_PATTERN = re.compile(r"<!--.*?-->\s*", re.DOTALL)
LINK_PATTERN = re.compile(r"(?<=\]\()(\.\.?/[^)\s]+|[^)\s/]+\.md)(#[^)]*)?(?=\))")


class SyncError(RuntimeError):
    """Raised when a page cannot be adapted for the site."""


def rewrite_link(target: str, anchor: str, lang: str, page: str) -> str:
    """Turn a repository-relative link into one the built site can serve.

    Routes stay relative rather than absolute because the site is served from a
    GitHub Pages base path, and Astro does not rewrite hrefs written inside
    Markdown. A relative link is correct under any base.
    """
    if target.startswith("../../"):
        # Into the source tree, which only GitHub can serve.
        return f"{BLOB}/{target.removeprefix('../../')}{anchor}"
    # An index page is served from the language root, one segment shallower than
    # its siblings, so it needs one fewer `../` to reach them.
    up = "" if page == "index" else "../"
    other = next(item for item in LANGUAGES if item != lang)
    if target.startswith(f"../{other}/"):
        name = Path(target).stem
        route = f"{up}../{other}/" if name == "index" else f"{up}../{other}/{name}/"
        return f"{route}{anchor}"
    if not target.endswith(".md"):
        raise SyncError(f"cannot map link {target!r} onto a site route")
    name = Path(target).stem
    route = f"{up}../{lang}/" if name == "index" else f"{up}{name}/"
    return f"{route}{anchor}"


def adapt(path: Path, lang: str) -> str:
    body = COMMENT_PATTERN.sub("", path.read_text(encoding="utf-8"), count=1)
    heading = H1_PATTERN.search(body)
    if not heading or heading.start() != 0:
        raise SyncError(f"{path.relative_to(ROOT)} must open with an H1 for the page title")
    title = heading.group(1)
    body = body[heading.end() :].lstrip("\n")
    name = path.stem
    body = LINK_PATTERN.sub(lambda m: rewrite_link(m.group(1), m.group(2) or "", lang, name), body)

    description = DESCRIPTIONS[lang].get(name)
    if description is None:
        raise SyncError(f"{path.relative_to(ROOT)} has no site description; add one to scripts/sync_site_docs.py")
    frontmatter = [
        "---",
        f"title: {title}",
        f"description: {description}",
        # Starlight would otherwise point "edit this page" at this generated
        # copy, which is not in the repository. The source is the page in docs/.
        f"editUrl: {BLOB.replace('/blob/', '/edit/')}/docs/{lang}/{path.name}",
        f"sidebar:\n  order: {ORDER.index(name)}" if name in ORDER else "",
        "---",
        "",
    ]
    return "\n".join(line for line in frontmatter if line) + "\n" + body


def sync() -> list[str]:
    if TARGET.exists():
        shutil.rmtree(TARGET)
    written = []
    for lang in LANGUAGES:
        source = DOCS / lang
        destination = TARGET / lang
        destination.mkdir(parents=True)
        for path in sorted(source.glob("*.md")):
            if path.stem in SITE_EXCLUDED:
                continue
            if path.stem not in ORDER:
                raise SyncError(f"{path.relative_to(ROOT)} is not in ORDER; add it to scripts/sync_site_docs.py")
            (destination / path.name).write_text(adapt(path, lang), encoding="utf-8")
            written.append(str((destination / path.name).relative_to(ROOT)))
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quiet", action="store_true", help="print only the page count")
    args = parser.parse_args()
    try:
        written = sync()
    except SyncError as exc:
        print(f"site docs sync failed: {exc}", file=sys.stderr)
        return 1
    if args.quiet:
        print(f"Synced {len(written)} pages into the site content collection.")
    else:
        print("\n".join(written))
        print(f"Synced {len(written)} pages.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
