# Row122 task-history sensitivity follow-up

Base29d951f0. Five named operator executions, not exhaustive/distinct-fault
coverage. No product implementation diff. Existing historical row122 receipt
and KeyError crash-discriminating caveat remain unchanged. This separate battery
covers shallow disclosure, root/boundary labeling, timestamp retention, history
truncation disclosure and completion nonpromotion. Literal group stays PARTIAL.

The added test creates a real local Git file:// depth-one clone; no public remote
fetch or remote ownership proof. Existing tests also use real temporary Git/file
state. Shallow boundary and commit timestamps are disclosed, not authenticated
task-time anchors or semantic task completion. No budget/sandbox/race guarantee.

Recorded baseline and restored baseline:11 passed each. Five mutants caught by
rc1 plus FAILED IDs, including product exceptions if present; not assertion-only.
ERROR-space/ERROR-at and timeout not credited; mixed FAILED+SKIP not rejected.
This does not rerun or replace the historical row122 five-operator battery.

Replay from a trusted repository root with the selected interpreter:
`python audits/program-evidence-mutations/task-history/replay.py`.
Do not use on untrusted repositories. Original raw logs retained privately;
delivered logs intentionally strip trailing whitespace and replace private paths
if listed. receipt.json records every changed line/path pair and original plus
delivered SHA256 for every log. Command interpreter is normalized to python;
no claim that this is the original absolute command. Local receipt-bound outcomes
are not independent acceptance or universal restoration guarantees.

## Delivered log provenance

- baseline.log: original `9e6ab3c6054abf0e7b92bcd34f7b6ee42528e1ac7dca0236ab2f8fa33885fced`; delivered `9e6ab3c6054abf0e7b92bcd34f7b6ee42528e1ac7dca0236ab2f8fa33885fced`. Changes: none.
- H122-M1.log: original `c4a4d1faa4e982da14f7da6f44720cfb6831ec7cc3d24480a8b60400c47055fb`; delivered `c4a4d1faa4e982da14f7da6f44720cfb6831ec7cc3d24480a8b60400c47055fb`. Changes: none.
- H122-M2.log: original `a23d01c3eaf28c0d82a9ce64820488ee7df709da03b067299d01802f25fbe128`; delivered `a23d01c3eaf28c0d82a9ce64820488ee7df709da03b067299d01802f25fbe128`. Changes: none.
- H122-M3.log: original `addbc716ccb23c611bc384b42c581b016deeacd89b91c9fa8639b3acb80577eb`; delivered `addbc716ccb23c611bc384b42c581b016deeacd89b91c9fa8639b3acb80577eb`. Changes: none.
- H122-M4.log: original `0e2848c12a0d43ca3115a237018fcc241a52948aae03be7042489ae9c3b4728a`; delivered `0e2848c12a0d43ca3115a237018fcc241a52948aae03be7042489ae9c3b4728a`. Changes: none.
- H122-M5.log: original `03459a062566a0bfce6c3f7aae3ca6adeafd0930757441b2fa858b8e1b3609c2`; delivered `03459a062566a0bfce6c3f7aae3ca6adeafd0930757441b2fa858b8e1b3609c2`. Changes: none.
- restored-baseline.log: original `a19a7ef5b8709585198e3a47d163ea7b74e4da482d0a00e9e8c0ddae64130ba4`; delivered `a19a7ef5b8709585198e3a47d163ea7b74e4da482d0a00e9e8c0ddae64130ba4`. Changes: none.

## LAND-113 chronology and selector reconciliation

29d951f0 is the original run HEAD, not the landing base. LAND-113 was composed
on a9cc5d54 and landed at a27d352f. Historical receipts retain their original
identity; they are not relabeled as a fresh mutation run on the landing tree.
The new test and replay were untracked at original run HEAD, so that Git object
cannot retrospectively bind their executed bytes. The original receipt did not
hash test files or the checkout tree; this provenance gap is not backfilled.
`reconciliation/record.json` records local Git HEAD/tree and selected file hashes
for the historical run HEAD, compose base, landed tip and current 27511b4a.
Missing files are recorded as null, not guessed. Matching selected file bytes
do not prove full dependency/environment equivalence or historical authorship.

The full selector is tests/test_task_progress_evidence.py plus
tests/test_task_history_sensitivity.py (11 tests). A new-file-only
selector tests/test_task_history_sensitivity.py contains one test (1 test). Those
counts refer to different selectors, not conflicting totals. A fresh full-selector
log on 27511b4a is retained under reconciliation/; no mutation battery was rerun
for this docs-only clarification. Its original/delivered SHA and every normalized
line are recorded in record.json; raw original bytes remain private.

Only H122-M1 gains a unique new kill from the depth-one-clone test. H122-M2..M5
were already killed by pre-existing tests; the new test adds shallow-context
assertions, not four newly discovered faults. M4 removes the whole truncation
expression, not isolated shallow versus limit branches. Timestamp is pinned only
as present, not exact value/format. No deeper shallow history, grafted merge,
public remote or authenticated task-time acceptance follows.

An initial hash-pair mismatch report was a comparison error, disproved
by direct reads. All seven historical original/delivered pairs remain equal with
no listed normalizations; no retained mismatch was found or silently repaired.
