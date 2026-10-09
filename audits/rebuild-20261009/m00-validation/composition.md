# M00 validation and state-integrity composition

Base: 75af693865a52bebde2293635191879ec0ac8997.
Family cut: accepted structural parents (a)-(ac), state/alias/wait and policy lanes through (bu), peer impact tip 39e46f75c0d0025ded64a4dd788a0e0e14a721f0 and policy tip b72c31c3cec25db46d0c6c5176f6e8a3b0e890b1. Next-family (bv) and later packages excluded.

These are our composition commits adapted from peer proposals with explicit credit, not unchanged peer cherry-picks. Original archives and independent per-candidate receipts retained. Three review cuts: structural validation, state/alias/wait, policy matching/input and compatibility/gap tests. Published TTL guards are preserved.

## Integration edits

- Structural (m) non-JSON rollback pin: StatementError -> ValueError, final accepted behavior under (w). Zero-row/zero-event assertions retained.
- (ap)/(z): one recursive payload-key helper serves submit and gate, instead of duplicate helpers.
- (au): math imported explicitly in composed runtime for finite wait checks; copy imported for alias isolation.
- Independent deterministic decision-during-probe control added alongside peer probabilistic race. The peer negative is PROBABILISTIC, not guaranteed every iteration; the additional control forces approval inside the probe before capture write.
- Function-level guard composition avoids replacing published TTL validation/overflow checks with pre-TTL peer bodies. No TTL docs or migrations changed.

## Deliberate contracts

- Current wait is terminal-first: a terminal decision observed late may be returned. Hard deadline-before-return is CHOSEN-BUT-OPEN future work, not implemented.
- Named probes track name and JSON state, not callable version; same-name identical JSON reuses snapshot; equal specificity is first-registration-wins.
- Policy comparison separates boolean from numeric values recursively. Numeric 1 == 1.0 remains intentional. Outer lists are alternatives; tuples normalize in stored JSON, while direct write view may retain tuple. Actual boolean DENY/REVIEW matches remain; formerly coercive true==1/false==0 rules can fall through to stored ALLOW. This is a semantics change, not a security improvement for those rules.
- Repository policy corpus at base contains no pre-existing DENY/REVIEW rule dependent on boolean-number coercion. This is not a deployed database migration audit.

## Named OPEN gaps, not repaired by this family

- Hard-deadline wait contract, as above.
- Policy-event audit model: policy events lack tenant attribution, share policy:<id>, SDK-readable but not retrievable through request-only HTTP audit. Separate event-model/schema/route design.
- Field width: policy ID120 produces event key127 against String(36); drift-block actor121 against String(120). SQLite accepts widths; PostgreSQL not executed. Future fail-closed policy-ID and drift actor identity/length validation, no truncation.
- Priority integer domain: SQLite priority2**63 raises raw OverflowError but atomically rolls back policy/event. Future fail-closed input-domain validation.
- Migrated SQLite policy PK: actual isolated migration and full clean upgrade-to-head retain ID-only PK, whereas ORM create_all uses tenant+ID. Second tenant same-ID write raises IntegrityError, no cross-tenant leak shown. Earlier two-tenant coexistence/list controls establish ORM-created schema ONLY. New composite-PK migration/backfill semantics need separate review. PostgreSQL branch unexecuted.
- Worker execution/idempotency: permit-once does NOT imply execute-once. Retry, retry after local action then Python exception, and malformed-result retry re-invoke executor while consume audit stays single. Choose at-least-once with idempotent effects vs execution guard separately. Local synchronous Celery/SQLite controls, not broker/provider/OS-crash acceptance.
- Worker consume-before-executor validation: missing executor LookupError occurs after permit consumed. Future fail-closed existence/effect-binding check before consume.
- Probe HTTP malformed/unavailable errors currently500 without consume event; desirable502/503 mapping remains unresolved.
- Postcommit broadcaster-failure response/retry semantics unresolved; callback exceptions preserve durable decision.

## Next-family source checks, excluded

Plain Pydantic int/bool route fields coerce raw wire values. Model validation confirmed True->1, whole-float/string->int, string enabled->bool; direct-service actual-type guards do not prove strict raw-wire validation. Strict-vs-coercive wire contract remains OPEN.
EffectPermit response model lists only approval_id/effect_id/allowed/consumed_at and filters state_verdict/state_hash returned by the wrapper. HTTP metadata contract remains OPEN. Later peer evidence is parked, not evaluated or composed here.
Concurrent duplicate-worker execution and cross-process callback/broadcast visibility are peer-reported next-family evidence only, not independently confirmed in this cut. Python exception controls here are not OS-crash recovery.

## Verification scope

Structural cut: 140 passed. State/alias/wait cut: 230 passed including impact and M10 drift. Final combined selection: 286 passed (M00 approval, M00 impact, M10 drift, M10 email). Exact combined tree requires independent review before publication. No full repository, live provider, PostgreSQL width/backfill, production deployment or M00 closure claim. Auxiliary repairs are not count-bearing; counter remains12/2452.
