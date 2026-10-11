# M20 Row 95 Contract: Exact Anchoring-Reference Audit (ANCHOR95)

Ledger source (audits/additional-2000-features.json, id 95, status PARTIAL):

> - requirement: "Anchoring Strategy"
> - description: "Sets negotiation reference points"

## Delta from the existing mechanism

Existing mechanism: `_anchoring()` in
`backend/app/modules/m20_general_cognitive_worker/negotiation_behavior_0085_0109.py` at line 339.
This row-95 audit unit changes it materially:

- **No confidence score or deployment verdict.** The mechanism returns `confidence: 0.6/0.9`
  and `deployment_allowed`; the unit reports neither - it audits whether a reference point is
  supported by the stated evidence range and leaves any decision to the human reviewer.
- **Exact rational arithmetic.** The mechanism uses floats throughout; the unit accepts integers
  or `"p/q"` strings and emits every figure as an exact `"p/q"` string. The clamp, midpoint,
  band and settlement zone are computed exactly.
- **Honestly labelled heuristic.** `estimated_adjustment_band` becomes
  `heuristic_adjustment_band`; the limits state plainly that (range / 4) is a stated heuristic.
- **Exact input validation.** Missing, boolean, float or non-rational values, inverted ranges,
  unknown keys and non-dict requests are refused with row-tagged codes.
- **Ethical refusal.** Requests keyed to deceive, mislead, bluff, fabricate, inflate or
  misrepresent are refused. The out-of-range rejection text is preserved from the mechanism.

## Refusal codes (`ANCHOR95:`)

`BAD_TYPE:request`, `BAD_TYPE:key`, `DECEPTIVE_ANCHOR:<key>`, `UNKNOWN_KEY:'<key>'`,
`MISSING:<field>`, `BAD_TYPE:value`, `INVERTED_RANGE`.

## Limits

- This is a bounded audit unit, not shipped product code.
- The adjustment band is (range / 4), a stated heuristic, not a measurement.
- Anchor pull varies widely by counterparty; no settlement outcome is predicted.
- A reference point outside the stated evidence range is rejected, not clamped.
- The unit does not advise on negotiation strategy and makes no claim that any anchor will be
  accepted or effective.
- The raw-length precheck on string values is a resource guard only; it is
  behavior-unobservable because the grammar already bounds every accepted string.
- Key refusal precedence follows sorted key order, not a ban-first guarantee:
  `{'a': 1, 'deceive': 1}` refuses `UNKNOWN_KEY:'a'` before any banned-key check
  runs. This is existing behavior and is stated, not changed.
- Unicode scope: control/format/line-separator characters in an unknown key are
  NOT screened; they can appear inside the `UNKNOWN_KEY` message only through
  `repr` escapes (e.g. a right-to-left override appears as its `\\u202e` escape,
  never as a live character). Full Unicode hygiene on keys is out of scope here.

## Value grammar (pinned)

- Raw string length at most 64 checked first, then a full ASCII match
  `^-?[0-9]{1,18}(/[0-9]{1,18})?$` - one optional leading minus, no plus sign, no
  whitespace, no exponent, no decimal point, nonzero denominator. Every failure refuses
  `BAD_TYPE:value` and the refusal never echoes the value text.
- Integer values: bools refused; magnitude at most 10^18-1 checked before any `Fraction`
  conversion; negative integers stay accepted.
- Key handling: non-string keys refuse `BAD_TYPE:key` before any echo; `UNKNOWN_KEY`
  echoes the key truncated to 128 raw characters before `repr`.
