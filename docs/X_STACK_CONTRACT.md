# X-STACK: ordered local Compose pair contract

Config-render acceptance only. No Docker run, build, pull, Vault provisioning,
TLS service boot, RabbitMQ delivery, tracing or Loki/Grafana ingestion is proven.
No new services are added by this unit. Existing single-override files are unchanged.

Use `deploy/local/docker-compose.yml` first. The root `docker-compose.yml` is a
different development topology with beat/ollama and is NOT a supported base.
Exactly these pairs are supported, with the final layer listed last:

| Pair | Ordered overrides | Final layer |
| --- | --- | --- |
| vault+loki | vault, loki | deploy/local/stacking/vault-loki.yml |
| otel+loki | otel, loki | deploy/local/stacking/otel-loki.yml |
| rabbitmq+vault | vault, rabbitmq | deploy/local/stacking/rabbitmq-vault.yml |
| mtls+vault | vault, mtls | deploy/local/stacking/mtls-vault.yml |
| grafana+otel | grafana, otel | deploy/local/stacking/grafana-otel.yml |

Commands/entrypoints are replacement fields, not appended by Compose. Mapping
keys merge, volumes/configs use target uniqueness, and published ports have
IP/target/published/protocol uniqueness. Source:
https://docs.docker.com/reference/compose-file/merge/

## Explicit replacements

- vault+loki: Loki's logging_bootstrap command replaces base/Vault api/worker
  commands; Vault's entrypoint still injects runtime secrets and execs that
  command. migrate keeps its Vault entrypoint and migration command.
- otel+loki: both single-override api/worker commands are deliberately replaced
  by stacked_observability_bootstrap. It installs JSON logging, uses the same
  OTEL provider/probe/auth/middleware and solo worker trace startup. API passes
  JSON log_config to Uvicorn so its startup cannot silently reset logging.
- rabbitmq+vault: RabbitMQ's broker-export/startup shell command and constrained
  Dockerfile win. Vault entrypoint is retained and execs the shell after secrets.
  This tests config/wiring, not an image build or actual broker/pin acceptance.
- mtls+vault: mTLS check-and-start commands win, including migrate and worker.
  mTLS database/Redis URLs and TLS healthchecks win. Vault entrypoint remains.
  This is a dev-volume root-user configuration, not production hardening.
- grafana+otel: application commands stay OTEL; Grafana/Prometheus configs stay
  intact. No logging integration or trace-to-dashboard linkage is claimed.
- Every pair's final layer replaces api ports with 127.0.0.1:8000:8080.
  Grafana+OTEL also replaces Grafana/Prometheus ports with loopback bindings.
  Other inherited published ports were already loopback and are pinned.

Every exact rendered key, including commands, entrypoints, environments, build,
healthchecks, volumes, dependencies, networks, configs and ports, is frozen in
expected.json. Relative repository paths are normalized only for portability.
This snapshot is review evidence, not self-certifying acceptance. Tests add
independent explicit critical assertions and reject command/entrypoint/network/
loopback mutations. The read-receipts file pins every original compose source,
including the overrides not selected in these five recipes. Future source drift
must trigger review, not automatic fixture regeneration.

## Config-only verification

Docker Compose v2.39.4 standalone binary was fetched from the Docker project's
release assets and matched the release SHA256 file. `config --format json` does
not need a daemon. Tests require ATLAS_COMPOSE_BINARY pointing to an installed
Compose binary; absence fails, it is not a passing skip or YAML emulation.

Run from repository root:

```
ATLAS_COMPOSE_BINARY=/path/to/docker-compose PYTHONPATH=backend:. \
  python -m pytest tests/deploy/test_override_stacking.py
```

The tests use public parse-only fixture strings for required interpolation,
including nonexistent log directories. They do not validate actual log mounts,
OIDC issuer availability, runtime secrets, hardware or external service cost.
The Vault env_file contains public-demo material and makes no confidentiality
claim. expected.json contains those public fixtures only, not real credentials.

Operator syntax for a pair (use real required environment values, do not start
from fixture credentials):

```
docker compose -f deploy/local/docker-compose.yml \
  -f deploy/local/docker-compose.vault.yml \
  -f deploy/local/docker-compose.loki.yml \
  -f deploy/local/stacking/vault-loki.yml config --format json
```

The snapshot validator is intended only for the documented parse-only inputs.
Runtime values differ, so passing a real-secret render into it is not supported.
Do not attach real-secret renders to bug reports. No combinations of three or
more overrides, reverse-order recipes or pairs outside this table are covered.
All named gaps in the original overrides remain open.
