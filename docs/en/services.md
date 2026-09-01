# Services

A LocalSM service is one command template in `services.yaml`. LocalSM does not
understand what your service does; it only handles ports, logs, processes, and
state.

## Lifecycle commands

```sh
LocalSM up [service]        # every service when the name is omitted
LocalSM down [service]
LocalSM restart [service]
LocalSM status [service]
LocalSM logs <service> [--lines N]
LocalSM set-port <service> <port>
LocalSM exec <service> <command>...
```

`up` is idempotent for a service that already runs: it returns the current
status instead of starting a second process.

## Process model

`up` uses `start_new_session` to launch the `start` command in a new session
detached from the terminal. Both stdout and stderr go to
`~/.local/state/localsm/logs/<service>.log`, and the pid is written to
`~/.local/state/localsm/pids/<service>.pid`. Because the process left the
controlling terminal, closing the window it was started from does not take the
service with it.

`down` sends `SIGTERM` to the whole process group, waits up to 5 seconds, sends
`SIGKILL` if the process is still alive, and then runs the service's own `stop`
command if one is configured. Signalling the process group rather than a single
pid is what catches children spawned by a shell wrapper.

Commands always run through `$SHELL` (`/bin/zsh` by default), so `start` can use
shell syntax, pipes, and environment expansion.

A service can also be handed to launchd, in which case the system starts it. See
[launchd service mode](launchd.md).

## Port allocation

Three rules, in order of precedence:

1. An explicit request: `LocalSM up api --port 8080`
2. The sticky port, the one last used successfully, recorded in
   `~/.local/state/localsm/ports.json`
3. `preferred_port`, then the first free port in `port_range` or the top-level
   `port_pool`

Stickiness is deliberate: restarting a service should normally land on the same
address, or every bookmark and hardcoded config pointing at it breaks. When the
preferred port is taken, LocalSM reports an error rather than quietly moving
elsewhere. To let it choose:

```sh
LocalSM up api --auto-port      # allow a different free port from the pool
LocalSM set-port api 9000           # change the port the way the service defines
```

`up` makes sure a service is running; it does not move one. Asking a running
service for a different port with `up --port 9000` is an error pointing you at
`restart --port 9000`, rather than a success that changed nothing.

The `set-port` command runs the service's `set_port` command sequence when one is
configured, and otherwise restarts on the new port. That makes "change the port"
work for services that need a config file rewritten and reloaded. `set_port`
templates can use `{current_port}` to refer to the port before the switch, which
is handy when you have to reach the old manager to tell it to move.

## How state is decided

Each service in `status` carries:

| Field | Meaning |
| --- | --- |
| `state` | `running` / `stopped` |
| `pid` | Process id, `null` when not running or unknown |
| `port` | Where it is running, or where it would come back once stopped |
| `url` | Address, set only while running and only when `url_from_log` is on |
| `managed_by` | `detached` / `launchd` / `null` |

Four things are tried in order:

1. Is the process in the pidfile alive (`ps` state check, then `kill -0`; a
   zombie counts as dead)
2. Is there a launchd agent with the same name, in which case pid and port come
   from launchd
3. Does the service configure `status_cmd`, in which case it is run and parsed
4. Otherwise, `stopped`

So killing a service by hand shows up in `status` immediately rather than being
papered over by a leftover pidfile, and stale pidfiles are cleaned up on the way.

Port and address follow one rule: **report what is true now**. A running
service's port comes from its log, since it may bind somewhere other than where
it was sent, and from LocalSM's own allocation when the log says nothing. Once
stopped, the port becomes where the next start would land: the frozen port under
launchd, the sticky one otherwise. The `url` is dropped when the service stops,
because the dashboard renders it as a link and nothing is listening behind it.

## Reading the URL out of the log

Plenty of dev servers only know their final address once they start: they picked
a different port, or added a random token. `url_from_log: true` makes LocalSM
pull the real URL out of the log, fragment included (`#token=...`), instead of
guessing `http://127.0.0.1:<port>`.

## Externally supervised services

Some services are supervised by something else (brew services, Docker, a
corporate supervisor). LocalSM can neither start nor stop those, but you still
want them in one view. Give them a `status_cmd`:

```yaml
services:
  db:
    start: "brew services start postgresql"
    status_cmd: "brew services info postgresql"
```

LocalSM runs `status_cmd` and counts the service as running when the output
mentions `running`, and as stopped when it mentions `stopped` or `not running`.
It also picks `pid N` and `port N` out of the same output when they are there.

Every field is defined in [Configuration](configuration.md).
