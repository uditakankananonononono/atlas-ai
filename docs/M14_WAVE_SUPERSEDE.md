# M14 human admin wave supersede

This is a blocked-project unblock, not automatic recovery or dependent task completion. An OIDC-authenticated tenant atlas-admin proposes a specific prior/new immutable submitted wave pair, reviews the evidence and approves or denies via the module decision endpoint. Generic M00 decision denies wave_supersede. A raw Service.decide cannot produce the SQL-transaction-bound admin role receipt. Application consumes the supersede approval exactly once in the same transaction as marking the prior wave superseded and appending its permanent key version.

The prior claim key, allocation, result and artifact history are never erased or refunded. Claimed with no durable result/tasks/artifacts is explicitly "unknown / no S6 evidence". Awaiting-review evidence requires matching task/result receipts, stored artifact bytes and hashes, and a verified S6 SHA256. Partial evidence and changed digests/version/expiry are refused.

The new wave can retry only the identical initially-ready task IDs. Its code may differ but requires its own normal execution approval, separate from supersede approval. Every claimed attempt keeps its complete reservation against cumulative calls, runtime and cost limits. Sandbox execution costs0 here. No model/provider budget claim is made. Only the selected new version may claim. Old worker finalization is fenced by locked row state/current version and CAS before any durable result, task or artifact publication. Review, dependent progress and all-DAG completion remain outside this unit.

Endpoints under /project-builder:
- POST /wave-supersedes {prior_wave_id,new_wave_id}
- GET /wave-supersedes/{sid}
- POST /wave-supersedes/{sid}/decision {decision: approved|denied}
- POST /wave-supersedes/{sid}/apply
- GET /projects/{project_id}/wave-key-history

Migration 20261010_m14_wave_supersede chains after 20261010_m05_m10_m15_tables. One Alembic head verified. Full fresh PostgreSQL empty->head, downgrade-one and re-upgrade passed; direct SQLite/PG revision up/down passed. Actual PG concurrent apply yields one winner, injected consumption fault rolls back, old real worker paused while a next version is applied cannot publish, and a following real sandbox attempt works.

## Receipts and limits

Base87ac283226bd773e6958b9451fcdc166a8b09cdb. Candidate non-overlapping M14 splits: supersede22PASS30.02s; existing sandbox+continuation+wiring97PASS1strictXFAIL52.79s; other M14874PASS9.94s. Total993PASS1strictXFAIL across994nodes. M00250PASS17.81s separately. The strictXFAIL is the existing artifact-read residue contract; not hidden as success. Prior monolithic suite attempts exceeded execution caps and remain incomplete, not green. Source-test allowlist changes allow only read-only reservation-history predicate and approved versioned claim-key computation, not key clearing/reassignment or retry methods.

Mutation probes remove role receipt, cumulative admission, initially-ready restriction and artifact SHA check independently. Each selected acceptance test fails at the intended assertion; sources restored after every probe. The first role-only mutation survived the raw-decide test because the separate approved-state guard still refused it. Added a state-only/no-role-receipt test, which kills that mutation; the first survival is preserved rather than counted as a kill. Initial reservation tests exposed missing cumulative admission; after the product change a30second runtime limit test remained valid for two10second reservations, so the test limit was corrected to15seconds rather than changing admission semantics.

No deployment. No browser UI, full DAG dispatch, abandonment inference, refund, automatic retry, M20 restoration, H approval or frozen AWS import6 changes. Independent audit remains required before landing.

An additional combined M00+other-M14 run also hit the execution cap before completing despite those groups passing separately. It is an incomplete attempt, not a failure-free combined-suite receipt. Keep test processes scoped by module/group for bounded execution.
