# LocalSM

LocalSM is a macOS-oriented console for local services and SSH resources. You
describe each local service as a configurable command template, and LocalSM
manages their ports, logs, remote listener scans, and SSH tunnels.

LocalSM has no resident supervisor. Services run detached and are tracked with
pidfiles, port probes, and logs, so a LocalSM exit does not automatically stop
the services it started.

![LocalSM terminal recording: status lists the services, up starts one of them,
and logs and --json status show its output](site/public/media/services.gif)

The website is at <https://shendeguize.github.io/Local_Service_Manager/>, with
the same bilingual documentation and a
[simulated dashboard](https://shendeguize.github.io/Local_Service_Manager/demo/):
the real dashboard front end over a fake backend in your browser, so you can
click through it without installing anything.

The full documentation is in [docs/en/index.md](docs/en/index.md) (中文:
[docs/zh/index.md](docs/zh/index.md)): installation, quickstart, configuration,
services, launchd, tunnels, remote scans, the web dashboard, the CLI reference,
and troubleshooting.

## Installation

### Recommended: direct installation with npm

You need Node.js 18+:

```sh
npx @shendeguize/local-sm init
npx @shendeguize/local-sm status
```

`init` writes a commented starter configuration to `~/.config/localsm/`. It
never overwrites an existing file, so running it again is safe.

The npm package includes the matching LocalSM wheel, so it does not require
LocalSM to be published on PyPI. On first run the launcher installs `uv` with
Astral's official installer when it is not already available, then `uv`
creates an isolated environment and installs the public runtime dependencies.
The package also ships an install script that does the same thing earlier, but
recent npm versions block lifecycle scripts by default, so the launcher's own
check is what usually performs the installation.

### Developers: install globally with uv

For development or running from source, you need Python 3.12+ and `uv`:

```sh
uv tool install --editable . --force
LocalSM --version
```

However it is installed, LocalSM reads configuration from
`~/.config/localsm/` and writes runtime state to `~/.local/state/localsm/`,
independently of where the repository lives. Set `LOCALSM_ROOT="$PWD"` to keep
both inside the checkout while developing. See
[`packages/npm/README.md`](packages/npm/README.md) for details.
See [`docs/releasing.md`](docs/releasing.md) for the release process, and
[`docs/website.md`](docs/website.md) for how the website and its simulated
dashboard are built.

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
# Create the starter configuration, then edit it
LocalSM init
$EDITOR ~/.config/localsm/services.yaml

LocalSM config
LocalSM status

LocalSM web
# Open http://127.0.0.1:8765/

LocalSM up demo --auto-port
LocalSM restart demo
LocalSM logs demo
LocalSM down demo
```

Every command accepts `--json`. Scripts should always use it; see
[docs/en/cli-contract.md](docs/en/cli-contract.md) for the shapes and exit codes.

```sh
LocalSM --json status | jq -r '.[] | select(.state == "running") | .name'
```

The Web console provides service lifecycle controls, port changes, a log
drawer, remote scans, terminal launch, and tunnel management. API failures are
shown as actionable error notifications.

## CLI reference

Every command and argument is listed in
[docs/en/cli-reference.md](docs/en/cli-reference.md), generated from the
`argparse` parser so it cannot drift from the real behaviour. The common ones:

```sh
LocalSM init                   # write the starter configuration
LocalSM up [SERVICE]           # every service when the name is omitted
LocalSM status
LocalSM logs demo --lines 120
LocalSM set-port demo 18080
LocalSM exec demo pwd          # run a command in the service's directory
LocalSM enable demo            # hand to launchd for start at login
LocalSM edit                   # change the config in $EDITOR and see the diff
LocalSM web
```

Completion scripts come from the same parser:

```sh
LocalSM completion zsh > "${fpath[1]}/_LocalSM"
source <(LocalSM completion bash)
```

Completion calls `LocalSM completion services` for real service names, so adding
a service does not mean regenerating the script.

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
`~/.config/localsm/tunnels.yaml`.

## Configuration

Configuration lives in `~/.config/localsm/services.yaml` and runtime state in
`~/.local/state/localsm/`, independently of the repository. `LocalSM init`
creates the starter files, and
[`config/services.example.yaml`](config/services.example.yaml) is a read-only
copy of the same template.

See [docs/en/configuration.md](docs/en/configuration.md) for all fields,
environment variables, and state layout. See
[docs/en/cli-contract.md](docs/en/cli-contract.md) for the output contract, and
[docs/en/architecture.md](docs/en/architecture.md) for the module and process
model.

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

The paired top-level sections in README.md and README.en.md must stay in sync,
and every page under `docs/zh/` needs a counterpart under `docs/en/` with the
same heading structure. Update both for user-visible features; CI checks the
section structure, the bilingual docs tree, and local links.

## Roadmap

- Direct npm installation: `@shendeguize/local-sm` includes the LocalSM wheel
  and automatically installs `uv` when needed.
- A project website with a simulated dashboard, so LocalSM can be evaluated
  before installing it.
- Remote listener diffs and notifications: currently scans and caches on demand.
