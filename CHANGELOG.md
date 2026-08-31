# Changelog

All notable changes to LocalSM are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and versions follow [Semantic Versioning](https://semver.org/).

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
