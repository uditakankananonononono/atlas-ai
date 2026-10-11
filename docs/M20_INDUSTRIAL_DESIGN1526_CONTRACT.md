# Row 1526 Industrial Design - INDUST contract (PREP-only, local candidate)

## Ledger source pin
audits/additional-2000-features.json, id 1526, requirement: "Industrial Design", status: PARTIAL.
Description: (empty). The ledger description is empty, so the requirement title is the whole specification; everything below is DESIGN text for a bounded, deterministic mechanism over caller-supplied declarations, not ledger text.

## Existing mechanism and delta
Existing: `_design(d,'industrial')` at backend/app/modules/m20_general_cognitive_worker/engineering_1510_1559.py:127 (main 3d3d768c) returns a concept template with the supplied lists unvalidated and `release_ready` pinned False.
This unit (new file, `industrial_design1526.py`, function `run(request)`): validated closed schema; weighted decision matrix over integer weights 1..100 and integer scores 0..10 (exact integer totals and exact fractions of the maximum), ranking with shared ranks and tie reporting, prototype-evidence references checked against concepts; selection left to a human (`selected_concept` is always null).

## Scope
Concept/selection bookkeeping over supplied inputs. Not release ready. No manufacturing claim. Bounded exact deterministic mechanism over caller-supplied declarations. No physical test, no solver execution, no certification, no release authority; any output is a labeled plan or bookkeeping result, never a test result. Nothing is persisted; no route or registry entry is added (integration is a separate step).

## Limits (N / N+1 pinned by tests)
- MAX_CRITERIA = 16
- MAX_CONCEPTS = 32
- MAX_NEEDS = 64
- MAX_EVIDENCE = 64
- MAX_TEXT = 128

## Refusals
Every refusal is `ValueError("INDUST1526:<code>")` with a fixed code token; no request text is ever echoed. Codes in this unit:
- `INDUST1526:invalid_count:keys`
- `INDUST1526:invalid_text:concept_id` (text checks use invalid_text:<field>)
- `INDUST1526:duplicate_id:`
- `INDUST1526:invalid_count:`
- `INDUST1526:invalid_item:`
- `INDUST1526:invalid_item:scores`
- `INDUST1526:invalid_request`
- `INDUST1526:invalid_score`
- `INDUST1526:invalid_weight`
- `INDUST1526:missing_score`
- `INDUST1526:unknown_concept`
- `INDUST1526:unknown_criterion`
- `INDUST1526:unknown_key`

## Text character rule
Every text field checked by this unit's text validator (ids, names, units, labels, references, descriptions) must be 1..128 characters (length cap applied first), then the Unicode check; refusal is `invalid_text:<field>` and names the field, never the value. The unit has no Unicode control, line/paragraph separator or bidi/format characters: it rejects categories Cc, Zl, Zp, DEL (127) and U+200B-200F, U+202A-202E, U+2066-2069, U+FEFF. Ordinary spaces and printable non-ASCII are allowed. Pinned: U+0085, U+2028, U+2029, U+202E, U+200B, U+FEFF, DEL. Note: descriptions are included, so a newline inside a description is refused. Enum/number fields are not text fields.

## Input size order
Text helper: after the exact-str type check the first operation is the raw length check (1..128), before strip, copy or Unicode check. The cap is on the raw length (a string whose stripped length fits but raw length exceeds 128 is refused). Builder read the actual code order in this unit; helpers other than the text and number helper take no caller strings.

## Dict key-count cap
Every caller dict (the request, every item, and nested dicts such as scores, specification and cells) is refused with `INDUST1526:invalid_count:keys` when it has more than 64 keys; the check is an exact-type then len() test that runs before any set construction or iteration. Existing stricter caps are kept. Prototype evidence concept_id must be valid text (type str, 1..128, no Unicode control/format characters) and is checked before the concept membership test; a list, dict or other non-string is refused `INDUST1526:invalid_text:concept_id`, never a raw TypeError.

## Disclosures
- Full repository test suite: NOT run. Only this unit's test file (and the neighbor files named in the package) were run.
- Python: the m20 package imports modules that need Python 3.11+ (`enum.StrEnum`), so the unit tests run on CPython 3.12 only; the unit itself uses only the standard library.
- Mutation audit is a builder-run token-mutation battery; survivors and dispositions are in the package, not claimed here as proof.
- No closure, landing or acceptance claim.
