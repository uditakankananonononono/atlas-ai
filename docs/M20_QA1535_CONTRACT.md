# QA1535-EVIDENCE-01: requirement and test evidence evaluation

Candidate target row 1535 Quality Assurance only. Scope is evaluation of
caller-supplied requirements, predeclared typed acceptance conditions and
caller-supplied observations. It is not a physical test, not a certification,
and it grants no release authority. A caller flag requesting release is
ignored and reported as ignored.

Function: `evaluate_qa_evidence(request)` in `qa_evidence1535.py`. Pure, no
persistence, no files, no network, no effects.

Request fields: `requirements`, `observations`, `defect_policy`
(`refuse` or `flag`, required), optional `caller_release_requested`.
Unknown fields are refused.

Requirement: `id`, `mode` (`all` default, or `any`), `min_repeats` (1..16,
default 1), `conditions` (1..16). A condition names `test_id`, `metric`, `op`
(`<`, `<=`, `>`, `>=`, `==`, `!=`, `between`) and a finite numeric
`threshold` (`[low, high]` inclusive for `between`).

Observation: `id`, `test_id`, `metric`, finite numeric `value`, `signed`
(must be `true`), `source` (non-empty), `time` (ISO-8601 with timezone),
optional `run_id`.

Bounds: requirements 1..64, observations 0..512, ids 1..128 characters.
Out-of-bound or malformed input is refused with an exact message naming the
offending id or field. Duplicate requirement or observation ids are refused.

Evaluation: an observation counts for a condition only when `test_id` and
`metric` both match. Observations with a known test id but no matching metric
are listed as mismatched; unknown test ids as unmapped. Neither counts as
evidence. Observations that are unsigned or lack a source or valid time are
either refused or, under `flag`, excluded and listed under `defects`.
Observations sharing a `run_id` for one test and metric with different values
make that condition UNRESOLVED and are listed under `conflicts`. Otherwise any
refuting observation makes a condition REFUTED; else the condition is
SATISFIED when at least `min_repeats` distinct runs support it (an observation
without `run_id` is its own run); else MISSING. Requirement status combines
conditions: `all` takes the worst of REFUTED, UNRESOLVED, MISSING; `any` is
SATISFIED if one condition is, else UNRESOLVED if one is, else REFUTED if all
are, else MISSING.

Release status is `EVIDENCE-SUPPORTED` only when every requirement is
SATISFIED, otherwise `RELEASE-UNREADY`. Coverage lists satisfied requirement
ids and the status of each unsupported one, by requirement identity, not by
observation count. Output is ordered by id and independent of input order; an
audit trace lists supporting and refuting observation ids per condition.

Not covered: statistical process control, sampling plans, measurement system
analysis, evidence authenticity beyond the declared `signed` flag, and any
ledger or release action. The existing engineering_1510_1559 row 1535
analysis is untouched.
