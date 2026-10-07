# Combined prototype merge gates

This prototype is not production clearance. A green local regression does not close the gates below. These gates must remain in the eventual merge commit until the corresponding evidence is recorded and reviewed.

## Production prerequisite: PostgreSQL unknown-hold migration

The PostgreSQL unknown-hold migration path is untested. The PostgreSQL-specific canary was skipped because `pgserver` is absent in both available interpreters. SQLite upgrade and hold-preserving downgrade refusal passed. PostgreSQL upgrade, restart retention of unresolved holds, and downgrade refusal while holds remain must be tested before production clearance.

## Peer PostgreSQL scratch corroboration

The peer reports 87 supplied canaries passed in its isolated checkout of our
ebba4b3 bundle, including the PostgreSQL migration parameter using its available
pgserver interpreter. This is attributed corroborating local scratch evidence,
not our independent reproduction or production verification. The PostgreSQL
unknown-hold migration production prerequisite remains open.

## Known Alembic revision collision

Our published `20261007_m20_model_unknown` revision has parent
`20261007_m20_risk_register`. The peer revision with the same id has parent
`20261007_m10_ingest_work` and a different migration body. Any future combination
of those histories requires an explicit Alembic-chain integration decision.
This is a known integration blocker; the decision is deferred. Do not rename
our published revision id unilaterally.

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
of nested planner/risk-register objects still bypass the runtime lock. Broader
`htn_planner` and `risk_register` semantic comparison remains open. Separate
runtime instances and workers are not serialized by this lock. The HTTP 409
mapping alone does not acquire a lock; each mutation wrapper does.

## Peer M13 failure and collection discrepancy

The original peer M13 combined-run failure remains unexplained. The peer reported 159 passed and 1 failed; the independent reproduction reported 159 passed, 1 skipped and 0 failed. Correction: the recovered independent original log and current collected list both contain 160 tests. The earlier 161 figure was a reporting arithmetic error, not evidence of an extra test. Exact cross-environment node-list parity remains to be compared. Do not treat the absence of a reproduced failure as clearance.

## Scoped assessed surfaces

These bounded comparisons are assessed as stated. They do not close broader production gates or imply peer source is an ancestor of our main.

- `local_tools`: assessed as our additive bounded offline surface; absent from peer bundle tip b944215. Preserve ours, not a peer-parity claim. Selected runtime tests 27 passed; solver tests 22 passed with overlap; catalog canary 1 passed.
- `function_schemas`: assessed-compatible for the two export methods against peer b944215; six new canaries pass. Preserve our stronger surrounding spec isolation/schema validation. Live provider compatibility is not established.
- `retrospectives`: assessed-compatible by retaining our detached snapshots, stage/save/publish ordering, stable restart identity and local execution reports rather than the older peer implementation; focused comparison suite 16 passed. Lesson truth is not independently verified.

## Open comparison surfaces

The following surfaces remain unassessed for combined semantic clearance, even where existing local tests pass:

- `risk_register`
- `htn_planner`: reviewed-payload TOCTOU found and locally fixed with durable hash checking plus exact JSON-snapshot compare-and-set in the activation UPDATE. Two SQLite cross-instance/check-to-write race canaries pass; PostgreSQL multi-writer CAS behavior remains untested. Broader planner comparison remains open.
- `model_ideation`
- `premortem`
- `ActionRow` migration
- `safety.py`
- Peer-derived provider/core surface `dd3ca6b2db`: generation POST retry and free-first fallback handling
- Peer-derived provider/core surface `78f0be856b`: shared-router generation uncertainty handling

The two provider/core surfaces are semantic adaptations, not cherry-picks. Free-first model selection remains. Pre-dispatch unavailable or unconfigured routes may fall through. Once generation is invoked and its outcome is unknown, repeated POSTs and hidden route fallback stop. The previous post-402 fallback behavior intentionally changes. Passing tests do not remove these surfaces from the comparison gates.

## Lock guarantee

The execution lock protects one bound runtime instance in one process. It does not protect separate runtime instances or workers sharing a database. Multi-instance and multi-worker database locking is unsupported by this prototype. No broader concurrency guarantee is implied.

## Fail-closed reconciliation

Reconciliation is a private integration hook, with no user-facing evidence-as-authority endpoint. By default no independent verifier is configured, so reconciliation is rejected. A bound independent verifier must approve evidence before a durable hold can be cleared.

Reconciliation does not dispatch, renew approval, supply successful structured output, or authorize automatic retry. It retains reviewed evidence and leaves the task blocked. Production evidence and authority integration remains a design gate.

## Scope and publication

The prototype does not include the non-M20 divergent peer commit range. Main merge requires the integration owner's explicit go after review. Publication is separate from local merge approval. No push is authorized by this file. The earlier GitHub incident restriction was lifted by the integration owner's retry-wave signal, and the reviewed commits were published with remote readback. Future incidents require a fresh publication-state check, not reuse of that recovery signal.
