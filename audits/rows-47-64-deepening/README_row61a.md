# Row 61 (part a) mutation deepening: m06 social_reading reader

Scope literal: test hardening only; row 61 stays PARTIAL. PART A ONLY: `m21_claire/social_signal_review.py` (the second
module named for row 61) is NOT covered. No production change. No platform access: browser pages, the paired-PC bridge and
the store are fakes. Uses the harness `run_mutations.py` from batch A.

## Reproduce
- Tests: `ATLAS_DEV_NO_AUTH=1 ATLAS_ENV=development python3 -m pytest tests/modules/test_m06_social_reading.py tests/modules/test_m06_reader_deepening.py -q`
- Battery: `ATLAS_DEV_NO_AUTH=1 ATLAS_ENV=development python3 audits/rows-47-64-deepening/run_mutations.py b61`
  (writes `receipts_b61.txt`; mutants in `batteries/b61.py`, exact old/new text on `reader.py`). CAUGHT only on pytest rc 1
  with FAILED lines; rc 0 SURVIVED; otherwise INVALID; SHA-256 restore check on the mutated file.

## Results
- Final run: 22 mutants S1-S22, CAUGHT=22, SURVIVED=0, INVALID=0, SHA restore True. They cover the paired-session and
  platform gates, blocked versus failed run states, LinkedIn limits and unknown operation, the Pinterest status, 429,
  host, login-path, captcha, login-form and operation checks, the Pinterest limit validation, honest provenance flags
  (`author_verified` False, `continuous_monitoring_configured` False), empty-feed status, Instagram username,
  relation and truncation, and naive-timestamp handling.
- First run (existing m06 tests only): CAUGHT=2, SURVIVED=20. Preserved as `receipts_b61_run1_existing_tests_only.txt`.
- New tests: `tests/modules/test_m06_reader_deepening.py` (13 tests).

## Limits: what stays untested
- `test_instinct_doc_56_66_runtime.py`, which holds the older Pinterest block tests, does NOT collect on this Python 3.10
  sandbox, so it is not in this battery. The new file re-covers the Pinterest block paths with its own fakes.
- `social_signal_review.py` is not mutated here; its test file also does not collect on 3.10 and would need standalone
  tests first. The parsers, the knowledge store and idea_feed are not mutated.
- Everything is fakes: no real LinkedIn, Instagram or Pinterest page, session, daemon or login was used, so nothing here
  shows continuous scanning or intelligent action on real feeds. The row's "act intelligently" part is not tested.
- A green run shows the tests notice these 22 edits, not that social reading works against the live platforms.
- Receipts are recorded local harness runs, not independently re-run.
