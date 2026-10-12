# Report Emission Gate - Contract (group 142, lines 55, 211)

Bounded mechanism: `backend/app/runtime/guardrails/report_gate.py`. An
enforced runtime check over every report BEFORE it leaves the system,
wrapping the landed claim_status check (P65|L55). This document scopes the
mechanism only; the claim grammar and label set belong to the claim_status
contract.

## Rule

`emit_report(report_id, body, now=..., ledger=...)` runs
`claim_status.check_text` and:

- every claim labeled -> verdict `emitted`; the report digest and counts are
  ledgered and the record returned;
- unmarked claims -> `GuardrailRefusal("REPGATE:refused:unmarked_claims")`;
- conflicting labels -> `refused:conflicting_claims`;
- structural ambiguity -> `refused:structural_ambiguous`;
- zero claims -> `refused:vacuous` (a vacuous check proves nothing).

Refusals are ledgered first, with the findings (1-based line, kind, reason,
capped at 64). Only the report digest is stored.

## Limits (named, none hidden)

- Enforces explicit claim labeling only; it cannot verify that a VERIFIED
  label is true. That binding comes from the evidence gates
  (research_gate, tool_usage_bar) the claims point at.
- The claim grammar covers table rows with exactly one Label/Status column
  and CLAIM: marker lines; other prose is not checked.
