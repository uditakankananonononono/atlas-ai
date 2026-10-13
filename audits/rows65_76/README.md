# Rows 65-76 evidence sheets

One README, one spec (`rowNN.json`) and one receipt (`receipts/rowNN.json`) per row, same format as `audits/rows134_142`.
`run1_receipts/` holds every first-run receipt, including the survivors that led to added tests (rows 70, 71, 72, 76).
Run: `python scripts/release/scoped_mutations.py audits/rows65_76/rowNN.json OUT`, sequentially (each run edits source files and restores them; do not run two at once).
An earlier parallel run of rows 70/71/72/76 was discarded and is not in the receipts.
All rows stay PARTIAL. These sheets show scoped behavior of the mapped helpers, not the literal row requirements.
Rows 65-69 and 73-75 were each mutated on one mapped file only; the mapped files not mutated are named in each row's UNTESTED line.
Receipt copies omit the per-file hash map (`tracked_code_test_hashes`) and keep its entry count and SHA-256; the `checkout.head` in each receipt is the pre-squash working commit of the run, not a commit in this history. Mutation outcomes are unchanged.
Final receipts were produced on a fresh empty SQLite database per row (`ATLAS_DATABASE_URL=sqlite:////tmp/x.db`, deleted before each row), so no row depends on database state from neighbors or earlier runs. Totals across receipts/: 61 mutations, 58 CAUGHT, 3 open (row 72: facts_check_dropped, unhumanized_draft_used; row 76: artifact_validation).
