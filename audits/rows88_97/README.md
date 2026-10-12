# Scoped row mutation receipts

Run from a trusted repository root with Python 3.12. This is not a sandbox.
Each row specification names an exact released selector, single-site textual
mutations, per-run timeout and UNTESTED limits. Harness counts CAUGHT only when
pytest rc=1 includes FAILED test IDs and no matched ERROR/collection,
Interrupted or skip marker. Mixed FAILED plus SKIP is INVALID, not CAUGHT.
FAILED includes product KeyError/RuntimeError, not just assertion failures.
rc0 with a skipped-count summary is SURVIVED-WITH-SKIPS and does not release
the baseline. Timeouts, process failures without qualifying rc1/FAILED evidence,
missing sites and surviving tests are not kills. Source bytes
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

Mixed FAILED plus SKIP outcomes are INVALID, not CAUGHT. FAILED means a pytest
failed-test outcome, which may include runtime exceptions within a test; this
is not an assertion-only kill classifier. Current receipts additionally retain
HEAD/tree/status and hashes of tracked code/test/spec files. These are local
checkout identities, not proof that all dependencies or external state match.

`evidence/row*-historical-receipts.json` publishes portable historical local
summaries, including initial survivor provenance for attachment (97), scaler
fit (95) and timeout forwarding (94). Exact raw logs/executable were supplied
in the private release archive. Historical results are not rerun-current
claims. Fresh follow-up logs/receipts are supplied separately. Row90 now pins
nonempty record/conflict counts; row96 pins exact intended refusal diagnostics.

## Receipt generation and split selectors

Every historical entry now names its generation and phase. The last entries
are the original rows88-97 final-composition batteries, not later follow-up
batteries. Corrected-per-row entries remain separate from initial survivors.
These labels were recovered by matching spec hashes and exact baseline seconds
to retained receipts. No checkout or test hashes were retrofitted. Later fresh
follow-up evidence is separate and is not inferred from these last entries.

Row94's duration pin landed in commit
`3964e8af3dbd0569d2be559ba1a51e8f578271eb`, in
`test_hanging_source_fails_and_blocks_downstream` in
`tests/modules/test_group94_isolated_workforce.py`. The added assertion is
`assert all(r['duration_seconds'] < 2.5 for r in receipts)`.
Its test name need not change for its body to become sensitive to timeout
forwarding. The historical receipts do not bind that test's bytes themselves.

`evidence/distinct-split-selector-receipt.json` records a fresh eleven-file
selection on the named base, before these new test additions: 49 passed in
7.75s. Its file set has empty intersection with the sixteen historical retro
files. The app-planner 49 is inside the historical retro1059; it is not this
split49. The two version-scoped runs are not a same-tree combined1108 run.
The single27-file and interrupted combined attempts remain uncredited.
The new two parametrized harness cases increase the current split selection
from49 to51, not an additive floor.

`evidence/row95-equal-log-comparison.json` records an exact retained-byte
comparison: corrected-per-row and final-composition scaling_scope logs both
end with `1 failed, 1 passed in 2.92s`. Their separately measured monotonic
runner durations differ. Equal rounded pytest durations and deterministic
failure text explain byte equality, but byte equality alone proves neither
independent execution nor repeated execution.

The end-to-end harness fixture runs actual pytest with a passing baseline,
then a failing mutant with either a passing companion or a skipped companion.
The latter must produce INVALID despite a FAILED test ID and must restore
source bytes. It also checks persisted HEAD/tree/status and exact tracked
source/test/spec hashes. Status records the untracked output directory;
recorded identity is not a cleanliness gate or environment attestation.
