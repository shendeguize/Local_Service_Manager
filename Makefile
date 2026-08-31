UV ?= uv
LOCALSM ?= ./LocalSM

.PHONY: install lint test test-js docs hygiene cov check build package-npm release-preflight smoke doctor web clean

install:
	$(UV) tool install --editable . --force

lint:
	$(UV) run ruff check scripts/ src/ tests/
	$(UV) run ruff format --check scripts/ src/ tests/

test:
	$(UV) run pytest

test-js:
	@for file in src/localsm/static/*.js packages/npm/bin/*.js; do node --check "$$file"; done
	npm test --prefix packages/npm

docs:
	$(UV) run python scripts/check_docs.py

hygiene:
	$(UV) run python scripts/check_repo_hygiene.py

check: lint test test-js docs hygiene

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
