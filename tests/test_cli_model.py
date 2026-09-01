import argparse
import subprocess

import pytest

from localsm.cli import build_parser
from localsm.cli_model import Argument, describe, missing_help
from localsm.completion import SHELLS, render, render_bash, render_zsh
from localsm.reference import render_markdown


@pytest.fixture(scope="module")
def root():
    return describe(build_parser())


def find(root, *path):
    return next(command for command in root.walk() if command.path == path)


def test_every_command_and_argument_documents_itself(root):
    assert missing_help(root) == []


def test_missing_help_is_reported(root):
    parser = argparse.ArgumentParser(prog="LocalSM")
    sub = parser.add_subparsers(dest="command")
    undocumented = sub.add_parser("mystery")
    undocumented.add_argument("target")
    gaps = missing_help(describe(parser))
    assert gaps == ["LocalSM mystery", "LocalSM mystery TARGET"]


def test_the_tree_matches_the_parser(root):
    names = {command.name for command in root.subcommands}
    assert {"up", "down", "status", "init", "edit", "enable", "disable", "completion", "tunnel", "remote"} <= names
    assert {item.name for item in find(root, "tunnel").subcommands} == {"add", "rm", "list", "ensure"}
    assert {item.name for item in find(root, "remote").subcommands} == {"scan"}


def test_global_and_help_flags_are_not_repeated_per_command(root):
    for command in root.walk():
        flags = {flag for option in command.options for flag in option.flags}
        assert "--json" not in flags
        assert "--quiet" not in flags
        assert "--help" not in flags


@pytest.mark.parametrize(
    ("nargs", "expected"),
    [
        (None, "SERVICE"),
        ("?", "[SERVICE]"),
        ("*", "[SERVICE...]"),
        ("+", "SERVICE..."),
        (argparse.REMAINDER, "SERVICE..."),
    ],
)
def test_positional_signatures_reflect_nargs(nargs, expected):
    argument = Argument(flags=(), metavar="SERVICE", help="x", choices=None, nargs=nargs)
    assert argument.signature() == expected


def test_option_signatures_distinguish_flags_from_values():
    valued = Argument(flags=("--port",), metavar="PORT", help="x", choices=None, nargs=None)
    switch = Argument(flags=("--auto-port",), metavar="AUTO_PORT", help="x", choices=None, nargs=0)
    assert valued.signature() == "[--port PORT]"
    assert switch.signature() == "[--auto-port]"


def test_command_signature_reads_like_usage(root):
    assert find(root, "up").signature() == "LocalSM up [SERVICE] [--port PORT] [--auto-port]"
    assert find(root, "tunnel").signature() == "LocalSM tunnel {add,rm,list,ensure}"


def test_reference_documents_every_command(root):
    markdown = render_markdown(root)
    for command in root.walk():
        if command.path:
            assert f" {command.full_name}\n" in markdown
    assert "cli-contract.md" in markdown
    assert "Do not edit by hand" in markdown


def test_reference_records_argument_choices(root):
    markdown = render_markdown(root)
    assert "`ghostty`, `terminal`" in markdown


@pytest.mark.parametrize("shell", SHELLS)
def test_completion_scripts_name_every_top_level_command(root, shell):
    script = render(shell, root)
    for command in root.subcommands:
        assert command.name in script


def test_completion_rejects_an_unknown_shell(root):
    with pytest.raises(ValueError, match="unsupported shell"):
        render("fish", root)


def test_completion_scripts_delegate_service_names(root):
    assert "LocalSM completion services" in render_zsh(root)
    assert "LocalSM completion services" in render_bash(root)


@pytest.mark.parametrize(("shell", "interpreter"), [("zsh", "zsh"), ("bash", "bash")])
def test_generated_completions_are_valid_shell(root, shell, interpreter, tmp_path):
    script = tmp_path / f"completion.{shell}"
    script.write_text(render(shell, root), encoding="utf-8")
    result = subprocess.run([interpreter, "-n", str(script)], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
