# M20 row 1266 - Equal Protection (contract)

## Source pin
Ledger source: `audits/coverage-register.json`, row id 1266, category "Specialized Domain Expertise", requirement (verbatim) "Equal Protection", description (verbatim) "" (empty - the requirement title is the whole spec). Ledger status in `audits/additional-2000-features.json`: PARTIAL. Read at main a294723b7a8f7bbe6067804ee4d7d325e1a8bde9.

## Standing boundary
"Legal work product for review, not legal advice. Licensed counsel must verify jurisdiction, currency, citations, facts, duties, deadlines and strategy before use."

## What this unit is
`backend/app/modules/m20_general_cognitive_worker/equal_protection1266.py`, function `map_equal_protection(payload)`. Bounded declared legal-support bookkeeping over caller-supplied data only. It organizes five elements of an equal-protection review (classification, comparator, intent evidence, scrutiny tier supplied by counsel, interest/means fit), checks that each cites authority ids that exist in the supplied authority list, and reports open items. It never reaches a legal conclusion, never decides a discrimination claim, never selects a scrutiny tier, never verifies authority or facts, and never files, serves or contacts anyone.

## Delta vs the existing mechanism
Existing: `backend/app/modules/m20_general_cognitive_worker/legal_support_1260_1309.py:23` (SPECS row 1266, "map classification, comparator, intent, scrutiny and fit") run through the shared `analyze_legal_feature` at `:96`. Its row-specific input is passed through unvalidated (`"inputs": data.get("row_inputs", {})`, `:131`) and its result states `named_capability_executed: False`. Earlier register evidence also names `backend/app/modules/m12_ai_research_lab/legal_support.py`.
Added here: a validated five-element structure; per-element resolution of cited authority ids (`unresolved_source_ids`); per-element jurisdiction-mismatch flags; staleness (`last_checked_at` before `as_of`) and not-yet-effective (`effective_date` after `as_of`) per authority; a fixed-order `open_items` list; strict unknown-field refusal and refusal of conclusion-seeking fields. Nothing in the existing files is edited; the shared cluster file is untouched.

## Input
`jurisdiction`, `as_of` (YYYY-MM-DD), `authorities` (1..64 of id, citation, jurisdiction, effective_date, last_checked_at; ids unique), and optional `classification`, `comparator`, `intent`, `scrutiny`, `fit` objects, each with `source_ids` (at most 8 unique ids). `intent.items` is 1..32 records of kind, text, source_ids. Text fields are non-empty and at most 2000 raw characters; the raw length is checked before anything else, then the character screen, then emptiness. Each source id obeys the same raw cap (2000, equal to the cap on authority ids, which source ids must match) and the same screen. Every container is length- or key-count-checked before iteration: payload at most 16 keys, each element object at most its field count plus 8, authorities at most 64, source ids at most 8, intent items at most 32. `scrutiny.tier_supplied_by_counsel` is one of strict, intermediate, rational_basis and is recorded, not evaluated.

## Output
`elements.<name>.status` is `missing`, `unsourced`, `unresolved_sources` or `supplied` (sourcing status only), `authorities[]` with `jurisdiction_match`, `stale`, `not_yet_effective`, `open_items` (elements in the order classification, comparator, intent, scrutiny, fit, then authorities in input order), `ready_for_counsel_review` (true only when there are no open items - the flag means only that the open-items list is empty; it is not a quality, correctness or merits signal), and the fixed flags `claim_decided`, `scrutiny_selected_by_unit`, `merits_assessed`, `authorities_verified`, `filed_or_sent` all false.

## Refusals
Every refusal is a `ValueError` whose message starts `EQUALP1266: `. Exact messages are pinned in `tests/modules/test_m20_equal_protection1266.py`.

## Text screening
Text that is echoed in the output is refused when it contains any character in Unicode category Cc (controls, including tab and newline), Cf (all format characters, including U+00AD and U+2060), Zl or Zp. Zs spaces are accepted. Refusal message: `<field> contains a control, format or line/paragraph-separator character`. Unknown field names are never echoed: the refusal is the fixed `unknown field in <where>`.
Cs (lone surrogates) is NOT a new refusal. Residual, disclosed: a text value containing a lone surrogate passes validation and is returned as supplied; it may fail UTF-8 encoding in a downstream writer. A test pins this as current behaviour, not as an endorsement.
Co (private use) and Cn (unassigned) characters are likewise accepted, not refused: they sit outside the refused categories (Cc, Cf, Zl, Zp) and follow the same residual path as Cs.
Mutation note (builder argument, not independently verified): the date length and fullmatch guards can mask each other in output-only tests. Individual removal survivors are not independent proof of validation-order equivalence; removing both fails the builder pins.

## Strict types and fixed reasons
Containers and scalars are checked with exact builtin types (`type(x) is dict|list|str`); subclasses, tuples and bytes are refused with the same refusal as any other wrong type. Mapping keys must be exact `str` too (a `str` subclass key is refused as an unknown field even when it equals an allowed name), and an enum value longer than the 2000-character raw cap is refused before the membership test. Refusal reasons are fixed strings naming only the field path, never a caller-supplied value: unknown field names and duplicate authority ids are not echoed. The one named field in a refusal (`field 'verdict' asks for a conclusion`) is drawn from a fixed constant tuple, not from free caller text. Mutation note (builder argument, not independently verified): replacing the root exact-type guard with isinstance survived the builder probes because `_object` repeats an exact-type check. Matching output alone does not establish order equivalence.

## Limits and residual disclosures
- Source ids are matched only against the caller's own authority list. A cited authority that exists is not checked to say what the caller says it does.
- "Supplied" means present and sourced, not correct. Dates are compared as given; no calendar, court or currency check is made.
- A text field can still carry a real name or identifier if the caller puts one there; the unit does not detect that. Sample data in the tests is synthetic.
- Jurisdiction match is exact string equality; different spellings of one jurisdiction read as a mismatch.
- The scrutiny tier is whatever counsel supplied; the unit does not check it against the classification.
- Not wired into any route or registry; no integration claim. The existing m20 package tests were not run by the builder (web stack not installed); this unit's tests load the module by file path.
- Nothing here is a closure claim for row 1266.

## Build chronology disclosure (permanent)
Builder-stated, kept as raw chronology:
1. The first version was committed locally as d8edaabf (branch review/m20-equal-protection1266, parent a294723b, never pushed) although the package asked for a patch. The repair that follows is an uncommitted working-tree change; d8edaabf is unchanged.
2. The repo conftest was never run: it imports `cryptography`, which the builder environment lacks. All runs used `pytest --noconftest` (py3.12.14 and py3.10.12), and the module is loaded by file path. No existing m20 test and no integration was run.
3. The first test run after the code existed had 9 failures; all were a builder test-fixture error (sample authority `last_checked_at` earlier than `as_of`), fixed in the fixture.
4. Mutation sweep: two earlier sweeps are invalid and get no credit (a stale bytecode cache for same-size mutants; then a bad pytest flag that errored every run). Only runs with PYTHONDONTWRITEBYTECODE=1 count. In the first valid sweep the mutant that dropped the `type(value) is not str` check in the enum validator survived; the builder first argued it equivalent (a tuple-membership test never matches a non-str). That argument was WRONG: a `str` subclass instance that equals an allowed value passes the membership test. A subclass test now kills that mutant (repair 2).
5. The Unicode screening, count-first, key-echo and date changes were later validation repairs. Recorded RED runs cover some repair pins; later strict-type pins were initially GREEN, and the enum-cap pin had no separate RED. The repairs create no legal authority.
