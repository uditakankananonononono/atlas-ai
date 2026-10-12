# Row 122 mutation sensitivity

Literal state: PARTIAL. Five named source operators, with IDs R122-M1..M5.
CAUGHT means pytest exit1 with FAILED test IDs, including product crash failures;
no ERROR/collection/setup/timeout credit. This is not an assertion-only classifier.
Timeout/ERROR/inapplicable is not caught; product crashes reported as FAILED can count. Logs and JSON retain full outcomes.
Every mutated source is restored byte-for-byte and SHA256 compared; restored
baseline must pass. No product implementation changes are included here.

The retained first-run receipts/logs show 5 CAUGHT, 0 SURVIVED, 0 INVALID, 0 NOT-APPLICABLE.
There was no separate final mutation rerun for this row; restored baseline was rerun.

Run from repo root using the trusted test interpreter:
`PYTHONPATH=backend python audits/program-evidence-mutations/runner.py audits/program-evidence-mutations/row122.json`

Evidence tiers: local offline filesystem/Git inspection and local pytest subprocess
checks, plus explicitly injected controlled receipt/error cases in selected tests.
No external dataset-source authenticity, live integration, remote ownership,
semantic acceptance, model quality or whole-program completion is established.
The battery checks test-failure sensitivity to these five named operators only; some operators duplicate source edits across rows; it is
not exhaustive mutation coverage. No benchmark victory or candy release claim.

R122-M2 is a crash-discriminating kill (KeyError for an untracked selected file), not proof of the intended explicit refusal behavior. The original test passes by expecting refusal on the unmutated product; mutant failure includes the wrong exception type.

Across all eight rows,40 counts named operator executions, not40 distinct source faults. Duplicate edit targets are not independent fault classes.
