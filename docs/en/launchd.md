# launchd service mode

By default a LocalSM service is an ordinary process detached from the terminal:
closing the terminal does not affect it, but a reboot takes it away and a crash
does not bring it back. For start-at-login and crash recovery, hand the service
to macOS launchd.

launchd supervision is **opt-in per service**, not a global switch. Detached is
still the default mode.

## Handing over and taking back

```sh
LocalSM enable api                # hand to launchd
LocalSM enable api --port 8080     # choose the port to freeze
LocalSM disable api               # take back
LocalSM status api                # managed_by shows who owns it
```

`enable` does four things in order:

1. If LocalSM is currently running the service detached, stop it first: launchd
   cannot bind a port somebody else still holds
2. Decide the port and **freeze** it into the plist, either through the usual
   sticky allocation or from `--port`
3. Write `~/Library/LaunchAgents/com.localsm.<service>.plist`
4. `launchctl bootout` the previous generation, then
   `launchctl bootstrap gui/<uid>` the new one; `RunAtLoad` starts it right away

Booting out before bootstrapping is necessary: launchd will not replace a label
that is already loaded, so a repeat `enable` without the unload would leave the
new plist inert.

`disable` reverses it: `launchctl bootout`, remove the plist, and the service
returns to LocalSM. It is safe on a service that was never enabled; it just says
so.

## Why the port has to be frozen

When launchd starts the service there is no LocalSM process in attendance:
nobody can probe for a free port, update `ports.json`, or substitute `{port}` in
the command template. So the port is settled at `enable` time, rendered into the
command line in the plist and also exposed as the `LOCALSM_PORT` environment
variable for the service to read.

`status` reads that frozen port back out of the plist, so you can see which port
a service will use even while it is not running.

## What the commands do while supervised

| Command | Behaviour |
| --- | --- |
| `up` | Delegates to `launchctl kickstart` |
| `down` | Refuses, and points at `disable`; launchd would restart it |
| `restart` | Delegates to `launchctl kickstart -k` |
| `status` | Reads pid and last exit status from `launchctl list` |
| `set-port` | Rewrites and reloads the plist with the new port |
| `up --port` / `restart --port` / `--auto-port` | Refused; the port is frozen |

`down` refuses rather than trying its best because the plist sets `KeepAlive`:
kill the process and launchd brings it back within seconds, so pretending to
have succeeded would only confuse. Use `disable` to actually stop it.

`up` and `restart` with a port are refused because those flags mean "run on this
port this time", while under launchd the port is a property of the plist rather
than of one start. To change it, use `LocalSM set-port`, or `disable` and `enable`
again.

## What the generated plist looks like

The keys that matter:

- `Label`: `com.localsm.<service>`
- `ProgramArguments`: `[$SHELL, "-lc", "<start command with the port frozen>"]`.
  A login shell keeps the service's PATH and environment the same as the one you
  wrote the command against interactively
- `RunAtLoad`, `KeepAlive`: start at login, restart on exit
- `ThrottleInterval`: 10 seconds, stated explicitly rather than relying on the
  platform default so the plist is self-documenting
- `StandardOutPath` / `StandardErrorPath`: both point at
  `~/.local/state/localsm/logs/<service>.log`, the same file the detached path
  appends to
- `WorkingDirectory`: the service's `working_dir` when set
- `EnvironmentVariables`: the service's `env` plus `LOCALSM_PORT`

Using one log path is deliberate: switching supervisors should not send you
looking elsewhere for logs, and `LocalSM logs` behaves the same either way.

## Debugging a supervised service

A non-zero `last_exit_status` in `status --json` means the service crashed on
startup. The log is where it always was:

```sh
LocalSM logs api --lines 100
```

For the system's own view:

```sh
launchctl print gui/$(id -u)/com.localsm.api
```

The plist is ordinary XML and can be read to confirm the frozen port and the
command. Do not edit it by hand, though: the next `enable` rewrites the whole
file and your change is gone.

## When not to use launchd

launchd suits services you want always present: a local database, a proxy, a
long-lived background job. It suits a dev server you touch ten times a day much
less; there, `LocalSM restart` on the detached path is faster and will not have
`KeepAlive` respawning the process while you are debugging a crash.
