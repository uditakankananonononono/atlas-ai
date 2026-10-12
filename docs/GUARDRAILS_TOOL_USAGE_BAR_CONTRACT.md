# Per-Project Verified Tool-Use Bar - Contract (groups 141 + 3 + 4, line 1
vs lines 67-68)

Bounded mechanism: `backend/app/runtime/guardrails/tool_usage_bar.py`. The
source doc contradicts itself (200+ tools EACH project vs 40+ per project
and 200+ program-wide). This gate implements evidence for the STRICTEST
reading so either ruling lands without rework: `DEFAULT_BAR = 200`,
`ALTERNATIVE_BAR = 40`, and every function takes `bar` as a parameter.
Nothing is silently reduced.

## Rule

- `record_use(ledger, project_id, tool, used_at=..., evidence_ref=...,
  verified_by=...)`: a use counts only with BOTH an evidence reference and a
  recorded verifier (fail closed).
- `verified_tools` counts DISTINCT verified tools per project; recording the
  same tool twice never inflates it.
- `evaluate(ledger, project_id, bar=200, now=...)` ledgers a `bar_evaluated`
  record with the count, the bar, the verdict (`met`/`unmet`) and the exact
  shortfall. An unmet evaluation is truthful evidence, not an error.
- `require_bar(...)` is the enforcement point: below the bar it raises
  `GuardrailRefusal("TOOLBAR:bar_unmet")` with the exact shortfall, after
  ledgering the unmet evaluation.

## Limits (named, none hidden)

- Verification is caller-attested; the gate cannot execute the tools.
- Counts say nothing about how well any tool was used.
- The bar counts distinct verified tools per project; the program-wide 200+
  reading is the sum over projects and needs no separate mechanism.
- The ledger is an unkeyed hash chain: tamper-evident, not tamper-proof. A rehashed edit is not detectable; safe storage of the serialized ledger is the caller's job.
