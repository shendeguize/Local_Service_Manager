# @shendeguize/local-sm

This package is a self-contained npm launcher for the LocalSM Python CLI. It
includes the matching LocalSM wheel, so it does not require the LocalSM
project to be published on PyPI.

Install Node.js 18+ first, then run:

```sh
npx @shendeguize/local-sm --version
```

The launcher installs `uv` with Astral's official installer on first run when
it is not already available, so no separate setup step is needed. The package
also ships an install script that does the same thing earlier, but recent npm
versions block lifecycle scripts by default, so the launcher's own check is
what usually performs the installation.

`uv` creates an isolated environment from the bundled wheel and downloads
only LocalSM's public runtime dependencies. The npm package is the direct
installation channel; it does not bundle Python itself.

For the full LocalSM documentation, see the
[repository README](https://github.com/shendeguize/Local_Service_Manager).
