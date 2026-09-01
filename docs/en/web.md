# Web dashboard

The dashboard is LocalSM's console: every service's state, port, and log on one
screen, start and stop in one click, plus remote scan results and tunnel
management. It is not a configuration editor; service definitions are read-only
there.

## Starting it

```sh
LocalSM web                # detached, as an ordinary LocalSM service
LocalSM web --foreground   # in this terminal, Ctrl-C to stop
```

It defaults to `http://127.0.0.1:8765/`. `web` is itself a service in
`services.yaml` (the template `init` writes includes it), so `LocalSM status`,
`LocalSM logs web`, and `LocalSM enable web` all work on it.

`--foreground` suits debugging the dashboard itself, or wanting a temporary one
that stops when you close the terminal.

## Security model

The dashboard has **no authentication, permanently**, and relies on three
boundaries instead:

1. It binds `127.0.0.1` only and accepts no connections from the network
2. It validates the `Host` header and answers only loopback names (`127.0.0.1`,
   `localhost`, `::1`)
3. Remote access goes through an SSH tunnel rather than exposing it

Leaving out a login page is deliberate: this is a single-user local tool, and a
password would add a credential to maintain while stopping nobody who can already
run code on your machine.

### What Host validation actually stops

The dashboard's API can start processes, which amounts to code execution on this
machine. Binding to loopback alone does not stop DNS rebinding: an attacker
controls a domain, points it at `127.0.0.1`, and your browser then sends requests
to your dashboard on behalf of the attacker's JavaScript. The bind address is
satisfied throughout, because the requests really do come from this machine.

Validating the `Host` header closes that path: the header the browser sends is
the attacker's domain, not a loopback name, so the request gets a 403.

To let the dashboard answer other names (a local hosts alias pointing at
127.0.0.1, for instance):

```sh
LOCALSM_WEB_ALLOWED_HOSTS=dev.local,box.internal LocalSM web
```

Separate names with commas. This is an explicit allowlist and does not change the
fact that the bind address stays on loopback.

## The sections

- **Services**: state, pid, port, URL, `managed_by`; start, stop, restart, change
  port, and pull up the log drawer
- **Configuration**: the read-only view from `/api/config` — config file paths,
  the port pool, and each service's `start` and `working_dir`. To change any of
  it, use `LocalSM edit`
- **Remote**: hosts and listening ports from the `remote_scan.json` cache with
  tunnel coverage, with rescan and create-a-tunnel actions
- **Tunnels**: rules and their state, plus create, remove, and `ensure`
- **SSH**: open a terminal window to any host

## Config awareness

The dashboard does not need a restart to see a new service. Every request checks
the mtime and size of `services.yaml` and rebuilds the ServiceManager when they
change. So the flow is:

```sh
LocalSM edit        # change the config, save, exit
```

The new service appears on the next of the front end's five-second refreshes.

Only `services.yaml` is watched, rather than the whole config directory, because
service definitions are the one thing the dashboard needs to notice; tunnel rules
are read fresh on every request anyway.

## API

The front end uses this HTTP API, and scripts can call it directly. Every path is
covered by Host validation:

| Method and path | Purpose |
| --- | --- |
| `GET /api/services` | Every service's status |
| `POST /api/services/<name>/<action>` | `up` / `down` / `restart` / `set-port` |
| `GET /api/config` | Read-only config view |
| `GET /api/logs/<name>?lines=N` | Log tail, N capped at 500 |
| `GET /api/remote` | Last scan result and its timestamp |
| `POST /api/remote/scan` | Trigger a scan |
| `GET /api/tunnels` | Tunnel rules and state |
| `POST /api/tunnels` | Create a tunnel |
| `POST /api/tunnels/ensure` | Rebuild dead tunnels |
| `DELETE /api/tunnels/<name>` | Remove a tunnel |
| `POST /api/ssh/<host>` | Open an SSH terminal window |

A failed service or tunnel action returns 400 with `{"error": "..."}`. For
scripting, the CLI's `--json` output is the more stable interface; see
[Output contract](cli-contract.md).

## Remote access

To reach the dashboard from another machine, forward it rather than changing the
bind address:

```sh
# on the remote machine
ssh -N -L 8765:127.0.0.1:8765 your-mac
```

Then open `http://127.0.0.1:8765/` there: the `Host` is a loopback name, so
validation passes.
