# ZOPA93-INTERVAL: declared-interval ZOPA mapping (row 93)

Candidate target: row 93 "ZOPA Mapping" in `audits/additional-2000-features.json` (title only; bounded accepted scope, not full negotiation capability). Independent gate: separate record.

Core: `backend/app/modules/m20_general_cognitive_worker/zopa93.py`, function `map_zopa(request)`.
Tests: `tests/modules/test_m20_zopa93.py`. Wiring into `negotiation_behavior_0085_0109.py` is a separate unapplied patch; until applied, no mounted route exposes this core, so no tenant/auth claim is made for it.

## Input
`currency` and `unit` (both required, non-empty strings), `buyer_intervals` and `seller_intervals` (non-empty lists). Each interval: `id` (non-empty string, unique across both sides), `low`, `high`, optional `low_inclusive` / `high_inclusive` (booleans, default true), optional `source`, optional `currency` / `unit` that must equal the top-level values. Numbers: int, finite float, decimal or fraction string. Booleans, NaN, infinity, None and unparsable strings are refused. Unknown fields are refused, so no reservation estimate can be smuggled in.

## Computation
All arithmetic is exact (`Fraction`). Each side is a set of declared acceptable-price intervals. Output is every pairwise buyer-seller intersection, normalized: sorted, overlapping or touching pieces merged when the meeting endpoint is covered by at least one inclusive side (`[0,5)` and `[5,9]` merge; `[0,5)` and `(5,9]` stay separate). Multiple disjoint feasible intervals are all kept. Each output interval lists the `buyer_ids` and `seller_ids` of declared intervals that touch it; `sources` echoes supplied source labels. Result is independent of input order.

Refused with `ZopaError`: empty or inverted interval (a single point needs both endpoints inclusive), duplicate ids, missing or mismatched currency/unit, empty sides, non-object input.

## Output
`status` is `overlap` or `no_overlap`; `zopa_intervals` as above with endpoints as exact strings (`"1/2"`). `overlap_is_agreement` and `inferred_reservation_values` are always false. `limits` states that overlap is not agreement, no-overlap is not proof that no deal exists, and that there is no inferred value, bargaining-power claim, persuasion or external message.

## Not done
No reservation inference, no recommendation of a price, no message sending, no negotiation on anyone's behalf, no counterparty fact verification, no network, no persistence. Declared intervals are taken as supplied.

## Evidence at authoring time
See manifest: red, green, mutant and exhaustive-oracle logs. Mutant m4 (lower-bound inclusive logic) survives and is judged equivalent, not killed.
