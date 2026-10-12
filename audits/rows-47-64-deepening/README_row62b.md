# Row 62 (part b) mutation deepening: c37 patents (claim-draft helper)

Scope literal: test hardening only; row 62 stays PARTIAL. Part b of row 62 (part a covers c32 dossier and c31
replicate_plan). The helper drafts claim text from SUPPLIED records, labeled "DRAFT NOT FOR FILING". It does no prior-art
search, novelty scoring, ownership check or filing. No production change, no network. Uses the harness
`run_mutations.py` from batch A.

## Reproduce
- Tests: `ATLAS_DEV_NO_AUTH=1 ATLAS_ENV=development python3 -m pytest tests/modules/test_c37_patents_v2.py tests/modules/test_c37_patents_text_deepening.py -q`
- Battery: `ATLAS_DEV_NO_AUTH=1 ATLAS_ENV=development python3 audits/rows-47-64-deepening/run_mutations.py b62b`
  (writes `receipts_b62b.txt`; mutants in `batteries/b62b.py`). CAUGHT only on pytest rc 1 with FAILED lines; rc 0
  SURVIVED; otherwise INVALID; SHA-256 restore check.

## Results
- Final run: 16 mutants T1-T16, CAUGHT=16, SURVIVED=0, INVALID=0, SHA restore True. They cover the owner check, draft
  label, claim body and dependent-claim numbering and wording, https-only prior-art URLs, duplicate prior-art ids, the
  novelty source, range and rounding, calendar-invalid dates, control and blank text, the unverified owner assertion,
  hostless URLs and the prior-art cap.
- First run (existing v2 tests only): CAUGHT=14, SURVIVED=2 (T12 control characters allowed in text, T14 whitespace-only
  text allowed). Preserved as `receipts_b62b_run1_with_2_survivors.txt`. Both were killed by new tests that refuse blank
  and control/format/line-separator text in id, title and summary, so they are not equivalent mutants.
- New tests: `tests/modules/test_c37_patents_text_deepening.py` (22 cases, including direct `_unicode_text` checks).

## Limits: what stays untested
- `tests/venture_v2/*` does not collect on this Python 3.10 sandbox and is not part of this battery; only
  `test_c37_patents_v2.py` (which passes here) is.
- Preflight shape caps (node count, depth, key length) and the forbidden-key scans (send, spend, file, credentials) are
  not individually mutated here.
- Nothing here shows the drafted claims are legally sufficient, novel or fileable.
- A green run shows the tests notice these 16 edits, not that the helper is correct or complete.
- Receipts are recorded local harness runs, not independently re-run.
