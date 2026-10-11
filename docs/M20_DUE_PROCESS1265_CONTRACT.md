# M20 Due Process 1265: declared-element completeness and date ordering contract

## Source pin

- Register: `audits/coverage-register.json`, row 1265.
- Verbatim: category "Specialized Domain Expertise", requirement "Due Process", description "" (empty). The title is the whole source; this contract states that rather than inventing a requirement text.
- Ledger: `audits/additional-2000-features.json`, row 1265, status PARTIAL (read at main a294723b7a8f7bbe6067804ee4d7d325e1a8bde9).
- Standing legal boundary: "Legal work product for review, not legal advice. Licensed counsel must verify jurisdiction, currency, citations, facts, duties, deadlines and strategy before use."

This unit is an explicitly chosen bounded mechanism, not a claim that the title is fully implemented.

## Relation to the existing row 1265 mechanism

Row 1265 already has a generic entry in `backend/app/modules/m20_general_cognitive_worker/legal_support_1260_1309.py`: the SPECS row at `legal_support_1260_1309.py:22` (method `due_process`, output key `process_entitlement_map`, mechanism "map protected interest, deprivation, notice, hearing and balancing factors") run by `analyze_legal_feature` at `legal_support_1260_1309.py:96`. That engine is shared by rows 1260-1309. For this row it passes the caller's `row_inputs` through untouched (`legal_support_1260_1309.py:131`) and validates nothing specific to due process.

Delta of this unit (`due_process1265.py`): it validates the five named elements itself (declared or not, sourced or not, source ids known or not), checks declared dates against `as_of`, and reports how the declared notice, hearing and deprivation dates order against each other. It does not call, import, edit or replace the template engine, and that file is unchanged.

## Entry point

`analyze_due_process(request)` in `backend/app/modules/m20_general_cognitive_worker/due_process1265.py`. Pure function, stdlib only, no file, network, clock or entropy access. Same input gives the same output; the input is not mutated and the output shares no object with it.

Request keys: `jurisdiction` (text), `as_of` (YYYY-MM-DD), `sources` (list of `{source_id, label}`) are required. Optional: `protected_interest {description, source_ids?}`, `deprivation {description, date?, source_ids?}`, `notice {given: bool, date?, content_summary?, source_ids?}`, `hearing {held: bool, date?, decision_maker?, source_ids?}`, `balancing_factors [{label, statement, source_ids?}]`. Every container and scalar is an exact built-in type (`type(x) is dict`, `list`, `str`, `bool`); container subclasses are refused as `BAD_TYPE`; text/`str` subclasses are refused as `BAD_TEXT`, and date-field subclasses as `BAD_DATE`. A non-`str` key (including a `str` subclass) is refused as `UNKNOWN_KEY` before the allowlist lookup. Unknown keys are refused with a fixed reason that names the containing object and does not echo the caller's key. Text must be an exact `str`, at most 500 raw characters (checked first, before any strip or Unicode scan), not blank, and free of Unicode categories Cc, Cf, Zl and Zp (the full categories, so U+00AD soft hyphen and U+2060 word joiner are refused); Zs spaces inside text are accepted. Dates must be an exact `str` of length 10 matching YYYY-MM-DD, length checked before the pattern. Every container is counted before it is iterated: at most 64 keys per object, 64 sources, 50 factors, 20 source ids per item; over-cap is TOO_MANY.

## Output

Per element a status: `NOT_DECLARED`, `DECLARED_UNSOURCED` or `DECLARED_SOURCED` (sourced means at least one source id and every id is in the supplied sources). Declared text and dates are passed through as supplied. `sequence` gives `notice_vs_deprivation`, `hearing_vs_deprivation` and `notice_vs_hearing` as `before`, `same_day`, `after` or `not_comparable` (first date relative to second; not comparable when either date is absent or the event is declared not to have happened). `gaps` lists the mechanical findings in element order. Fixed fields: `adequacy_judged` false, `legal_conclusion` null, `requires_licensed_counsel` true, `filing_or_external_effect` false, `authority_independently_verified` false.

Gap codes: ELEMENT_NOT_DECLARED, UNSOURCED, UNKNOWN_SOURCE_ID, DATE_AFTER_AS_OF, DATE_UNDECLARED, NOTICE_DECLARED_NOT_GIVEN, HEARING_DECLARED_NOT_HELD. A gap is a bookkeeping fact about the declaration. A date ordering such as a hearing before notice is reported in `sequence` and is not a gap or a finding.

## Refusals

Format `DUEPRO1265:<CODE>:<field path>`. Codes (UNKNOWN_KEY carries the container path only): BAD_TYPE, MISSING, UNKNOWN_KEY, BAD_TEXT, BAD_DATE, TOO_MANY, DUPLICATE_SOURCE, INCONSISTENT (a date supplied for notice that was declared not given, or a hearing declared not held). The error class is `DueProcessError`, a `ValueError` subclass with the `code` attribute.

## Limits and residual disclosures

- It never decides whether process was adequate, timely, required or fair, never weighs a factor, never names or applies a legal test, and never reaches a legal conclusion. It is not legal advice.
- It does not verify any declared fact, date, source or authority; `sources` are labels the caller supplied. Citations and jurisdictional currency are not checked.
- Date ordering is calendar-date only. No time of day, no time zone, no business-day or deadline calculation.
- It does not file, serve, notify or contact anyone and has no side effects.
- Balancing-factor labels and statements are the caller's words, passed through; none is invented, scored or ranked.
- The row title is the whole source, so this is one chosen reading, not the only one. The generic template engine remains the only other implementation for this row.
- Tests are hermetic stdlib unittest. Full-suite status is unverified; only this unit's test file and the legacy row 1265 tests were run, on the interpreters named in the builder report.
- No audit, closure or acceptance claim is made. Independent gate: separate record.
- Unicode surrogates (category Cs) are not refused. This is a disclosed residual, not a new refusal in this unit.
- Build disclosures (builder-stated): the original delivery was made as a permanent local commit 5bb48316ab5beca30ae050c61913f07d71e6f7a3, which violated the patch-only instruction; it is kept as is. The two pins added after the first mutation run (`test_hearing_held_without_date_is_a_gap`, `test_summary_counts`) had no individual RED. Mutation figures from the builder's own AST generator: first run 106 ran, 61 assertion kills, 41 exception kills, 4 survivors; after those 2 pins, 65 assertion and 41 exception kills and 0 survivors in that generator's set (no equivalence or completeness claim). The raw per-mutant output was not kept; only the summary lines were retained.
- Base read: main a294723b7a8f7bbe6067804ee4d7d325e1a8bde9.
