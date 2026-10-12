# Guardrail Enforcer - Contract (groups 134-142, single choke point)

Bounded mechanism: `backend/app/runtime/guardrails/enforcer.py`.
`GuardrailEnforcer` holds one hash-chained ledger per gate and exposes the
guarded operations as one surface:

| Operation | Gate | Group |
|---|---|---|
| run_bio_work / admit_bio_work | bio_gate | 134 + 135 |
| dispatch_outbound | outbound_gate | 136 |
| open_review / record_decision / issue_permit / grant_preauthorization / revoke_preauthorization / execute_reviewed | review_gate | 137 |
| emit_text | claim_lint_gate | 138 |
| register_account / verify_account / revoke_account / call_service | owner_account_gate | 139 |
| register_dataset / record_run / record_result / claim_research_done | research_gate | 140 |
| record_tool_use / evaluate_tool_bar / require_tool_bar | tool_usage_bar | 141 |
| emit_report | report_gate | 142 |

## Persistence of refusals

Each gate appends its refusal verdict to its ledger BEFORE raising
`GuardrailRefusal`; the extended ledger rides on the exception and the
enforcer persists it (after re-verifying the chain). A refused attempt is
durable evidence: `audit()` reports per-gate record and refusal counts plus
chain tip hashes.

`dumps()` / `loads()` serialize and restore all eight ledgers with full
chain and content re-verification; edits anywhere break the load.

## Hooks

`approval_check` (bio gate) and `review_check` (outbound gate) are supplied
at construction. Unset hooks fail closed. Wire them to the review gate or
Module 0 for real approval validation; the enforcer never authenticates
references by itself.

## Scope honesty

This layer enforces the guardrails at ITS choke points with firing tests.
It does not rewrite every module's internal paths: adoption by other
runtime surfaces is separate integration work, and each gate's own LIMITS
(lexical scope, caller-attested verification, tamper-evidence) stand.
