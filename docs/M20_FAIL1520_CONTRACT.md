# M20 Row 1520 Failure Analysis contract

Ledger source pin: audits/coverage-register.json row 1520, requirement verbatim "Failure Analysis", description verbatim "" (empty - the requirement title is the whole spec). Row status in the ledger ("verified-practitioner-depth") is a builder attribution read from the ledger, not re-verified by this unit.

Purpose: bounded validation and reference bookkeeping over caller-supplied failure-analysis declarations (problem statement, evidence register, hypotheses with supporting/contrary evidence references, timeline, preservation actions). This is NOT a root-cause capability and NOT a physical examination: it is a bounded plan over supplied declarations. Pure stdlib, no I/O, deterministic.

Delta against the existing mechanism `_failure(d)` in `backend/app/modules/m20_general_cognitive_worker/engineering_1510_1559.py` (read on live main 36e4793f77619645cb221f397cdcd5d2116997a4, line 98):
- Existing: set-intersection counts over supplied evidence references - dangling references are silently dropped; hypothesis fields pass through unvalidated via {**h}; no schema, no bounds, untagged failure modes; status candidate_not_root_cause and root_cause_claimed False.
- New (interface only): bounded declaration (evidence 1..50, hypotheses 1..20, timeline 0..50, preservation actions 0..20) with exact input and item key sets, FAIL1520-tagged refusals, unique evidence and hypothesis ids, reference integrity (dangling or duplicated references refused; an item listed as both supporting and contrary for the same hypothesis refused), counts and net support derived from validated references only, bookkeeping flags for unsupported hypotheses and unreferenced evidence, plan explicitly labeled plan_only with test_executed False, root_cause_claimed False, evidence_verified False.

Input keys (exactly): problem_statement, evidence, hypotheses, timeline, preservation_actions. Evidence keys (exactly): id, kind, description. Hypothesis keys (exactly): id, statement, supporting_evidence_ids, contrary_evidence_ids. Timeline event keys (exactly): at, event. Text caps (cap before strip, before Unicode): problem_statement 512, evidence id 64, kind 32, description 256, hypothesis id 64, statement 256, reference entries 64 (at most 50 per list), timeline at 64, event 256, preservation action 256. Timeline "at" is a caller-supplied label, never parsed or ordered.
Refusals: FailError (a ValueError) with prefix "FAIL1520: ". Output carries three fixed limits strings.
Validation order pins: strict builtin types only (type(x) is, never isinstance, so subclasses and bool are refused); strict key types (every mapping key must be exactly str); container length and key counts before any set construction or iteration. Unicode refusal (Cc/Cf/Zl/Zp refuse, Zs accept, explicit U+00AD, U+2060 and U+200B pins) applies to all free text: problem statement, evidence id/kind/description, hypothesis id/statement, reference ids, timeline at/event, preservation actions. Cs surrogates: free text carries the Cs residual (a lone surrogate is neither refused nor normalized; consumers must treat it as opaque). Co (private-use) and Cn (unassigned) categories are also accepted, alongside Cs.

Scope: bounded exact deterministic bookkeeping over caller-supplied declarations. No root-cause determination, physical examination, laboratory work, evidence authentication or failure adjudication; plans are labeled plans, never results. Reference-integrity rules and caps are builder bookkeeping conventions (interpretation choice, disclosed), not analysis standards.

New files only: failure_analysis1520.py, test_m20_failure_analysis1520.py, this document. The shared cluster file engineering_1510_1559.py is not edited; no wiring or routes added.

Limits and residual disclosures:
- Support/contrary counts and net_support are arithmetic over supplied references, not evidentiary weight; a hypothesis with negative net support is still accepted and never adjudicated.
- unsupported_hypothesis_ids and unreferenced_evidence_ids are bookkeeping flags, not judgments of quality.
- Supplied timeline labels and preservation actions are carried as bookkeeping only and are never parsed, ordered or evaluated.

## Change note

Build order: tests committed red first (module absent, collection error), then the module landed green. The red commits carried three test-authoring bugs (a helper default that silently attached a supporting reference, a validation-order expectation for a 6-key non-str-key input, and raw control bytes in two Unicode pins) which were corrected in this green commit; the corrected pins are the ones the battery ran against. No commit history was rewritten.
