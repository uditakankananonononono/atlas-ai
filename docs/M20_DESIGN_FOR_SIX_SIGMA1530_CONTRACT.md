# Row 1530 Design for Six Sigma - DFSS contract (PREP-only, local candidate)

## Ledger source pin
audits/additional-2000-features.json, id 1530, requirement: "Design for Six Sigma", status: PARTIAL.
Description: (empty). The ledger description is empty, so the requirement title is the whole specification; everything below is DESIGN text for a bounded, deterministic mechanism over caller-supplied declarations, not ledger text.

## Existing mechanism and delta
Existing: `_dfss` at backend/app/modules/m20_general_cognitive_worker/engineering_1510_1559.py:147 (main 3d3d768c) lists CTQs as given and returns ids of CTQs with a falsy `specification`; the phase and verification plan are echoed unchecked.
This unit (new file, `design_for_six_sigma1530.py`, function `run(request)`): validated closed schema; DMADV phase must be one of define/measure/analyze/design/verify; specification bounds checked (lower <= target <= upper where given, at least one bound, a unit); verification-plan references checked; unverified CTQs listed; phase gate notes for open CTQs at design/verify and unverified CTQs at verify.

## Scope
CTQ/DMADV bookkeeping over supplied inputs. No sigma level computed, no statistical validation claim. Bounded exact deterministic mechanism over caller-supplied declarations. No physical test, no solver execution, no certification, no release authority; any output is a labeled plan or bookkeeping result, never a test result. Nothing is persisted; no route or registry entry is added (integration is a separate step).

## Limits (N / N+1 pinned by tests)
- MAX_CTQS = 64
- MAX_PLAN = 129
- MAX_TEXT = 128
- MAX_MAGNITUDE = 10 ** 12

## Refusals
Every refusal is `ValueError("DFSS1530:<code>")` with a fixed code token; no request text is ever echoed. Codes in this unit:
- `DFSS1530:invalid_count:keys`
- `DFSS1530:duplicate_id:ctqs`
- `DFSS1530:duplicate_id:verification_plan`
- `DFSS1530:invalid_count:`
- `DFSS1530:invalid_item:`
- `DFSS1530:invalid_item:specification`
- `DFSS1530:invalid_number:`
- `DFSS1530:invalid_phase`
- `DFSS1530:invalid_request`
- `DFSS1530:invalid_specification`
- `DFSS1530:invalid_text:`
- `DFSS1530:specification_needs_bound`
- `DFSS1530:unknown_ctq`
- `DFSS1530:unknown_key`

## Text character rule
Every text field checked by this unit's text validator (ids, names, units, labels, references, descriptions) must be 1..128 characters (length cap applied first), then the Unicode check; refusal is `invalid_text:<field>` and names the field, never the value. The unit has no Unicode control, line/paragraph separator or bidi/format characters: it rejects categories Cc, Zl, Zp, DEL (127) and U+200B-200F, U+202A-202E, U+2066-2069, U+FEFF. Ordinary spaces and printable non-ASCII are allowed. Pinned: U+0085, U+2028, U+2029, U+202E, U+200B, U+FEFF, DEL. Note: descriptions are included, so a newline inside a description is refused. Enum/number fields are not text fields.

## Input size order
Text helper: after the exact-str type check the first operation is the raw length check (1..128), before strip, copy or Unicode check. The cap is on the raw length (a string whose stripped length fits but raw length exceeds 128 is refused). Numeric helper: for an int, an O(1) bit_length() > 64 refusal (invalid_number:<field>) is the first size operation, before abs() or any parse; strings are refused by type before any parse. The 64-bit threshold is a guard only; the 10**12 magnitude limit decides acceptance. Builder read the actual code order in this unit; helpers other than the text and number helper take no caller strings.

## Dict key-count cap
Every caller dict (the request, every item, and nested dicts such as scores, specification and cells) is refused with `DFSS1530:invalid_count:keys` when it has more than 64 keys; the check is an exact-type then len() test that runs before any set construction or iteration. Existing stricter caps are kept.

## Disclosures
- Full repository test suite: NOT run. Only this unit's test file (and the neighbor files named in the package) were run.
- Python: the m20 package imports modules that need Python 3.11+ (`enum.StrEnum`), so the unit tests run on CPython 3.12 only; the unit itself uses only the standard library.
- Mutation audit is a builder-run token-mutation battery; survivors and dispositions are in the package, not claimed here as proof.
- No closure, landing or acceptance claim.
