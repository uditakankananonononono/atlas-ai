# Row 1272 - Treaties (contract)

## Source pin
- Register: audits/coverage-register.json, row 1272, category "Specialized Domain Expertise".
- Requirement (verbatim): "Treaties". Description (verbatim): "" (empty; the requirement title is the whole spec).
- Existing register mapping: backend/app/modules/m20_general_cognitive_worker/legal_support_1260_1309.py.
- Read at main 070f7ffb838db4b012bd443c4e1054f426220ebe (mechanism re-verified unchanged there: SPECS rows 1270-1279 lines 27-36, analyze_legal_feature line 96). The unit's build base was the older 85567d684018a1f6dad850228c24e68cb98c709e; an earlier draft of this note pinned that older read. Ledger status claims are historical attribution, not reproduced behavior or acceptance.

## Standing legal boundary
Legal work product for review, not legal advice. Licensed counsel must verify jurisdiction, currency, citations, facts, duties, deadlines and strategy before use.

## What this is
`organize(payload)` in backend/app/modules/m20_general_cognitive_worker/treaties1272.py. Bounded bookkeeping over caller-supplied data. It records what the caller declares for each item (signature, ratification, reservation, entry_into_force, domestic_effect) in closed vocabularies and flags unknown values, unresolved source ids, and authority jurisdiction or effective-date mismatches. Prefix for refusals: `TREAT1272:<REASON>[:<field>]`, plain ValueError.

## Delta vs the existing mechanism
Existing: SPECS row 1272 at legal_support_1260_1309.py:29 ("map signature, ratification, reservations, entry into force and domestic effect") run by analyze_legal_feature (line 96). That engine copies caller `row_inputs` into the artifact unchanged and returns `named_capability_executed=False`; it performs no row-specific classification. Added here: closed vocabularies with exact refusals, unknown and missing-source flags, counts, caps and a blocked/counsel-review state. The shared file is not edited. Original unit supplied no route wiring. The fresh mounted follow-up adds `/api/v1/api/modules/20/legal/1272/run` through the real application; see audits/row1272-mounted/README.md.

## Inputs and refusals
Top-level keys: jurisdiction, as_of (YYYY-MM-DD), authorities (1-32), items (1-16). Item keys: id, signature, ratification, reservation, entry_into_force, domestic_effect, source_ids (1-8). Authority keys: id, citation_text, jurisdiction, effective_date. Text 1-256 chars, no control characters. A truthy `decide`/`constitutional`/`conclusion` key is refused CONCLUSION_REFUSED; a truthy `file`/`serve`/`contact`/`send`/`spend` key is refused EXTERNAL_EFFECT_REFUSED. Other codes: BAD_TYPE, EMPTY, CONTROL_CHARS, TEXT_TOO_LONG, MISSING, UNKNOWN_KEY, UNKNOWN_VALUE, TOO_MANY, DUPLICATE, BAD_DATE. Refusals never echo caller-supplied keys or values.

## Output
Per item: declared values, unclassified_fields, missing_source_ids. Plus authority_flags, counts (items, unclassified, blocked_items), review_state ("blocked" or "counsel_review_required") and fixed fields treaty_status_decided=False, legal_conclusion=None, filing_or_external_effect=False, authorities_independently_verified=False.

## Vocabularies (source-derived, builder convention)
Derived from the row mechanism text quoted above; they are coarse bookkeeping vocabularies, not doctrine, and omit many concepts; "unknown" (and "none_declared"/"other"/"disputed" where present) exist for that reason.
- `signature`: signed, not_signed, accession, succession, unknown
- `ratification`: ratified, accepted, approved, not_ratified, unknown
- `reservation`: none, declared_reservation, declared_understanding, objection_received, unknown
- `entry_into_force`: in_force, not_in_force, provisional_application, disputed, unknown
- `domestic_effect`: directly_applicable, implementing_legislation, not_implemented, disputed, unknown

## Limits and residual disclosures
- It never reaches a legal conclusion, determination, recommendation or decision, and gives no legal advice; flags are for counsel, not findings.
- Authorities and citations are caller text only; none is verified, fetched or checked for currency.
- No persistence, no network, no filing, service or contact. Original unit was not mounted; the fresh follow-up supplies a dedicated authenticated computation route.
- Text policy: raw length cap (256) before strip or any Unicode check; categories Cc, Cf, Zl, Zp refused (covers every Cf code point including U+00AD and U+2060); Zs accepted; lone surrogates (Cs) NOT newly refused - disclosed residual. Co (private-use) and Cn (unassigned, including noncharacters) code points are likewise accepted, disclosed alongside the Cs residual. Containers: list length and dict key count (16) checked before any iteration. Strict builtin types only (type() is; subclasses refused BAD_TYPE). Date gate: exact str, exact raw length 10, ASCII YYYY-MM-DD shape, then calendar validity (non-str is BAD_TYPE).
- Tests are hermetic stdlib (pytest over unittest-style helpers; no services, no network, no legal cases). FULL SUITE NOT RUN. No closure claim. Independent gate: separate record. Licensed counsel review remains required.

## Chronology disclosure
Tests were committed RED first (modules absent, collection errors) before the module files landed GREEN in the following commit. The modules and tests were produced from one disclosed row-spec table to keep the ten-row block uniform; per-row vocabularies are the row-specific content. Original builder verification used CPython 3.12.15; that verification does not establish a CPython 3.12.14 result.
