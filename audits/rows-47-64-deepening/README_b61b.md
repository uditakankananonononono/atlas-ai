# Row 61 part b: m21_claire/social_signal_review.py mutation deepening

Scope: `review_signals` only. Part a (m06 reader.py) is a separate patch.

The existing test file for this module does not collect on Python 3.10 (the package import chain needs StrEnum).
New file `tests/modules/test_m21_social_signal_review_standalone.py` loads the module by path and uses a fake store, so no platform or network is touched.

Battery: `batteries/b61b.py`, 16 mutants (V1-V16): validation bounds, since handling, scan window, limit, score threshold, missing score, https/userinfo/host checks, excerpt cap, contacted flag, status label, external_effects.
Result: 16 CAUGHT, 0 SURVIVED, 0 INVALID; source SHA restored. Receipt: `receipts_b61b.txt`.
CAUGHT = pytest exits 1 with FAILED lines.

Not covered: the old test file still cannot be collected on 3.10 and was not run; the store's own filtering is not exercised (fake store).
Run: `python audits/rows-47-64-deepening/run_mutations.py b61b`
