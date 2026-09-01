# Troubleshooting

## Start with doctor

```sh
LocalSM doctor --local-only     # local checks only, returns in seconds
LocalSM doctor                  # adds remote SSH reachability, slower
```

`doctor` reports in groups: local tools (`uv`, `ssh`, `osascript`, Ghostty),
Python dependencies, the executable behind each service's `start` command,
configuration validity, and whether the state directory is writable. Any `FAIL`
makes the exit code 1, so it drops straight into a script.

A `WARN` does not affect the exit code: a missing Ghostty only means
`LocalSM ssh --app ghostty` will not work, and a service command that is not on
PATH may just need an environment activated first.

## Configuration

### A command says there is no configuration

```text
LocalSM: no configuration at /Users/you/.config/localsm/services.yaml. Run 'LocalSM init' to create one.
```

Read commands print that to stderr as a hint and still exit 0. Run
`LocalSM init` to write the templates.

### The configuration exists but LocalSM does not see it

First check where it is looking:

```sh
LocalSM config
```

That prints the config and state directories in effect. If they are not what you
expect, the usual cause is a leftover `LOCALSM_CONFIG_DIR`, `LOCALSM_STATE_DIR`,
or `LOCALSM_ROOT` in the environment:

```sh
env | grep LOCALSM
```

This is especially easy while developing: you set `LOCALSM_ROOT="$PWD"` to work
inside the repository and then forget it is still in the shell.

### Configuration seems lost after an upgrade

Before 0.2.0 LocalSM derived its config path from the install directory and kept
configuration in the repository's `config/`. It now lives in
`~/.config/localsm/`. There is no compatibility shim in 0.x, so move it once:

```sh
mkdir -p ~/.config/localsm
cp path/to/repo/config/*.yaml ~/.config/localsm/
```

## A service will not start

### `failed to start` followed by a log line

LocalSM waits briefly after starting a process and then checks it is alive; a
process that exits immediately produces this, with the last log line attached.
For the whole log:

```sh
LocalSM logs api --lines 100
```

The most common cause is that the environment the `start` command needs is not
there. LocalSM runs commands through `$SHELL` but **not** as a login shell, so
functions and aliases defined only in `.zshrc` are unavailable (launchd mode, in
contrast, does use a login shell). Write the full command out, or use
`working_dir` with relative paths.

### The port is taken

```sh
LocalSM up api --auto-port      # allow a different free port
LocalSM set-port api 9001           # name a new port
```

To find out who holds it:

```sh
lsof -nP -iTCP:8080 -sTCP:LISTEN
```

### Status says running but nothing answers

`status` reports process liveness, not service readiness. A process can be alive
without having bound its port (bad config, a startup that hung halfway). Read the
log, and give the service a `status_cmd` so LocalSM uses your own criterion.

If the service's real port differs from the one LocalSM reports, the service
probably moved itself. Turn on `url_from_log: true` so LocalSM reads the real
address from the log.

### The process is still there after `down`

`down` sends `SIGTERM` to the process group and `SIGKILL` after 5 seconds.
Something left over usually means a child escaped the original process group (the
`start` command called `setsid` itself, or the service is a client that hands work
to a daemon). Give it a `stop` command so it shuts down its own way:

```yaml
services:
  api:
    start: "myservice up --port {port}"
    stop: "myservice down"
```

## launchd

### `down` is refused

The service is under launchd, where `KeepAlive` would bring it straight back. To
actually stop it:

```sh
LocalSM disable api
```

### The service restarts over and over after enable

Check the exit status and the log:

```sh
LocalSM --json status api | jq '.pid, .managed_by'
LocalSM logs api --lines 100
launchctl print gui/$(id -u)/com.localsm.api
```

A service that crashes on startup is respawned every 10 seconds
(`ThrottleInterval`) under `KeepAlive`. Fix the startup problem, or `disable` it
while you investigate.

### A command is not found under launchd

The inverse trap: launchd runs the command through a login shell (`-lc`) while the
detached path does not. So some services work under launchd and not detached, or
the other way round. Test both modes.

### The port will not change

The port is frozen in the plist. Use `LocalSM set-port api 9000`, which rewrites and
reloads it, or `disable` and `enable` on the new port. `up` and `restart` with
`--port` are refused.

## Tunnels

### The tunnel is running but nothing connects

`state` only reflects whether the ssh process exists. See what ssh itself said:

```sh
tail -50 ~/.local/state/localsm/logs/tunnel-api.log
```

It is just as likely the remote service is not running: a healthy tunnel with
nothing at the far end. Confirm the remote port is really listening with
`LocalSM remote scan`.

### Tunnels keep dying

That is normal; networks drop. `ServerAliveCountMax=3` makes ssh exit cleanly
rather than linger half-dead, and bringing it back is `ensure`'s job:

```sh
LocalSM tunnel ensure
```

To automate it, put `ensure` in a scheduled launchd job, or rely on the
dashboard: it does not ensure automatically, but a `stopped` state is visible at a
glance.

### add says the local port is in use

`add` checks before acting, so nothing is left half-built. Pick another local
port, or stop whatever holds it.

## Remote scans

### A host is unreachable

Check that SSH itself works:

```sh
ssh my-pod true
```

Scans use `BatchMode=yes`, so any connection needing an interactive password or
key passphrase fails. Authentication has to be non-interactive (a key plus an
agent) for scanning to work.

### The host is reachable but no ports were found

`reachable: true` with empty `ports` and an `error` means the connection worked
but the probe did not. Read `error`: this is what it looks like when all four
probe methods (`ss`, `lsof`, `netstat`, and the `python3` reader for
`/proc/net/tcp`) are missing on the remote.

`reachable: true` with empty `ports` and `error: null` means nothing is actually
listening.

### The scan is slow

The default is an 8-second timeout per host with up to 12 in parallel. With many
hosts and some unreachable, the worst case is `hosts / 12 × timeout`. Shorten the
timeout, or scan only what you care about:

```sh
LocalSM remote scan pod-a pod-b --timeout 3
```

## Dashboard

### 403 refused Host

The dashboard only answers loopback names. You are probably reaching it through a
custom hosts alias:

```sh
LOCALSM_WEB_ALLOWED_HOSTS=dev.local LocalSM web
```

The reasoning is in the [Web dashboard](web.md) security model.

### A config change does not show up

The dashboard watches the mtime of `services.yaml` and the front end refreshes
every five seconds, so it can take that long. Longer than that, check that the
dashboard process and your CLI look at the same config directory: the dashboard
was started by `LocalSM web` and may carry different `LOCALSM_*` variables.

### The dashboard will not start

It is an ordinary service:

```sh
LocalSM logs web --lines 50
LocalSM web --foreground        # see the error in the terminal
```

Port 8765 already being in use is the most common reason.

## Still stuck

Include this in an issue:

```sh
LocalSM --version
LocalSM config
LocalSM doctor --local-only
```

Neither `LocalSM config` nor `doctor` prints the contents of `start` commands,
but both include service names and paths, so give the output a glance before
pasting it.
