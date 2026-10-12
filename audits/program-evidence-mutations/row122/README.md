# Row 122 mutation sensitivity

Literal state: PARTIAL. Five core source replacements, with IDs R122-M1..M5.
CAUGHT means pytest exit1 with FAILED test IDs and no collection/setup error.
Timeout/crash/error/inapplicable is not caught. Logs and JSON retain full outcomes.
Every mutated source is restored byte-for-byte and SHA256 compared; restored
baseline must pass. No product implementation changes are included here.

Initial and final outcomes: 5 CAUGHT, 0 SURVIVED, 0 INVALID, 0 NOT-APPLICABLE.

Run from repo root using the trusted test interpreter:
`PYTHONPATH=backend python audits/program-evidence-mutations/runner.py audits/program-evidence-mutations/row122.json`

Evidence tiers: local offline filesystem/Git inspection and local pytest subprocess
checks, plus explicitly injected controlled receipt/error cases in selected tests.
No external dataset-source authenticity, live integration, remote ownership,
semantic acceptance, model quality or whole-program completion is established.
The battery checks assertion sensitivity to these five named faults only; it is
not exhaustive mutation coverage. No benchmark victory or candy release claim.
