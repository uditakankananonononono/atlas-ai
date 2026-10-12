# Outbound Action Dispatch Gate - Contract (group 136, line 59)

Bounded mechanism: `backend/app/runtime/guardrails/outbound_gate.py`. An
enforced runtime check over every outbound platform action BEFORE it is
performed, composing the landed P70 preflight with ledger-derived rate
history. This document scopes the mechanism only.

## Enforcement surface

`dispatch(action, declarations, effect=..., now=..., ledger=...,
review_check=...)`. The action is a P70 action dict plus an `id` field. The
gate:

1. rebuilds `recent_actions` for the action's platform from its own ledger's
   dispatched records (each contributing its declared `at`, count 1) and
   merges them UNDER the caller's declarations - an action stream that
   passed the gate cannot redeclare its own history to slip under a limit;
   refused dispatches contribute nothing;
2. runs P70 `preflight` over the merged declarations;
3. `deny` -> `GuardrailRefusal("OUTGATE:refused:denied")` with the failed
   check names; the effect is never called;
4. `needs_review` -> requires `review_check(action)` to accept (strict True
   or a verified-permit object), else
   `refused:review_required` (no hook: fail closed);
5. `allow` (or approved review) -> the effect runs and the decision is
   ledgered as `dispatched` / `dispatched:after_review`.

`history(ledger, platform)` exposes the rebuilt rate history.

## Ledger

Hash-chained `decision` records carrying platform, kind, both timestamps,
the preflight verdict, failed check names, review booleans and the final
verdict. `dumps`/`loads` re-verifies chain and content.

## Limits (named, none hidden)

- Checks caller-declared platform rules only; the gate does not fetch live terms
  of service and is not proof of legal compliance.
- `review_check` is caller-bound: only a strict True or a verified-permit
  object accepts (truthy non-True values reject); the gate records the verdict and
  never authenticates a review.
- Ledger-derived rate history covers actions that went through this gate
  only; actions performed outside it are invisible to it.
- The ledger is an unkeyed hash chain: tamper-evident, not tamper-proof. A rehashed edit is not detectable; safe storage of the serialized ledger is the caller's job.
- Admission/spend records are committed write-ahead via the `on_commit` hook BEFORE the effect runs and are retained on ANY exception the effect raises; an effect that fails after admission reconciles as spent-pending-review, never silently re-usable. Without a wired `on_commit`/persist sink the ledger lives in memory only.
