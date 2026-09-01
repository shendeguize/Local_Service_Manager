# Remote scans

A remote scan answers one question: on the hosts in my SSH config, what is
listening right now? It is for people who SSH into a pile of dev boxes, pods, and
machines behind jump hosts, and would rather not log into each one to type
`ss -ltn`.

## Usage

```sh
LocalSM remote scan                  # every host in ssh config
LocalSM remote scan pod-a pod-b      # only the named hosts
LocalSM remote scan --timeout 15
LocalSM --json remote scan
```

The result is also written to `~/.local/state/localsm/remote_scan.json`. The web
dashboard reads that cache, so opening the dashboard does not trigger a fresh
scan.

## Where the hosts come from

LocalSM parses `~/.ssh/config`, takes the aliases from `Host` blocks, and notes
`HostName`, `Port`, `User`, and `ProxyJump`. Aliases containing wildcards (`*`,
`?`, `!`) are skipped: `Host *` is a block of defaults, not a machine you can
connect to.

LocalSM does not reimplement SSH's connection logic; it invokes `ssh` with the
alias and lets SSH handle jump hosts, keys, and ports from your config. So if
`ssh my-pod` works, the scan works.

## How the scan works

For each host, LocalSM runs one probe script over a single SSH connection, trying
these in order of availability:

1. `ss -ltnH` (modern Linux)
2. `lsof -nP -iTCP -sTCP:LISTEN` (macOS and older Unix)
3. `netstat -lnt`
4. A Python fallback that reads `/proc/net/tcp` and `/proc/net/tcp6`

Only when all four are missing does it report an error. That fallback chain
exists so scans work inside stripped-down containers: plenty of pod images have
neither `ss` nor `netstat`, but almost always have `python3`.

The connection options are fixed: `BatchMode=yes` (never prompt for a password,
which would otherwise hang a concurrent scan waiting on your input),
`ConnectTimeout` (8 seconds by default, adjustable with `--timeout`), and
`StrictHostKeyChecking=accept-new` (accept a host key on first connection, but
still refuse a changed one).

Hosts are scanned in parallel, up to 12 at a time.

## Reading the result

One record per host:

| Field | Meaning |
| --- | --- |
| `host` | The alias from ssh config |
| `reachable` | Whether the probe connected and completed |
| `ports` | Listening ports found, deduplicated and sorted |
| `tunnels` | Map from port to the names of tunnels covering it |
| `error` | Failure reason, `null` on success |

The `tunnels` field is where this becomes genuinely useful: it lines up "what is
out there" with "what I already forward", so uncovered ports are one query away:

```sh
LocalSM --json remote scan \
  | jq -r '.[] | . as $h | .ports[] | select(($h.tunnels[tostring] | length) == 0) | "\($h.host):\(.)"'
```

## reachable versus error

Failures come in two kinds, and LocalSM distinguishes them on purpose:

- Network-level failures (connection timed out or refused, name not resolvable,
  permission denied) produce `reachable: false`
- Connected but the probe failed (all four probe tools missing, say) produces
  `reachable: true` with the reason in `error`

The distinction tells you whether to fix your SSH config or the remote
environment.

## In the dashboard

The dashboard's remote section shows the same data, with tunnel coverage next to
each port, and lets you create a tunnel for an uncovered port directly. See
[Web dashboard](web.md) and [SSH tunnels](tunnels.md).

## Opening an SSH session

To log in and look around after a scan:

```sh
LocalSM ssh my-pod              # Ghostty by default
LocalSM ssh my-pod --app terminal
```

That opens a new window or tab running `ssh my-pod` in the terminal application,
leaving your current shell alone.
