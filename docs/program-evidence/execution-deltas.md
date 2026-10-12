# Execution delta row mapping

| Row | API | Bounded result | Still missing |
|---|---|---|---|
| 126 | inspect_projects | Selected tracked code/test counts and optional executed JUnit | Exhaustive project list, semantic code/test pairing, coverage |
| 127 | compare_selected_tests | Repeated local test timing receipts with cross-subject tree coherence | Same-workload field comparator, leading-tool benchmark evidence |
| 121,131 | audit_selected_checks | Executed selected checks tied to current line hashes | Authenticated original source, semantic line/test correspondence |
| 132 | audit_selected_checks.blockers | Missing/nonpassing check or separate semantic blocker for every line | Exhaustive external dependency and program blocker audit |
| 133 | audit_selected_checks.candy_gate | Release always disabled in this API | Authenticated semantic acceptance channel and complete dependent scope |

All source-to-test and project-to-path selections are operator declarations, not
semantic proof. Passing execution never removes semantic blockers. The disabled
release is intentional because this API accepts no authenticated semantic evidence;
it does not claim to discriminate evidence that it cannot receive. Blockers on a
scoped pass refer to this separate semantic gap, not an executed-test failure.

Validation of request shape precedes any execution. Project/helper exceptions
stay UNVERIFIED. Current hashes and post-run source stability are disclosed.
Aggregate time/disk budgets are NOT enforced, and execution is NOT sandboxed;
only trusted repository code is allowed. Per-run timeout/output limits do not
bound aggregate work or temporary disk writes. Maximum counts remain resource
caps, not a claim of safe execution for arbitrary untrusted inputs.

## Remaining row blockers

- Row129: no authenticated external ChatGPT judge access/transcripts, semantic
  grading definition or before/after novelty improvement evidence supplied.
  Local reports cannot create that evidence. Literal state PARTIAL.
- Row130: per-module plans exist, but no independently accepted module criteria,
  executed improvement coverage or externally checked resulting gains supplied.
  Proposed plans are not executed self-improvement. Literal state PARTIAL.

Acceptance audit retains completed run receipts even if the post-run source read
fails. `source_artifact_sha256` hashes actual local inventory bytes; a manifest's
export hash is separately declared metadata, not authenticated original bytes.
Source drift/read errors suppress scoped promotion while preserving evidence.
