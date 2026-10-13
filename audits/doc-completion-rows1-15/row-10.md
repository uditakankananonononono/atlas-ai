# Row 10 evidence sheet

Snapshot: atlas-ai origin/main 4d2c75de, checked 2026-10-13 IST. Sources: the Oct 12 audit table (historical, pinned 4163f497) and the crosswalk disposition map 20261013. Neither is the owner doc text.

## (b) Literal request, as the audit table words it

ChatGPT judge loop improving novelty, rigor and benchmark performance

Doc source line refs in the table: 74,1,155. The owner doc was not re-read for this sheet; the line above is the table's paraphrase.

## (a) Existing files and tests

- present: `backend/app/validation/judges.py` (211 lines): judge packet construction, provider adapters, verdict parsing and receipts. This is where the judge wiring lives.
- test file that names the module (filename/import match only; results not run for this sheet): 1
  - `tests/modules/test_validation_judges_g115.py`
- Pointer correction: this sheet first cited `backend/app/modules/c30/worldclass.py`, copied from the Oct 12 table. That file is a supplied-numbers benchmark board with no judge logic (0 occurrences of "judge"); it belongs to rows 8 and 15, not here.

## Snapshot update: groups 1-16 program evidence on main

Main also carries a groups 1-16 evidence layer that the historical table cell does not name: `backend/app/modules/instinct_doc/program_evidence_g1_16.py` (480 lines), `backend/app/modules/instinct_doc/resolved_registers_g1_16.py` (74 lines) and tests under `backend/tests_g1_16/`. The module docstrings say the verifier checks repo existence, dataset hash integrity and repeatable command output under a caller-supplied allowlist, and does NOT verify provenance, scientific validity or authenticity; leader values, dataset origin labels and judge identities remain caller claims.
Function(s) in that module whose names relate to this row, by my reading of the names only (the module does not state a row mapping): check_judge.
Running `python3 -m pytest --noconftest -q backend/tests_g1_16` at this snapshot gave 52 passed, 1 skipped (builder-reported run, 2026-10-13 01:44 IST, my sandbox, not independently verified).

## Crosswalk state

- state: CLOSED-SCOPED
- evidence ids: GATE-20261012-228 (map update); 21:53 enumeration
- note: doc group PARTIAL; literal rows PARTIAL. NOTE 01:02: bulk-enumeration source (21:53 + GATE-228), no per-row closure evidence in this lane - same source class as the 41-46 sweep; verifier-lane confirmation recommended

## (c) Verdict

**PARTIAL.**

Missing scope from the Oct 12 audit table (HISTORICAL; code was not re-read file by file for this sheet): No program-wide actual judge transcripts and measured resulting improvements established by this audit.

CLOSEABLE delta: none proposed. This process has not established literal acceptance for this row. This sheet makes no completion claim.
