# Memo3 local worker execution ledger, preliminary checkpoint

Base438724e9f0b54c56a07ddcb6947109db83a2386f. Branch only. Not ready for main; independent review and full-repository acceptance remain outstanding. This is a first local-ledger slice, not full memo3 closure.

Implemented: immutable tenant/approval/effect/request-digest row; permit+ready intent in one transaction; SQL CAS ready->dispatching with random fencing token/deadline; last-moment local claim check; fenced/unexpired completion; finite JSON result persistence; successful replay before adapter lookup/current drift; legacy consumed permit without ledger held unknown; expired/crashed claims and exceptions/malformed results held unknown with no automatic retry. Default M10 conditional refusal retained. Intent table registered for metadata bootstrap. New migration20261009_m00_execution_intents on actual sole head20261008_m20_chroma_jobs; populated downgrade refuses, historical permits are not backfilled as fresh dispatches.

Crash controls launch real subprocesses and os._exit(17): ready-before-claim is recoverable; claimed-before-dispatch conservatively unknown after lease expiration; local effect before result commit unknown; committed result after process crash replayable. Real SQLite concurrent claims and actual PostgreSQL separate sessions have one winner. Permit/intent rollback atomicity, populated migration and effect-key loser rollback checked. Three20-trial start profiles0/1/10ms yield one local adapter call per intent;20executed returns plus20held competitors each. These are observed fixture profiles, not production rates.

Affected regression final333PASS. New31ledger parameter nodes included. Scratch PG warning XDG_RUNTIME_DIR fallback retained. Initial failures preserved: naive/aware SQLAlchemy in-memory update evaluator; historical contract expectations; winner commits between intent and permit lookup; raw unique IntegrityError for losing cross-approval key. Fixed with database-side sync-off update, exact winner recovery, and conflict translation. All failed/success receipts included; not erased.

Original test corrections quote old contract:
- test_worker_same_effect_retry_invokes_local_executor_twice expected call1 then call2 and two payload calls; new test_worker_same_effect_retry_returns_persisted_outcome_once expects same stored call1 and one effect.
- test_worker_missing_executor_consumes_actual_permit_before_lookup expected audit ['created','approved','effect_consumed']; new missing_executor_refuses_before_permit expects ['created','approved'].
- test_worker_failed_executor_can_be_retried_with_same_permit expected second call result{'call':2}; new failed_executor_is_unknown_and_retry_held refuses second effect.
- test_worker_malformed_result_retry_reexecutes_local_effect likewise expected call2; new malformed_result_is_unknown_and_retry_held refuses retry.
Existing fake SimpleNamespace worker test replaced with actual SQLite Service/ledger. Initial affected291PASS/5FAIL retained to show this contract change. Historical concurrency diagnostic explicitly run unchanged17FAIL/1PASS, retained; it asserts duplicate effects/two arrivals and is incompatible with single-claim behavior. New outcome-accounting profiles do not demand two executor arrivals. No silent deselection/green-historical-harness claim.

Important open contracts/limits:
- No provider idempotency/reconciliation implementation or external fencing. Local last-moment check cannot prevent external effects after a lease expires. Unknown stays blocked; no result can be accepted from stale token. No exactly-once promise.
- No reviewed reconciliation/status UI/API, no outcome adjudication or unknown->ready transition. Failure-before-dispatch is conservatively unknown once claim exists; distinct failed-before-dispatch classification still unimplemented. Required full memo3 contract remains partial.
- Adapter versions default legacy-v1; mutable callable registry is not deployment/adapter provenance. Strong capability/version pinning needs review, no provider support inferred.
- M06/M24 direct module adapters bypass this worker; M15 orphan bytes, M12 budget release, M02 persistence and M03 numeric-claim policy remain separate queued fixes. This worker slice does not close them.
- Existing consumed permit blocks fresh dispatch without durable outcome, intentionally reducing availability. No historical database migration/production applied.
- Full repository suite not rerun after workspace reset; only affected333PASS plus PG/crash/migration controls. No CI/deployment/broker/full suite readiness claim.
- Error sanitization across all adapters, audit/state transition events, lease extensions, durable adapter capability records and PG full migration acceptance remain open. Unknown marker persists without raw exception; original adapter errors currently propagate to caller as before.

Named controls in tests/modules/test_m00_execution_ledger.py and original-vs-new test diff accompany this checkpoint. Gate must read transactional/race boundaries and evaluate scope, not infer safety from test labels.
