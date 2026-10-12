# Row 123 mutation sensitivity

Literal state: PARTIAL. Five core source replacements, with IDs R123-M1..M5.
CAUGHT means pytest exit1 with FAILED test IDs and no collection/setup error.
Timeout/crash/error/inapplicable is not caught. Logs and JSON retain full outcomes.
Every mutated source is restored byte-for-byte and SHA256 compared; restored
baseline must pass. No product implementation changes are included here.

Initial receipt: 4 CAUGHT, 1 SURVIVED. Original logs retained under initial/. A dedicated sensitivity assertion was added and the same five source mutants rerun: 5 CAUGHT. This does not rewrite the first outcome.

Run from repo root using the trusted test interpreter:
`PYTHONPATH=backend python audits/program-evidence-mutations/runner.py audits/program-evidence-mutations/row123.json`

Evidence tiers: local offline filesystem/Git inspection and local pytest subprocess
checks, plus explicitly injected controlled receipt/error cases in selected tests.
No external dataset-source authenticity, live integration, remote ownership,
semantic acceptance, model quality or whole-program completion is established.
The battery checks assertion sensitivity to these five named faults only; it is
not exhaustive mutation coverage. No benchmark victory or candy release claim.
