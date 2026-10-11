# Row 1268: Regulatory Practice

## Source pin and exact delta

Source: audits/coverage-register.json row 1268, category "Specialized Domain
Expertise", requirement "Regulatory Practice", description "" (empty).
The requirement
title is the whole spec; this contract does not claim the title is fully
covered, only the bounded mechanism below.

Standing legal boundary (verbatim): "Legal work product for review, not legal
advice. Licensed counsel must verify jurisdiction, currency, citations, facts,
duties, deadlines and strategy before use."

Public base read: a294723b7a8f7bbe6067804ee4d7d325e1a8bde9 (ls-remote main).
Existing mechanism: backend/app/modules/m20_general_cognitive_worker/
legal_support_1260_1309.py:25 SPECS row 1268 ("map regulated activity to rule
text, effective date, regulator and control evidence", output key
regulatory_obligation_map) through analyze_legal_feature at :96. That shared
template engine validates authorities and echoes caller row_inputs unchanged; it
does not map activities to rules, compute effectiveness, or link controls.

Exact delta (new files only, no cluster, dispatcher, ledger or existing test edit):
a separate closed-schema validator and deterministic mapper,
`map_regulatory_obligations(data)` in
backend/app/modules/m20_general_cognitive_worker/regulatory_practice1268.py.
It does not replace the shared template and has no dispatcher entry.

## Input (closed schema)

Top level: jurisdiction (text), as_of (YYYY-MM-DD), activities (1..64),
rules (1..64), controls (optional, 0..64). Unknown or missing fields refuse.
- activity: id, text, rule_ids (0..64 unique rule ids)
- rule: id, regulator, rule_text_ref, effective_date, optional end_date
  (must be after effective_date)
- control: id, rule_id, evidence_ref
Ids match [A-Za-z0-9_.-]{1,64} and are unique per collection. Text is exact str,
1..500 chars, no control, bidi, format or line/paragraph separator characters.

## Output

Rules sorted by id with effectiveness at as_of: not_yet_effective (as_of before
effective_date), ended (as_of on or after end_date), else in_effect; linked
control ids and evidence refs. Activities sorted by id. Findings:
activities_without_rules, rules_without_control_evidence, rules_without_activities,
rules_not_in_effect_at_as_of, activities_touching_rules_not_in_effect. A
provenance_sha256 over the validated, id-sorted input; output order does not
depend on input order. Output is built in fresh containers (no aliasing).
Always: compliance_certified=False, rule_text_verified=False,
control_evidence_verified=False, legal_conclusion=None,
counsel_review_required=True, status declared_input_bookkeeping_only.

## Refusals

Exception RegulatoryPracticeRefusal (ValueError subclass), .code "REGULA1268",
message prefix "REGULA1268: ". Reasons are generic and never contain caller
keys, values or ids. Exact reasons are asserted in the tests.

## Validation order (v2 repair)

Raw length/count caps run first at every level: text length (raw, before strip
and the Unicode scan), id and date length, and the key count of the top level
and of every rule/activity/control object (before the key-type scan and before
the allowlist scan). Exact container types are checked before len().

## Reproduction

`python3 tests/modules/test_m20_regulatory_practice1268.py` (stdlib unittest,
hermetic, no network). Builder-stated run: Python 3.10.12, 42 tests OK.
Chronology (all builder-run, not independent):
- v1: original RED was module missing (FileNotFoundError) with the first 26
  tests; 2 more tests (control-coverage of the hash, rule_ids cap reason) were
  added after a hand-mutation probe found 2 survivors, so their own RED is not
  logged. v1 had 28 tests. v1 probe: 15 hand mutants, 13 killed by the first 26
  tests, 15 of 15 by the 28.
- v2 repair: 4 order pins (OrderPins) were added first and ran RED (32 tests, 4
  failed) before the source repair; the old 28 passed. A first RED run aborted
  on a SyntaxError in a test edit and is not counted.
- v2 Unicode pins (UnicodePins, 6 tests) were added afterwards as regression
  pins and passed immediately, so they have no RED of their own. Total 38.
- v3 gate pins (GatePins, 4 tests: unknown root field under the key cap,
  end_date present vs absent, non-ASCII jurisdiction hash, Cs escape hash) were
  added from targeted review probes against unchanged runtime. They passed
  immediately, so they have no RED of their own; instead each of the 3 named
  survivor mutants was re-applied by hand and killed. Total 42.
- Builder hand-mutation probes: 19 mutants killed by the 38 tests, plus the 3
  named mutants killed by the 42 tests. Written and run by the builder,
  not an independent audit.

## Limits and residual disclosures

- Scope is bookkeeping over declared data. It never certifies compliance,
  verifies rule text or control evidence, reaches a legal conclusion, files,
  serves or contacts anyone.
- Rule currency beyond the caller's dates, jurisdiction applicability, and
  whether a control actually satisfies a rule are not assessed.
- Unicode scope: the check rejects categories Cc, Cf, Zl and Zp only. Lone
  surrogates (Cs) are accepted as text, and provenance_sha256 is computed over
  JSON with ensure_ascii=True, so such input hashes as \\udXXX escapes. This is
  a disclosed scope, not a claim that Cs is handled further.
- Synthetic sample data only; no real regulator, rule or person is represented.
- Not run: whole repo suite (FULL-SUITE UNVERIFIED), other Python versions,
  Windows, routing or dispatcher integration, independent mutant-battery audit.
- Builder-stated; no closure or acceptance claim.
