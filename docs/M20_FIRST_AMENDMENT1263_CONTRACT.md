# Row 1263 - First Amendment (contract)

## Source pin
- Register: audits/coverage-register.json, row 1263, category "Specialized Domain Expertise".
- Requirement (verbatim): "First Amendment". Description (verbatim): "" (empty; the requirement title is the whole spec).
- Existing register mapping: backend/app/modules/m20_general_cognitive_worker/legal_support_1260_1309.py, test_row_1263_distinct_legal_mechanism.
- Read at main a294723b7a8f7bbe6067804ee4d7d325e1a8bde9.

## Standing legal boundary
"Legal work product for review, not legal advice. Licensed counsel must verify jurisdiction, currency, citations, facts, duties, deadlines and strategy before use."

## What this is
`classify(payload)` in backend/app/modules/m20_general_cognitive_worker/first_amendment1263.py. Bounded bookkeeping over caller-supplied data. It records what the caller declares for each item (speech, speaker, forum, restriction, scrutiny) in closed vocabularies, adds a fixed conventional reference label per restriction kind for counsel to compare, and flags unknown values, unresolved source ids, and authority jurisdiction or effective-date mismatches. Prefix for refusals: `FIRSTA1263:<REASON>[:<field>]`, plain ValueError.

## Delta vs the existing mechanism
Existing: SPECS row 1263 at legal_support_1260_1309.py:20 ("classify speech, speaker, forum, restriction and scrutiny without deciding constitutionality") run by analyze_legal_feature (line ~97). That engine copies caller `row_inputs` into the artifact unchanged and returns `named_capability_executed=False`; it performs no speech, speaker, forum, restriction or scrutiny classification. Added here: closed vocabularies with exact refusals, the reference-label table, mismatch and unknown flags, counts, caps and a blocked/counsel-review state. The shared file is not edited.

## Inputs and refusals
Top-level keys: jurisdiction, as_of (YYYY-MM-DD), authorities (1-32), items (1-16). Item keys: id, speech, speaker, forum, restriction, scrutiny_declared, source_ids (1-8). Authority keys: id, citation_text, jurisdiction, effective_date. Text 1-256 chars, no control characters. A truthy `decide`/`constitutional`/`conclusion` key is refused CONCLUSION_REFUSED; a truthy `file`/`serve`/`contact`/`send`/`spend` key is refused EXTERNAL_EFFECT_REFUSED. Other codes: BAD_TYPE, EMPTY, CONTROL_CHARS, TEXT_TOO_LONG, MISSING, UNKNOWN_KEY, UNKNOWN_VALUE, TOO_MANY, DUPLICATE, BAD_DATE.

## Output
Per item: declared values, reference_scrutiny_label, scrutiny_matches_reference (True, False, or None when unknown or none_declared), unclassified_fields, missing_source_ids. Plus authority_flags, counts, review_state ("blocked" or "counsel_review_required") and fixed fields constitutionality_decided=False, legal_conclusion=None, filing_or_external_effect=False, authorities_independently_verified=False.

## Limits and residual disclosures
- It never decides constitutionality or whether a restriction is valid, and gives no legal advice.
- The reference label table is a fixed convention, not a statement of the controlling test in any jurisdiction; a mismatch is a flag for counsel, not an error finding.
- Authorities and citations are caller text only; none is verified, fetched or checked for currency.
- Vocabularies are coarse and omit many doctrines; "other" and "unknown" exist for that reason.
- No persistence, no network, no filing, service or contact. Not wired to any route or mount in this change.
- Tests are hermetic stdlib. FULL SUITE NOT RUN. No closure claim; independent audit needed.

- Text policy: raw length cap (256) is checked before strip or any Unicode check; code points in categories Cc, Cf, Zl, Zp are refused (CONTROL_CHARS, covers every Cf code point including U+00AD and U+2060); Zs is accepted. Lone surrogates (Cs) are NOT newly refused; that remains a disclosed residual. Containers: list length and dict key count (16) are checked before any iteration.

- Strict types: payload, items, authorities, source_ids and item dicts must be exactly builtin dict/list and text exactly builtin str (type() is checked, subclasses are refused BAD_TYPE). Refusals use fixed codes and field names from this module's own tables; no caller-supplied key or value is echoed (UNKNOWN_KEY carries no key name).

- Every echoed value (source_ids, ids, jurisdiction) passes the full text screen and raw cap; enum values get a raw length cap before membership; non-str dict keys are refused BAD_TYPE:key before any key lookup.

- Date gate (as_of, effective_date): exact type str, then exact raw length 10, then ASCII YYYY-MM-DD shape, then calendar validity. Error-mapping change, disclosed: a date value that is blank, over-long, or contains control or format characters now returns BAD_DATE:<field> (previously EMPTY, TEXT_TOO_LONG or CONTROL_CHARS for that field). A non-str date still returns BAD_TYPE:<field>. The shape check is ASCII-only (non-ASCII digits are refused).

## Chronology disclosure
The assignment was patch-only (no push, rebase, amend or reset). The builder nevertheless made one LOCAL commit of these three new files on a local branch, 9412ba77e708f8b01ba0ef6e67648d441111ab11 (parent a294723b7a8f7bbe6067804ee4d7d325e1a8bde9), before delivering the files as attachments. Nothing was pushed, amended, rebased or reset; the commit stays as is. It carries no authority and is not an acceptance or landing.
