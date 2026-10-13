# Fresh replay follow-up: driver behavior and evidence boundaries

This follow-up changes tests and documentation only. The waiver runtime, driver
and shared runner are unchanged. Original missing historical logs remain a
permanent provenance gap; no historical execution or final-tree proof is recovered.

## Driver versus shared runner

The original single driver test uses a stub and proves parent creation and
no-overwrite wiring only, not shared classification. Parent mkdir is redundant
with the shared runner's parents=True creation, but remains harmless driver setup.
The six new parametrized driver tests copy the unchanged real driver and shared
runner into an inert git fixture and execute real child pytest. They verify:
assertion failure CAUGHT/exit 0; product RuntimeError CAUGHT/exit 0; surviving
mutation exit 1; FAILED plus SKIP INVALID/exit 1; missing site INVALID-SITE/exit 1;
and failed baseline with zero mutations/exit 1. Receipts equal CLI JSON, source
bytes restore exactly, and repeated output is refused without receipt overwrite.
These are local runner mechanics, not waiver behavior or external effects.

## 158 versus 159

The two original/current replay baselines use only test_c35_waiver_drafts_s43.py
and test_c35_waiver_drafts_s43_delta.py: 132 + 26 = 158 cases. The retained r2
release JUnit has those same counts plus the single original stub-driver case,
for 159 with no failures/errors/skips. verification.json binds its SHA256 and
names the extra case. Fresh pre-edit execution on 2f89b9fe independently passed
that same three-file selector: 159 passed. The new six real-driver cases bring
the three-file selector to 165; they do not retroactively change the old totals.

## What a runtime failure means

CAUGHT is failed-test sensitivity, not an assertion-only or exception-kind
validity judgment. The current year_minimum_offbyone mutant rejects year 1,
and test_year_one_accepted fails with ValueError: APPLY_REFUSED_BAD_TYPE:as_of.
That is a specific contract regression on a previously admitted boundary,
not a crash-without-tests. The other current-site failures are assertion failures
or missing expected ValueError refusals. Six named operators do not prove all
mutants meaningful or certify arbitrary runtime-exception kills. Collection,
process failures without qualifying FAILED IDs, FAILED plus SKIP, and timeout
are not CAUGHT. These trusted local tests are not hostile-process isolation;
direct-child timeout does not contain escaped descendants.

## Normalization

There are 12 delivered log pairs and 94 changed lines TOTAL across them, not
94 per log. The original private fresh-run bytes remain available locally;
this follow-up rechecks every original/delivered SHA256, every changed-line
mapping, and the exact declared root substitutions plus trailing-whitespace
normalization. verification.json records pair hashes and line counts. This
resolves local substitution verification only: private originals are not
redistributed and a peer without them cannot independently check substitutions.
No existing log, receipt or normalization mapping is edited.

Full composed selector (Python 3.12, plugin autoload disabled, noconftest,
PYTHONPATH=backend, ATLAS_DEV_NO_AUTH=1, ATLAS_ENV=development): the two waiver
files, driver file, tests/release/test_scoped_mutations.py, m12 education helper
hardening, m06 publish guardrail and m06 scheduler. Fresh result: 238 passed,
0 failed/error/skipped. Logs and case inventories accompany the review package.
All broad/literal groups remain PARTIAL. No provider, account, send or approval
truth is established. The education edit only renames a registry-key test;
it does not build the parked Class 11 application or any science research lane.
