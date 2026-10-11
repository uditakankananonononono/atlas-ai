# M20 Row 94 Contract: Exact Integrative-Bargaining Priority Audit (INTEGR94)

Ledger source (audits/additional-2000-features.json, id 94, status PARTIAL):

> - requirement: "Integrative Bargaining"
> - description: "Creates win-win solutions"

## Delta from the existing mechanism

Existing mechanism: `_integrative()` in
`backend/app/modules/m20_general_cognitive_worker/negotiation_behavior_0085_0109.py` at line 304.
This row-94 audit unit changes it materially:

- **No confidence score.** The mechanism returns `confidence: 0.65`; the unit reports no
  confidence, probability or estimate numbers anywhere.
- **Exact rational arithmetic.** The mechanism normalizes with floats and rounds every output to
  6 decimals; the unit normalizes with `Fraction` and emits every priority, complementarity and
  gain as an exact `"p/q"` string. Weights are accepted as integers or `"p/q"` strings.
- **Explicit ties.** The mechanism assigns `efficient_holder: party_a` whenever priorities are
  equal; the unit reports `tie` and counts ties. The mechanism flags purely-distributive cases
  with a `1e-9` epsilon; the unit uses exact equality.
- **Deterministic ordering.** The tradeoff order sorts by complementarity descending, ties
  broken by issue name, so output is order-independent of nothing but the declared inputs.
- **Exact input validation.** Misaligned lengths, duplicate or blank issues, non-rational or
  negative weights, zero-sum parties, oversized lists, unknown keys and non-dict requests are
  refused with row-tagged codes instead of mixing types or dividing by a substituted 1.0.
- **Ethical refusal.** Requests keyed to deceive, mislead, hide, conceal, exploit or manipulate
  are refused. The existing mechanism has no such refusal.

## Refusal codes (`INTEGR94:`)

`BAD_TYPE:request`, `DECEPTION_REQUEST:<key>`, `UNKNOWN_KEY:'<key>'`, `BAD_TYPE:issues`,
`EMPTY:issues`, `BAD_TYPE:issue`, `DUPLICATE:issue`, `OVERSIZE:issues`, `LENGTH_MISMATCH`,
`BAD_TYPE:key`, `OVERSIZE:keys`, `BAD_TYPE:weight`, `NEGATIVE:weight`, `OVERSIZE:weight`, `ZERO_SUM:party_a`, `ZERO_SUM:party_b`.

Refusal order: the request dict's key-count cap fires before any key is
inspected; then key conformance (exactly `str`, at most 128 chars, no Unicode
Cc/Cf/Zl/Zp characters - Zs is allowed); then deception keys; then unknown keys.
All collections are checked in the order: exact type (`type(x) is list/dict`),
then count, with caps enforced before item iteration.

## Limits

- This is a bounded audit unit, not shipped product code.
- Weights are stated priorities normalized exactly per party; misstated priorities change the
  mechanical allocation the audit reports.
- A tie is reported as tie; the audit never silently awards an issue.
- The audit compares declared numbers only. It never manufactures issues, advises on negotiation
  strategy, or claims any agreement is achievable or fair.

## Pinned output surface

- `limits` carries exactly four strings, in order, and they are pinned verbatim by tests.
- `tradeoff_order` is always present; each entry has exactly the keys `issue` and
  `complementarity`, sorted by complementarity descending then issue name ascending.

## Weight grammar (pinned)

- String weights: raw length at most 40 checked first (no echo on refusal), then a
  full ASCII match `^[0-9]{1,18}(/[0-9]{1,18})?$` - no whitespace stripping, no sign,
  no exponent, no decimal point. Denominator must be nonzero. All failures refuse
  `BAD_TYPE:weight`. Leading zeros (`007`, `1/02`) are accepted by design.
- Integer weights: bools refused `BAD_TYPE:weight`; negatives refused
  `NEGATIVE:weight`; the range 0..10^18-1 is checked before any `Fraction`
  conversion and larger integers refuse `OVERSIZE:weight`.
- Floats and every other non-int, non-string type refuse `BAD_TYPE:weight`.
- String change disclosure: strings carrying a sign (e.g. `-1`) previously parsed
  and refused `NEGATIVE:weight`; under the grammar they now refuse
  `BAD_TYPE:weight`. They are refused either way - no acceptance changed.
- Refusal messages never echo the offending weight text.

## Known gaps (reported, not fixed)

- **Issue-name echo has no Unicode cleaning.** Issue strings are echoed into the
  allocation and tradeoff order exactly as supplied; no control/format character
  screening is applied.
