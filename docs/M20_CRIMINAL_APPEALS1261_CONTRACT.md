# CRIMIN1261: criminal-appeal preservation bookkeeping

Source pin: `audits/coverage-register.json`, row 1261, category "Specialized Domain Expertise", requirement "Criminal Appeals", description empty. The requirement title is the whole spec. Source mechanism reviewed at public base a294723b7a8f7bbe6067804ee4d7d325e1a8bde9. Landing composition parent is public 9cf6ff8e087d805a8f6d5ed2b961af452abbe403.

Standing boundary: "Legal work product for review, not legal advice. Licensed counsel must verify jurisdiction, currency, citations, facts, duties, deadlines and strategy before use."

Scope: bounded declared legal-support bookkeeping over caller-supplied data only. It separates what the caller declared about orders, preservation, record cites, review standards and remedies, and lists gaps. It never reaches a legal conclusion, never files, serves or contacts anyone, and never verifies supplied assertions, record cites or authority references. It never assesses appeal merit or predicts outcomes.

## Delta vs the existing mechanism

Existing: `backend/app/modules/m20_general_cognitive_worker/legal_support_1260_1309.py` line 18 (SPECS row 1261, "map orders, preservation, review standards, record cites and remedy limits") run through `analyze_legal_feature` at line 96, the shared template engine. That engine passes `row_inputs` through unchecked (`"inputs":data.get("row_inputs",{})`), so the row-specific orders, preservation, record cites and remedies are not structured, validated or cross-checked there. It returns `supplied_legal_review_template_only` with `named_capability_executed=False`.

This module adds, in a new file only: `map_appeal_preservation(packet)` with an exact schema (orders, record_cites, issues), strict types, caps, cross-reference checks (each issue names a known order and known record cite ids, no duplicates), a fixed set of per-issue gap flags, and exact refusal codes. It does not call or edit the shared engine and does not claim to replace it.

## Input

Exactly: jurisdiction, as_of (ISO date), orders (1..50), record_cites (1..500), issues (1..100). Order: id, kind (judgment, sentence, post_trial_order, suppression_ruling, other_declared), entered_on (ISO date, not after as_of), court. Record cite: id, document, page (integer 1..100000). Issue: id, order_id, label, preservation {status: preserved, not_preserved or unknown; cite_ids 0..50}, review_standard {label, authority_ref or null}, remedy {sought or null, limit_note or null}.

Ids are ASCII letters, digits and `_ . : -`, up to 100 characters. Text is nonblank, up to 2000 characters, with no Cc, Cf (full category, plus explicit pins U+00AD and U+2060), Zl, Zp, Co or Cn characters. Zs spaces are accepted. Surrogates (Cs) get no refusal: disclosed residual, a lone surrogate can pass through and be echoed. Co (private use) and Cn (unassigned) are refused as EXTRA strictness chosen by this module. They are NOT mandated by the uniform text policy and are not a policy requirement. This module has no code-content field, so the TAB/LF/CR carve-out does not apply and TAB, LF and CR are refused as Cc like any other control character. Types are exact (no bool for int, no tuple for list, no dict subclass). Enum fields (orders.kind, preservation.status) check strict str type, then a raw cap of 32 characters (refusal reason `must be bounded enum text`), and only then membership (`not an allowed value`). Dict keys must be exact `str` (a str subclass equal to an allowed name is refused with the usual `unexpected or missing keys`). Counts come first: every list length and every dict key count is checked before any set construction or iteration, and the raw text length cap is checked before strip or any Unicode check.

## Output

Issues sorted by id, each with its order, its cited record entries (copies), the caller-declared review standard (`verified` false), remedy declaration and a gaps list from: preserved_declared_without_record_cite, preservation_status_unknown, declared_not_preserved, review_standard_authority_ref_missing, remedy_sought_missing, remedy_limit_note_missing. A gap flag is bookkeeping, not a view on merit or waiver. Fixed flags: merit_assessed, outcome_predicted, deadlines_computed, authority_verified, record_verified and filing_or_external_effect are all false; legal_conclusion is null; review_state is counsel_review_required.

## Refusals

`Crimin1261Error` with message `CRIMIN1261:<field>:<fixed reason>`. Field names are schema paths such as `issues.order_id`. Request text never appears in a message.

## Tests

`tests/modules/test_m20_criminal_appeals1261.py`: 29 hermetic stdlib unittest tests, synthetic data only. Test file written first; RED was a collection error because the module file did not exist. Two tests were added after the first GREEN run to kill two surviving hand-written mutants (dict subclass, shared output cite objects); that is a post-RED test change. Four more tests were added with a later policy repair (count-before-set via a spy, full Cf plus U+00AD and U+2060, Zl/Zp refused and Zs accepted, surrogate not a new refusal); their RED was 2 failed, 23 passed. One more test was added with a later enum repair; its RED was 1 failed, 25 passed. A last test pins str-subclass dict keys (every object level) as refused; its RED was 1 failed, 26 passed. Two final tests pin the review_standard output dict exactly (label, authority_ref or null, declared_by_caller True, verified False). They were test-only additions with no runtime change: targeted review found the old suite did not kill flips of those two flags, and the builder checked 4 operators (ops5.txt) against the old suite (all 4 survived) and the new suite (all 4 killed).

## Limits and residual disclosures

- Builder-stated; run locally on Python 3.12.14 and 3.10.12 only. The full repo suite was NOT run.
- Mutation probe: 51 hand-written single-edit operators (ops.txt 33, ops2.txt 5, ops3.txt 6, ops4.txt 3, ops5.txt 4), each run once on a copy. 49 killed (30 of the first 33 at first run, 2 more after two added tests, 4 of 5 policy-repair, 6 of 6 enum-repair, 3 of 3 key-type, 4 of 4 review-standard against the final suite). Two survived, both argued equivalent by the builder, not independently verified. First: the date regex written as `\d` instead of `[0-9]`; the builder argues equivalence because `date.fromisoformat` refuses non-ASCII digits (checked on 3.12.14 and 3.10.12 only; may differ on other interpreters). Second: dropping the explicit U+00AD/U+2060 pin, the builder argues equivalence because both are category Cf (the pin is belt and braces). This is not an independent audit.
- Review-standard labels, authority refs and record cites are caller text, never checked against any law, record or database. Preservation status is a caller declaration, not a finding.
- No deadline, timeliness, waiver, harmlessness or standard-of-review computation. No jurisdiction rules. Not wired into any route, registry or the ledger; ledger status and crosswalk are not changed. No closure claim.
- Synthetic data only; no personal names, ids or secrets.
