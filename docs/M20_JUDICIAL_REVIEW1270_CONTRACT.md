# Row 1270 - Judicial Review (contract)

## Source pin
- Register: audits/coverage-register.json, row 1270, category "Specialized Domain Expertise".
- Requirement (verbatim): "Judicial Review". Description (verbatim): "" (empty; the requirement title is the whole spec).
- Existing register mapping: backend/app/modules/m20_general_cognitive_worker/legal_support_1260_1309.py.
- Read at main 070f7ffb838db4b012bd443c4e1054f426220ebe (mechanism re-verified unchanged there: SPECS rows 1270-1279 lines 27-36, analyze_legal_feature line 96). The unit's build base was the older 85567d684018a1f6dad850228c24e68cb98c709e; an earlier draft of this note pinned that older read. Ledger status claims are historical attribution, not reproduced behavior or acceptance.

## Standing legal boundary
Legal work product for review, not legal advice. Licensed counsel must verify jurisdiction, currency, citations, facts, duties, deadlines and strategy before use.

## What this is
`organize(payload)` in backend/app/modules/m20_general_cognitive_worker/judicial_review1270.py. Bounded bookkeeping over caller-supplied data. It records what the caller declares for each item (finality, standing, exhaustion, review_standard_declared, record_scope) in closed vocabularies and flags unknown values, unresolved source ids, and authority jurisdiction or effective-date mismatches. Prefix for refusals: `JREV1270:<REASON>[:<field>]`, plain ValueError.

## Delta vs the existing mechanism
Existing: SPECS row 1270 at legal_support_1260_1309.py:27 ("map finality, standing, exhaustion, review standard and record boundaries") run by analyze_legal_feature (line 96). That engine copies caller `row_inputs` into the artifact unchanged and returns `named_capability_executed=False`; it performs no row-specific classification. Added here: closed vocabularies with exact refusals, unknown and missing-source flags, counts, caps and a blocked/counsel-review state. The shared file is not edited. No route wiring is supplied.

## Inputs and refusals
Top-level keys: jurisdiction, as_of (YYYY-MM-DD), authorities (1-32), items (1-16). Item keys: id, finality, standing, exhaustion, review_standard_declared, record_scope, source_ids (1-8). Authority keys: id, citation_text, jurisdiction, effective_date. Text 1-256 chars, no control characters. A truthy `decide`/`constitutional`/`conclusion` key is refused CONCLUSION_REFUSED; a truthy `file`/`serve`/`contact`/`send`/`spend` key is refused EXTERNAL_EFFECT_REFUSED. Other codes: BAD_TYPE, EMPTY, CONTROL_CHARS, TEXT_TOO_LONG, MISSING, UNKNOWN_KEY, UNKNOWN_VALUE, TOO_MANY, DUPLICATE, BAD_DATE. Refusals never echo caller-supplied keys or values.

## Output
Per item: declared values, unclassified_fields, missing_source_ids. Plus authority_flags, counts (items, unclassified, blocked_items), review_state ("blocked" or "counsel_review_required") and fixed fields reviewability_decided=False, legal_conclusion=None, filing_or_external_effect=False, authorities_independently_verified=False.

## Vocabularies (source-derived, builder convention)
Derived from the row mechanism text quoted above; they are coarse bookkeeping vocabularies, not doctrine, and omit many concepts; "unknown" (and "none_declared"/"other"/"disputed" where present) exist for that reason.
- `finality`: final_order, interlocutory, agency_action, other, unknown
- `standing`: direct_injury, statutory_interest, associational, third_party, none_asserted, unknown
- `exhaustion`: exhausted, partial, not_exhausted, futility_asserted, unknown
- `review_standard_declared`: de_novo, clear_error, abuse_of_discretion, substantial_evidence, arbitrary_capricious, other_declared, none_declared, unknown
- `record_scope`: agency_record, trial_record, supplemented, extra_record, unknown

## Limits and residual disclosures
- It never reaches a legal conclusion, determination, recommendation or decision, and gives no legal advice; flags are for counsel, not findings.
- Authorities and citations are caller text only; none is verified, fetched or checked for currency.
- No persistence, no network, no filing, service or contact. Not wired to any route or mount in this change.
- Text policy: raw length cap (256) before strip or any Unicode check; categories Cc, Cf, Zl, Zp refused (covers every Cf code point including U+00AD and U+2060); Zs accepted; lone surrogates (Cs) NOT newly refused - disclosed residual. Co (private-use) and Cn (unassigned, including noncharacters) code points are likewise accepted, disclosed alongside the Cs residual. Containers: list length and dict key count (16) checked before any iteration. Strict builtin types only (type() is; subclasses refused BAD_TYPE). Date gate: exact str, exact raw length 10, ASCII YYYY-MM-DD shape, then calendar validity (non-str is BAD_TYPE).
- Tests are hermetic stdlib (pytest over unittest-style helpers; no services, no network, no legal cases). FULL SUITE NOT RUN. No closure claim. Independent gate: separate record. Licensed counsel review remains required.

## Chronology disclosure
Tests were committed RED first (modules absent, collection errors) before the module files landed GREEN in the following commit. The modules and tests were produced from one disclosed row-spec table to keep the ten-row block uniform; per-row vocabularies are the row-specific content. Original builder verification used CPython 3.12.15; that verification does not establish a CPython 3.12.14 result.
