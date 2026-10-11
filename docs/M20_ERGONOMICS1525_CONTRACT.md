# Row 1525 Ergonomics - ERGONO contract (PREP-only, local candidate)

## Ledger source pin
audits/additional-2000-features.json, id 1525, requirement: "Ergonomics", status: PARTIAL.
Description: (empty). The ledger description is empty, so the requirement title is the whole specification; everything below is DESIGN text for a bounded, deterministic mechanism over caller-supplied declarations, not ledger text.

## Existing mechanism and delta
Existing: `_ergo` at backend/app/modules/m20_general_cognitive_worker/engineering_1510_1559.py:124 (main 3d3d768c) echoes the task, exposures, anthropometric data, controls and a bare `score`, even without any instrument.
This unit (new file, `ergonomics1525.py`, function `run(request)`): validated closed schema; a supplied score is kept only with a named instrument, version and source citation and a declared scale (score outside the scale refuses); per-exposure comparison with a caller-declared limit (exceeds only when value > limit; margin rounded to 64 significant digits, half-even); per-dimension percentile coverage (spans_p5_p95) with unit and duplicate checks; the unit never computes a score.

## Scope
Assessment-instrument context preserved; interpretation needs a qualified reviewer; no scoring authority; no ergonomic test performed. Bounded deterministic mechanism over caller-supplied declarations. No physical test, no solver execution, no certification, no release authority; any output is a labeled plan or bookkeeping result, never a test result. Nothing is persisted; no route or registry entry is added (integration is a separate step).

## Limits (N / N+1 pinned by tests)
- MAX_EXPOSURES = 64
- MAX_ANTHROPOMETRIC = 128
- MAX_CONTROLS = 64
- MAX_TEXT = 128
- MAX_MAGNITUDE = 10 ** 12

## Refusals
Every refusal is `ValueError("ERGONO1525:<code>")` with a fixed code token; no request text is ever echoed. Codes in this unit:
- `ERGONO1525:arithmetic`
- `ERGONO1525:invalid_count:keys`
- `ERGONO1525:duplicate_id:controls`
- `ERGONO1525:duplicate_id:exposures`
- `ERGONO1525:duplicate_percentile`
- `ERGONO1525:invalid_count:`
- `ERGONO1525:invalid_item:`
- `ERGONO1525:invalid_item:assessment_instrument`
- `ERGONO1525:invalid_item:score`
- `ERGONO1525:invalid_number:`
- `ERGONO1525:invalid_number:duration_s`
- `ERGONO1525:invalid_percentile`
- `ERGONO1525:invalid_request`
- `ERGONO1525:invalid_scale`
- `ERGONO1525:invalid_text:`
- `ERGONO1525:score_out_of_scale`
- `ERGONO1525:score_without_instrument`
- `ERGONO1525:unit_mismatch`
- `ERGONO1525:unknown_key`

## Text character rule
Every text field checked by this unit's text validator (ids, names, units, labels, references, descriptions) must be 1..128 characters (length cap applied first), then the Unicode check; refusal is `invalid_text:<field>` and names the field, never the value. The unit has no Unicode control, line/paragraph separator or bidi/format characters: it rejects categories Cc, Zl, Zp, DEL (127) and U+200B-200F, U+202A-202E, U+2066-2069, U+FEFF. Ordinary spaces and printable non-ASCII are allowed. Pinned: U+0085, U+2028, U+2029, U+202E, U+200B, U+FEFF, DEL. Note: descriptions are included, so a newline inside a description is refused. Enum/number fields are not text fields.

## Input size order
Text helper: after the exact-str type check the first operation is the raw length check (1..128), before strip, copy or Unicode check. The cap is on the raw length (a string whose stripped length fits but raw length exceeds 128 is refused). Numeric helper: for an int, an O(1) bit_length() > 64 refusal (invalid_number:<field>) is the first size operation, before abs() or any parse; strings are refused by type before any parse. The 64-bit threshold is a guard only; the 10**12 magnitude limit decides acceptance. Builder read the actual code order in this unit; helpers other than the text and number helper take no caller strings.

## Decimal arithmetic
All arithmetic (margins, limit comparisons, normalisation and rendering) runs inside a fixed local Decimal context: precision 64, ROUND_HALF_EVEN, Emin -999999, Emax 999999, clamp 0, capitals 1, flags cleared; traps InvalidOperation, DivisionByZero, Overflow and Underflow enabled and reported as `ERGONO1525:arithmetic` (no raw Decimal exception, no value echoed); Inexact and Rounded are not trapped. Input numbers (int or float, as before; no silent change to strings) are parsed exactly from their str() form. Derived values are rounded to 64 significant digits, half-even; not claimed exact. The caller's ambient decimal context is neither used nor changed. Input schema is unchanged: numeric fields are JSON int/float, not decimal strings, so no decimal-string grammar applies.

## Dict key-count cap
Every caller dict (the request, every item, assessment_instrument and score) is refused with `ERGONO1525:invalid_count:keys` when it has more than 64 keys; the check is an exact-type then len() test that runs before any set construction or iteration. Existing stricter caps are kept.

## Disclosures
- Full repository test suite: NOT run. Only this unit's test file (and the neighbor files named in the package) were run.
- Python: the m20 package imports modules that need Python 3.11+ (`enum.StrEnum`), so the unit tests run on CPython 3.12 only; the unit itself uses only the standard library.
- Mutation audit is a builder-run token-mutation battery; survivors and dispositions are in the package, not claimed here as proof.
- No closure, landing or acceptance claim.
