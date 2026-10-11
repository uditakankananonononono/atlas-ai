# Row 1309 - Legal Education (bounded legal-support bookkeeping)

## Ledger source pin
- Register: audits/coverage-register.json row 1309 (read on live main 4da7f8e5)
- requirement (verbatim): "Legal Education"
- description (verbatim): "" (empty - the requirement title is the whole spec)
- Ledger status: Earlier scope was PARTIAL; the register row itself carries post_semantic_status "verified" for the shared cluster mechanism. Disclosed discrepancy: this unit is an additions-only PREP card and claims no closure beyond scoped.

## Legal review boundary
Legal work product for review, not legal advice. Licensed counsel must verify jurisdiction, currency, citations, facts, duties, deadlines and strategy before use.

## Scope
Bounded declared legal-support bookkeeping over caller-supplied data only (as-of/provenance-bound; jurisdiction not supplied or validated; separates sourced facts from assertions and from analysis); never reaches a legal conclusion, never files, serves or contacts anyone, never verifies supplied assertions or authority references; never states that a course, exercise or assessment satisfies any educational or licensing requirement.

## Existing mechanism and delta
- SPECS row 1309 @ backend/app/modules/m20_general_cognitive_worker/legal_support_1260_1309.py line 66 ("map audience, learning objective, source authority, exercise and assessment limits") via analyze_legal_feature @ line 96 (line numbers verified on live main 4da7f8e5).
- Delta: the existing engine accepts free-form analysis items and checks no row-specific vocabulary; this unit checks which named elements of the row the caller supplied a reference for. "referenced" means a reference string was supplied; nothing is verified, no deadline is computed or advised.

## Interface and refusals
- run(request); exact request keys {row, as_of, entries}; entries length 1..200 checked before iteration; entry keys a subset of {element, status, source_ref, entry_date} with element and status required.
- Element state precedence: disputed > referenced > declared_missing > unaddressed; also_declared_missing is set only on referenced. latest_entry_date ranges over supplied entries only; days_since_latest is whole days, never negative, no threshold applied.
- Refusal codes (message is exactly "LEGALE1309: " + code): EMPTY:entries, OVERSIZE:entries, BAD_TYPE:request, BAD_TYPE:entries, BAD_TYPE:entry, BAD_TYPE:source_ref, BAD_TYPE:as_of, BAD_TYPE:entry_date, UNKNOWN:row, UNKNOWN:element, UNKNOWN:status, and forbidden-table refusals "<TABLE>:<matched key>".
- Output never echoes source_ref text; refusal reasons never carry source text (schema field names and table keys only).

## Interpretation disclosures
- BAD_TYPE:request and BAD_TYPE:entry are not in the package's example code list; both are schema field names per the package's reason rule.
- SEND/SPEND/NOCREDS tables reuse the canonical sets from backend/app/modules/c30/worldclass.py lines 34-43 (the package names the tables without listing their keys). EFFECT is the package-specified set {file, serve, send, contact, submit, execute, advise, settle}. Scan order SEND, SPEND, NOCREDS, EFFECT, so a "send" key reports SEND:send.
- Missing-status entries may omit source_ref or carry it as null; an entry_date is allowed on any status.
- This contract describes supplied-data bookkeeping only; it grants no permission for external actions.

## Test and gate evidence
- tests/modules/test_m20_legal_education1309.py - 20 hermetic stdlib tests with exact-value pins; RED evidence retained in git (red commit 9f8c2249860f6dea5ae13f433c80ed0ce23ebffd, tests failing on missing module, precedes the implementation commit).
- Mutation battery: 10 mutants per unit (status partition, vocabulary table, date gate, duplicate rule, days arithmetic, prefix, unicode scan, source_ref cap, forbidden scan, latest-max); raw results in the package manifest.
- Interpreter floor: Python 3.12.15.

## Limits and residual disclosures
- FULL-SUITE UNVERIFIED: only this package's 13 test files were run.
- Bookkeeping only: no legal conclusion, no filing/serving/contacting, no verification of supplied references or authority, counsel review required before any use.
- Cs (surrogate) characters are not separately refused (same disclosed residual as the engineering siblings); Cc/Cf/Zl/Zp refused, Zs accepted.
- Additive new files only; the shared cluster file legal_support_1260_1309.py is untouched; no wiring or routes.

Change note: test-first this unit - red commit 9f8c2249860f6dea5ae13f433c80ed0ce23ebffd precedes the implementation commit.
