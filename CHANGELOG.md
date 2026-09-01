# Changelog

All notable changes to LocalSM are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and versions follow [Semantic Versioning](https://semver.org/).

## [0.3.4] - 2026-09-01

### Added

- Describe the user-visible changes in this release.

## [Unreleased]

### Fixed

- A version bump no longer leaves the installed package metadata behind, which
  failed `make release-preflight` on the release branch until someone
  reinstalled the package by hand. uv decides whether a local build is current
  from the files in `cache-keys`, which defaults to `pyproject.toml` alone —
  and this project reads its version from `src/localsm/__init__.py`.

## [0.3.3] - 2026-09-01

### Changed

- A service's `env` now covers the same commands `working_dir` does. It reached
  only `start`, so a service needing a token to come up ran without it when
  being stopped, asked for its status, told to change port, or used as the
  context for `LocalSM exec`.
- `logs --lines` requires a positive count. Zero printed the whole log, since a
  tail of `[-0:]` is the entire list, and a negative count dropped that many
  lines off the front instead.
- A taken preferred port now says which port is in the way and that
  `--auto-port` opens the pool, instead of "no free port found" while the pool
  sat unused.

### Fixed

- `remote scan` finds the listeners on hosts that have none of `ss`, `lsof` or
  `netstat`. The `/proc/net/tcp` fallback writes a bare port per line and the
  parser required a colon, so the scan reported no open ports at all on the
  slim images these hosts often are — which also left tunnel coverage blank.
- `edit tunnels` summarises the tunnels that changed. It diffed the services
  either way, so it reported that no service definitions had changed and said
  nothing about the file just edited.
- The dashboard answers with JSON rather than an HTML 500 page when a
  `set-port` request carries no usable port, or when `services.yaml` does not
  parse — the state it is in while being edited.
- `LocalSM ssh --app ghostty` reports a launch that failed. It never waited for
  `open`, so a missing Ghostty still produced `{"launched": ...}`.
- `tunnel list` reports no pid for a stopped tunnel instead of the dead one left
  in its pidfile.
- The CLI contract documents `enable`, `disable`, and both forms of `edit`, and
  states that `completion` ignores `--json`.

## [0.3.2] - 2026-09-01

### Fixed

- `doctor` prints one heading per section. The per-service checks landed between
  the local tool checks, so `[本地工具]` appeared twice with an unrelated section
  in between. The report now groups by section, which also keeps a future
  insertion from splitting one.
- The installation guide no longer suggests writing the zsh completion to
  `${fpath[1]}`, which under oh-my-zsh is a plugin directory that a plugin
  update overwrites.

## [0.3.1] - 2026-09-01

### Added

- A website at <https://shendeguize.github.io/Local_Service_Manager/>, built
  from the same sources as the product: the documentation is copied out of
  `docs/`, and the simulated dashboard it hosts is the real dashboard with only
  its HTTP layer replaced by an in-browser state machine. The payloads that
  state machine starts from are recorded from a real LocalSM, so the site build
  fails when the web API changes without them.

### Changed

- `up` refuses an explicit `--port` that it cannot honour instead of reporting
  success without moving anything. A service already running on the requested
  port is still a no-op, and `--auto-port` is still satisfied by any running
  service.
- `doctor` checks the ssh hosts LocalSM's own tunnels use, rather than every
  host in `~/.ssh/config`. An unrelated machine being down is not a LocalSM
  fault, and a diagnostic should not open connections to hosts nobody pointed
  LocalSM at. With no tunnels configured the section is skipped.

### Fixed

- A stopped service no longer advertises the address from its log. The
  dashboard renders that address as a link with a copy button, and nothing is
  listening behind it. Its port now reports where the next start would land —
  the frozen port under launchd, the sticky one otherwise — so the two fields
  answer the same question: what is true now.
- `status` reports the port LocalSM allocated when a running service's log does
  not mention one. A service whose stdout is still buffered — including the
  `python3 -m http.server` example `init` writes — appeared to be running on no
  port at all, in both the CLI and the dashboard.
- A tunnel that fails to start quotes what ssh said, instead of only its exit
  code. "exited with code 255" sent the reader to the log file to discover a
  misspelled host.
- `LocalSM logs` no longer leaves the shell prompt on the same line as the
  output when a log's last line has no newline.
- Dashboard icons rendered in a context without their own size rule, such as
  the host column of the remote table, no longer stretch to fill the cell.
- The dashboard's service table shows its state in the same language as the
  rest of the interface.

## [0.3.0] - 2026-09-01

### Added

- `LocalSM enable <service>` and `LocalSM disable <service>` hand a service to
  launchd and take it back, so it starts at login and is restarted when it
  dies. Supervision is opt-in per service; detached remains the default. The
  port is frozen into the agent at `enable` time, because launchd starts the
  service with no LocalSM process in attendance to negotiate one.
- `LocalSM edit` opens a configuration file in `$EDITOR` and reports which
  services were added, removed, or changed, and which running services need a
  restart.
- `LocalSM completion zsh|bash` prints a completion script generated from the
  parser, so completions cannot drift from the commands. The scripts call
  `LocalSM completion services` for real service names, meaning a new service
  needs no regeneration.
- `LocalSM web --foreground` runs the dashboard in the current terminal.
- A read-only `GET /api/config` endpoint, and a configuration section in the
  dashboard showing paths, the port pool, and each service's definition.
- `docs/zh/` and `docs/en/` now carry a full page set: install, quickstart,
  configuration, services, launchd, tunnels, remote, web, cli-contract,
  cli-reference, architecture, and troubleshooting.

### Changed

- The dashboard rejects requests whose `Host` header is not a loopback name,
  closing the DNS-rebinding path to an API that can start processes. Add names
  with `LOCALSM_WEB_ALLOWED_HOSTS` when a local hosts alias is needed.
- The dashboard rebuilds its ServiceManager when `services.yaml` changes on
  disk, so a config edit shows up on the next refresh without a restart.
- `status` reports `managed_by` (`detached` or `launchd`) and, for a supervised
  service, reads its pid and frozen port from `launchctl`.
- `docs/cli-reference.md` is generated for both languages, and
  `scripts/check_docs.py` verifies that every `docs/zh/` page has an
  English counterpart with the same heading structure. Maintainer-facing
  `docs/releasing.md` is exempt.
- The READMEs point at the generated CLI reference instead of carrying a
  hand-maintained command list that drifted.

## [0.2.0] - 2026-09-01

### Added

- `LocalSM init` writes a commented starter configuration and never overwrites
  an existing file.
- Global `--json` and `--quiet` flags on every command, accepted either before
  or after the subcommand. The output shapes and the exit-code convention are
  documented in the CLI contract page.

### Changed

- **Breaking.** Configuration now lives in `~/.config/localsm/` and runtime
  state in `~/.local/state/localsm/`, following the XDG base directories.
  LocalSM no longer derives these paths from its own install location. Set
  `LOCALSM_ROOT` to keep both inside a source checkout, or use
  `LOCALSM_CONFIG_DIR` and `LOCALSM_STATE_DIR` individually.
- `doctor` derives its service-CLI checks from the configured services instead
  of a hardcoded list, and reports a missing `services.yaml` as a failure that
  points at `LocalSM init`.
- `scripts/smoke.sh` takes its service list from `LocalSM --json config`
  instead of hardcoded service names.
- Personal `config/*.yaml` files are no longer tracked; only
  `config/services.example.yaml` is. `make hygiene` now fails when a real
  config is committed.

### Fixed

- A wheel or npm installation resolved its configuration directory to a random
  path inside uv's cache, which never exists and is erased by `uv cache prune`.
  Nothing reported this: `status` printed nothing, and `doctor` passed every
  check against a configuration that was not there. Commands now name the
  configuration path they expect and point at `LocalSM init`.

## [0.1.2] - 2026-09-01

### Changed

- The npm package now bundles the matching LocalSM wheel, so npm installation
  no longer depends on LocalSM being published to PyPI.
- The npm installation script now automatically installs `uv` with the
  official installer when it is not already available.
- Release builds now publish the npm package from GitHub Actions through the
  npm trusted-publisher environment.

### Fixed

- The published 0.1.1 npm package shipped without a wheel and resolved
  `local-sm` from PyPI, where it does not exist, so every
  `npx @shendeguize/local-sm` call failed. The launcher now runs the bundled
  wheel.
- The tag workflow now dispatches the release workflow explicitly. Tags pushed
  with `GITHUB_TOKEN` raise no push event, so releases were never built.
- The release workflow now builds from the released tag instead of `main` when
  it is started manually.

## [0.1.1] - 2026-09-01

### Fixed

- The npm launcher invoked uv with the nonexistent `uv x` subcommand, so
  every `npx @shendeguize/local-sm` call failed; it now uses `uv tool run`.
- Local npm publishes are pinned to registry.npmjs.org via `publishConfig`
  so mirror registries configured in `~/.npmrc` are never targeted.

## [0.1.0] - 2026-09-01

### Added

- Local service lifecycle management with detached processes, pidfiles, logs,
  port allocation, and configurable commands.
- Web dashboard and CLI for service, log, SSH, remote scan, and tunnel control.
- SSH host scanning with listener discovery and tunnel coverage reporting.
- Explicit SSH local tunnel lifecycle management.
