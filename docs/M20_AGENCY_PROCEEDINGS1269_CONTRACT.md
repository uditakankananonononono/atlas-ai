Source pin: audits/coverage-register.json row 1269, requirement verbatim "Agency Proceedings", description verbatim "" (empty, title is the whole source spec). Source mechanism reviewed at public base a294723b7a8f7bbe6067804ee4d7d325e1a8bde9; landing composition parent is public 0d148d1305f4f411d46021efc46eb872446445eb. audits/additional-2000-features.json records PARTIAL. Ledger claims are historical attribution, not reproduced behavior or acceptance.

# Agency proceedings1269: declared record bookkeeping

Legal work product for review, not legal advice. Licensed counsel must verify jurisdiction, currency, citations, facts, duties, deadlines and strategy before use.

## Delta and collision

Existing shared mechanism backend/app/modules/m20_general_cognitive_worker/legal_support_1260_1309.py:26 names "map tribunal authority, pleadings, administrative record, hearing steps and exhaustion". Its engine at :96 and :130-139 organizes supplied references/analysis and echoes row_inputs. It does not validate record-to-pleading/hearing links. This separate component validates an explicit schema and produces an actual reverse record index, unused-record list and review flags. The shared engine, router, ledgers and tests are unchanged. All three new routes were absent at the pinned base. No endpoint integration is supplied.

## Interface and declared bounds

organize(payload) is pure, stdlib-only, no imports of the Atlas application stack and no I/O. Exactly ten fields: jurisdiction, as_of, sources, tribunal, records, pleadings, hearings, exhaustion, assertions, analysis. No identities, account identifiers or credentials are requested. Keys are anonymous bookkeeping tokens, not personal identifiers. Text is exact nonempty unpadded string, at most 2048 characters, Unicode Cc/Cf/Zl/Zp refused using the full category table; Zs accepted. Raw length is checked before stripping/category inspection. Every container length/key count is checked before set construction or iteration. Cs surrogates remain accepted as a disclosed residual, not a new refusal. Every list contains at most 128 items. Sources and reference lists have minimum one; other lists may be empty. Object schema keys must have exact str type, not subclasses, after raw key-count validation and before set comparison. Exhaustion state has a 2048-character raw cap before membership/hash. Keys are unique within each typed collection; references must exist and may not repeat. References are explicitly typed, not globally interchangeable identifiers.

Sources: key/citation/jurisdiction/checked_on/url. URLs must be HTTPS with a host and no credentials; they are never fetched. Dates are strict YYYY-MM-DD and calendar-valid. Source checked_on later than as_of refuses; earlier checks and declared jurisdiction mismatches are flags, not actual source currency or legal applicability findings.

Tribunal: label/source_keys. Records: key/text/source_keys. Pleadings: key/text/record_keys/source_keys. Hearings: key/on/text/record_keys/source_keys. Exhaustion: key/state/text/source_keys, with state exactly declared_done, declared_pending or unknown. Assertions are separate strings; analysis contains text/source_keys. No representation of a party, inferred procedural order, determination of exhaustion or deadline calculation.

Output: row_id 1269; exact collection counts named by unit; reverse record_usage, unreferenced_record_keys, unknown_exhaustion_steps; mismatch/stale/future-hearing flags. A defensive copy preserves sourced records, caller assertions and caller analysis separately. status needs_review or review_required always requires counsel. exhaustion_decision is None, authority_verified and external_effect false, evidence_status caller_supplied_unverified. A future scheduled hearing is flagged, not declared unlawful or overdue.

## Exact refusal codes

AGENCY1269:SCHEMA - wrong object shape; TEXT - invalid string; BOUND - wrong list type/count; DATE - invalid/noncanonical date; URL - unsupported source reference; DUPLICATE - duplicate typed key; REFS - repeated reference; SOURCE_REF - undeclared source; RECORD_REF - undeclared record; STATE - unsupported exhaustion declaration; FUTURE_SOURCE - source check later than declared as_of. Refusals never echo supplied content.

## Test evidence

Hermetic unittest file loads the actual component by path, with no fake services/application stubs, no external network or legal cases. Genuine pre-implementation RED is FileNotFoundError with exit 1; preserved before source creation. GREEN count is named as unittest cases, not assertions, legal outcomes or feature closure. Independent audit is still required before landing; supplied mutation evidence is builder-stated. Initial stdlib chronology used Python3 3.10.12. Final focused tests and selected 49-operator retake used CPython 3.12.14: 33 focused cases passed. This does not verify mounted/full-suite execution or the full production environment. Original RED, Unicode policy RED and strict-key repair RED are preserved; the state-length pin alone already refused under old membership behavior, so the raw-cap ordering change has source-grounded review plus a pin, not a standalone observed behavioral RED.

## Policy repair evidence

Targeted new RED retained before the Unicode/count repair, followed by stdlib GREEN. Tests enumerate the complete runtime Cf category and explicitly pin U+00AD/U+2060; Zs and the accepted Cs residual are pinned. Original source/tests/contract and chronology are preserved separately. No scope change.

## Re-anchored builder probe evidence

Builder retook the supplied 49 real operator variants on the repaired runtime: 49 assertion kills, zero error kills, zero survivors; four variants argued equivalent survived; those equivalence arguments remain independently unverified. The earlier pristine-source run was 37 assertion kills plus 12 error kills and is preserved separately. Four exhaustion-context patches needed explicit re-anchoring after the state raw cap was added, with the new raw cap kept intact. Runtime changed only for strict schema key types and exhaustion raw cap, so the old unchanged-runtime claim no longer applies. No independent fresh gate or full mutant-battery closure claimed. Exact refusal helper now converts unexpected exceptions into assertion failures with the expected/actual exception type, rather than counting accidental errors as clean kills.

## Limits and residuals

Cs surrogates remain accepted and may fail downstream serialization; no new surrogate refusal is added. Bounded caller-declared bookkeeping only. No legal advice, verified authority, substantive legal conclusion, outcome prediction, actual exhaustion decision, filing/service/contact, deadline control, legal validity or privacy de-identification guarantee. Supplied content can still contain personal information; users must keep it out. No route wiring, authentication/tenant boundary, persistence, source retrieval, large-scale concurrency or full application test. FULL-SUITE UNVERIFIED. No closure claim; independent audit and licensed counsel review remain required.
