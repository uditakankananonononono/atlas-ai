# QUALC1534: spec-limit conformance bookkeeping (row 1534)

Ledger source pin: `audits/additional-2000-features.json` row 1534, requirement "Quality Control", description "" (empty), status "verified-pushed" (historical builder attribution, not current proof). Ledger file SHA256 `285cc16c474215b241383fb922c8a2f2abfa9f7cda3592b04dc61141317d83ff`, checked at main 3d3d768c; this unit is based on main 0ca1bbee. The ledger description is empty, so the requirement title is the whole spec; the behavior below is this unit's proposal for it. PREP only: nothing is wired, landed or closed.

## Delta against the existing mechanism
Existing: `backend/app/modules/m20_general_cognitive_worker/engineering_1510_1559.py:158` `_qc` (read), using `_values` (L28) and `_summary` (L33), and its test `tests/modules/test_m20_engineering_1510_1559.py:54`. `_qc` casts measurements with `float()`, builds a nonconforming list of index and value, a float `yield_fraction`, a float mean and population standard deviation summary, and the constant `disposition_requires_approval: True`. It has no unit, no ids, no number grammar (float strings, ints and bools pass through the cast), no check that the lower limit is not above the upper, no count bound, no refusal codes and no distinction between below and above limit.
This unit (`quality_control1534.py`, `evaluate_spec_conformance`, new file; it does not import or modify the existing one) differs in these checkable ways:
- Measurements are records (id, value); values and limits are decimal strings (at most 12 integer and 6 fractional digits, ASCII, no exponent); floats, ints, bools and padded strings are refused. Comparison is exact integer comparison. Limits are inclusive: a value equal to a limit conforms.
- A lower limit above the upper limit is refused (`spec_order`); equal limits are allowed.
- Each item gets a status (conforming, nonconforming_below_lower_spec, nonconforming_above_upper_spec), sorted by id; nonconforming items are also listed with a reason.
- The conforming fraction is an exact numerator and denominator plus a six-decimal floor string; there is no float and no standard deviation.
- Observed min and max are exact strings. 1 to 256 measurements.
- Disposition: `disposition` is `none_assigned`, `disposition_requires_approval` true, `disposition_authority` false. Nothing is accepted, rejected or released.
- Refusals are `ValueError("QUALC1534:<code>")` with fixed codes that never echo input.

## Input
Exactly `unit` (text, at most 16 characters), `lower_spec`, `upper_spec`, `measurements`. Each measurement is exactly `id` (unique, nonblank text at most 128 characters, no control characters) and `value`. Input is not mutated.

## Rules checked against the actual schema (child update)
- Limits are inclusive (lower <= x <= upper); equal limits are legal; lower above upper is refused with `QUALC1534:spec_order`. Pins: value at the lower limit, at the upper limit, one millionth outside each, and equal limits.
- The count of measurements (1 to 256) is checked first, before the unit or any number is parsed. A bad count is refused with `QUALC1534:invalid_count:measurements`, which names the field, never the value. Empty is refused; no yield is computed for zero measurements.
- The conforming ratio is exact integer counts plus a six-decimal floor (never rounded up): 2 of 3 is 0.666666.
- `unit` is a label only: nonblank, at most 16 characters, no control characters, echoed, with no conversion and no mixed-unit detection. Text checks run in order: type, length cap, blank, control characters.
- `disposition_requires_approval` is always true; no disposition or release authority; pass and fail are bookkeeping only.
- Not changed: schema and refusal prefix stay `QUALC1534:<code>` as built.

## Refusal codes
invalid_packet, unknown_fields:packet, invalid_text:unit, invalid_number:lower_spec, invalid_number:upper_spec, spec_order, invalid_count:measurements, invalid_record:measurements, invalid_fields:measurements, invalid_text:id, duplicate_id, invalid_number:value. All prefixed `QUALC1534:`.

## Tests and gaps
`tests/modules/test_m20_quality_control1534.py`: hermetic, standard library, N and N+1 pins at both limits, counts, text lengths and number grammar. Raw RED, GREEN, mutation and scan outputs are supplied separately.
FULL-SUITE UNVERIFIED: only this unit's tests and named neighbor tests were run, not the full repository suite.

## Limits
Bookkeeping over declared values only. No statistical process control, capability index, sampling plan, measurement system analysis or acceptance criteria. No disposition, release or certification authority. Values, limits and ids are declared by the caller and not verified. Not an acceptance or closure claim.

## Text characters (child update)
Text fields refuse any character that is a Unicode control, line or paragraph separator, or bidi or format character: categories Cc (including DEL, U+0085), Zl (U+2028), Zp (U+2029) and the ranges U+200B-U+200F, U+202A-U+202E, U+2066-U+2069 and U+FEFF. In short: no Unicode control, line/paragraph separator or bidi/format characters. Ordinary spaces and printable non-ASCII text stay allowed. The helper is `_hidden`, applied inside `_text` after the type, length cap and blank checks.
