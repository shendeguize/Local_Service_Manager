# Building the website

The website at <https://shendeguize.github.io/Local_Service_Manager/> lives in
`site/` and is built from the product rather than alongside it. Nothing on it is
written twice: the documentation is copied out of `docs/`, and the simulated
dashboard is copied out of `src/localsm/static`. `.github/workflows/site.yml`
deploys it whenever any of those change on `main`, and builds it without
deploying on a pull request.

Like `docs/releasing.md`, this page is for maintainers and is deliberately
monolingual.

## Pieces

| Source | Script | Lands in |
| --- | --- | --- |
| `docs/zh`, `docs/en` | `scripts/sync_site_docs.py` | `site/src/content/docs/` |
| `src/localsm/static`, `templates/index.html` | `scripts/build_demo.py` | `site/public/demo/` |
| `site/demo/scenario.yaml` through a real LocalSM | `scripts/gen_demo_fixtures.py` | `site/public/demo/fixtures.json` |
| `site/demo/tapes/*.tape` through a real LocalSM | `scripts/record_demo.sh` | `site/public/media/` |

Only the last two produce committed files. The rest is generated on every build
and git-ignored, because a copy in the repository would be a second place to
maintain the same text.

## Running it locally

```sh
make site-dev     # sync docs, build the demo, start the dev server
make site         # what CI builds, into site/dist
```

## The simulated dashboard

`scripts/build_demo.py` copies the dashboard verbatim and replaces exactly one
file: `static/api.js`, the only module that talks to the backend.
`site/demo/mock-api.js` takes its place and answers from memory, so a visitor
drives the real interface. Two checks run on every build and fail it rather than
shipping a demo that has drifted:

- the mock must export exactly the methods the real client exports, so a new
  endpoint cannot reach the demo unsimulated;
- no other module may call `fetch`, so `api.js` stays the only seam.

`site/demo/mock-api.test.js` covers the transitions themselves, including the
refusals: stopping a launchd-managed service fails in the demo the way it fails
on a real machine. It runs under `make test-js`.

The state the demo opens with comes from `site/public/demo/fixtures.json`, which
`scripts/gen_demo_fixtures.py` records by driving the real Flask app through its
test client against a sandbox seeded from `site/demo/scenario.yaml`. The
scenario's services are genuinely started, so the recorded payloads are the
product's, not an idea of them. Two values are real for capture and fictional
for display: a service's `working_dir` is created inside the sandbox and mapped
back to a plausible path, and its start command is an inert `echo` mapped back to
the `shown_as` command the demo displays. The remote scan is the exception —
those hosts do not exist, so the scan's values are written by hand and only its
field names are checked against a real scan.

When the web API changes, regenerate and review the result:

```sh
make demo-fixtures
```

CI runs the same script with `--check`, so forgetting fails the site build.

## The terminal recording

```sh
make demo-cast    # needs `brew install vhs`
```

`scripts/record_demo.sh` seeds a throwaway LocalSM home from the same scenario,
puts it on `PATH`, and runs every tape in `site/demo/tapes`. It never reads or
writes your own configuration. The GIFs are committed because CI has no terminal
to record in; re-record when the output of the commands in a tape changes.
