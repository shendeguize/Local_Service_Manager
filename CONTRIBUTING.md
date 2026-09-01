# Contributing to LocalSM

## Development setup

LocalSM requires Python 3.12 or newer and [uv](https://docs.astral.sh/uv/).

```sh
uv sync --dev
make check
```

LocalSM reads configuration from `~/.config/localsm/` and writes state to
`~/.local/state/localsm/`, wherever the repository sits. To keep both inside
your checkout while developing, export `LOCALSM_ROOT="$PWD"`. Never commit a
real `config/*.yaml`; only `config/services.example.yaml` is tracked, and
`make hygiene` fails the build if a personal config sneaks in.

The test suite isolates these paths automatically through the autouse
`localsm_home` fixture in [tests/conftest.py](tests/conftest.py), so tests can
never read or damage your own configuration.

`make check` is the pull-request gate. It runs Ruff's lint and format checks,
then the pytest suite with the 75% coverage floor. `make build` builds the
Python distribution, and `make release-preflight` runs both checks and the
build.

## Test layers

Tests use the following markers:

- `unit`: isolated component tests;
- `integration`: tests spanning LocalSM components;
- `e2e`: tests against a running LocalSM application;
- `requires_ssh`: tests requiring a configured, reachable SSH host.

The test suite is safe for CI. `scripts/smoke.sh` is different: it starts and
stops real services, changes local ports, uses real SSH hosts, and may change
launchd state. Run it only on a machine where those side effects are
acceptable; it is not a pull-request gate.

## Pull requests

Use a feature branch and open a pull request against `main`. Every change
should include relevant tests and documentation. User-visible changes should
also update `CHANGELOG.md`.

Before requesting review, run:

```sh
make check
make release-preflight
```

Do not commit runtime state, logs, virtual environments, coverage output, or
distribution artifacts.
