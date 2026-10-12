# Row 125 mutation sensitivity

Literal state: PARTIAL. Five named source operators, with IDs R125-M1..M5.
CAUGHT means pytest exit1 with FAILED test IDs, including product crash failures such as KeyError/RuntimeError;
no ERROR/collection/setup/timeout credit. This is not an assertion-only classifier.
Mixed FAILED plus SKIP is not rejected; counts are failure sensitivity.
Timeout/ERROR/inapplicable is not caught; product crashes reported as FAILED can count. Logs and JSON retain full outcomes.
Every mutated source is restored byte-for-byte and SHA256 compared; restored
baseline must pass. No product implementation changes are included here.

The retained first-run receipts/logs show 5 CAUGHT, 0 SURVIVED, 0 INVALID, 0 NOT-APPLICABLE.
There was no separate final mutation rerun for this row; restored baseline was rerun.

Run from repo root using the trusted test interpreter:
`PYTHONPATH=backend python audits/program-evidence-mutations/runner.py audits/program-evidence-mutations/row125.json`

Evidence tiers: local offline filesystem/Git inspection and local pytest subprocess
checks, plus explicitly injected controlled receipt/error cases in selected tests.
No external dataset-source authenticity, live integration, remote ownership,
semantic acceptance, model quality or whole-program completion is established.
The battery checks test-failure sensitivity to these five named operators only; some operators duplicate source edits across rows; it is
not exhaustive mutation coverage. No benchmark victory or candy release claim.

Across all eight rows,40 counts named operator executions, not40 distinct source faults. Duplicate edit targets are not independent fault classes.
