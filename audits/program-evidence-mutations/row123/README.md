# Row 123 mutation sensitivity

Literal state: PARTIAL. Five named source operators, with IDs R123-M1..M5.
CAUGHT means pytest exit1 with FAILED test IDs, including product crash failures;
no ERROR/collection/setup/timeout credit. This is not an assertion-only classifier.
Timeout/ERROR/inapplicable is not caught; product crashes reported as FAILED can count. Logs and JSON retain full outcomes.
Every mutated source is restored byte-for-byte and SHA256 compared; restored
baseline must pass. No product implementation changes are included here.

Initial receipt: 4 CAUGHT, 1 SURVIVED. Original logs retained under initial/. A dedicated sensitivity assertion was added and the same five source mutants rerun: 5 CAUGHT. This does not rewrite the first outcome.

Run from repo root using the trusted test interpreter:
`PYTHONPATH=backend python audits/program-evidence-mutations/runner.py audits/program-evidence-mutations/row123.json`

Evidence tiers: local offline filesystem/Git inspection and local pytest subprocess
checks, plus explicitly injected controlled receipt/error cases in selected tests.
No external dataset-source authenticity, live integration, remote ownership,
semantic acceptance, model quality or whole-program completion is established.
The battery checks test-failure sensitivity to these five named operators only; some operators duplicate source edits across rows; it is
not exhaustive mutation coverage. No benchmark victory or candy release claim.

Across all eight rows,40 counts named operator executions, not40 distinct source faults. Duplicate edit targets are not independent fault classes.
