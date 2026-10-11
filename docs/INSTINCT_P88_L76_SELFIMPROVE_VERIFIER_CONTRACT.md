# P88|L76 deliverable 12 - self-improvement hook verifier contract

Source line, verbatim as relayed by the integrator (the crosswalk lane has nothing more; I did not see the original instinct doc myself):

> Deliverable 12: self-improvement mechanisms per tool/module,

Module: `backend/app/modules/instinct_doc/selfimprove_verifier_p88.py`. Pure stdlib (`fractions`, `math`, `typing`), no I/O, no network, no clock, no module import, no code execution.

## Scope
This unit VERIFIES that a declared self-improvement mechanism has a consistent recorded round trip on fixture tasks: register -> propose delta -> re-score -> accept/reject.
It does not implement module self-improvement, does not run the mechanism, and does not touch the separate P61 line.
The source line pins no field names, verdicts, refusal codes, limits or accept rule. **Everything below is an INTERPRETATION CHOICE** unless stated otherwise, to be confirmed or replaced by the contract owner.

## API (INTERPRETATION CHOICE)
`verify(record) -> dict`. Record keys, exactly: `id` (nonblank, <=64), `mechanism` {`declared` bool, `hook_ref` string <=128}, `accept_threshold` (finite number, |x|<=10^12), `min_improvement` (finite number, 0..10^12),
`tasks` (list of 0..32 tasks; INTERPRETATION CHOICE: 0 is allowed so that an undeclared module needs no fixtures).
Task keys: required `id` (nonblank, <=64), `baseline_score` (number); optional `delta` (nonblank string <=128), `rescored` (number), `decision` (`accept` or `reject`). Absent and null mean the stage has not happened. Numbers are int or float, never bool or subclasses.

## Rule (INTERPRETATION CHOICE)
Expected decision for a task with `rescored`: `accept` iff `rescored - baseline_score >= min_improvement` and `rescored >= accept_threshold`, otherwise `reject`. Comparison uses exact `Fraction` arithmetic on the given binary values; both boundaries are inclusive.

## Stages and verdicts (INTERPRETATION CHOICE)
Registered = `declared` true and a non-blank `hook_ref`. A task is `complete` when proposed (delta), re-scored and decided are all present and the decision equals the expected one; `incomplete` if any stage is missing; `inconsistent` if all stages are present and the decision differs.
Verdict precedence: `no_mechanism_declared` (not registered) > `roundtrip_incomplete` (no tasks or any incomplete task) > `decision_inconsistent` > `roundtrip_consistent`.
`reasons` lists every cause found (sorted): `not_declared`, `hook_ref_missing`, `no_fixture_tasks`, `incomplete_tasks`, `decision_mismatch`.
`both_decisions_exercised` is informational (INTERPRETATION CHOICE: it never changes the verdict): true when complete tasks include both an accept and a reject.
Tasks are returned sorted by id. The record states `mechanism_executed`, `improvement_claimed` and `real_mechanism_verified` all false.

## Refusals (INTERPRETATION CHOICE; ValueError, exact text)
`P88:bad_type:<name>`, `P88:unknown_fields:<record|mechanism|task>`, `P88:empty_field:<name>` (missing required key or blank string; task id is `task_id`), `P88:text_too_long:<name>`, `P88:bad_value:<name>` (non-finite or out-of-range number, or a decision other than accept/reject), `P88:limit_exceeded:tasks` (>32), `P88:duplicate_task_id:<id>`.
Order: record type, unknown keys, missing keys, id, mechanism (type, keys, declared, hook_ref), accept_threshold, min_improvement, tasks container and count, then tasks in sorted-id order (items without a string id last, in input order); inside a task: type, keys, missing keys, id, baseline_score, delta, rescored, decision. First failure wins.

## Limits
Consistency check over caller-supplied recorded fixtures only. `roundtrip_consistent` is not evidence of real self-improvement or of the hook's existence. No wiring, no ledger edits.
