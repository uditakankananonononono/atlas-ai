# Atlas rebuild status - October 7, 2026

Not complete. No full-spec completion claim is supported.

## Independent audit snapshots at main 313309b

These counts use different tests and must not be merged or rounded up:

- 2,006-row audit: VERIFIED 0, SCOPED 1,556, PARTIAL 230, OVERSTATED 220. No row behavior was reproduced individually. Many labels came from AST scanning or file-level inference.
- 2,009-row register audit: VERIFIED 771, SCOPED 1,027, PARTIAL 178, OVERSTATED 33. VERIFIED here means mechanically located row computation with passing tests, plus approximately 15 close reads. It is not a manual source read of every row.
- Missing is not a verdict in these audits. A complete missing-feature count is unknown.

The old `verified-pushed` ledger is historical builder attribution, not current verification. Existing paths, row numbers in source, canned invariants and passing constant-assert tests do not prove features work. Its original claims remain available for comparison.

## First repair, M20 and certification surfaces

- Three legacy semantic reports now return unverified, never pass based on file/path/text checks. Their 862 inventory rows are not certified. Artifact checks remain separate.
- Row 823's static metacognitive-loop strings were replaced with measured strategy calibration. Actual scored attempts produce per-attempt and per-strategy Brier loss, signed overconfidence and an evidence-linked observed strategy comparison. Empty/unscored/nonfinite/duplicate inputs fail. Ties do not invent a winner.
- Scope: descriptive calibration of caller-supplied observations. Not causal strategy evaluation, autonomous self-awareness or full metacognition. The full original row 823 remains PARTIAL.
- No models loaded, no paid API or keys used, no deployment attempted in this repair.
- Focused run: 379 passed. M20 suite: 1,448 passed, 1 failed. The failure is `test_full_loop_pauses_for_external_approval`: a dependent send remains PENDING after a completed read instead of becoming WAITING_APPROVAL. Reproduced in isolation. This path was not changed by the calibration repair. Full suite and independent audit of the new code are still outstanding.

## Remaining work

M20 is still open. Next: inspect all its overstated row branches against the source requirement, build real computations and execution paths, then request independent review. Later units follow the tier-ordered worklist. Other major gaps include absent model-backed cognition, research-method constants, unmounted research-method routes and production infrastructure.
