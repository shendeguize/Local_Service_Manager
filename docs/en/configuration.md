# Configuration

LocalSM keeps configuration and runtime state under your home directory,
independent of where the repository is:

```text
~/.config/localsm/services.yaml      service definitions and the port pool
~/.config/localsm/tunnels.yaml       SSH tunnel rules
~/.local/state/localsm/              pidfiles, logs, port state, scan cache
```

`LocalSM init` writes commented starter files into the config directory and
**never overwrites an existing file**. The repository's
[`config/services.example.yaml`](../../config/services.example.yaml) is a
read-only copy of the same template, there so it can be read on the web.

When a configuration file does not exist, read commands still work and print a
hint on stderr suggesting `LocalSM init`; `LocalSM doctor` reports it as a
`FAIL`.

## Path environment variables

| Variable | Effect |
| --- | --- |
| `LOCALSM_CONFIG_DIR` | Override the config directory outright |
| `LOCALSM_STATE_DIR` | Override the state directory outright |
| `LOCALSM_ROOT` | Provide both: `<root>/config` and `<root>/state` |
| `XDG_CONFIG_HOME` / `XDG_STATE_HOME` | Follow the XDG convention and change the base directories |
| `PYTHON` | The Python executable used by the `{python}` command template |

Precedence is `LOCALSM_CONFIG_DIR` / `LOCALSM_STATE_DIR` > `LOCALSM_ROOT` > the
XDG variables > the home-directory defaults.

For example, to run against isolated state for a test:

```sh
LOCALSM_STATE_DIR=/tmp/localsm-state LocalSM status
```

While developing from source, `LOCALSM_ROOT` keeps both configuration and state
inside the repository:

```sh
LOCALSM_ROOT="$PWD" ./LocalSM status
```

## services.yaml

The top-level `port_pool` is the inclusive range used for automatic allocation:

```yaml
port_pool: [8000, 8999]
services:
  demo:
    start: "python -m http.server {port}"
    preferred_port: 8080
    port_range: [8100, 8199]
    set_port: ["demo config {port}", "demo restart"]
    stop: "demo stop"
    status_cmd: "demo status"
    url_from_log: true
    working_dir: "~/workspace"
    env:
      MODE: development
```

The fields:

- `start`: the start command template, and the only required field. LocalSM runs
  it through a shell.
- `preferred_port`: the service's first choice. When it is taken, LocalSM only
  looks further if `--auto-port` was passed.
- `port_range`: this service's own range for automatic allocation; defaults to the
  top-level `port_pool`.
- `set_port`: the commands that change the port, either a string or a list. Each
  one can use `{port}`.
- `stop`: the stop command, either a string or a list.
- `status_cmd`: the status command for an externally supervised service. LocalSM
  reads it as running when the output contains `running`, `运行中`, or `已运行`.
- `url_from_log`: read the real URL out of the log, keeping the URL fragment (for
  example Kimi's `#token=...`).
- `working_dir`: the working directory for start, stop, and exec commands.
- `env`: extra environment variables.

The variables available in command templates:

- `{port}`: the port LocalSM allocated or the user requested.
- `{current_port}`: the service's port at the time `set_port` runs, for services
  that must reach the old manager before switching.
- `{python}`: the path of the Python currently running LocalSM.

A service like `dshc` can use a multi-command port template:

```yaml
dshc:
  start: "dshc up --port {port}"
  set_port:
    - "dshc config set manager.port {port} --port {current_port}"
    - "dshc restart --port {current_port}"
```

## tunnels.yaml

```yaml
tunnels:
  - name: api-pod
    host: my-pod
    local_port: 18080
    remote_host: 127.0.0.1
    remote_port: 8080
```

`host` must be a Host alias from `~/.ssh/config`. LocalSM opens the tunnel with a
detached `ssh -N -L` process and writes its pid to `pids/tunnel-*.pid` in the
state directory. `tunnel ensure` checks for the process and rebuilds it from the
same rule when it is gone.

## The state layout

```text
~/.local/state/localsm/
├── logs/<service>.log
├── logs/tunnel-<name>.log
├── pids/<service>.pid
├── pids/tunnel-<name>.pid
├── ports.json
└── remote_scan.json
```

State is runtime data and does not belong in the repository. Deleting
`ports.json` clears the sticky port record but does not stop any running process.

## Machine-readable output

Every command accepts `--json`. The output shapes and exit codes are specified in
[cli-contract.md](cli-contract.md).
