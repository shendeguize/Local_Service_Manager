# LocalSM

LocalSM is a macOS-oriented console for local services and SSH resources. It
normalizes services such as `enva`, `dshc`, `aqp`, `kimi`, and `dsh` into
configurable command templates, while also managing ports, logs, remote
listener scans, and SSH tunnels.

LocalSM has no resident supervisor. Services run detached and are tracked with
pidfiles, port probes, and logs, so a LocalSM exit does not automatically stop
the services it started.

## Installation

### Recommended: direct installation with npm

You need Node.js 18+ and [uv](https://docs.astral.sh/uv/):

```sh
npx @shendeguize/local-sm --version
```

The npm package includes the matching LocalSM wheel, so it does not require
LocalSM to be published on PyPI. On first run, `uv` creates an isolated
environment and installs the public runtime dependencies.

### Developers: install globally with uv

For development or running from source, you need Python 3.12+ and `uv`:

```sh
uv tool install --editable . --force
LocalSM --version
```

Editable installation keeps the global command pointed at the repository's
`config/` and `state/` directories. See
[`packages/npm/README.md`](packages/npm/README.md) for details.
See [`docs/releasing.md`](docs/releasing.md) for the release process.

### Run from the project

```sh
./LocalSM status
uv run python -m localsm.cli status
```

The first `uv` invocation creates `.venv` and installs dependencies. Runtime
dependencies are Flask and PyYAML; test dependencies are installed with
`uv sync --dev`.

## Quick start

```sh
LocalSM config
LocalSM status

LocalSM web
# Open http://127.0.0.1:8765/

LocalSM up enva --auto-port
LocalSM restart enva
LocalSM logs enva
LocalSM down enva
```

The Web console provides service lifecycle controls, port changes, a log
drawer, remote scans, terminal launch, and tunnel management. API failures are
shown as actionable error notifications.

## CLI reference

```text
LocalSM --version
LocalSM up [SERVICE] [--port PORT] [--auto-port]
LocalSM down [SERVICE]
LocalSM restart [SERVICE] [--port PORT] [--auto-port]
LocalSM status [SERVICE]
LocalSM set-port SERVICE PORT
LocalSM exec SERVICE COMMAND...
LocalSM logs SERVICE [--lines N]
LocalSM config
LocalSM doctor [--local-only] [--timeout SECONDS]
LocalSM remote scan [HOST...] [--timeout SECONDS]
LocalSM tunnel add NAME HOST LOCAL_PORT REMOTE_PORT [--remote-host HOST]
LocalSM tunnel rm NAME
LocalSM tunnel list
LocalSM tunnel ensure [NAME]
LocalSM ssh HOST [--app ghostty|terminal]
LocalSM web
```

When `SERVICE` is omitted, `up`, `down`, `restart`, and `status` operate on all
configured services. `exec` runs its argument list without replacing the
managed process:

```sh
LocalSM exec enva pwd
LocalSM logs kimi --lines 120
LocalSM set-port aqp 18080
```

`doctor` scans SSH-configured hosts by default. Use
`LocalSM doctor --local-only` in a restricted network environment.

## Remote scans and tunnels

```sh
LocalSM remote scan
LocalSM tunnel add api-pod my-pod 18080 8080
LocalSM tunnel list
LocalSM tunnel ensure api-pod
LocalSM tunnel rm api-pod
LocalSM ssh my-pod --app ghostty
```

Scans run concurrently and probe remote listeners using `ss`, `lsof`,
`netstat`, and `/proc` fallbacks. LocalSM only reads `~/.ssh/config`; it never
writes `LocalForward` entries. Tunnel definitions are stored in
`config/tunnels.yaml`.

## Configuration

See [docs/configuration.md](docs/configuration.md) for all fields, environment
variables, and state layout. See [docs/architecture.md](docs/architecture.md)
for the module and process model.

## Diagnostics, tests, and smoke

```sh
make install
make doctor
make test
make cov
make smoke
```

Hermetic tests do not connect to real SSH hosts or start real service CLIs.
`scripts/smoke.sh` performs the full real acceptance flow and may restart local
services. It records and attempts to restore dshc's original port and launchd
state.

The paired top-level sections in README.md and README.en.md must stay in sync.
Update both files for user-visible features; CI checks their section structure
and local links.

## Roadmap

- Direct npm installation: `@shendeguize/local-sm` includes the LocalSM wheel
  and requires `uv` on the user's machine.
- Native launchd templates: detached processes are supported today; per-service
  system management can be added later.
- Remote listener diffs and notifications: currently scans and caches on demand.
