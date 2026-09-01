# Quickstart

This assumes LocalSM is installed; see [Installation](install.md).

## 1. Create the starter configuration

```sh
LocalSM init
```

This writes commented `services.yaml` and `tunnels.yaml` files into
`~/.config/localsm/`. `init` never overwrites an existing file, so running it
again is safe.

## 2. Define your services

```sh
LocalSM edit
```

`edit` opens `services.yaml` in `$EDITOR`, and on exit tells you which services
were added, removed, or changed, and which running services need a restart for
the change to take effect.

A minimal definition only needs `start`:

```yaml
port_pool: [8000, 8999]

services:
  api:
    start: "uvicorn app:api --port {port}"
    preferred_port: 8080
    url_from_log: true
```

`{port}` is replaced with the port LocalSM allocated. `url_from_log: true` makes
LocalSM read the real address out of the log rather than guessing it. Every field
is listed in [Configuration](configuration.md).

## 3. Start and inspect

```sh
LocalSM up api        # start one service
LocalSM up            # start every service
LocalSM status        # state, pid, port, URL
LocalSM logs api      # tail the log
LocalSM down api      # stop
```

When the port is taken, `--auto-port` lets LocalSM pick a free one from the pool:

```sh
LocalSM up api --auto-port
```

LocalSM remembers the port each service last used successfully, so a restart
usually lands back on the same port.

## 4. Open the dashboard

```sh
LocalSM web
```

The dashboard defaults to `http://127.0.0.1:8765/`. It offers start and stop,
port changes, a log drawer, remote scans, SSH terminals, and tunnel management.
To run it in the current terminal and stop it with Ctrl-C:

```sh
LocalSM web --foreground
```

## 5. Start a service at login

```sh
LocalSM enable api
```

This writes a launchd agent that starts the service at login and restarts it when
it dies. To hand it back to LocalSM:

```sh
LocalSM disable api
```

The details, and why the port gets frozen, are in
[launchd service mode](launchd.md).

## Scripting

Every command accepts `--json`. The wording of the human-readable output is not
covered by any compatibility promise, so scripts should always use `--json`:

```sh
# list the running services
LocalSM --json status | jq -r '.[] | select(.state == "running") | .name'

# check the environment quietly in CI
LocalSM --quiet doctor --local-only || echo "environment is unhealthy"
```

The full contract is in [Output contract](cli-contract.md).

## Next

- Listening ports on remote hosts: [Remote scans](remote.md)
- Forwarding remote ports to this machine: [SSH tunnels](tunnels.md)
- Something is broken: [Troubleshooting](troubleshooting.md)
