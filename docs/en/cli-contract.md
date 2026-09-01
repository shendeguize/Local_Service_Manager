# CLI output contract

Every LocalSM command has two output modes: the default human-readable text, and
machine-readable JSON under `--json`. Scripts should always use `--json`; the
wording of the human-readable text is not covered by any compatibility promise.

## Global flags

| Flag | Effect |
| --- | --- |
| `--json` | Write a JSON document to stdout instead of human text |
| `--quiet` | Suppress informational stdout; errors still go to stderr |

Both flags work before or after the subcommand, so `LocalSM --json status` and
`LocalSM status --json` are equivalent. When both are given, `--json` wins: the
JSON is an explicitly requested payload and is not suppressed by `--quiet`.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Success |
| `1` | A LocalSM runtime error (service, tunnel, terminal, configuration), with the message on stderr |
| `2` | Usage error (argparse validation failed), or an unhandled command branch |
| Other | `exec` only: the child process's exit code, passed through |

`doctor` returns `1` when any check is a `FAIL`, and `0` otherwise.

When the configuration file does not exist, read commands still return `0` and
print one line on stderr pointing at `LocalSM init`: "not configured yet" is not
a failure. `doctor` is the one exception, reporting missing configuration as a
`FAIL`.

## JSON shapes per command

### The service object

`up`, `restart`, `down`, and `status` always return an **array**, even for a
single named service:

```json
[
  {
    "name": "web",
    "state": "running",
    "pid": 42123,
    "port": 8765,
    "url": "http://127.0.0.1:8765/",
    "log": "...",
    "error": null
  }
]
```

`state` is `running` or `stopped`. `set-port` and `web` return one service object
rather than an array.

### The other commands

| Command | JSON shape |
| --- | --- |
| `init` | `{"config_dir": str, "created": [str], "skipped": [str]}` |
| `config` | `{"config_dir", "services_file", "tunnels_file", "state_dir", "port_pool": [int, int], "tunnels": int, "services": [{"name", "preferred_port", "start"}]}` |
| `doctor` | `{"checks": [{"section", "name", "status", "detail"}], "failed": int}` |
| `exec` | `{"service", "command": [str], "exit_code": int}` |
| `logs` | `{"service", "lines": int, "content": str}` |
| `remote scan` | `[{"host", "reachable": bool, "ports": [int], "error", "tunnels": {port: [name]}}]` |
| `tunnel add` | One tunnel object, with `pid` and `state` |
| `tunnel rm` | `{"removed": name}` |
| `tunnel list` / `tunnel ensure` | An array of tunnel objects |
| `ssh` | `{"launched": host, "app": "ghostty"\|"terminal"}` |

A tunnel object carries `name`, `host`, `local_port`, `remote_host`, and
`remote_port`; `list` and `ensure` add `state` and `pid`.

`doctor`'s `status` is `PASS`, `WARN`, or `FAIL`; only `FAIL` affects the exit
code.

## Examples

```sh
# names of every running service
LocalSM --json status | jq -r '.[] | select(.state == "running") | .name'

# check the environment quietly in CI
LocalSM --quiet doctor --local-only || echo "environment is unhealthy"

# remote listening ports with no tunnel covering them
LocalSM --json remote scan | jq -r '.[] | .tunnels | to_entries[] | select(.value == []) | .key'
```
