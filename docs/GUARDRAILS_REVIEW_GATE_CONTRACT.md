# Effect-Category Review Gate - Contract (group 137, lines 60-61)

Bounded mechanism: `backend/app/runtime/guardrails/review_gate.py`. An
enforced runtime check: no contact, application, submission or account
action executes without an approved hash-exact review permit or a live
exact-scope preauthorization. Generalizes the landed m02 reviewed_execution
draft gate to the four effect categories in the doc.

## Flow

1. `open_review(ledger, action, ...)` binds (action_id, category,
   payload_sha256) - the payload digest is recomputed from the payload, so a
   tampered payload cannot ride a stale hash.
2. `record_decision(...)` appends the human decision; one decision per
   review, final.
3. `issue_permit(...)` requires approved, hash-exact, inside the validity
   window; single permit per review.
4. `grant_preauthorization(...)` / `revoke_preauthorization(...)` implement
   the doc's "unless specifically preauthorized" branch with EXACT
   category + payload-hash scope, an expiry, and final revocation. There are
   no wildcard scopes.
5. `execute(ledger, action, effect=..., now=..., permit_id=...)` is the
   choke point: without a valid permit or live preauthorization it raises
   `GuardrailRefusal("REVGATE:...")` and the effect is never called. A
   permit is spent on the chain before the effect runs (single-use); a
   preauthorization use is ledgered.

## Ledger

Hash-chained records: review_opened, review_decision, execution_permit,
permit_spent, preauthorization, preauthorization_revoked,
preauthorization_used, execution_refused. Refused executions are ledgered
with the reason code as durable evidence. `loads` re-verifies chain, per-kind
content and cross-record order (no decision before open, no permit before
approval, no spend before issue, no use of unknown grants).

## Limits (named, none hidden)

- Reviewer and grantor identities are caller-supplied labels, not
  authentication; the gate cannot know who decided.
- A permit or preauthorization covers exactly one category + payload hash
  and authorizes nothing outside `execute()`; no external system is
  notified.
- The ledger is tamper-evident, not tamper-proof; safe storage of the
  serialized ledger is the caller's job.
