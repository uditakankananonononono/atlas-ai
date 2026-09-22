# Product acceptance harness

`scripts/product_acceptance.py` answers one question honestly: which production
capabilities are **live-verified**, which are **configured but unproven**, and
which are **missing**. It exists so "deployed" never gets claimed from config
files alone.

## The three statuses

| Status | Meaning |
|---|---|
| `accepted` | A live probe ran against the real dependency and passed. |
| `configured` | The setting or artifact exists, but there is no live evidence. Not accepted. |
| `missing` | Neither live evidence nor configuration. Unaccepted. |

The overall verdict is `accepted` only when every check is accepted;
`configured_unaccepted` when nothing is missing but some checks lack live
evidence; `unaccepted` when any check is missing.

## Checks

- **auth_config** - `ProductionConfig.from_env` validation (in production: OIDC
  issuer/audience required, PostgreSQL, Redis, external secret provider).
  Accepted only when the issuer's JWKS endpoint answers with keys.
- **database** - live `SELECT 1` against the configured engine.
- **migrations** - Alembic current revision equals the repo head.
- **redis** - live `PING` against `ATLAS_REDIS_URL`.
- **workers** - broker configured, and accepted only when a Celery worker
  answers `control.inspect().ping()`.
- **adapters** - the production runtime registry
  (`app/runtime/production.py: build_runtime`) reports its registered adapter
  operations and any module without one. Static by nature: stays `configured`.
- **monitoring** - OTel collector config, Grafana dashboard, SLO alert rules,
  and `OTEL_EXPORTER_OTLP_ENDPOINT`. Stays `configured` until alert-firing
  evidence exists.
- **backup_restore** - the runbook plus a restore-drill record
  (`docs/**/*restore*drill*` or `docs/**/*backup*evidence*`). The runbook alone
  is `missing`: the repository makes no backup claim without a drill.

A probe that *fails* against a configured target is `missing`, not
`configured` - a broken live dependency is worse than an unproven one.

## Running

```bash
python scripts/product_acceptance.py            # human-readable, exit 1 if anything missing
python scripts/product_acceptance.py --json     # machine-readable report
python scripts/product_acceptance.py --require-live  # also fail configured-but-unproven
```

Environment is read from the process env (`ATLAS_ENV=production` turns on the
strict config rules). Probes have short timeouts and never print secrets.

## Current honest state (2026-09-23)

Against a fresh checkout with no environment set, the verdict is
**unaccepted**: adapters register (28 operations across 26 modules) and the
auth config validates for development, but there is no live database
migration evidence, no Redis, no workers, no OTLP endpoint, and no
restore-drill record. These move to `configured` as the free-tier deployment
lands, and to `accepted` only when the harness runs against the live stack.

Tests: `tests/test_product_acceptance.py` (9 tests) pins the status rules -
configured checks must never appear as accepted.
