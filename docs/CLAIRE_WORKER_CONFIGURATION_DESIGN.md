# Claire worker configuration: bounded next slice

Status: design preparation only. Depends on the local ModelPort adapter candidate.
No production process started, no deployment change or main integration.

## Observed gap

The mounted /claire/runtime/goals routes instantiate a durable GoalStore from
ATLAS_CLAIRE_RUNTIME_DB. They have no worker process or selected-model configuration.
Worker exists as a class, used by tests. A mounted queue is not execution readiness.

## Proposed seam

A configuration object reads only explicit Claire runtime environment keys:
- ATLAS_CLAIRE_RUNTIME_DB, required, durable SQLite file or PostgreSQL URL.
- ATLAS_CLAIRE_MODEL_PROVIDER, required, ornith / inkling / hermes.
- ATLAS_CLAIRE_MODEL_URL and ATLAS_CLAIRE_MODEL_NAME, both required.
- Worker identifier, bounded step/call/lease settings and opt-in development schema.

Refuse in-memory SQLite, missing/unknown values, non-loopback model URLs, credential-
bearing model URLs and call deadlines that can outlast the lease. Database secrets
must never be included in repr, exception output, model context or startup logs.
Production schema belongs to Alembic; no automatic production create_all or migration.
Self-approval remains disabled here. The API and worker must reference the same DB.

A runtime factory accepts an explicit operator-owned READ-only tool registry. No
arbitrary dynamic Python import from an environment string; no default empty registry
presented as ready. Every registered tool stays subject to the existing frozen risk
checks. The factory constructs the shared local adapter and engine per claim; tenant
and actor originate in the claim, not an operator-supplied header.

Provide run_once and bounded drain, with no new infinite retry loop. Existing Worker
settlement, attempt limits, leases and cancellation remain the authority for job
state. A lease/configuration violation blocks execution, not a fake completion.
No external/write capability registry or channel delivery added in this slice.

## Required tests

1. Configuration refuses absent DB/model, in-memory SQLite, unknown provider,
nonlocal/credential-bearing endpoint, invalid numeric ranges and timeout >= lease.
2. Exceptions/repr do not expose database password or model URL diagnostics.
3. API-enqueued goal is consumed by the configured factory on the same SQLite file;
provider transport receives selected model and JSON-action context; receipts persist
through separate store instances. Explicitly label synthetic transport evidence.
4. Declared model failure and invalid output settle blocked; tool/model programming
bugs remain loud; empty queue returns no work; bounded drain stops at its limit.
5. A WRITE tool cannot be enabled by this factory. Payment/comms and unknown-effect
journal remain outside the slice and cannot be bypassed through configuration.
6. Tests on exact base plus candidate; record independent review before integration.

## Release gates still outside this preparation

Real selected-model canary, authenticated production route, actual PostgreSQL migrations
and two-worker fencing, live deployment inventory, browser/device/channel parity and
process supervision. A synthetic provider and SQLite are insufficient for plan A.

## Boundary questions resolved by design choice

The runtime factory is read-only and explicit, not a second assistant server. This
avoids silently enabling legacy Meemee tools. Production service installation comes
after model canary, migration and independent review. Operator-supplied tool classes
are trusted application code, not model-selected plugin paths.
