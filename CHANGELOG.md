# Changelog

All notable changes to LocalSM are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and versions follow [Semantic Versioning](https://semver.org/).

## [0.2.0] - 2026-09-01

### Added

- `LocalSM init` writes a commented starter configuration and never overwrites
  an existing file.
- Global `--json` and `--quiet` flags on every command, accepted either before
  or after the subcommand. `docs/cli-contract.md` documents the output shapes
  and the exit-code convention.

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
