# METROL1533: exact uncertainty budget arithmetic (row 1533)

Ledger source pin: `audits/additional-2000-features.json` row 1533, requirement "Metrology", description "" (empty), status "verified-pushed" (historical builder attribution, not current proof). Ledger file SHA256 `285cc16c474215b241383fb922c8a2f2abfa9f7cda3592b04dc61141317d83ff`, checked at main 3d3d768c; this unit is based on main 0ca1bbee. The ledger description is empty, so the requirement title is the whole spec; the behavior below is this unit's proposal for it. PREP only: nothing is wired, landed or closed.

## Delta against the existing mechanism
Existing: `backend/app/modules/m20_general_cognitive_worker/engineering_1510_1559.py:155` `_metrology` (read) and its test `tests/modules/test_m20_engineering_1510_1559.py:53`. `_metrology` casts `standard_uncertainties` with `float()`, takes a float square root of the sum of squares, multiplies by a `coverage_factor` defaulting to 2 (no range check; zero, negative, nan accepted), and returns the `traceability_chain` value as given (any type, default empty list, not copied) beside a fixed equation text. It has no sensitivity coefficients, ids, kinds, source references, units, count bounds, bounds on rounding, refusal codes or authority flags; an empty list gives 0.
This unit (`metrology1533.py`, `compute_uncertainty_budget`, new file; it does not import or modify the existing one) differs in these checkable ways:
- Components are records: id, standard_uncertainty (unsigned decimal string), sensitivity (signed decimal string; its sign does not matter for the result), kind (`type_a` or `type_b`), source_ref.
- Decimal strings only (at most 12 integer and 6 fractional digits, ASCII, no exponent); floats, ints, bools and padded strings are refused. All arithmetic is exact integers; the squared combined value is returned exactly with 24 decimals.
- The square root is returned as a floor and ceiling bracket to six decimals. The expanded uncertainty bracket comes from the exact value k squared times the squared sum, not from a rounded root.
- The coverage factor is required and must be greater than 0 and at most 10. No coverage probability is claimed.
- The caller must declare `assumption` = `uncorrelated_inputs`; it is echoed with a statement and not checked.
- `traceability_chain`: required list of 0 to 16 text items, copied and echoed in order, with `traceability_verified` false and `calibration_authority` false.
- Counts 1..64 components; refusals are `ValueError("METROL1533:<code>")` with fixed codes that never echo input.

## Input
Exactly `unit` (text, at most 16 characters), `assumption`, `coverage_factor`, `components`, `traceability_chain`. Text is nonblank, at most 128 characters (unit 16), no control characters. Ids are unique. Input is not mutated and output holds no aliases.

## Output
unit, coverage_factor, combined_standard_uncertainty {squared, bounds}, expanded_uncertainty {bounds}, contributions sorted by id (each with exact contribution |sensitivity| x standard uncertainty to 12 decimals), assumption, statement, traceability_chain, traceability_status `echoed_not_verified`, traceability_verified false, coverage_factor_as_given, calibration_authority false, requires_metrologist_review true, scope `declared_standard_uncertainties_arithmetic_only`, boundary.

## Caps, per list and per text
- `components`: 1 to 64 records. Empty is refused with `METROL1533:invalid_count:components`; there is no zero-uncertainty result for an empty list.
- `traceability_chain`: 0 to 16 text items; empty is allowed and echoed as empty.
- Each text (component id, source_ref, each chain item): at most 128 characters. `unit`: at most 16 characters.
- Checks run in this order per text: type, length cap, then blank and control characters. A refusal carries only the fixed code, never the offending value.
- `coverage_factor` is REQUIRED (no default), a decimal string greater than 0 and at most 10, and is also echoed exactly as given in `coverage_factor_as_given` next to the normalized six-decimal value. No NaN, Infinity, exponent, bool, float or padded string is accepted. No confidence level is mapped to it.
- `traceability_status` is `echoed_not_verified`: the chain is echoed only; no link is claimed to exist or resolve, and no accreditation or calibration is claimed.
- `unit` is a label only (nonblank, at most 16 characters, no control characters), echoed, with no conversion and no mixed-unit detection.

## Refusal codes
invalid_packet, unknown_fields:packet, invalid_text:unit, invalid_assumption, invalid_coverage_factor, invalid_count:traceability_chain, invalid_text:traceability_chain, invalid_count:components, invalid_record:components, invalid_fields:components, invalid_text:id, invalid_text:source_ref, duplicate_id, invalid_kind, invalid_number:standard_uncertainty, invalid_number:sensitivity. All prefixed `METROL1533:`.

The text helper is `_text` (type, length, blank, control character checks); the number helper is `_micro` (ASCII fullmatch of an unsigned or signed decimal with at most 12 integer and 6 fractional digits).

## Tests and gaps
`tests/modules/test_m20_metrology1533.py`: hermetic, standard library, N and N+1 pins on counts, text lengths, number grammar and the coverage factor bounds. Raw RED, GREEN, mutation and scan outputs are supplied separately.
FULL-SUITE UNVERIFIED: only this unit's tests and named neighbor tests were run, not the full repository suite.

## Limits
Arithmetic over declared standard uncertainties only. No uncertainty evaluation (no Type A statistics from readings), no correlation handling, no degrees of freedom, no coverage probability, no verification of the traceability chain, no calibration, accreditation or compliance authority, no measurement result. Values, sensitivities, kinds, references and the chain are declared by the caller and not verified. Not an acceptance or closure claim.

## Text characters (child update)
Text fields refuse any character that is a Unicode control, line or paragraph separator, or bidi or format character: categories Cc (including DEL, U+0085), Zl (U+2028), Zp (U+2029) and the ranges U+200B-U+200F, U+202A-U+202E, U+2066-U+2069 and U+FEFF. In short: no Unicode control, line/paragraph separator or bidi/format characters. Ordinary spaces and printable non-ASCII text stay allowed. The helper is `_hidden`, applied inside `_text` after the type, length cap and blank checks.
