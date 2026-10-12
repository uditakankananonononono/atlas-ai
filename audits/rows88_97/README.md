# Scoped row mutation receipts

Run from a trusted repository root with Python 3.12. This is not a sandbox.
Each row specification names an exact released selector, single-site textual
mutations, per-run timeout and UNTESTED limits. Harness counts CAUGHT only when
pytest rc=1 includes FAILED test IDs and no collection/error failure. Skips,
timeouts, crashes, missing sites and surviving tests are not kills. Source bytes
are restored in finally and each restore checked against its pre-run SHA256.
Output directories must be new. Exact logs and external JSON receipts bind
spec/log hashes and failed test IDs. No model downloads are intended.

```sh
python scripts/release/scoped_mutations.py audits/rows88_97/row90.json OUT
```

The harness sets PYTHONPATH=backend and local development-auth test fixture
values; production defaults are unchanged. Timeout bounds the direct pytest
process, not escaped descendants. Whole-repository regressions, external
provider effects, semantic quality and unlisted mutation sites remain UNTESTED.
Broad literal groups stay PARTIAL; killed core mutations are scoped sensitivity
checks, not proof of universal correctness.
