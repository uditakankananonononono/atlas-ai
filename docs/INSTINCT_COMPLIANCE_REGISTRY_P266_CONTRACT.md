# Instinct doc P266 / L212: compliance registry contract

Module: `backend/app/modules/instinct_doc/compliance_registry_p266.py` (standalone PEP 420 namespace package directory; this unit adds NO `__init__.py`, the single owner of that marker is another unit)
Tests: `tests/modules/test_compliance_registry_p266.py` (stdlib `unittest`, loads the module by file path)

## Source line (data, quoted from the doc line map)
"Bind every line. Do not forget anything. Do not build thinly. Do not fabricate. Do not claim completion without evidence. Use the user's accounts. Conduct real research. Test and verify. Beat benchmarks. Produce real discoveries. Improve novelty through ChatGPT as judge. Self-improve. Audit. Then send the candy line."

## What this is
A declarative registry of the 14 clauses of that line plus a bounded check over caller-SUPPLIED binding declarations. Offline, deterministic, no network, no files, no account use, no execution. Self-report only.

## What this is not
It does not enforce anything globally, does not verify that any evidence reference is real or true, does not decide that work is complete, thorough, honest or good, and does not fulfil the line. It checks only that supplied declarations are present and well-formed. No output field says "compliant" or "passed".

## Registry
`CLAUSES` is a fixed tuple of frozen records `id`, `text`, `checkability`, `required_evidence_kinds`.
| id | text | checkability | required evidence kinds |
|---|---|---|---|
| C01 | Bind every line | presence | binding_ref |
| C02 | Do not forget anything | presence | inventory_ref |
| C03 | Do not build thinly | not_checkable_offline | - |
| C04 | Do not fabricate | not_checkable_offline | - |
| C05 | Do not claim completion without evidence | presence | other |
| C06 | Use the user's accounts | not_checkable_offline | - |
| C07 | Conduct real research | not_checkable_offline | - |
| C08 | Test and verify | presence | test_log_ref |
| C09 | Beat benchmarks | not_checkable_offline | - |
| C10 | Produce real discoveries | not_checkable_offline | - |
| C11 | Improve novelty through ChatGPT as judge | not_checkable_offline | - |
| C12 | Self-improve | not_checkable_offline | - |
| C13 | Audit | presence | audit_ref |
| C14 | Then send the candy line | not_checkable_offline | - |
"candy line" is not defined in the material available to this unit; C14 is an opaque clause and nothing about its content is assumed. C06 grants no permission and the module never touches an account.

## API
`check_bindings(items, *, expected_lines=None, max_items=1000, max_evidence=50, max_text=500) -> dict`
- `items`: list of dicts `{"line_ref": str, "clause_id": str, "claim": "complete"|"in_progress"|"not_started", "evidence": [{"kind": str, "ref": str}, ...]}`. `evidence` may be omitted (empty).
- `expected_lines`: optional list of line_ref strings that must each have at least one item.
- Refused with `ValueError` (nothing evaluated): non-list items, more than `max_items` items (exactly `max_items` accepted), non-dict item, missing or non-string or blank `line_ref`/`clause_id`, text longer than `max_text` characters, unknown clause id, claim outside the three values, more than `max_evidence` evidence entries on one item, evidence entry that is not a dict with string `kind` and `ref`, evidence kind outside `EVIDENCE_KINDS` (`binding_ref`, `inventory_ref`, `test_log_ref`, `audit_ref`, `other`), duplicate (line_ref, clause_id), duplicate or non-string expected line, bad bounds. Booleans and non-int values for bounds are refused.
- An evidence entry counts only if its `ref` is non-blank after stripping.

## Item verdicts
- not_checkable_offline clause: `NOT_CHECKABLE_OFFLINE` whatever the claim or evidence. Never counted as bound.
- presence clause, claim `complete`, every required kind present with a non-blank ref: `BOUND`.
- presence clause, claim `complete`, a required kind missing: `MISSING_EVIDENCE`.
- presence clause, claim `in_progress` or `not_started`: `OPEN` (no completion claim is made, evidence is not required).
`BOUND` means only "a well-formed reference of each required kind was supplied".

## Line verdicts (by line_ref, precedence top to bottom)
`UNBOUND` (expected line with no items), `MISSING_EVIDENCE`, `OPEN`, `BOUND_WITH_UNCHECKED` (all presence items bound and at least one not-checkable item), `UNCHECKED_ONLY` (only not-checkable items), `BOUND` (all items bound, none not-checkable).
Lines supplied in items but absent from a given `expected_lines` are listed in `unexpected_lines`, not refused.

## Output
`{"registry_version", "items": [...sorted by (line_ref, clause_id)...], "lines": [...sorted by line_ref...], "unexpected_lines": [...], "counts": {...}, "limits": {...}}`. Output is deterministic and independent of input order. Inputs are not mutated. `limits` has `evidence_truth_verified`, `whole_line_fulfilment_claimed`, `global_enforcement`, `network`, `account_use`, `executes_anything` all false.

## Known gaps
Seven-plus clauses (thin building, fabrication, accounts, research, benchmarks, discoveries, judge loop, self-improvement, candy line) cannot be checked offline and are only reported as such. The evidence-kind mapping per clause is this unit's declared choice, not something the doc line states. Reference strings are not resolved, fetched or hashed. No wiring into any module catalog or dispatcher.
