.PHONY: install test acceptance compose-check local-up local-down
install:
	python -m pip install -e '.[dev]'
test:
	pytest -q
acceptance:
	python scripts/module_acceptance.py --check --output docs/MODULE_ACCEPTANCE_EVIDENCE.json
compose-check:
	docker compose --env-file .env.local -f deploy/local/docker-compose.yml config --quiet
local-up:
	./scripts/bootstrap_local.sh
local-down:
	docker compose --env-file .env.local -f deploy/local/docker-compose.yml down
