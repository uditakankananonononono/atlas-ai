# Combined prototype merge gates

This prototype is not production clearance. A green local regression does not close the gates below. These gates must remain in the eventual merge commit until the corresponding evidence is recorded and reviewed.

## PostgreSQL scratch evidence and production deployment prerequisite

Independent October 8 scratch PostgreSQL evidence now passes: existing SQLite/PostgreSQL unknown-hold migration suite 2 passed, 0 skipped; new real PostgreSQL reviewed-payload CAS/risk-revision suite 3 passed, 0 skipped. Dependencies installed outside the repository: pgserver 0.1.4 and psycopg 3.3.6. Upgrade, restart retention, hold-preserving downgrade refusal, successful activation and separate-writer CAS rejection are tested locally. Production deployment/rollback configuration and operations remain unverified; scratch tests are not production clearance. Receipts: `audits/rebuild-20261008/postgres-gates/`.

## Peer PostgreSQL scratch corroboration

The peer reports 87 supplied canaries passed in its isolated checkout of our
ebba4b3 bundle, including the PostgreSQL migration parameter using its available
pgserver interpreter. This is attributed corroborating local scratch evidence,
not our independent reproduction or production verification. The Production unknown-hold deployment prerequisite remains open; independent local PostgreSQL evidence is now recorded above.

## Known Alembic revision collision

Our published `20261007_m20_model_unknown` revision has parent
`20261007_m20_risk_register`. The peer revision with the same id has parent
`20261007_m10_ingest_work` and a different migration body. Any future combination
of those histories requires an explicit Alembic-chain integration decision.
History-preserving current adaptation decision: keep our published revision/parent untouched and exclude the peer colliding migration from this namespace. No rename, rewrite, stamp or new schema operation. Source receipts and rationale: `audits/rebuild-20261008/alembic-history-decision/`. Future deployment from the peer parent chain remains blocked until a schema-inspected, uniquely identified forward migration plan is reviewed and tested.

## Nested-object mutation coverage

The four mounted runtime routes for method activation and risk-register create,
revise, and risk-control patch now call locked runtime mutation wrappers instead
of calling nested planner/risk-register mutators directly. Canaries first exposed
eight failures, retained in `audits/rebuild-20261007/m20-nested-mutation-locks/`.
After the fix, thirteen route/concurrency canaries pass, including held-lock
rejection before mutation, actual concurrent model execution, reverse-direction
execution rejection, exception release, and real risk-register write isolation.
The affected runtime suite reports 216 passed and 0 failed.

This closes only the identified four-route instance-lock bypass. Direct callers
of nested planner/risk-register objects still bypass the runtime lock. Their scoped source assessments are recorded below; production and direct-call boundaries remain open. Separate
runtime instances and workers are not serialized by this lock. The HTTP 409
mapping alone does not acquire a lock; each mutation wrapper does.

## Peer M13 failure and collection discrepancy

The original peer M13 combined-run failure remains unexplained. The peer reported 159 passed and 1 failed; the independent reproduction reported 159 passed, 1 skipped and 0 failed. Correction: the recovered independent original log and current collected list both contain 160 tests. The earlier 161 figure was a reporting arithmetic error, not evidence of an extra test. Exact cross-environment node-list comparison now matches 160 node IDs in the same order. Default and two seeded-file combined runs plus ten exact-browser repeats pass locally; no connection/order root cause is established. Do not treat the absence of a reproduced failure as clearance.

## Scoped assessed surfaces

These bounded comparisons are assessed as stated. They do not close broader production gates or imply peer source is an ancestor of our main.

- `local_tools`: assessed as our additive bounded offline surface; absent from peer bundle tip b944215. Preserve ours, not a peer-parity claim. Selected runtime tests 27 passed; solver tests 22 passed with overlap; catalog canary 1 passed.
- `function_schemas`: assessed-compatible for the two export methods against peer b944215; six new canaries pass. Preserve our stronger surrounding spec isolation/schema validation. Live provider compatibility is not established.
- `retrospectives`: assessed-compatible by retaining our detached snapshots, stage/save/publish ordering, stable restart identity and local execution reports rather than the older peer implementation; focused comparison suite 16 passed. Lesson truth is not independently verified.

- `premortem`: scoped assessed-compatible for AST-identical analyze; additive assess_register preserved with supplied ordinal/control-completeness labels, no verified evidence/probability/approval claim; focused suite 7 passed.

## Scoped comparisons with open integration boundaries

The following assessments retain named boundaries; none grants combined production clearance:

- `risk_register`: additive local surface, absent from actual peer b944215; retain tenant-scoped transactional revisions/CAS and detached snapshots. Selected SQLite/runtime/HTTP 31 passed plus one new snapshot/non-authority canary. Real scratch PostgreSQL simultaneous-writer revision CAS now passes; production deployment and independent evidence/authority remain unverified.
- `htn_planner`: reviewed-payload TOCTOU found and locally fixed with durable hash checking plus exact JSON-snapshot compare-and-set in the activation UPDATE. Two SQLite cross-instance/check-to-write race canaries pass; Real scratch PostgreSQL successful and separately committed check-to-update race CAS now pass; production deployment remains unverified. Scoped planner source comparison assessed by preserving stronger local validation/snapshots/bindings and fresh state. Selected suite 54 passed. Semantic applicability, reviewer identity and concurrent durable usage-counter updates remain unverified.
- `model_ideation`: additive response path assessed; typed unknown flattening to unavailable/503 corrected to ProviderOutcomeUnknown and 409 with retry_allowed=false. No durable cross-request hold/reconciliation is provided by this service API; that broader boundary remains open. Proposed ideas remain unverified.
- `ActionRow` migration: scoped SQLite additive schema/journal roundtrip assessed (10 selected tests plus 1 migration-only unknown-payload canary). PostgreSQL deployment remains untested. Downgrade drops the journal and is data-destructive, not an automatic uncertainty-preserving recovery path.
- `safety.py`: scoped source/effect-binding assessment compatible; peer differs only by lacking our two deep-copy protections. Preserve ours. Approval provenance, durable cross-worker token state and complete semantic effect classification remain unverified boundaries.
- Peer-derived provider/core surface `dd3ca6b2db`: scoped uncertainty adaptation assessed; single invoked POST, no fallback after unknown, pre-dispatch eligibility policy retained. Combined core suite 52 passed. Conservative rejection-status/connection classification and live usage/effect verification remain boundaries.
- Peer-derived provider/core surface `78f0be856b`: scoped shared-generation uncertainty adaptation assessed; private-route policy and general-router callers preserved, SharedModelError compatibility retained. Arbitrary custom adapter errors and production integration remain unverified.

The two provider/core surfaces are semantic adaptations, not cherry-picks. Free-first model selection remains. Pre-dispatch unavailable or unconfigured routes may fall through. Once generation is invoked and its outcome is unknown, repeated POSTs and hidden route fallback stop. The previous post-402 fallback behavior intentionally changes. The scoped assessments above do not remove their stated production and custom-adapter boundaries.

## Lock guarantee

The execution lock protects one bound runtime instance in one process. It does not protect separate runtime instances or workers sharing a database. Multi-instance and multi-worker database locking is unsupported by this prototype. No broader concurrency guarantee is implied.

## Fail-closed reconciliation

Reconciliation is a private integration hook, with no user-facing evidence-as-authority endpoint. By default no independent verifier is configured, so reconciliation is rejected. A bound independent verifier must approve evidence before a durable hold can be cleared.

Reconciliation does not dispatch, renew approval, supply successful structured output, or authorize automatic retry. It retains reviewed evidence and leaves the task blocked. Production evidence and authority integration remains a design gate.

## Scope and publication

The prototype does not include the non-M20 divergent peer commit range. Main merge requires the integration owner's explicit go after review. Publication is separate from local merge approval. No push is authorized by this file. The earlier GitHub incident restriction was lifted by the integration owner's retry-wave signal, and the reviewed commits were published with remote readback. Future incidents require a fresh publication-state check, not reuse of that recovery signal.

## Reviewer provenance design gate

Mounted method activation now requires authenticated atlas-reviewer/atlas-admin and an actor distinct from the persisted proposer. Actor/hash/timestamp receipt is durably written in the guarded activation update. Authenticated task creator is propagated to learned proposals; unknown legacy proposer fails closed. Direct trusted adapters must authenticate the identity/roles they pass. Distinct subjects do not prove different humans or non-collusion. Live identity-provider policy and production deployment remain unverified. Original five failures and new canaries retained in `audits/rebuild-20261008/reviewer-provenance/`. Fresh full regression: 519 files across 52 isolated batches, 10,302 passed / 0 failed / 14 skipped / 0 errors. Product publication remains gated on restored Atlas key access.
