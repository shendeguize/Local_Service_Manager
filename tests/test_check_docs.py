"""Tests for the bilingual documentation tree checker."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_checker(docs: Path):
    """Import scripts/check_docs.py with its DOCS root pointed at a fixture."""
    spec = importlib.util.spec_from_file_location("check_docs_under_test", ROOT / "scripts" / "check_docs.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.DOCS = docs
    return module


@pytest.fixture
def docs(tmp_path):
    for lang in ("zh", "en"):
        (tmp_path / lang).mkdir()
    return tmp_path


def write(docs: Path, lang: str, name: str, body: str) -> Path:
    path = docs / lang / name
    path.write_text(body, encoding="utf-8")
    return path


def test_matching_pages_pass(docs):
    write(docs, "zh", "install.md", "# 安装\n\n## 上手\n\n### 细节\n")
    write(docs, "en", "install.md", "# Installation\n\n## Getting started\n\n### Details\n")
    assert load_checker(docs).check_docs_tree() == []


def test_a_missing_translation_is_reported(docs):
    write(docs, "zh", "launchd.md", "# launchd\n")
    failures = load_checker(docs).check_docs_tree()
    assert failures == ["docs/en/launchd.md: missing translation of docs/zh/launchd.md"]


def test_an_untranslated_english_page_is_reported(docs):
    write(docs, "zh", "install.md", "# 安装\n")
    write(docs, "en", "install.md", "# Installation\n")
    write(docs, "en", "orphan.md", "# Orphan\n")
    failures = load_checker(docs).check_docs_tree()
    assert failures == ["docs/en/orphan.md: has no docs/zh/orphan.md to translate"]


def test_a_dropped_section_is_reported(docs):
    write(docs, "zh", "web.md", "# 面板\n\n## 安全\n\n## API\n")
    write(docs, "en", "web.md", "# Dashboard\n\n## Security\n")
    failures = load_checker(docs).check_docs_tree()
    assert len(failures) == 1
    assert "heading structure [1, 2] does not match" in failures[0]


def test_a_reordered_heading_depth_is_reported(docs):
    write(docs, "zh", "web.md", "# 面板\n\n## 安全\n\n### 细节\n")
    write(docs, "en", "web.md", "# Dashboard\n\n### Details\n\n## Security\n")
    failures = load_checker(docs).check_docs_tree()
    assert len(failures) == 1
    assert "[1, 3, 2]" in failures[0]


def test_headings_inside_code_fences_are_ignored(docs):
    fenced = "# 标题\n\n```sh\n# 这是注释，不是章节\nLocalSM up\n```\n\n## 真章节\n"
    write(docs, "zh", "quickstart.md", fenced)
    write(docs, "en", "quickstart.md", "# Title\n\n```sh\n# a comment, not a section\nLocalSM up\n```\n\n## Real\n")
    assert load_checker(docs).check_docs_tree() == []


def test_a_broken_local_link_is_reported(docs):
    write(docs, "zh", "index.md", "# 索引\n\n[缺失](nope.md)\n")
    write(docs, "en", "index.md", "# Index\n\n[missing](nope.md)\n")
    failures = load_checker(docs).check_docs_tree()
    assert failures == [
        "docs/zh/index.md: missing links: nope.md",
        "docs/en/index.md: missing links: nope.md",
    ]


def test_external_and_anchor_links_are_not_checked(docs):
    body = "# 标题\n\n[web](https://example.com) [anchor](#x) [mail](mailto:a@b.c)\n"
    write(docs, "zh", "index.md", body)
    write(docs, "en", "index.md", "# Title\n\n[web](https://example.com) [anchor](#x) [mail](mailto:a@b.c)\n")
    assert load_checker(docs).check_docs_tree() == []


def test_a_page_left_at_the_top_level_is_reported(docs):
    write(docs, "zh", "install.md", "# 安装\n")
    write(docs, "en", "install.md", "# Installation\n")
    (docs / "stray.md").write_text("# Stray\n", encoding="utf-8")
    failures = load_checker(docs).check_docs_tree()
    assert len(failures) == 1
    assert failures[0].startswith("docs/: stray.md must live under")


def test_maintainer_docs_may_stay_at_the_top_level(docs):
    write(docs, "zh", "install.md", "# 安装\n")
    write(docs, "en", "install.md", "# Installation\n")
    (docs / "releasing.md").write_text("# Releasing\n", encoding="utf-8")
    assert load_checker(docs).check_docs_tree() == []


def test_an_empty_source_tree_is_reported(docs):
    assert load_checker(docs).check_docs_tree() == ["docs/zh/: no pages found"]


def test_the_real_documentation_tree_passes():
    assert load_checker(ROOT / "docs").check_docs_tree() == []
