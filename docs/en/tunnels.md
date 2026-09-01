# SSH tunnels

LocalSM tunnels are explicit rules: you declare that a local port forwards to a
port on a remote host, and LocalSM starts the `ssh -N -L` process, watches it,
and rebuilds it when needed. It does no discovery and does not guess what you
want forwarded.

## Commands

```sh
LocalSM tunnel add <name> <host> <local-port> <remote-port> [--remote-host HOST]
LocalSM tunnel list
LocalSM tunnel ensure [name]
LocalSM tunnel rm <name>
```

`<host>` must be a Host alias from `~/.ssh/config`. LocalSM does not accept a
bare IP plus a pile of connection options: authentication, jump hosts, and ports
belong in your SSH config, and LocalSM only references the alias.

## Creating a tunnel

```sh
LocalSM tunnel add api my-pod 18080 8080
```

That rule forwards local `127.0.0.1:18080` to `127.0.0.1:8080` on `my-pod`. The
remote target defaults to `127.0.0.1`; to forward to another machine the remote
host can see, use `--remote-host`:

```sh
LocalSM tunnel add db my-pod 15432 5432 --remote-host db.internal
```

`add` checks that the local port is free and the name is not taken before doing
anything, so a rejected request leaves nothing half-built. The rule is written to
`~/.config/localsm/tunnels.yaml`, the pid to
`~/.local/state/localsm/pids/tunnel-<name>.pid`, and ssh's own output to
`~/.local/state/localsm/logs/tunnel-<name>.log`.

## The ssh process options

Every tunnel LocalSM starts carries these options, and the reasons are worth
stating:

| Option | Why |
| --- | --- |
| `-N` | Do not run a remote command; forward only |
| `ExitOnForwardFailure=yes` | Exit when the port cannot be bound, instead of leaving a connection that pretends to work |
| `ServerAliveInterval=30` | Probe every 30 seconds so a half-dead connection surfaces |
| `ServerAliveCountMax=3` | Disconnect after three failed probes and leave the rebuild to `ensure` |

`ExitOnForwardFailure` is the important one. Without it, a port conflict gives
you an ssh that is connected but forwards nothing, which presents as "the tunnel
is clearly running, but connecting is refused". With it, a failure is a failure.

## Self-healing

A dead tunnel does not come back on its own; `ServerAliveCountMax` only ensures
ssh exits cleanly. Bringing it back is what `ensure` is for:

```sh
LocalSM tunnel ensure          # check every rule, rebuild only the dead ones
LocalSM tunnel ensure api      # just one
```

`ensure` walks the rules and checks whether each pid is alive: live ones are
reported as they are, dead ones get their stale pidfile removed and are rebuilt
from the stored rule. It is idempotent, which makes it suitable for a scheduled
job or a run before every `LocalSM web`.

If ssh cannot start during the rebuild (the remote is down, say), `ensure`
restores `tunnels.yaml` to its previous contents before raising: one failure will
not lose your rule definitions.

## Inspecting state

```sh
LocalSM tunnel list
LocalSM --json tunnel list | jq -r '.[] | select(.state=="stopped") | .name'
```

Each rule in `list` carries `state` (`running` / `stopped`) and `pid`. `state`
only reflects whether the ssh process exists, not whether the remote service is
healthy: a dead remote service still leaves the tunnel `running`.

## Working with remote scans

`LocalSM remote scan` annotates every remote listening port it finds with the
tunnels that already cover it, so unforwarded ports are visible directly. See
[Remote scans](remote.md).

## Removing

```sh
LocalSM tunnel rm api
```

`rm` sends `SIGTERM` to the process group, removes the pidfile, and drops the
rule from `tunnels.yaml`. Once the rule is gone, `ensure` naturally stops
rebuilding it.
