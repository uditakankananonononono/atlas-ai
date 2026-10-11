# M20-BDD686-EXEC-01: bounded execution of a declarative Given/When/Then DSL

Scoped capability for row 686 Behavior-Driven Development only. Does NOT close
the full row title: no natural-language parsing of prose feature files, no
step-definition matching, no test-runner or repository integration, no
certification that any real system behaves as the scenario claims. The row's
existing PARTIAL diagnostic in `software_practice_685_709.py`
(`behavior_driven_development`, Given/When/Then completeness labeling) is
untouched; this unit adds actual bounded execution as a separate module.
Wiring into the shared 685-709 method surface ships as a separate
integrator-applied row-686-only patch.

Input: `scenarios` (1..16), each with `given`, `when`, `then` sections
(0..32 steps each), optional unique `name`; run-level `max_steps`
(1..4096, default 512). State is typed scalar: bounded integers
(abs <= 2^62), booleans, strings (<= 256 chars). `True` and `1` are distinct
values. Variables are identifiers; every scenario starts from fresh empty
state (isolation: no cross-scenario leakage, verified by test).

Operations (allowlisted, everything else refused): `assign` (set a variable
to a literal) and `increment` (add a bounded integer to an existing integer
variable) in `given`/`when`; assertions `equals` / `not_equals` with typed
equality in `then`. No arithmetic expressions, no arbitrary code, no I/O.

Semantics: steps apply sequentially in listed order - simultaneous or
parallel assignment semantics is NOT used, so step order is observable and
reordering changes outcomes (documented and tested). `then` requires ALL
assertions to hold (never any-of); the first failure is reported with a
source-linked trace: section, step index within the section, the step
content, reason (`assertion_failed`, `unknown_variable`, `type_mismatch`,
`integer_overflow`) plus expected/actual where meaningful. Integer overflow
past +/-2^62 is a traced failure, never wraparound.

Run status: `all_passed` only when every scenario passes; `failures_present`
when any scenario fails; `inconclusive_step_cap_exceeded` when the exact
executed-step cap (counted across all sections and scenarios) is hit - no
pass is claimed, affected scenarios are `incomplete`/`not_run`, and
`steps_executed` equals the cap.

Refusals (ValueError, 422 at the route): non-object input; scenario count
outside 1..16 (16 accepted, 17 refused); missing sections; section steps
outside 0..32 (33 refused); duplicate scenario names; unsupported op or
assert kind; invalid variable identifiers; floats, nulls, lists, objects,
over-long strings or out-of-range integers as literals; boolean or float
`by`; invalid `max_steps`.

Receipt: deterministic (byte-identical for identical input), with
`semantics` (ordering, simultaneous=false, isolation, then_requires=all),
`steps_executed`, `max_steps`, and `provenance` (input sha256;
`repository_behavior_certified: false`, `natural_language_interpreted:
false`, `arbitrary_code_executed: false`, `external_task_scheduled: false`).
`human_review_required: true`.

Tests (`tests/modules/test_m20_bdd686_exec.py`): exhaustive small
state-machine oracle - all 1555 op sequences of length <= 4 over a 6-op
2-variable set checked against an independent reference interpreter, both
for correct-state acceptance and wrong-state rejection; known-answer
pass/fail fixtures with exact source-linked traces; sequential-order
observability; scenario isolation; then-all-not-any; unknown variable and
type-mismatch traces; overflow and boundary-increment acceptance; exact
step caps (cap-1 runs, cap hits inconclusive); exact scenario/section
bounds N/N+1; malformed-step and malformed-request refusals; duplicate
names; bool/int type distinction; receipt determinism and provenance; a
naive shared-state any-of-then baseline floor over a 150-case seeded corpus
(engine detection is a superset of the baseline's, with strictly more
catches from isolation and all-of-then). Mounted auth/tenant route checks
live in the separate wiring patch.

## Advisory disclosures (auditor pin round)

- Exact acceptance/refusal pairs are pinned, both directions: assignment integers
  and increment amounts accept +2^62 and -2^62 and refuse +/-(2^62+1); scalar
  strings accept 256 characters and refuse 257; variable names accept 64
  characters and refuse 65.
- `provenance.input_sha256` binds the WHOLE caller packet: top-level JSON keys
  the executor does not use are ignored for execution but still change the hash.
- Status priority: an assertion failure in an earlier scenario followed by the
  step cap in a later one reports top status `inconclusive_step_cap_exceeded`
  while the earlier failure trace is preserved per scenario.
- Generated names for unnamed scenarios (`scenario-<index>`) live in the same
  namespace as explicit names; a generated name colliding with an explicit one
  is refused as a duplicate.
- Scenario names have NO length cap by deliberate resource-hardening choice:
  resource limits live on scenario count, steps per section, and the executed
  step cap, not on name length (a 5,000,000-character name is permitted).
- Caller packets are JSON-typed. Inputs outside JSON types (for example bytes,
  or dicts with non-string keys) can surface a TypeError from canonical hashing
  rather than a ValueError; this contract does NOT claim that every malformed
  input is refused with ValueError.
- Equality is exact type identity: an int subclass (including bool) is a
  different type from int, and an unknown variable fails BOTH assertion kinds
  (`equals` and `not_equals`) with an `unknown_variable` trace.
