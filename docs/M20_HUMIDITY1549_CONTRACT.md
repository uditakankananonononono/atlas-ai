# ATLAS-HUMIDITY1549-EXPOSURE-01: bounded sourced humidity-exposure evaluation

Candidate target row 1549 Humidity Testing only. Adds evaluation of sourced,
timestamped, timezone-aware relative-humidity observations against a
predeclared exposure specification, beside the existing supplied test-profile
template in `engineering_1510_1559.py`, which remains the row's live
diagnostics surface. This unit does NOT perform a physical humidity test,
material degradation or lifetime modeling, or certification, and does not
close the full row title. Independent acceptance must decide bounded SCOPED
closure.

Core surface `humidity_exposure1549.evaluate(data)` accepts `rh_limit`
(0..100 percent), 1..4096 `observations` (each `time` an ISO-8601 timestamp
with explicit offset, `rh` a finite non-boolean number in [0, 100], optional
`source`, `id`, `protocol`, `unit`), optional `horizon` (default: the last
observation's timestamp), optional `max_gap_seconds` with `gap_policy`
(`report` default or `refuse`), optional declared `protocol`, and optional
`measured` supplied outcomes with a declared `time_unit`
(seconds/minutes/hours) for exact comparison.

The model is piecewise constant with a declared left-closed endpoint
convention: each observation holds from its own timestamp until the next, and
the last observation holds until the declared horizon. Time is bucketed
exactly into above / below / at-limit (an observation exactly on the limit is
its own bucket and breaks an above-limit run). Reports disjoint sums per
bucket, the maximum continuous above-limit excursion with run count, per
interval source-linked traces (source, id, source_index in input order, sorted
by normalized instant), and coverage: largest sampling gap, gap list, and gap
policy. Duplicate instants refuse after UTC normalization, including across
different offset spellings. Naive timestamps, unsupported units, and
observations whose declared protocol conflicts with the spec protocol refuse;
observations without a declared protocol are traced as `protocol_declared:
false` rather than silently accepted as verified. Horizon before the last
observation, observations past the declared horizon, and zero-duration
evaluations refuse; nothing is extrapolated or gap-filled. Inputs are never
mutated.

Refusals: non-object input; missing/out-of-range/non-finite/boolean `rh_limit`
or `rh`; unknown or mixed units; naive or malformed timestamps; duplicate
instants; observations cap exceeded (4096 accepted, 4097 refused); non-positive
`max_gap_seconds`; unknown `gap_policy` or `time_unit`; coverage gaps under
`refuse` policy. Boundary flags always report `physical_test_performed:
false`, `degradation_or_lifetime_modeled: false`, `certification_issued:
false`, `gaps_filled: false`, `extrapolated_past_horizon: false`.

Verification: hand rectangle and piecewise bucket known answers; exact
at-limit endpoint handling; max continuous run versus disjoint sum including
at-limit run reset; an independent test-local rectangle integrator as base
comparison; mutant checks flipping one observation across the limit and
tampering with supplied measured outcomes; exact caps N/N+1. Mounted
production auth/tenant checks verified with the wiring patch applied locally,
then reverted.

Wiring into the shared engineering workbench (`engineering_1510_1559.py`
`humidity_testing` accepting an optional `exposure` object, plus mounted
auth/tenant tests) is delivered as a separate unapplied patch for the
integrator. No model, paid API, external execution, persistent state, shared
PG, or other row closure.
