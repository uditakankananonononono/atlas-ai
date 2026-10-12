# Doc completion evidence sheets, rows 1-15

15 sheets (row-1.md to row-15.md). Snapshot dated 2026-10-13 IST, first built against atlas-ai origin/main 4d2c75de and re-checked for file existence on 41083205: every named path still exists there. Every row is PARTIAL; no row is marked CLOSEABLE. Row 16 has its own sheet in `audits/doc-completion-row16/` and is not repeated here.

Limits:
- Test results for the per-row module lists were NOT run. A listed test file imports the module or names its `.py` file; a common module name can match an unrelated test.
- The one test run mentioned in the sheets (52 passed, 1 skipped on backend/tests_g1_16, 2026-10-13 01:44 IST at 4d2c75de) is builder-reported and not independently verified. It was not re-run on 41083205.
- Request text is the Oct 12 table's paraphrase; the owner doc was not re-read. The Missing cells are that table's and historical; code was not re-read file by file.
- The "Snapshot update" sections name the groups 1-16 verifier on main (`program_evidence_g1_16.py`, `resolved_registers_g1_16.py`, `backend/tests_g1_16`). Relations of its functions to rows come from function names only, not from any mapping the module states. The verifier's own docstring says it does not verify provenance, scientific validity or authenticity, and these sheets do not either.
- The crosswalk map says rows 1-16 come from a bulk enumeration with no per-row closure evidence; these sheets do not change that.

| row | named paths found | named paths absent | referencing test files |
|---|---|---|---|
| 1 | 1 | 0 | 1 |
| 2 | 1 | 0 | 2 |
| 3 | 1 | 0 | 2 |
| 4 | 1 | 0 | 2 |
| 5 | 1 | 0 | 1 |
| 6 | 1 | 0 | 2 |
| 7 | 1 | 0 | 1 |
| 8 | 1 | 0 | 2 |
| 9 | 1 | 0 | 1 |
| 10 | 1 | 0 | 2 |
| 11 | 1 | 0 | 1 |
| 12 | 2 | 0 | 21 |
| 13 | 1 | 0 | 2 |
| 14 | 1 | 0 | 1 |
| 15 | 1 | 0 | 2 |
