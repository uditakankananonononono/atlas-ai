# M20 META-DUR: opt-in state persistence

Persists existing meta patterns, world-model versions/history, epistemic
beliefs/reviews and curiosity counts in m20_meta_state. Calibration reuses
DurableCalibrationEngine and m20_calibration_claims, not a second claim table.
CognitiveWorkerService accepts meta_repository and a matching-tenant calibration
repository, loads all five stores, and refuses a durable service bound to a
different authenticated tenant. Existing routes operate on these actual stores.
The default service remains in-memory until an integrator opts in.

Mutations stage a deep copy, apply the unchanged existing operator, write the
whole operator state under tenant/kind with revision compare-and-swap, commit,
then publish memory. A failed SQL write does not publish staged memory. Stale
writers refuse and must reload. Rehydration restores exact timestamps, counters,
histories, role sequences, domain tokens and supplied scores, not recomputed
beliefs or predictions. Each operator mutation is atomic; cross-operator and
cross-calibration transactions are NOT promised. One snapshot per kind is
simple, not a bounded large-scale journal. Direct writes to public inherited
state mappings can bypass write-through; use the documented mutation methods.
CuriosityEngine.random seeded RNG state is NOT persisted in the snapshot.
A restart does not resume the prior sampling sequence; serendipity sampling
sequences can change after restart. Only curiosity gap counts are durable.

Alembic migration follows the actual current head20261010_m14_local_dispatch.
DDL creates empty tenant/kind composite-key snapshots. No backfill, production
rollout or automatic schema creation. Explicit create_schema is local tests only.
Acceptance is SQLite including migration constraints, stale writer, rollback,
process-object restart, tenant binding and real mounted production/OIDC routes.
Real PostgreSQL16 Compose acceptance remains ours and unverified.

This is a persistence sub-unit, NOT semantic closure of the15PARTIAL rows11-34.
Row11 remains role-sequence retrieval only; row13 observed calibration without
predictive confidence correction; row21 assumption registry/supplied weights
without Bayesian truth; row33 obsolescence model unavailable; row34 lexical
frequency budget without investigation. No rubric/content changes, hidden
chain-of-thought capture, model/provider/spend or AGI claim. Those original
capabilities need separate implementation units. Existing ledger statuses stay.
