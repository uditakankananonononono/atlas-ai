# TOLER1531: exact 1D tolerance stack arithmetic (row 1531)

Ledger source pin: `audits/additional-2000-features.json` row 1531, requirement "Tolerance Analysis", description "" (empty), status "verified-pushed" (historical builder attribution, not current proof). Ledger file SHA256 `285cc16c474215b241383fb922c8a2f2abfa9f7cda3592b04dc61141317d83ff` at main 3d3d768c. The ledger description is empty, so the requirement title is the whole spec; the behavior below is this unit's proposal for it. PREP only: nothing is wired, landed or closed.

## Delta against the existing mechanism
Existing: `backend/app/modules/m20_general_cognitive_worker/engineering_1510_1559.py:149` `_tol` (read) and its test `tests/modules/test_m20_engineering_1510_1559.py:49-50`. `_tol` takes `component_nominals` and `component_tolerances` lists, coerces them with `float()` (accepting strings, bools and non-finite values through the float path), returns the plain sum as the nominal, the sum of absolute tolerances as the worst case and a float square root of the squares as the RSS, with the fixed text "independent centered components for RSS only". It has no unit, no ids or source references, no direction per component (every dimension adds), only symmetric tolerances, no count bound, no limit comparison and no refusal of an empty stack.
This unit (`tolerance_analysis1531.py`, `analyze_tolerance_stack`, new file; it neither imports nor modifies the existing one or `datum_stack1532.py`) differs in these checkable ways:
- Components carry id, a sign (+1 adds the dimension to the stack, -1 subtracts it), a nominal, separate plus and minus tolerances and a source reference. A subtracted dimension swaps which tolerance widens which side of the result.
- Numbers are decimal strings (at most 12 integer and 6 fractional digits, ASCII, no exponent); floats, ints, bools and padded strings are refused. Arithmetic is exact (integer millionths); results are fixed six-decimal strings.
- The caller must declare `assumption`: `worst_case_only` (no RSS is produced) or `rss_independent` (RSS with the independence statement echoed). RSS is returned as exact squared deviations plus floor and ceiling bounds to six decimals from an integer square root, not a float.
- Optional `limits` {min, max}: the worst-case range and the outward RSS bracket (the lower end against min and the upper end against max, both must hold) are compared with them, each as a plain boolean. No capability or pass-to-release claim is made.
- Counts 1..64 and text bounds are enforced; an empty stack is refused. Refusals are `ValueError("TOLER1531:<code>")` with fixed codes that never echo input.

## RSS leg
Symmetric components (plus equal to minus): upper and lower deviation are each the exact square root of the sum of the squares of the tolerances, returned as an exact square (12 decimals) with a floor and a ceiling to six decimals; the outward end is the ceiling. Asymmetric components: the plus side and the minus side are each treated as an independently centered tolerance of their own; up is the square root of the sum of squared plus tolerances and low is the square root of the sum of squared minus tolerances. This is not a mean-shift model: no shift of the nominal is applied. The output carries `distribution_assumption` = "independent components, RSS leg only" and the longer statement. The outward bracket is [nominal - low_ceiling, nominal + up_ceiling], compared as lower >= min and upper <= max.
Refusal form: this unit refuses unsupported input with the `TOLER1531:<code>` form (for example invalid_assumption); it has no input path that reaches a separate `TOLER1531_REFUSED_UNSUPPORTED:rss` code, and none is implemented (open question in NOTES).

## Input
Exactly `unit` (mm, cm, m, inch), `components`, `assumption`, plus optional `limits`. Each component is exactly `id`, `sign`, `nominal`, `plus`, `minus`, `source_ref`. `plus` and `minus` are unsigned; `nominal` and limits may be negative. Ids unique, text nonblank at most 128 characters with no control characters. Input is not mutated; output holds no aliases.

## Output
unit, nominal_stack, worst_case {upper_deviation, lower_deviation, max, min}, rss (or null), limits_check (or null), contributions sorted by id, scope `linear_1d_declared_values_only`, physically_verified false, requires_engineer_review true, boundary.

## Refusal codes
invalid_packet, unknown_fields:packet, unsupported_unit, invalid_assumption, invalid_count:components, invalid_record:components, invalid_fields:components, duplicate_id, invalid_text:id, invalid_text:source_ref, invalid_sign, invalid_number:nominal|plus|minus|limits, invalid_limits, limits_order. All prefixed `TOLER1531:`.

## Tests and gaps
`tests/modules/test_m20_tolerance_analysis1531.py`: hermetic, standard library, N and N+1 pins on every bound and limit. Raw RED, GREEN, mutation and scan outputs are supplied separately.
FULL-SUITE UNVERIFIED: only this unit's tests and named neighbor tests were run, not the full repository suite.

## Limits
One linear dimension only; no geometry, GD&T, datum chains (see `datum_stack1532.py`), process capability, inspection data, simulation, physical test, certification or release authority. Component values, tolerances, signs, source references and the distribution assumption are declared by the caller and are not verified. The RSS bracket assumes the declared independence. A calculation is not a certified design. Not an acceptance or closure claim.

## Text characters (child update)
Text fields refuse any character that is a Unicode control, line or paragraph separator, or bidi or format character: categories Cc (including DEL, U+0085), Zl (U+2028), Zp (U+2029) and the ranges U+200B-U+200F, U+202A-U+202E, U+2066-U+2069 and U+FEFF. In short: no Unicode control, line/paragraph separator or bidi/format characters. Ordinary spaces and printable non-ASCII text stay allowed. The helper is `_hidden`, applied inside `_text` after the type, length cap and blank checks.

## Child update: cap-first helpers (peer-stated rule, relayed; not owner words)
- `_text`: after the `type(value) is str` check the first operation is the raw length check (`len(value) > MAX_TEXT`); the blank check (`strip`) and the Unicode scan run only after it. Before this child `_text` evaluated `value.strip()` first, which allocates a copy of an oversize string: a defect, now repaired. The cap was already the raw length (a value padded with spaces counts in full), so accepted and refused inputs do not change; only the order does.
- `_micro`: new first operation after the type check is `len(value) > MAX_NUMBER_CHARS` (20, the longest string the number grammar can accept: sign, 12 whole digits, point, 6 fraction digits). Before this child the regex ran on any length. No accepted or refused input changes (the regex already refused longer strings); the regex now never sees an oversize string.
- Pins: cap and cap+1, a space-padded raw-length case, a 10 MB string refused with a tracemalloc peak under 100 KB (a strip copy would be about 10 MB), and spies proving the Unicode scan and the regex are not reached for oversize input.
