# M20 Row 96 Contract: Exact Framing-Equivalence Audit (FRAMIN96)

Ledger source (audits/additional-2000-features.json, id 96, status PARTIAL):

> - requirement: "Framing Effects Utilization"
> - description: "Presents options to influence choices"

## Delta from the existing mechanism

Existing mechanism: `_balanced_frames()` (shared with row 97) in
`backend/app/modules/m20_general_cognitive_worker/negotiation_behavior_0085_0109.py` at line 368.
This row-96 audit unit changes it materially:

- **No confidence score or deployment verdict.** The mechanism returns `confidence: 0.8/0.4` and
  `deployment_allowed`; the unit reports neither - it audits equivalence and consistency and
  leaves any decision to the human reviewer.
- **Exact rational arithmetic.** The mechanism extracts numerals as floats and compares the fact
  delta with a `1e-9` epsilon; the unit extracts numerals as exact `Fraction` values, compares
  sorted lists exactly, and checks delta consistency by exact equality.
- **Exact input validation.** The mechanism raises one generic error for any bad input; the unit
  distinguishes missing, mistyped and empty frames and facts, refuses float, bool and
  non-decimal deltas, and refuses unknown keys, each with a row-tagged code.
- **Ethical refusal.** Requests keyed to exploit, manipulate, deceive, mislead, coerce or hide
  are refused. Balanced presentation remains required: the unit always reports both frames and
  selects `both`, never a single frame.

## Refusal codes (`FRAMIN96:`)

`BAD_TYPE:request`, `OVERSIZE:request`, `BAD_TYPE:key`, `MANIPULATION_REQUEST:<key>`,
`UNKNOWN_KEY:'<key>'`,
`MISSING:gain_frame`, `MISSING:loss_frame`, `MISSING:facts`, `BAD_TYPE:frame`,
`EMPTY:frame`, `OVERSIZE:gain_frame`, `OVERSIZE:loss_frame`, `BAD_TYPE:facts`,
`EMPTY:facts`, `OVERSIZE:facts`, `BAD_TYPE:facts_key`, `BAD_TYPE:facts_value`,
`BAD_TYPE:delta`, `OVERSIZE:delta`.

## Limits

- This is a bounded audit unit, not shipped product code.
- Equivalence is checked on extracted numerals only; wording emphasis is not measured.
- One-sided framing and exploitation of loss aversion are refused.
- The unit does not advise which frame to use and makes no claim that framing changes decisions.

## Numeral grammar (pinned)

- Numerals are ASCII only: `[0-9]+(\.[0-9]+)?`. Arabic-Indic and other non-ASCII
  digits are NOT numerals.
- `-` is a sign only at string start, directly after whitespace, or directly after
  `(`, and only before a digit; everywhere else it is a range separator.
  So `10-15` yields 10 and 15, `x-5` yields 5, while `-5`, `(-5)` and `a -5`
  yield negative five.
- Thousands: the strict form `[0-9]{1,3}(,[0-9]{3})+` (optional decimal) is ONE
  number with commas removed - `1,234` is 1234, never a list; `1,000` is 1000;
  `1,234.5` is 2469/2. Every other comma form is a separator: `1,2,3` yields
  1, 2, 3 and `1,00` yields 1 and 0.
- Resource guards: raw frame text longer than 2000 chars refuses
  `OVERSIZE:gain_frame` / `OVERSIZE:loss_frame` before any processing; a numeral
  with more than 18 integer or 18 fraction digits refuses the same field code
  before any `Fraction` conversion; more than 64 numerals in one frame refuses
  the same field code.

## Facts payload (pinned)

- Exact dict (`type(x) is dict`), key count cap 64 checked first
  (`OVERSIZE:facts`); a key over 128 raw chars refuses `OVERSIZE:facts` BEFORE
  the Unicode check, otherwise keys are strings with no Cc, Cf, Zl or Zp
  character (`BAD_TYPE:facts_key`) and accept Zs; a string value over 128 raw
  chars refuses `OVERSIZE:facts` BEFORE the Unicode check, otherwise the same
  Unicode rules apply (`BAD_TYPE:facts_value`).
- Values are scalars only: str (<=128 chars), int, float, bool or None. Nested
  lists/dicts refuse `BAD_TYPE:facts_value`.
- DISCLOSURE (behavior change): earlier revisions accepted nested lists/dicts in
  `facts` and echoed them; they are now refused.

## Tri-state consistency (pinned)

- `consistent_with_facts` is `None` and `facts_checked` is `False` when the facts
  carry no `delta` or either frame yields no numerals. A real comparison yields
  `True`/`False` and `facts_checked` is `True`.
- DISCLOSURE (behavior change): earlier revisions reported
  `consistent_with_facts: True` when there was no delta or no numerals; they now
  report `None` with `facts_checked: False`.

## Fact delta grammar (pinned)

- Strings: raw length at most 64 first (`OVERSIZE:delta`), then full ASCII match
  of the signed decimal `-?[0-9]{1,18}(\.[0-9]{1,18})?` - no p/q, no exponent,
  no sign other than leading minus, no whitespace. Wrong type or invalid grammar
  (`1/2`, `1e3`, `.5`, `5.`, `+1`, spaces, underscores, thousands forms, a bare
  minus, non-ASCII digits) refuses `BAD_TYPE:delta`; a plain digit shape with
  over 18 whole or over 18 fraction digits refuses `OVERSIZE:delta`. Integers:
  bool refused, absolute value at most 10^18-1 before any `Fraction` conversion,
  larger integers refuse `OVERSIZE:delta`. Negative deltas stay accepted.
  Failures never echo the value.
- DISCLOSURE (behavior change): earlier revisions accepted p/q delta strings
  (`19/1`, `-1/2`) and refused decimals; deltas are now DECIMAL - `12.5` parses
  and `1/2` refuses.
- `consistent_with_facts` compares MAGNITUDES only; the sign of the delta is not
  checked against the text.

## Free-text rules (pinned)

- Free text never refuses numeric SHAPE: `1e3` reads as 1, 3; `.5` and `5.` read
  as 5; `1/2` reads as 1, 2; strict thousands read as one number; other commas
  separate; Arabic-Indic digits are not numerals; `10-15` reads as 10, 15.
- Any digit RUN over 18 integer or 18 fraction digits refuses the ENTIRE field
  with `OVERSIZE:gain_frame` / `OVERSIZE:loss_frame` (no skip, split or
  truncate); more than 64 numerals and raw text over 2000 chars refuse the same
  field codes (raw first). Refusals carry no digit or value echo.

## Facts payload (pinned additions)

- Non-finite float values (NaN, inf, -inf) refuse `BAD_TYPE:facts_value` via a
  finite check before any echo or comparison; finite floats (0.0, -0.0, 1e300,
  12.5) are accepted and echoed. DISCLOSURE (behavior change): non-finite facts
  were previously accepted.

## Key handling (pinned)

- A request key over 128 raw chars refuses `OVERSIZE:request`; a non-string key
  or one with Cc/Cf/Zl/Zp characters refuses `BAD_TYPE:key`, all before any echo
  and with no key text or length in the reason; `UNKNOWN_KEY` echoes the key
  truncated to 128 raw chars before `repr`.
