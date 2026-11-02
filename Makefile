PY ?= .venv/bin/python
PIPELINE = $(PY) -m isolated_italy

.PHONY: install lint test web-test build data deploy

install:
	python3 -m venv .venv
	.venv/bin/pip install -e ".[dev]"
	cd web && npm ci

lint:
	.venv/bin/ruff check src tests infra/lambda
	.venv/bin/ruff format --check src tests infra/lambda
	.venv/bin/cfn-lint infra/template.yaml
	cd web && npm run lint

test:
	.venv/bin/python -m pytest -q
	cd web && npm test

build:
	cd web && npm run build

# Full data pipeline. Needs AWS credentials for the last two stages and the pharmacy register CSV (see README).
data:
	$(PIPELINE).buildings --resolution 8
	$(PIPELINE).buildings --resolution 9
	$(PIPELINE).places
	$(PIPELINE).admin
	$(PIPELINE).pharmacies
	$(PIPELINE).distances
	$(PIPELINE).population
	$(PIPELINE).export
	$(PIPELINE).services_bin
	$(PIPELINE).sites
	$(PIPELINE).validate
	$(PIPELINE).lakehouse

deploy:
	./infra/deploy.sh
