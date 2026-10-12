# Bio Work Admission Gate - Contract (groups 134 + 135, lines 57-58)

Bounded mechanism: `backend/app/runtime/guardrails/bio_gate.py`. An enforced
runtime check over every biology-scoped work item BEFORE any effect runs,
composing the two landed contract helpers into one admission decision. This
document scopes the mechanism only.

## Decision pipeline

1. **P69|L58 prohibited-bio screen** over the item's `text`: a blocked
   verdict (`wet_lab_protocol`, `pathogen_enhancement`, `harm_instruction`)
   is an unconditional refusal. No approval path can override it; the
   approval hook is never called.
2. **P68|L57 in-silico classification** over `domain_terms` +
   `execution_mode`: `not_bio_scoped` and `allowed_in_silico` admit;
   `refused_physical_without_review` refuses;
   `flagged_physical_with_review_ref` admits only when the caller-supplied
   `approval_check(approval_ref, action_digest)` hook accepts. The digest is
   the sha256 of the canonical checked item, so the approval binds to the
   action's exact content. With no hook the gate
   fails closed (`refused:physical_approval_unverifiable`).

## Enforcement surface

- `admit(item, now=..., ledger=..., approval_check=...)` -> (ledger, decision
  record). Refusal is a verdict on the record, never an exception.
- `run_guarded(effect, item, ...)` -> (ledger, effect result). The choke
  point: raises `GuardrailRefusal` on a refused verdict and the effect is
  never called. Admitted effects ledger `effect` outcome records
  (completed/failed with the error type name).

## Ledger

Hash-chained, append-only (shared `ledger.py` machinery, same construction
as m02 reviewed_execution). `decision` records carry the exact P68/P69
verdicts, the approval-hook booleans and the final verdict; `effect` records
carry the outcome. `dumps`/`loads` round-trip re-verifies chain, per-kind
shape and field validity. Tampering with any record breaks the chain check.

## Limits (named, none hidden)

- Lexical enforcement over the item's declared text and domain terms only;
  not a biosafety, ethics or legal review.
- A clear P69 screen means only that no listed pattern matched; the closed
  pattern list is contract-governed by the P69 contract doc.
- `approval_check` is caller-bound and must return the boolean True or a
  verified-permit mapping {"verified": True}; any truthy non-True value
  rejects. The gate records its strict verdict and
  never authenticates, resolves or trusts an `approval_ref` by itself.
- The ledger is tamper-evident, not tamper-proof; safe storage of the
  serialized ledger is the caller's job.
- Admission/spend records are committed write-ahead via the `on_commit` hook BEFORE the effect runs and are retained on ANY exception the effect raises; an effect that fails after admission reconciles as spent-pending-review, never silently re-usable. Without a wired `on_commit`/persist sink the ledger lives in memory only.
