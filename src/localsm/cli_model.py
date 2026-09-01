"""Read an argparse parser back as data.

The parser in cli.py is the single source of truth for LocalSM's surface. This
module turns it into a tree so shell completions, the CLI reference, and the
help-completeness check all describe exactly the parser that ships, instead of
drifting from it.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field

# Documented once globally rather than repeated under every command.
GLOBAL_FLAGS = ("--json", "--quiet")
HELP_FLAGS = ("-h", "--help")


@dataclass(frozen=True)
class Argument:
    flags: tuple[str, ...]
    metavar: str
    help: str | None
    choices: tuple[str, ...] | None
    nargs: object | None

    @property
    def is_positional(self) -> bool:
        return not self.flags

    @property
    def takes_value(self) -> bool:
        return not self.is_positional and self.nargs != 0

    def signature(self) -> str:
        if self.is_positional:
            if self.nargs == "?":
                return f"[{self.metavar}]"
            if self.nargs == "*":
                return f"[{self.metavar}...]"
            if self.nargs in ("+", argparse.REMAINDER):
                return f"{self.metavar}..."
            return self.metavar
        flag = self.flags[0]
        return f"[{flag} {self.metavar}]" if self.takes_value else f"[{flag}]"


@dataclass(frozen=True)
class Command:
    path: tuple[str, ...]
    help: str | None
    positionals: tuple[Argument, ...] = ()
    options: tuple[Argument, ...] = ()
    subcommands: tuple[Command, ...] = field(default_factory=tuple)

    @property
    def name(self) -> str:
        return self.path[-1] if self.path else ""

    @property
    def full_name(self) -> str:
        return " ".join(("LocalSM", *self.path))

    def signature(self) -> str:
        parts = [self.full_name]
        if self.subcommands:
            parts.append("{" + ",".join(item.name for item in self.subcommands) + "}")
        parts.extend(item.signature() for item in self.positionals)
        parts.extend(item.signature() for item in self.options)
        return " ".join(parts)

    def walk(self) -> list[Command]:
        """This command followed by every descendant, depth first."""
        found = [self]
        for child in self.subcommands:
            found.extend(child.walk())
        return found


def _metavar(action: argparse.Action) -> str:
    if action.metavar:
        return str(action.metavar)
    if action.option_strings:
        return action.dest.upper()
    return action.dest.upper()


def _argument(action: argparse.Action) -> Argument:
    return Argument(
        flags=tuple(action.option_strings),
        metavar=_metavar(action),
        help=action.help,
        choices=tuple(str(choice) for choice in action.choices) if action.choices else None,
        nargs=action.nargs,
    )


def _subparsers_action(parser: argparse.ArgumentParser) -> argparse._SubParsersAction | None:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action
    return None


def _choice_help(action: argparse._SubParsersAction) -> dict[str, str | None]:
    return {item.dest: item.help for item in action._choices_actions}


def describe(
    parser: argparse.ArgumentParser,
    path: tuple[str, ...] = (),
    help_text: str | None = None,
) -> Command:
    subparsers = _subparsers_action(parser)
    positionals: list[Argument] = []
    options: list[Argument] = []
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            continue
        if set(action.option_strings) & set(HELP_FLAGS):
            continue
        if set(action.option_strings) & set(GLOBAL_FLAGS):
            continue
        if isinstance(action, argparse._VersionAction):
            options.append(_argument(action))
            continue
        (positionals if not action.option_strings else options).append(_argument(action))

    children: list[Command] = []
    if subparsers is not None:
        helps = _choice_help(subparsers)
        for name, child in subparsers.choices.items():
            children.append(describe(child, (*path, name), helps.get(name)))

    return Command(
        path=path,
        help=help_text or (parser.description if not path else None),
        positionals=tuple(positionals),
        options=tuple(options),
        subcommands=tuple(children),
    )


def missing_help(root: Command) -> list[str]:
    """Names of commands and arguments that ship without help text."""
    gaps: list[str] = []
    for command in root.walk():
        if command.path and not command.help:
            gaps.append(command.full_name)
        for argument in (*command.positionals, *command.options):
            if argument.help:
                continue
            label = argument.flags[0] if argument.flags else argument.metavar
            gaps.append(f"{command.full_name} {label}")
    return gaps
