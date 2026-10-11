# Row 1528 Design for Assembly - DESASS contract (PREP-only, local candidate)

## Ledger source pin
audits/additional-2000-features.json, id 1528, requirement: "Design for Assembly", status: verified-pushed.
Description: (empty). The ledger description is empty, so the requirement title is the whole specification; everything below is DESIGN text for a bounded, deterministic mechanism over caller-supplied declarations, not ledger text.

## Existing mechanism and delta
Existing: `_dfa` at backend/app/modules/m20_general_cognitive_worker/engineering_1510_1559.py:137 (main 3d3d768c) counts essential parts from truthy flags (any truthy value counts), picks combination candidates by dict equality (`p not in essential`), and has no id, reference or fraction handling.
This unit (new file, `design_for_assembly1528.py`, function `run(request)`): validated closed schema with real booleans for the three flags; essential/candidate split by id; exact reduction and efficiency fractions in lowest terms; assembly-step references checked; parts not used in any step listed.

## Scope
Part-reduction bookkeeping over supplied parts. No assembly time, line or cost claim. Bounded exact deterministic mechanism over caller-supplied declarations. No physical test, no solver execution, no certification, no release authority; any output is a labeled plan or bookkeeping result, never a test result. Nothing is persisted; no route or registry entry is added (integration is a separate step).

## Limits (N / N+1 pinned by tests)
- MAX_PARTS = 128
- MAX_STEPS = 128
- MAX_STEP_PARTS = 32
- MAX_TEXT = 128

## Refusals
Every refusal is `ValueError("DESASS1528:<code>")` with a fixed code token; no request text is ever echoed. Codes in this unit:
- `DESASS1528:invalid_count:keys`
- `DESASS1528:duplicate_id:assembly_steps`
- `DESASS1528:duplicate_id:parts`
- `DESASS1528:invalid_bool:`
- `DESASS1528:invalid_count:`
- `DESASS1528:invalid_count:part_ids`
- `DESASS1528:invalid_item:`
- `DESASS1528:invalid_request`
- `DESASS1528:invalid_text:`
- `DESASS1528:unknown_key`
- `DESASS1528:unknown_part`

## Text character rule
Every text field checked by this unit's text validator (ids, names, units, labels, references, descriptions) must be 1..128 characters (length cap applied first), then the Unicode check; refusal is `invalid_text:<field>` and names the field, never the value. The unit has no Unicode control, line/paragraph separator or bidi/format characters: it rejects categories Cc, Zl, Zp, DEL (127) and U+200B-200F, U+202A-202E, U+2066-2069, U+FEFF. Ordinary spaces and printable non-ASCII are allowed. Pinned: U+0085, U+2028, U+2029, U+202E, U+200B, U+FEFF, DEL. Note: descriptions are included, so a newline inside a description is refused. Enum/number fields are not text fields.

## Input size order
Text helper: after the exact-str type check the first operation is the raw length check (1..128), before strip, copy or Unicode check. The cap is on the raw length (a string whose stripped length fits but raw length exceeds 128 is refused). Builder read the actual code order in this unit; helpers other than the text and number helper take no caller strings.

## Dict key-count cap
Every caller dict (the request, every item, and nested dicts such as scores, specification and cells) is refused with `DESASS1528:invalid_count:keys` when it has more than 64 keys; the check is an exact-type then len() test that runs before any set construction or iteration. Existing stricter caps are kept.

## Disclosures
- Full repository test suite: NOT run. Only this unit's test file (and the neighbor files named in the package) were run.
- Python: the m20 package imports modules that need Python 3.11+ (`enum.StrEnum`), so the unit tests run on CPython 3.12 only; the unit itself uses only the standard library.
- Mutation audit is a builder-run token-mutation battery; survivors and dispositions are in the package, not claimed here as proof.
- No closure, landing or acceptance claim.
