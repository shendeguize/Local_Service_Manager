# Installation

LocalSM is macOS-only: it depends on `launchd`, `osascript`, and macOS terminal
applications.

## Recommended: install from npm

Needs Node.js 18 or newer:

```sh
npx @shendeguize/local-sm init
npx @shendeguize/local-sm status
```

The npm package bundles a matching LocalSM wheel, so it does not depend on
LocalSM being published to PyPI. On first run, the launcher notices that `uv` is
missing and installs it with Astral's official script; `uv` then creates an
isolated environment and installs the runtime dependencies. The package also
ships an install script that does the same thing, but recent npm versions block
lifecycle scripts by default, so in practice the launcher's own check is what
runs.

For a shorter command, install globally:

```sh
npm install -g @shendeguize/local-sm
LocalSM --version
```

## Developers: global install with uv

Working from source needs Python 3.12+ and [uv](https://docs.astral.sh/uv/):

```sh
uv tool install --editable . --force
LocalSM --version
```

## Running inside the project

Without installing a global command:

```sh
./LocalSM status
uv run python -m localsm.cli status
```

On the first run `uv` creates `.venv` and installs dependencies. The runtime
dependencies are just Flask and PyYAML.

## Where configuration lives

However you install it, LocalSM reads configuration from one place:

```text
~/.config/localsm/         configuration
~/.local/state/localsm/    runtime state
```

This is independent of where LocalSM itself is installed. Earlier versions
derived the paths from the install directory, which under a wheel install
pointed at a throwaway path inside the `uv` cache. To keep configuration and
state inside the repository while developing, set `LOCALSM_ROOT="$PWD"`. See
[Configuration](configuration.md).

## Shell completion

Completion scripts are generated from the parser, so they cannot drift away from
the commands:

```sh
# zsh
LocalSM completion zsh > "${fpath[1]}/_LocalSM"

# bash, in ~/.bashrc
source <(LocalSM completion bash)
```

Completion calls `LocalSM completion services` for real service names, so adding
a service does not mean regenerating the script.

## Verifying the install

```sh
LocalSM doctor --local-only
```

`doctor` checks the commands it depends on, the Python dependencies, the
configuration files, and whether the state directory is writable. Missing
configuration is reported as `FAIL` and points at `LocalSM init`.
