# Row 1524 Human Factors Engineering - HUMANF contract (PREP-only, local candidate)

## Ledger source pin
audits/additional-2000-features.json, id 1524, requirement: "Human Factors Engineering", status: PARTIAL.
Description: (empty). The ledger description is empty, so the requirement title is the whole specification; everything below is DESIGN text for a bounded, deterministic mechanism over caller-supplied declarations, not ledger text.

## Existing mechanism and delta
Existing: `_human` at backend/app/modules/m20_general_cognitive_worker/engineering_1510_1559.py:119 (main 3d3d768c) passes tasks through and marks `critical` from `safety_consequence`; no validation, no ids, no risk values, no reference checks, hard-coded `unvalidated: True`.
This unit (new file, `human_factors_engineering1524.py`, function `run(request)`): validated closed schema; per use error an integer risk_index = severity x likelihood (both integers 1..5); fixed bands (low <= 7, medium 8..14, high >= 15, this unit's own convention, not a standard); mitigation references checked against the supplied mitigation list; unmitigated-high list; per-error ordering by index then id.

## Scope
Use-error risk framing over supplied tasks only. No usability study, no user validation, no human-factors compliance claim. Bounded exact deterministic mechanism over caller-supplied declarations. No physical test, no solver execution, no certification, no release authority; any output is a labeled plan or bookkeeping result, never a test result. Nothing is persisted; no route or registry entry is added (integration is a separate step).

## Limits (N / N+1 pinned by tests)
- MAX_TASKS = 64
- MAX_USERS = 64
- MAX_MITIGATIONS = 128
- MAX_ERRORS = 32
- MAX_MITIGATION_IDS = 16
- MAX_PARTICIPANTS = 64
- MAX_TEXT = 128

## Refusals
Every refusal is `ValueError("HUMANF1524:<code>")` with a fixed code token; no request text is ever echoed. Codes in this unit:
- `HUMANF1524:invalid_count:keys`
- `HUMANF1524:duplicate_id:`
- `HUMANF1524:invalid_bool:safety_consequence`
- `HUMANF1524:invalid_count:`
- `HUMANF1524:invalid_count:mitigation_ids`
- `HUMANF1524:invalid_item:`
- `HUMANF1524:invalid_request`
- `HUMANF1524:invalid_scale:`
- `HUMANF1524:invalid_text:`
- `HUMANF1524:unknown_key`
- `HUMANF1524:unknown_mitigation`

## Text character rule
Every text field checked by this unit's text validator (ids, names, units, labels, references, descriptions) must be 1..128 characters (length cap applied first), then the Unicode check; refusal is `invalid_text:<field>` and names the field, never the value. The unit has no Unicode control, line/paragraph separator or bidi/format characters: it rejects categories Cc, Zl, Zp, DEL (127) and U+200B-200F, U+202A-202E, U+2066-2069, U+FEFF. Ordinary spaces and printable non-ASCII are allowed. Pinned: U+0085, U+2028, U+2029, U+202E, U+200B, U+FEFF, DEL. Note: descriptions are included, so a newline inside a description is refused. Enum/number fields are not text fields.

## Input size order
Text helper: after the exact-str type check the first operation is the raw length check (1..128), before strip, copy or Unicode check. The cap is on the raw length (a string whose stripped length fits but raw length exceeds 128 is refused). Builder read the actual code order in this unit; helpers other than the text and number helper take no caller strings.

## Dict key-count cap
Every caller dict (the request, every item, and nested dicts such as scores, specification and cells) is refused with `HUMANF1524:invalid_count:keys` when it has more than 64 keys; the check is an exact-type then len() test that runs before any set construction or iteration. Existing stricter caps are kept.

## Disclosures
- Full repository test suite: NOT run. Only this unit's test file (and the neighbor files named in the package) were run.
- Python: the m20 package imports modules that need Python 3.11+ (`enum.StrEnum`), so the unit tests run on CPython 3.12 only; the unit itself uses only the standard library.
- Mutation audit is a builder-run token-mutation battery; survivors and dispositions are in the package, not claimed here as proof.
- No closure, landing or acceptance claim.
