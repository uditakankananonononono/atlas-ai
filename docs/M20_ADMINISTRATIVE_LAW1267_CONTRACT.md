Source pin: `audits/coverage-register.json`, row 1267, requirement verbatim: "Administrative Law"; description verbatim: "" (empty, requirement title is the whole source specification); read base `a294723b7a8f7bbe6067804ee4d7d325e1a8bde9`. `audits/additional-2000-features.json` row 1267 status at that base: `PARTIAL`.

# M20 row 1267: declared administrative review bookkeeping

Legal work product for review, not legal advice. Licensed counsel must verify jurisdiction, currency, citations, facts, duties, deadlines and strategy before use.

## Delta against current mechanism

At the pinned base, `backend/app/modules/m20_general_cognitive_worker/legal_support_1260_1309.py:24` defines administrative law as "map statutory delegation, procedure, record, deference and remedy questions". Its shared `analyze_legal_feature` at line 96 validates context and organizes supplied material, but line 131 echoes arbitrary `row_inputs`; line 136 explicitly reports supplied templates and no named capability execution.

This new file does not edit, replace, import, mount or invoke that shared mechanism. It adds a strict five-domain review-question map and validates a typed reference graph across independently labeled authorities, sourced facts, assertions, analysis and questions. It detects duplicate identifiers/references, dangling or wrong-namespace references, missing domain declarations, and declared jurisdiction/date gaps. It performs real deterministic bookkeeping, not substantive administrative-law analysis. The existing register's verified-practitioner-depth claim was read, not reproduced or adopted. New-file routes were absent on the pinned base; no collision identified there. Future main collisions remain possible.

## Interface and schema

`build_review(data)` in `backend/app/modules/m20_general_cognitive_worker/administrative_law1267.py` is an offline, stateless function returning a detached plain dict. Dependencies: Python stdlib only. No persistence, tenant store, subprocess, network, source retrieval, auto-submission or personal data requirement.

Root required fields: `jurisdiction` (caller-declared text), `as_of` (canonical ISO calendar date), `provenance` (`source_label`, `observed_on`), `authorities`, `issues`. Optional collections: `sourced_facts`, `assertions`, `analysis`, default empty. Unknown fields are refused at every schema level.

All lists are bounded at 200 entries, including reference lists. Raw strings are capped at 4,000 characters before stripping or Unicode scanning. Every echoed free-text field and schema key passes a uniform Unicode category screen: Cc, Cf, Zl and Zp are refused as ADMINI1267:TEXT; Zs is accepted with existing edge trimming. Full Cf category is covered, including U+00AD and U+2060. Container list sizes and schema-specific key counts are checked before iteration or SET construction. Dates check exact str type first, exact raw length 10 second (source-order observation; output equality does not prove scan order, while the targeted patched-scanner pin observes that oversized dates do not invoke the generic text scanner), ASCII digit/hyphen format third, then real calendar validity. All malformed dates, including short dates and controls/Cf, map to ADMINI1267:DATE rather than TEXT. Fixed date syntax rejects these characters without applying the generic free-text screen; no date trimming is performed. This explicitly changes the prior generic-TEXT date-screen semantics. Packet observations and authority checks after `as_of` are refused. Authority validity endpoints must be ordered. HTTPS authority URLs cannot contain credentials, queries, fragments, whitespace/control characters or a nondefault port. These restrictions reduce accidental secret-bearing URLs, but are not a guarantee that caller-supplied text is secret-free.

Authority fields: `id`, `title`, `citation`, `source_url`, `jurisdiction`, `effective_on`, `checked_on`, `valid_through`. These are caller declarations, never independently checked. Jurisdiction equality is literal text comparison, not jurisdiction normalization. A check before `as_of`, declared expiry, future effectiveness or mismatched jurisdiction yields a review gap, not a legal finding.

Sourced fact fields: `id`, `text`, nonempty `authority_refs`. Assertions: `id`, `text`. Analysis: `id`, `text`, `authority_refs`, `fact_refs`, `assertion_refs`. Analysis refs may be empty; this does not imply support or completeness. Analysis remains `caller_analysis_unverified`.

Issue fields: `id`, `domain`, `question`, `authority_refs`, `fact_refs`, `assertion_refs`, `analysis_refs`. Domains exactly: `delegation`, `procedure`, `record`, `deference`, `remedy`. Those are caller-selected labels, never classifier outputs. Reference namespaces cannot be interchanged. All entry identifiers across collections are globally unique. References preserve declared order and must be unique in each list. Empty issue authority refs are visible gaps. No issue is automatically created for missing domains.

## Output and refusal contract

Output carries original context/provenance; separately labeled `supplied_material`; five-key `domain_map`; `gaps`; counts naming their collection; and review state `counsel_review_required` or `declared_gaps_require_counsel_review`. All results remain review-only, even when no bookkeeping gaps are found. Text is data, not instruction.

Always: `feature_id=1267`, `status=declared_administrative_bookkeeping_only`, `evidence_verified=False`, `named_legal_capability_executed=False`, `legal_conclusion=None`, `external_effect=False`, `requires_licensed_counsel=True`.

Refusals are `ValueError` with exact message:
- `ADMINI1267:SCHEMA`: wrong object shape, missing fields or unknown fields.
- `ADMINI1267:TEXT`: blank/nonstring/oversized text.
- `ADMINI1267:DATE`: invalid/noncanonical/nonstring date.
- `ADMINI1267:FUTURE_PROVENANCE`: observation/check later than declared as-of.
- `ADMINI1267:DATE_ORDER`: valid-through before effective-on.
- `ADMINI1267:SOURCE_URL`: disallowed authority URL.
- `ADMINI1267:COLLECTION`: wrong list type or more than 200 entries.
- `ADMINI1267:AUTHORITY_REQUIRED`: empty authorities.
- `ADMINI1267:DUPLICATE_ID`: repeated identifier across any entry collection.
- `ADMINI1267:DUPLICATE_REF`: repeated reference within a list.
- `ADMINI1267:UNKNOWN_REF`: absent or wrong-namespace supplied reference.
- `ADMINI1267:FACT_SOURCE_REQUIRED`: sourced fact lacking authority refs.
- `ADMINI1267:DOMAIN`: unsupported declared domain.

Gap codes, not refusals: `jurisdiction_mismatch`, `declared_expired`, `not_checked_as_of`, `not_yet_effective`, `issue_without_supplied_authority`, `missing_declared_domain`. Source linkage is structural only.

## Builder verification and review gate

Hermetic invocation: `python3 tests/modules/test_m20_administrative_law1267.py -v`. Test loads only this file, avoiding application imports and dependency installation. Samples use generic declarations and `.invalid` URLs, not real people or legal propositions. Genuine pre-implementation RED was an absent-module failure at 2026-10-11T21:52:27+05:30, exit 1, before source authoring. It did not execute 25 failing methods. Original RED log is preserved, never reconstructed.

First GREEN: Python 3.10.12, 25 unittest methods passed at 21:52:58 IST. Separate targeted guard-removal mutation probe is builder-stated evidence, not independent audit. Identity hashes and complete raw results accompany the handoff. Project requires Python >=3.12; that toolchain was not available here. No full-suite execution: FULL-SUITE UNVERIFIED. No endpoint integration or landing. Independent gate: separate record. No closure, release authority or legal-practice claim.

## Limits and residual disclosures

Bounded declared legal-support bookkeeping over caller-supplied data only, jurisdiction/as-of/provenance-bound; separates sourced facts from assertions and analysis. Never reaches a legal conclusion, never decides deference or validity of agency action, never files, serves or contacts anyone, and never verifies supplied assertions or authority references. No legal advice, authority retrieval, citation interpretation, substantive analysis, deadline computation, exhaustive issue spotting, current-law verification, protected-data isolation service, or API mount. All data remains unverified and must be reviewed by licensed counsel. Project >=3.12 and full-suite compatibility remain unverified. The bounded delta cannot satisfy the whole open-ended "Administrative Law" title; ledger scope remains PARTIAL and no closure claim is made.

Repair residual: Cs surrogate characters receive no new category refusal; retained Cs can fail later serialization/encoding. This pre-existing residual remains, and no Unicode-safety certification is made. Repair preserves the scope and all legal limits above.
