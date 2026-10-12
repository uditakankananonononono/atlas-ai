# Research-Conduction Completion Gate - Contract (group 140, lines 1, 54,
81, 211)

Bounded mechanism: `backend/app/runtime/guardrails/research_gate.py`. An
enforced runtime check: a research project may only be marked "conducted"
with bound conduction evidence. This document scopes the mechanism only.

## Evidence legs (all required)

1. `register_dataset` - at least one dataset the work ran on.
2. `record_run` - at least one executed run with ordered start/end
   timestamps, carrying the digest of what it produced.
3. `record_result` - at least one recorded result; every run's
   `result_sha256` must match a recorded result digest (binding).

`claim_conducted(ledger, project_id, claim_id, statement=..., now=...)` is
the choke point. Missing legs -> `GuardrailRefusal("RESGATE:refused:missing_evidence")`
naming exactly which legs are absent; a run whose digest binds no recorded
result -> `refused:unbound_run_result` naming the runs. Refusals are
ledgered first. The exact completion statement is hash-bound into the claim
record so it cannot be swapped afterwards.

## Limits (named, none hidden)

- The gate enforces presence and digest-binding of caller-attested evidence;
  it does not rerun experiments or judge scientific validity, novelty or
  benchmark standing.
- A `conducted` verdict means evidence exists and is bound - not that the
  research is correct.
