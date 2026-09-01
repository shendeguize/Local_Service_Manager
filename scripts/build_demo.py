#!/usr/bin/env python3
"""Assemble the simulated dashboard the website ships under /demo/.

The demo is the dashboard LocalSM installs, not a re-creation of it: every
stylesheet and module is copied verbatim from src/localsm/static, and the single
file replaced is api.js, whose real implementation is the only code that talks to
the backend. site/demo/mock-api.js takes its place and answers from memory.

Two checks keep that swap honest, and both fail the site build rather than
shipping a demo that has drifted from the product:

  - the mock must export exactly the methods the real client exports, so a new
    endpoint cannot reach the demo unsimulated;
  - no other module may call fetch, so api.js must remain the only seam.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src" / "localsm" / "static"
TEMPLATE = ROOT / "src" / "localsm" / "templates" / "index.html"
MOCK = ROOT / "site" / "demo" / "mock-api.js"
TARGET = ROOT / "site" / "public" / "demo"
FIXTURES = TARGET / "fixtures.json"

DOCS_URL = "/Local_Service_Manager/zh/web/"
INSTALL_URL = "/Local_Service_Manager/zh/install/"

BANNER = """  <div class="demo-banner">
    <p><strong>模拟数据</strong>：这是 LocalSM 真实面板的前端，后端换成了浏览器内的状态机。
    启动、停止、扫描、建隧道都会改变状态，刷新页面即复位；不会连接任何主机。</p>
    <p class="demo-banner-links"><a href="{install}">安装到本机</a><a href="{docs}">面板文档</a></p>
  </div>
"""

BANNER_CSS = """
/* Added by scripts/build_demo.py for the website's simulated dashboard. */
.demo-banner {
  display: flex; flex-wrap: wrap; gap: 12px 24px; align-items: center; justify-content: space-between;
  margin-bottom: 20px; padding: 14px 18px; border-radius: var(--radius-md, 12px);
  border: 1px solid var(--border, #d8e0ec); background: var(--surface, #fff);
  box-shadow: var(--shadow-sm, 0 1px 2px rgb(15 23 42 / 6%));
}
.demo-banner p { margin: 0; font-size: 13px; line-height: 1.7; color: var(--text-muted, #64748b); }
.demo-banner strong { color: var(--text, #0f172a); }
.demo-banner-links { display: flex; gap: 16px; white-space: nowrap; }
.demo-banner-links a { color: var(--accent, #2563eb); font-weight: 600; text-decoration: none; }
.demo-banner-links a:hover { text-decoration: underline; }
"""


class DemoError(RuntimeError):
    """Raised when the dashboard and its mock have drifted apart."""


def exported_methods(source: str) -> set[str]:
    """The keys of the `export const api = { ... }` object literal."""
    body = re.search(r"export const api = \{(.*?)\n\};", source, re.S)
    if not body:
        raise DemoError("could not find the exported api object")
    return set(re.findall(r"^\s{2}(?:async )?([A-Za-z]\w*)[:(]", body.group(1), re.M))


def check_contract(modules: dict[str, str], mock: str) -> None:
    real = exported_methods((STATIC / "api.js").read_text(encoding="utf-8"))
    simulated = exported_methods(mock)
    if real != simulated:
        raise DemoError(
            "site/demo/mock-api.js is out of step with the dashboard's api.js: "
            f"unsimulated {sorted(real - simulated)}, stale {sorted(simulated - real)}"
        )
    stray = sorted(name for name, source in modules.items() if "fetch(" in source)
    if stray:
        raise DemoError(
            f"{', '.join(stray)} calls fetch directly, so the demo cannot intercept it; "
            "route the request through api.js"
        )


def render_page() -> str:
    """The Flask template as a static page: no url_for, plus the demo banner."""
    html = TEMPLATE.read_text(encoding="utf-8")
    html = re.sub(r"\{\{ url_for\('static', filename='([^']+)'\) \}\}", r"./\1", html)
    if "{{" in html or "{%" in html:
        raise DemoError("the dashboard template gained template syntax the demo cannot render")
    html = html.replace("<title>", "<title>Demo · ", 1)
    banner = BANNER.format(install=INSTALL_URL, docs=DOCS_URL)
    marker = '  <main class="shell">\n'
    if marker not in html:
        raise DemoError('the dashboard template no longer opens with <main class="shell">')
    return html.replace(marker, f"{marker}{banner}", 1)


def build() -> dict[str, str]:
    """The files the demo consists of, keyed by name, without touching disk."""
    if not FIXTURES.exists():
        raise DemoError(f"{FIXTURES.relative_to(ROOT)} is missing; run `make demo-fixtures` first")
    modules = {
        path.name: path.read_text(encoding="utf-8") for path in sorted(STATIC.glob("*.js")) if path.name != "api.js"
    }
    mock = MOCK.read_text(encoding="utf-8")
    check_contract(modules, mock)
    return {
        **modules,
        "api.js": mock,
        "app.css": (STATIC / "app.css").read_text(encoding="utf-8") + BANNER_CSS,
        "index.html": render_page(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verify",
        action="store_true",
        help="check the dashboard against its mock without writing the demo",
    )
    args = parser.parse_args()

    try:
        files = build()
    except DemoError as exc:
        print(f"demo build failed: {exc}", file=sys.stderr)
        return 1

    if args.verify:
        print(f"Demo mock covers the dashboard's API; {len(files)} files would be written.")
        return 0

    TARGET.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (TARGET / name).write_text(content, encoding="utf-8")
    print(f"Wrote {TARGET.relative_to(ROOT)}: {len(files)} files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
