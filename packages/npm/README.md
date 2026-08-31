# @shendeguize/local-sm

This package is a self-contained npm launcher for the LocalSM Python CLI. It
includes the matching LocalSM wheel, so it does not require the LocalSM
project to be published on PyPI.

Install Node.js 18+ first, then run:

```sh
npx @shendeguize/local-sm --version
```

The npm install script automatically installs `uv` with the official installer
when it is not already available. The launcher retries this check at runtime,
so it also works when npm lifecycle scripts were disabled.

`uv` creates an isolated environment from the bundled wheel and downloads
only LocalSM's public runtime dependencies. The npm package is the direct
installation channel; it does not bundle Python itself.

For the full LocalSM documentation, see the
[repository README](https://github.com/shendeguize/Local_Service_Manager).
