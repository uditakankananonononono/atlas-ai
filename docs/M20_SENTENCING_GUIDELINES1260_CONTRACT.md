# Row 1260 - Sentencing Guidelines

Landing composition parent: c9c1ca26bb80d2562a3e9c67e5788f11ab538a4b.

## Ledger source pin

- Source spec: audits/coverage-register.json row 1260 read at main
  a294723b7a8f7bbe6067804ee4d7d325e1a8bde9.
- Requirement (verbatim): "Sentencing Guidelines"
- Description (verbatim): "" (empty - the requirement title is the whole spec,
  as stated on the row card).
- Ledger status (audits/additional-2000-features.json, id 1260): PARTIAL.
- Standing legal boundary (verbatim): "Legal work product for review, not legal
  advice. Licensed counsel must verify jurisdiction, currency, citations, facts,
  duties, deadlines and strategy before use."

## Delta vs the existing mechanism

The shared cluster engine
backend/app/modules/m20_general_cognitive_worker/legal_support_1260_1309.py
carries row 1260 as a _SPECS entry (line 17 at main a294723b) executed by
analyze_legal_feature (line 96). That engine returns
status="supplied_legal_review_template_only" with
named_capability_executed=False: a generic template artifact with no
row-specific mapping. Earlier register evidence path:
backend/app/modules/m12_ai_research_lab/legal_support.py.

This unit executes the row-1260 mechanism itself in a NEW file
(backend/app/modules/m20_general_cognitive_worker/sentencing_guidelines1260.py;
the shared cluster file is never edited): validated per-entry bookkeeping of
guideline edition + offense characteristics + adjustments + departures, each
entry caller-tagged as sourced_fact, assertion or analysis, with separation
counts, exact row-tagged refusal codes (SENTEN1260:), and explicit
never-computed flags.

## Interface

map_guideline_inputs(data) -> receipt dict.

Input object keys (unknown keys refuse with a generic reason):
- guideline_edition (required non-empty string, max 64; a declared label,
  never verified)
- offense_characteristics, adjustments, departures (optional lists of entry
  objects, max 64 entries each, counted before any iteration; empty allowed)
- jurisdiction (optional string, max 128), as_of (optional ISO date string),
  provenance (optional string, max 256; echoed as provenance_label)

Entry object keys: text (required non-empty string, max 256), basis (required:
"sourced_fact" | "assertion" | "analysis"), source_ref (optional string,
max 256).

Receipt: row, capability, scope ("supplied_guideline_input_mapping"), status
("mapping_complete"), guideline_edition, jurisdiction, as_of, provenance_label,
guideline_map (the three lists in input order), separation (sourced_facts /
assertions / analysis counts), input_trace, provenance (input_sha256 over the
validated canonical, hash_scope="validated_fields", edition_verified=False,
assertions_verified=False, sources_verified=False), flags
(sentence_computed=False, guideline_range_computed=False, legal_advice=False,
filing_or_contact=False), boundary (not_legal_advice=True,
requires_licensed_counsel=True, text=standing legal boundary verbatim),
human_review_required=True.

## Refusals

SentencingGuidelinesRefusal(ValueError) with .code and .detail (always {}):
- SENTEN1260:invalid_input - shape, type, enum, format and content violations
- SENTEN1260:resource_limit - size-bound violations
- SENTEN1260:unknown_key - unknown keys (reason names the parent field only)
- SENTEN1260:oversize - aggregate string-leaf budget (200000)

## Validation order

Exact container types (type(x) is list/dict) before len(); count caps before
any iteration; every string check is exact type (type(x) is str, no
isinstance); keys at both levels must be exact str - a str-subclass key is
refused even when it carries an allowed name; per string: raw length cap
first (before any strip, regex or other check - as_of takes its 10-char raw
cap before the ISO regex, basis takes its 12-char raw cap before membership),
then the Unicode check (no Unicode control (Cc), format (Cf) or
line/paragraph separator (Zl/Zp) characters - the full Cf category, with
explicit pins for U+00AD and U+2060; space separators (Zs) accepted), then
aggregate accounting. The incoming object is never copied; the receipt and the
hash are built only from validated values in fresh containers. Refusal reasons
are generic and name schema fields only.

## Known residuals

- Unpaired surrogates (Unicode category Cs) in caller-supplied text are NOT
  refused; they pass validation and are echoed/hashed as supplied (JSON
  output escapes them). This residual is kept deliberately; no refusal is
  added for Cs.

## Limits and residual disclosures

- The unit NEVER computes a sentence, a guideline range, an offense level, a
  criminal-history category or any outcome; it never files, serves or contacts
  anyone; it never verifies the edition, entries, citations or source
  references. Jurisdiction/as-of/provenance are caller-supplied labels and are
  not checked for currency or accuracy.
- "Sourced_fact" is a caller tag, not a verified fact; source_ref strings are
  caller-supplied labels and are not resolved or validated against any
  authority.
- Tests are hermetic stdlib-only (tests/modules/test_m20_sentencing_guidelines1260.py);
  the FULL SUITE was NOT run (FULL-SUITE UNVERIFIED).
- Mutation battery over this unit was run by the builder; results are reported
  with the delivery. No closure claim is made beyond this scope.
