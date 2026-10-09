# M24 slice2 checkout dispatcher, INACTIVE production wiring

Base main6406be8c, branch m24-slice2-checkout-dispatcher-20261009. LOCAL checkpoint for exact-tip independent gate, not published/landed/deployed. No provider credentials read, rotated or sent; no Stripe network requests. Parent's slice1 gate authorized landing then slice2. Slice1 landed unchanged6406be8c over SSH FF, read back by ls-remote. First failed push had a misspelled owner, fixed by deriving SSH routing from configured origin; no repo/key config changes.

## Implemented

- CheckoutRepository subclass uses a shared domain snapshot hook in the same intent+M00permit transaction. Intent INSERT flush precedes dependent FK snapshot INSERT, still one COMMIT and rollback unit. Snapshot form/hash binds exact reviewed catalog payload, endpoint, server UUID:checkout key, TEST account/environment, pinned API2026-09-30.endive and adapteratlas-checkout-v2. Existing slice1 intents lacking exact snapshot refuse; no silent enrichment/backfill.
- New revision20261009_m24_checkout_snapshot on landed20261009_m24_write_ahead. Empty snapshot downgrade allowed; populated snapshot downgrade refuses. PopulatedSQLite/PG upgrade with pre-existing parent intent creates ZERO snapshots, locked epoch remains0; old intent cannot dispatch. Metadata registry imports new model. No user database mutation/deployment.
- Claim approval lock then SQL CAS prepared/fence-null/cutover-exists predicate. One attempt/fence committed before adapter; readback required. DB clock for lease, first-attempt time retained,12h ceiling shortened by authority/preview deadline; no dispatching/unknown takeover even before key pruning. No automatic failed-before-dispatch retry in this slice either.
- Adapter serialization and binding validation before entry. Immediate pre-entry authority/impact-snapshot/permit/expiry/cutover/fence/form check. Marker is a LOCAL IN-PROCESS FACT only. Restarted row cannot infer adapter entry from missing request/receipt. HTTP500/malformed/timeout/cancellation after entry are unknown. Unknown/error results use stable operation ID and bounded codes, no raw provider error. Receipt failure holds original attempt; no blind retry.
- Receipt validates TEST object/type/mode/metadata/tenant/operation/amount/currency/status before bounded identifiers stored. Checkout created/succeeded is not payment or entitlement activation. Late receipt retained as succeeded_late, never redispatched. No reviewed acceptance/close/retry API yet. Immutable provider form is not returned by HTTP status.
- Legacy service checkout now routes to durable dispatcher when injected, never StripeClient.create_checkout or legacy record_execution. Default route does NOT configure dispatcher yet. Existing require_dispatch_ready remains unconditional refusal. Invoice/cancel remain legacy fail-closed.
- Tenant-authenticated GET /billing/checkout-operations/{operation_id} exposes id/state/bounded result/failure/times only. Foreign tenant404, no form or account disclosure.

## Activation and scope

Production readiness remains UNAVAILABLE. There is no operational credential/egress checker, rotation, TEST account version availability proof, account credential identity check, activation API, or fabricated-digest acceptance. Every product path calls unconditional require_dispatch_ready. Tests explicitly monkeypatch that function and insert a fixture-only cutover row to exercise future dispatcher mechanics. Those controls are MOCK ACTIVATION, NOT readiness evidence. Pinned version is implementation constant, not a verified Stripe account feature. Default HTTP service cannot dispatch even with an env flag or forged row. Operational cutoff remains a hard prerequisite before enabling epoch2. Free-first; no money/provider spend.

A60s lease with30s HTTP timeout and no heartbeat is finite, not complete clock-skew/heartbeat-runtime acceptance. SQLite CURRENT_TIMESTAMP resolution is seconds. Read-only check before entry is a local race boundary, not external conditional enforcement; revocation after entry cannot undo effect. Low-level legacy StripeClient remains a capability for hypothetical callers, not claimed eliminated from the universe.

## Evidence, exact disjoint counts

Python3.12.14 /tmp/atlas-memo3-venv. PYTHONPATH=backend PATH=/tmp/atlas-memo3-venv/bin:$PATH throughout.
- final-dispatcher-cas.log:72PASS,2deselected,52.77s; pytest -q tests/modules/test_m24_checkout_dispatcher.py -k 'not populated_checkout'.
- final-migrations.log:2PASS,68deselected,58.74s on then70-node manifest; pytest same file -k populated_checkout. Those exact2nodes unchanged through final74-node manifest; run has smaller earlier collection count, do not call74 single-run success.
- final-storage.log:29PASS50.66s; pytest -q tests/modules/test_m24_write_ahead_repository.py.
- final-other-affected.log:264PASS31.62s; pytest -q sorted test_m24*.py excluding the two above, plus test_m00_approval_center.py and test_m00_impact_preview.py.
Thus367 distinct named affected nodes in disjoint completed sets (74new+293prior), NOT a successful combined run or whole-repository census. acceptance-nodes.txt records74new nodes. Earlier overlapping54/62/68/72controls not additive.

10 REAL externalSIGKILL nodes:5boundaries xSQLite/PG (prepared, attempt committed before entry, adapter-entered before acceptance, mock accepted before receipt, committed receipt before acknowledgment). Fsynced PID barrier, parent sendsSIGKILL, asserts -SIGKILL, then launches PID-distinct restart worker. Prepared restart calls/effects1; attempt and adapter-entry restart0; accepted restart retains1effect/no extra; receipt restart readback1effect/no extra. Mock provider acceptance is an fsynced fixture effect log, NOT Stripe server acceptance. At restart dispatching stays held; separate lease-expire controls mark unknown. These extend storage-only slice1 evidence, never relabel its parent-process resume.

MockTransport controls count calls/effects independently, including concurrent dispatchers1call/1effect, concurrent claims1attempt, exact key+form/version, HTTP500 first-result replay, changed parameters400, artificial pruningnew-effect contract. Dispatcher uncertainty never replayed even under prune-enabled mock. Claim rollback/ack-loss/readback-failure, pre-entry revocation, corrupted form/account/version/key/deadline, foreign/live refusal, result-shape/late-fence controls included.

5 RED mutation receipts bite: bypass readiness, reclaim unknown, approval-key substitution, classify post-entry timeout safe, drop late-state. A separate redundant fastpath mutation SURVIVED because claim CAS still prevented replay; retained mutation-survived-redundant-fastpath.log, not counted as bitten mutation. No claim of complete mutation adequacy.

## Failures and resource receipts retained

- RED-missing-dispatcher collection ERROR, not behavioral failure.
- initial-controls21PASS18FAIL:PG FK insert ordering from independently mapped snapshot/intent; repaired by explicit intent flush inside original transaction, never separate commit. repaired-controls39PASS.
- affected-first.log truncated combined run hit execution limit after progress, NO success summary. affected-storage-dispatch.log OS-killed after63dots, no success summary. Resource evidence: owned scratchPG instances remained alive after interrupted run; stopped only those owned test dirs. Fixtures now explicitly clean up scratch server after dispose. No global kill. Completed split runs don't erase interruptions.
- final-dispatcher.log interrupted after63progress with1failure; focused deadline-migration-focused.log1PASS1FAIL preserved: test used replace(tzinfo=UTC) on PG Asia/Calcutta timestamp, shifting an instant. Fixed assertion to _aware(...).astimezone(UTC), not product clock/code. migration-focused-repair4PASS includes those exact deadline controls and2migration nodes. Later full nonmigration controls pass.

## Still open

Actual checked cutover and TEST version/account readiness, live/network contract, interrupted migration, PG server restart/failover/WAL/power-loss, broader cancellation/authority race matrix, persistent late-attempt evidence detail/append-only multiple-result conflicts, reviewed reconciliation/closure/absence proof, inode/storage loss. No budget/invoice substep/signed inbox implementation. No default dispatcher activation config. No blind retries/external exactly-once promise.

Memo3/Claire remain non-ancestors: later integration must rebase memo3 onto landed M00 optional_session helper and coordinate Alembic heads. No renamed published revision or cross-lane merge. Exact-tip gate must inspect hook/shared transaction, status route, migration, in-process marker wording and fixture-only activation boundary before landing or next slice.

## Gate amendment

Independent gate SCOPED PASS as inactive mechanics; read whole dispatcher and touched product diff, executed36SQLite controls only. Gate did not independently runPGor affected367sets; those remain builder evidence. Gate12mutations:4bit,5survivors judged redundant by second guards,3real gaps. Added12parameter nodes covering mismatched claim readbackfence/state, lease expiry between claim/entry, previewcancellation_deadline expiry at claim/entry, and unknown->pre-entry-safe refusal. Cheap product guard restricts failed_before_dispatch to dispatching, never outcome_unknown. Fresh84nonmigrationPASS/2deselected55.98s in gate-final-84.log;2migration nodes unchanged previousPASS,86new+293prior=379distinct named nodes in completed disjoint sets, NOT combined/fullsuite success.5gap mutation nodes bite (readback,lease,deadlineclaim,deadlineentry,unknownsafe) with raw receipts.

CancelledError after adapter entry is deliberately caught and persisted/returned unknown rather than propagated; pre-entry cancellation is classified local-safe in-process only. httpx30s timeout is PER PHASE, not a total wall-time bound; adapter can outlive60s lease, late success retained succeeded_late. Checkout still refuses without configured dispatcher and readiness unavailable. Gate conditional landing instruction covers these gap tests/cheapguard with this slice, not operational activation. No scope widening beyond those changes.
