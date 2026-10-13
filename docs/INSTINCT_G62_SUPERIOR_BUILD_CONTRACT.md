# Group 62 superior-build acceptance pipeline contract

Source request (instinct doc, group 62, paragraphs 53/135/214/222): research
successful people, startups, ventures and patents; build better versions.

## What is built (real runtime behavior)

`backend/app/modules/instinct_doc/superior_build_g62.py` closes the gap the
landed units (c32.dossier, c31.replicate_plan, c37.patents) left: those stop
at dossiers, ticket lists and claim drafts over supplied records. This
module adds the research-to-superior-build acceptance stage:

- gap analysis per subject: reference capabilities absent from the build,
  per-metric comparison against supplied reference measurements
- "better versions" made measurable: every supplied numeric reference metric
  becomes a strict superiority target (higher-is-better by default,
  lower-is-better per metric; optional margin from 1x to 10x - margins below
  1 are refused because they manufacture superiority or overflow the derived
  target; at margin 1.0 a tie is NOT superior; derived targets are checked
  finite)
- acceptance-tests-first build tickets for every gap: capability gaps,
  metric gaps (naming the exact measurable bar), and evidence gaps when a
  build metric was never measured
- an honest verdict per subject: SUPERIOR / NOT_SUPERIOR /
  INCOMPLETE_EVIDENCE (missing build measurements are never silently
  counted as failure or as success, and capability-only presence is never
  SUPERIOR - at least one beaten numeric metric is required)
- a task-bound verification receipt: verify() trusts nothing in the result,
  validates the exact result envelope (no extra or missing top-level
  fields), and recomputes capability sets, per-metric targets and verdicts,
  subject verdicts, the ticket list, margin and every count from the
  original task inputs; run() flips status to verification_failed on any
  mismatch. Honest limit: verify() shares validation and ticket-format
  helpers with analyze(), so the receipt proves internal consistency
  between task and result - it is not an independent measurement of the
  build.

Bounds and refusals: at most 64 subjects, 256 capabilities and 256 metrics
per side; metrics must be non-negative, finite, <= 10**18 (booleans,
NaN/inf, negatives and unknown keys are refused); names pass the shared c30
text hygiene guard.

## Verification

27 hermetic stdlib-unittest tests in
`tests/modules/test_group62_superior_build.py`: happy path, missing
capability/metric/evidence semantics, tie-is-not-superior, margin scaling,
lower-is-better, zero-reference edge, determinism, every refusal class, and
tamper cases proving the receipt rejects edited verdicts, targets,
actuals, tickets, counts, margins and unknown envelope fields - including
a full leaf-tamper sweep over every scalar in a result (0 survivors). All
green.

## What is NOT achieved (named missing scope)

- No live research or fetching of any kind: dossiers, capability records,
  patent data and reference metrics are caller-supplied. The "research"
  half of the request remains unbuilt.
- The builds the tickets describe are not executed here.
- Superiority is judged only on supplied numeric metrics plus capability
  presence; qualitative axes, weighting across metrics and negative-valued
  metrics are out of scope.
- Library surface only: no HTTP route, no UI.

Verdict for group 62 remains PARTIAL.
