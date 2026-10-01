# A: discovery source promotion approval

Base: 313309be2a960a84b909d1834c3046f884e21a7e.
Local branch: fix/approval-binding-and-rank-permutation.

Native baseline reproduction enabled a source and marked a candidate approved with no approval record. See baseline-native.txt and reproduce_baseline.py. Actual package imports, real dependencies and file SQLite were used, not AST fixtures or stub modules.

## Changes

- Default promotion fails closed without a server-supplied authority.
- request_candidate_promotion queues a Module 0 pending review and persists a unique, append-only candidate -> approval ID -> tenant -> SHA-256 binding. No source is enabled during preparation.
- The reviewed hash includes candidate identity, tenant, action, source ID/key, prior config and enabled state, proposed config and collection settings. Drift rejects promotion.
- NativePromotionApprovalAuthority reads real Module 0 rows inside the promotion transaction. It matches status, tenant, action, owner identity from a server-owned directory, decision event, hash, decision time, expiry and revocation events. Caller approved flags grant nothing.
- SQLite BEGIN IMMEDIATE protects the check/mutate/consume transaction. Candidate/source locks and a tenant/platform advisory lock are included for PostgreSQL. Source update, candidate review and single-use receipt commit together. Bindings and receipts have immutable database triggers in the migration; SQLite create_all uses the same guard.
- Existing disabled sources are enabled only after valid exact-scope approval. Reuse fails without any change.

## Acceptance

Command: PYTHONPATH=backend python -m pytest tests/test_discovery_promotion_approval_native.py -v

29 passed in 3.21s. Full stdout: acceptance-A.txt.

Checks include absent approval/authority, pending/denied/expired/revoked/missing records, wrong tenant/owner/action/hash, missing event/expiry, caller flag rejection, immutable binding and receipt, changed candidate/source/review payload, owner directory change, one successful consumer in an eight-thread race, unchanged state in denied races, concurrent different-candidate stale-source rejection, authority failure rollback, existing-source enablement, and direct SQLite migration upgrade/downgrade.

## Limits and integration contract

This is source promotion, not model training. No collector ran and no real Instagram/account was accessed. Nothing was pushed.

Server composition must supply an authoritative current owner directory and must not expose authority injection to request JSON. The Module 0 API supplies persisted decisions; promotion validates owner identity independently. Revocation is recognized as a persisted Module 0 'revoked' event, but this patch does not add a revocation HTTP endpoint. For PostgreSQL, a revocation writer must use the same approval-row lock transaction to order revocation versus consumption. PostgreSQL SQL paths/triggers were not executed here. Database administrators can bypass triggers; they are outside the threat model. Unsupported databases fail closed.

The full repository migration chain/application startup and full test suite were not exercised. The new migration was applied and reversed directly on native SQLite. Relevant dependency versions are recorded, not the entire ML/browser stack.

The binding is deliberately permanent: a rejected or stale candidate cannot be rebound. A retry/re-review lifecycle, including restaging under the existing unique tenant/platform/account key, is not implemented. Existing already-approved candidates are not grandfathered into new approval authority. Calls using the former two-argument promotion API now fail closed and must be wired to the new server authority.
