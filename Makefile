UV ?= uv
LOCALSM ?= ./LocalSM

.PHONY: install lint test test-js docs docs-cli hygiene cov check build package-npm release-preflight smoke doctor web clean \
	site site-dev site-docs demo demo-fixtures demo-cast

install:
	$(UV) tool install --editable . --force

lint:
	$(UV) run ruff check scripts/ src/ tests/
	$(UV) run ruff format --check scripts/ src/ tests/

test:
	$(UV) run pytest

test-js:
	@for file in src/localsm/static/*.js packages/npm/bin/*.js site/demo/*.js; do node --check "$$file"; done
	npm test --prefix packages/npm
	node --test site/demo/mock-api.test.js

docs:
	$(UV) run python scripts/check_docs.py
	$(UV) run python scripts/gen_cli_reference.py --check

docs-cli:
	$(UV) run python scripts/gen_cli_reference.py

hygiene:
	$(UV) run python scripts/check_repo_hygiene.py

check: lint test test-js docs hygiene
	$(UV) run python scripts/build_demo.py --verify

# The website. `site` builds what Pages deploys; the demo it embeds is the real
# dashboard, so it is rebuilt from src/localsm/static every time.
site: site-docs demo
	npm --prefix site ci
	npm --prefix site run build

site-dev: site-docs demo
	npm --prefix site run dev

site-docs:
	$(UV) run python scripts/sync_site_docs.py --quiet

demo:
	$(UV) run python scripts/build_demo.py

# Replays the demo scenario through a real LocalSM and records what it answers.
# Only needed when the web API changes; the result is committed.
demo-fixtures:
	$(UV) run python scripts/gen_demo_fixtures.py

demo-cast:
	./scripts/record_demo.sh

build:
	$(UV) build

package-npm:
	rm -rf dist packages/npm/wheel
	$(UV) build
	mkdir -p packages/npm/wheel
	set -- dist/*.whl; test "$$#" -eq 1; cp "$$1" packages/npm/wheel/

release-preflight: check build

cov:
	$(UV) run pytest --cov-report=term-missing --cov-report=html

smoke:
	./scripts/smoke.sh

doctor:
	$(LOCALSM) doctor

web:
	$(LOCALSM) web

clean:
	$(LOCALSM) down
	$(LOCALSM) tunnel rm smoke || true
