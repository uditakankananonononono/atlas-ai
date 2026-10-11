# Row 1529 Design for Sustainability - DESSUS contract (PREP-only, local candidate)

## Ledger source pin
audits/additional-2000-features.json, id 1529, requirement: "Design for Sustainability", status: verified-pushed.
Description: (empty). The ledger description is empty, so the requirement title is the whole specification; everything below is DESIGN text for a bounded, deterministic mechanism over caller-supplied declarations, not ledger text.

## Existing mechanism and delta
Existing: `_sustain` at backend/app/modules/m20_general_cognitive_worker/engineering_1510_1559.py:141 (main 3d3d768c) sums `float()` impact values per key with no unit handling, accepts a missing functional unit or system boundary, and echoes stages.
This unit (new file, `design_for_sustainability1529.py`, function `run(request)`): validated closed schema; functional unit and system boundary required; exact decimal sums with one unit per category (mismatch refuses); per-stage shares as exact fractions (null when the total is zero); hotspot stage(s) per category; values may be negative (credits).

## Scope
Caller-supplied impact tallies only; a comparative claim needs review; no LCA certification claim; no characterisation factors. Bounded exact deterministic mechanism over caller-supplied declarations. No physical test, no solver execution, no certification, no release authority; any output is a labeled plan or bookkeeping result, never a test result. Nothing is persisted; no route or registry entry is added (integration is a separate step).

## Limits (N / N+1 pinned by tests)
- MAX_STAGES = 32
- MAX_CATEGORIES = 16
- MAX_TEXT = 127
- MAX_MAGNITUDE = 10 ** 12

## Refusals
Every refusal is `ValueError("DESSUS1529:<code>")` with a fixed code token; no request text is ever echoed. Codes in this unit:
- `DESSUS1529:invalid_count:keys`
- `DESSUS1529:duplicate_id:lifecycle_stages`
- `DESSUS1529:invalid_count:impacts`
- `DESSUS1529:invalid_count:lifecycle_stages`
- `DESSUS1529:invalid_item:impacts`
- `DESSUS1529:invalid_item:lifecycle_stages`
- `DESSUS1529:invalid_number:`
- `DESSUS1529:invalid_request`
- `DESSUS1529:invalid_text:`
- `DESSUS1529:unit_mismatch`
- `DESSUS1529:unknown_key`

## Text character rule
Every text field checked by this unit's text validator (ids, names, units, labels, references, descriptions) must be 1..128 characters (length cap applied first), then the Unicode check; refusal is `invalid_text:<field>` and names the field, never the value. The unit has no Unicode control, line/paragraph separator or bidi/format characters: it rejects categories Cc, Zl, Zp, DEL (127) and U+200B-200F, U+202A-202E, U+2066-2069, U+FEFF. Ordinary spaces and printable non-ASCII are allowed. Pinned: U+0085, U+2028, U+2029, U+202E, U+200B, U+FEFF, DEL. Note: descriptions are included, so a newline inside a description is refused. Enum/number fields are not text fields.

## Input size order
Text helper: after the exact-str type check the first operation is the raw length check (1..128), before strip, copy or Unicode check. The cap is on the raw length (a string whose stripped length fits but raw length exceeds 128 is refused). Numeric helper: for an int, an O(1) bit_length() > 64 refusal (invalid_number:<field>) is the first size operation, before abs() or any parse; strings are refused by type before any parse. The 64-bit threshold is a guard only; the 10**12 magnitude limit decides acceptance. Builder read the actual code order in this unit; helpers other than the text and number helper take no caller strings.

## Dict key-count cap
Every caller dict (the request, every item, and nested dicts such as scores, specification and cells) is refused with `DESSUS1529:invalid_count:keys` when it has more than 64 keys; the check is an exact-type then len() test that runs before any set construction or iteration. Existing stricter caps are kept. Arithmetic is exact: parsed values are Fractions of the exact decimal of the supplied int/float text, totals and shares are exact Fractions rendered exactly (totals as exact decimals, no rounding), and the ambient decimal context is neither used nor changed. This replaces the earlier context-dependent Decimal sums.

## Float and negative-impact semantics (doc-only addendum, no runtime change)
- A float impact value is represented by its shortest decimal string (the text Python's str() gives, for example 0.1), taken exactly as a decimal; it is not the binary double's exact expansion. So 0.1 and 0.2 total exactly 0.3, not 0.30000000000000004. An int is exact as written.
- Negative impact values are accepted (credits). Shares are exact value/total fractions, so with a negative stage a share can be above 1 or negative (for example values 3 and -1 give total 2 and shares 3/2 and -1/2). A zero total gives null shares. The unit makes no claim that shares lie in 0..1.

## Disclosures
- Full repository test suite: NOT run. Only this unit's test file (and the neighbor files named in the package) were run.
- Python: the m20 package imports modules that need Python 3.11+ (`enum.StrEnum`), so the unit tests run on CPython 3.12 only; the unit itself uses only the standard library.
- Mutation audit is a builder-run token-mutation battery; survivors and dispositions are in the package, not claimed here as proof.
- No closure, landing or acceptance claim.
