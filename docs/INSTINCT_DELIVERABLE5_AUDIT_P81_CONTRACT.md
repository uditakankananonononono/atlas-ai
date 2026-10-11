# Deliverable 5 presence audit (P81|L69) - contract

Source line: "5. Vast amounts of code, tests, verification scripts, and mathematical formulas."

Module: `backend/app/modules/instinct_doc/deliverable5_audit_p81.py`
Tests: `tests/modules/test_deliverable5_audit_p81.py`

## What it does
Takes the result dict of the per-project deliverable checker (the checker is a separate, unmerged unit and is NOT imported here) and reports, for each of code, test, verification_script and formula, one verdict:
- ABSENT: no artifact of that kind was counted by the checker.
- PRESENT_UNCORROBORATED: counted, but the path does not look like that kind.
- PRESENT_CORROBORATED: counted, and the path hint matches, and (if the caller supplied file text whose sha256 equals the artifact's measured sha256) a content marker was found.

It also validates the input (count consistency, known kinds and statuses, no duplicate id or path, every claim field still UNVERIFIED, doc_lines_fulfilled False). Callers may declare minimum counts per category; they are caller-declared, not set here.

## What it does not claim
- It proves only what the checker counted. Category labels are the caller's declarations.
- Path hints and content markers are heuristics (named lists in the module). A file named test_x.py is not shown to hold working tests.
- No threshold for "vast" exists. No vastness, quality, correctness or execution claim is made, and the doc line is never reported as fulfilled.
- Tests are not run, formulas are not checked mathematically.
- The checker whose result it consumes is not landed. Tests declare the consumed schema with hand-written stub data only; no comparison against the real checker has been made. That comparison belongs after the checker is repaired, audited and landed, through the repo integration, not private bytes.
- The checker is Linux-specific (per its own contract); this module is pure and portable.
- A neighbouring requirement-matrix audit unit was not compared.
- No mounted auth or tenant tests, no repo-wide floor run, no wiring (none applied).
- The namespace directory has no `__init__.py` (peer-stated: another builder owns it); the module is loaded by file path.
