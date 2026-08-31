UV ?= uv
LOCALSM ?= ./LocalSM

.PHONY: install test cov smoke doctor web clean

install:
	$(UV) tool install --editable . --force

test:
	$(UV) run pytest

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
