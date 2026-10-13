# E8: proof-carrying conclusions (direction 6)

Label: small implementation of the proof-carrying idea (Necula 1997 for code; the checkers and the test fixtures are authored synthetic for this experiment). Source pin: atlas-ai main f7ae6fe7 (new files only), Python 3.12.14, pytest. `pcc.py`, `test_pcc.py`.

A conclusion carries a kind and evidence; `verify` re-runs or re-reads the evidence in a fresh process and returns VERIFIED, UNVERIFIED, or VERIFICATION_IMPOSSIBLE (no checker for that kind). Confidence is stored and returned but never changes the status. Kinds: factorization (certificate checked by multiplication), analysis (script re-run, output hash compared), code_change (tests re-run on the given source; the pytest summary line is parsed exactly and must read only "N passed" with N equal to the expected count, so skipped, failed or extra tests are rejected), sourced_quote (quote must occur in text whose hash matches).

| Claim | Status |
|---|---|
| 9 tests pass: valid evidence accepted; wrong factor, trivial factor, wrong output hash, nonzero exit, broken patch, quote absent, source hash mismatch each rejected; expected count 1 is rejected for an 11-test suite; a suite with a skipped test is rejected; a suite with zero tests (pytest exit 5) is rejected | VERIFIED |
| A confidence of 0.999 on a conclusion with bad evidence still reports UNVERIFIED | VERIFIED |
| An opinion-type conclusion reports VERIFICATION_IMPOSSIBLE with a reason | VERIFIED |
| Coverage is four evidence kinds; no math-proof assistant, no source-fetching, no integration with `improvement_gate` or Claire | UNVERIFIED |
| Progress is measured by externally validated results (no external validator is wired in) | UNVERIFIED |
| Checkers cannot be gamed by a hostile conclusion author (scripts run unsandboxed in a temp dir) | UNVERIFIED |
