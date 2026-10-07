# Local-tool comparison

Our local_tools.py is absent from peer commit b944215353d8d641cb476cf3ffba8075072840da in the transferred full-history recon-482 bundle. This is an additive local surface, not method-level peer parity. Preserve the existing implementation; there is no peer counterpart to import.

Static review: registered handlers are offline computations on supplied arguments. Catalog: rule_check, require_value, temporal_check, csv_filter, csv_reconcile, csv_summary. All are READ-risk, one handler attempt, object schemas with additionalProperties false. Output labels separate supplied computations from source verification and approval. CSV handlers enforce bytes/row/group/key/finite-number bounds. Rule/temporal handlers use their bounded local solvers. No source truth or effect permission is granted by these outputs.

Selected runtime tests: 27 passed, 180 deselected. Solver suite separately: 22 passed (some overlap with the selected run; do not add those counts as unique tests). New catalog canary: 1 passed. No product code change required. This is a bounded additive-surface assessment, not independent provenance verification of supplied inputs or production clearance.

Source provenance: offline bundle atlas-recon482-full-hz28-b944215353.bundle, SHA256 700a76e3f66f83c433f437a77ec1e7d745245175cd71b0f1a9ea3680bbc18b8b; refs/heads/recon-482 points to b944215353d8d641cb476cf3ffba8075072840da. No verified peer GitHub repository URL was supplied. It is not a ref fetched from our origin.
