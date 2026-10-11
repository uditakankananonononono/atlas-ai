# Row 89 - Commitment Device Creation (COMMIT89)

Ledger source pin: `audits/additional-2000-features.json`, row id 89.
Verbatim requirement: "Commitment Device Creation".
Verbatim description: "Locks in future behavior".
Ledger status: PARTIAL.

## Delta against the existing mechanism
Existing: `backend/app/modules/m20_general_cognitive_worker/negotiation_behavior_0085_0109.py:171`
(`_commitment_device`): heuristic weighted strength score (`0.3 + 0.2*...`)
plus an adherence point estimate with an "80% interval" - invented numbers
over a declared structure.

This unit's delta, and only this:
1. No scores, estimates, intervals or confidence numbers anywhere; the output
   is exact structural arithmetic (counts, a reduced-Fraction coverage ratio,
   calendar-day spacing) and an explicit property checklist.
2. Check-ins are validated as ISO dates, deduplicated, sorted, and split into
   before/after-deadline counts exactly.
3. Coercive or irrevocable requests are refused (`COMMIT89:COERCE_REQUEST:<key>`
   for enforce/coerce/irrevocable/lock/punish keys; `COMMIT89:IRREVOCABLE` for
   `reversible=false`), turning the landed unit's prose limit into an enforced
   guard.
4. The penalty value is not echoed; the output reports only whether a penalty was declared (penalty_declared, a boolean). It is never created, enforced or escalated.

It does not edit, wrap, or replace the landed mechanism.

## Interface
`run(request: dict) -> dict` in
`backend/app/modules/m20_general_cognitive_worker/commitment_device_creation89.py`.
Stdlib only (`datetime`, `fractions`); pure, offline, deterministic (check-ins
sorted, verdict derived, byte-stable JSON with sort_keys).

Input keys (all optional except none required beyond schema):
`goal` (non-blank string, <= 200 chars), `deadline` (ISO date),
`checkins` (list of unique ISO dates, <= 64; a check-in exactly on the deadline counts as before-deadline; output order is sorted), `reversible` (bool, must be
true), `self_selected_penalty` (string if present).

Output keys exactly: `goal`, `deadline`, `checkins`, `checkin_count`,
`checkins_before_deadline`, `checkins_after_deadline`, `coverage_ratio`,
`first_to_last_spacing_days`, `checklist` (`has_goal`, `has_deadline`,
`has_checkins`, `all_checkins_before_deadline`, `owner_revocable`,
`penalty_declared`), `missing`, `verdict` (`structurally_complete` or
`missing_properties`), `limits`.

## Refusal codes (ValueError, prefix COMMIT89:)
- `BAD_TYPE:request`, `UNKNOWN_KEY:'<key>'`
- `COERCE_REQUEST:<key>` - banned coercion key
- `BAD_TYPE:goal`, `EMPTY:goal`, `OVERSIZE:goal`
- `BAD_TYPE:deadline`, `BAD_DATE:deadline`
- `BAD_TYPE:checkins`, `BAD_DATE:checkin`, `DUPLICATE:checkin`, `OVERSIZE:checkins`
- `BAD_TYPE:reversible`, `IRREVOCABLE`
- `BAD_TYPE:penalty`

## Limits
- Reports the declared structure only; nothing is measured or predicted about
  adherence or behavior.
- The device remains owner-revocable; coercive, enforced or irrevocable
  requests are refused.
- Calendar arithmetic over supplied ISO strings; no reminder is scheduled and
  no party is notified.
- The penalty value is not echoed; the output reports only whether a penalty was declared (penalty_declared, a boolean). It is never created, enforced or escalated.
