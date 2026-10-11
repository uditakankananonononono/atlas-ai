# Row 1527 Design for Manufacturing - DESMAN contract (PREP-only, local candidate)

## Ledger source pin
audits/additional-2000-features.json, id 1527, requirement: "Design for Manufacturing", status: verified-pushed.
Description: (empty). The ledger description is empty, so the requirement title is the whole specification; everything below is DESIGN text for a bounded, deterministic mechanism over caller-supplied declarations, not ledger text.

## Existing mechanism and delta
Existing: `_dfm` at backend/app/modules/m20_general_cognitive_worker/engineering_1510_1559.py:130 (main 3d3d768c) float()-converts feature values with no validation, treats a missing field as a PASS (inf / -inf default), and has no unit check; the min/max clause relies on operator precedence of `and`/`or` without parentheses.
This unit (new file, `design_for_manufacturing1527.py`, function `run(request)`): validated closed schema; exact decimal comparison with inclusive bounds; a feature lacking a constrained field is reported as missing and is never counted as without findings; units must match exactly; violation records carry kind, value, bound and exact margin.

## Scope
Rule checks over supplied constraints only. No process planning, no shop-floor claim. Bounded exact deterministic mechanism over caller-supplied declarations. No physical test, no solver execution, no certification, no release authority; any output is a labeled plan or bookkeeping result, never a test result. Nothing is persisted; no route or registry entry is added (integration is a separate step).

## Limits (N / N+1 pinned by tests)
- MAX_CONSTRAINTS = 64
- MAX_FEATURES = 64
- MAX_VALUES = 32
- MAX_TEXT = 128
- MAX_MAGNITUDE = 10 ** 12

## Refusals
Every refusal is `ValueError("DESMAN1527:<code>")` with a fixed code token; no request text is ever echoed. Codes in this unit:
- `DESMAN1527:invalid_count:keys`
- `DESMAN1527:constraint_needs_bound`
- `DESMAN1527:duplicate_id:features`
- `DESMAN1527:duplicate_id:process_constraints`
- `DESMAN1527:invalid_bounds`
- `DESMAN1527:invalid_count:`
- `DESMAN1527:invalid_count:values`
- `DESMAN1527:invalid_item:`
- `DESMAN1527:invalid_item:values`
- `DESMAN1527:invalid_number:`
- `DESMAN1527:invalid_request`
- `DESMAN1527:invalid_text:` with field token `process`, `id`, `field` or `unit`
- `DESMAN1527:unit_mismatch`
- `DESMAN1527:unknown_key`

## Text character rule
Every text field checked by this unit's text validator (ids, names, units, labels, references, descriptions) must be 1..128 characters (length cap applied first), then the Unicode check; refusal is `invalid_text:<field>` and names the field, never the value. The unit refuses every character of Unicode category Cc, Cf, Zl or Zp wherever text is echoed (this includes DEL, U+0085, U+2028, U+2029, U+00AD, U+2060, U+061C, U+FFF9, U+E0001 and every other Cf code point; all are pinned by a test over the full Cf category). Zs characters such as U+00A0 are accepted. Lone surrogates (category Cs) get no new refusal; this is a disclosed residual. Ordinary spaces and printable non-ASCII are allowed. Pinned: U+0085, U+2028, U+2029, U+202E, U+200B, U+FEFF, DEL. Note: descriptions are included, so a newline inside a description is refused. Enum/number fields are not text fields.

## Input size order
Text helper: after the exact-str type check the first operation is the raw length check (1..128), before strip, copy or Unicode check. The cap is on the raw length (a string whose stripped length fits but raw length exceeds 128 is refused). Numeric helper: for an int, an O(1) bit_length() > 64 refusal (invalid_number:<field>) is the first size operation, before abs() or any parse; strings are refused by type before any parse. The 64-bit threshold is a guard only; the 10**12 magnitude limit decides acceptance. Builder read the actual code order in this unit; helpers other than the text and number helper take no caller strings.

## Output summary
The former aggregate boolean is removed. The output keeps process, feature_checks (feature_id, missing_constraint_ids, violations with value/bound/margin), process_planning_claimed=False, and summary constraint_count, feature_count, missing_count, violation_count; it adds summary features_with_violations_count, features_with_missing_count and features_without_findings_count (feature_count minus the number of features with violations or missing constraints; violation and missing counts may overlap, a missing-only feature is not without findings) and top-level disposition "bookkeeping_only". This unit counts the outcome of the unit's supplied-constraint checks; not a manufacturability, process-planning or shop-floor claim; process planning is not performed.

## Key type
At every dict shape (root, constraint, feature, cell) the key count is checked first, then every key must be an exact `str` (`type(key) is str`) before any set or allowlist comparison; a str-subclass or non-str key refuses with `unknown_key`. Pinned with a spy key that counts `__hash__`/`__eq__` calls after the input is built (building the input calls `__hash__`; a set built from an exact dict reuses stored hashes, the later set difference and lookups call `__eq__`); the test shows no comparison happens before the refusal and makes no claim about hashing done while the caller builds the input. Keys of the feature `values` dict go through the text validator (`invalid_text:field`).

## Exact arithmetic
Bounds, values and margins are parsed exactly (Fraction of the exact decimal of the supplied int/float text), compared and subtracted exactly, and rendered exactly; the ambient decimal context is never used or changed. Margins are differences of finite decimals, so they always terminate: no nonterminating margin can occur. Feature value keys must be valid text (type str, 1..128, no Unicode control/format characters; refusal `DESMAN1527:invalid_text:field`). Dict key counts are capped at 64 (`DESMAN1527:invalid_count:keys`) before any iteration.

## Disclosures
- Full repository test suite: NOT run. Only this unit's test file (and the neighbor files named in the package) were run.
- Python: the m20 package imports modules that need Python 3.11+ (`enum.StrEnum`), so the unit tests run on CPython 3.12 only; the unit itself uses only the standard library.
- Mutation audit is a builder-run token-mutation battery; survivors and dispositions are in the package, not claimed here as proof.
- No closure, landing or acceptance claim.
