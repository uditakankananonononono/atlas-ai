# Guardrail Enforcer - Contract (groups 134-142, facade over the gate choke points)

Bounded mechanism: `backend/app/runtime/guardrails/enforcer.py`.
`GuardrailEnforcer` holds one hash-chained ledger per gate and exposes the
guarded operations as one surface:

| Operation | Gate | Group |
|---|---|---|
| run_bio_work / admit_bio_work | bio_gate | 134 + 135 |
| dispatch_outbound | outbound_gate | 136 (send/post/submit/invite/account/payment kinds also require validated owner effect authority) |
| open_review / record_decision / issue_permit / grant_preauthorization / revoke_preauthorization / execute_reviewed | review_gate | 137 |
| emit_text | claim_lint_gate | 138 |
| register_account / verify_account / revoke_account / call_service | owner_account_gate | 139 |
| register_dataset / record_run / record_result / claim_research_done | research_gate | 140 |
| record_tool_use / evaluate_tool_bar / require_tool_bar | tool_usage_bar | 141 |
| emit_report | report_gate | 142 |

## Write-ahead persistence

Each gate commits its admission/spend record to the enforcer BEFORE the
guarded effect runs (`on_commit` write-ahead), and the record is retained
on ANY exception the effect raises - not only `GuardrailRefusal`. An effect
that raises after admission is an ambiguous outcome: it reconciles as
spent-pending-review (the permit stays spent, the rate budget stays
consumed), never silently re-usable. Refusal verdicts are also appended
before raising; the extended ledger rides on the exception and the enforcer
persists it after re-verifying the chain.

Persistence is incremental per admission/spend/refusal when a `persist`
sink is wired at construction (`GuardrailEnforcer(persist=fn)` receives
`(gate_name, re-verified ledger)` on every commit; sink failures
propagate). Without a sink the ledgers live in memory until `dumps()`.
`audit()` reports per-gate record and refusal counts plus chain tip hashes.

`dumps()` / `loads()` serialize and restore all eight ledgers with full
chain and content re-verification; edits anywhere break the load. The
chains are unkeyed: tamper-evident, not tamper-proof. A rehashed edit is
not detectable; safe storage of serialized ledgers is the caller's job.

## Hooks

`approval_check` (bio gate), `review_check` (outbound gate) and
`authority_check` (review decisions, preauthorization grants, account
verifications) are supplied at construction. Unset hooks fail closed. Wire
them to the review gate or Module 0 for approval-store-backed validation; the
enforcer never authenticates references by itself.

Hook verdict contract (all hooks): accept means returning the boolean True
or a structured verified-permit mapping {"verified": True}; any truthy
non-True value (1, "yes", a non-empty string) is a rejection. The bio
approval hook receives (approval_ref, action_digest) so an approval binds
to the action's exact content.

Reviewer / verified_by / granted_by labels are caller-supplied
DECLARATIONS, not authentication. A record carrying `authority_ref` is
validated through `authority_check` and ledgered as
`authority_validated=True` only when the hook accepts it.

TWO MODES, no third path. An enforcer WITHOUT authority_check is in RECORD
mode: it ledgers declarations and CANNOT execute effects - execute_reviewed
and call_service refuse unconditionally (ledgered refusals), and
person-facing outbound kinds (send/post/submit/invite/account/payment)
refuse at dispatch_outbound. Public-read outbound kinds still dispatch on
policy admission alone - exactly matching the outbound gate's enforcement. An enforcer
WITH authority_check is in GATE mode: record_decision,
grant_preauthorization, issue_permit, execute_reviewed and verify_account
without a validated authority_ref all fail closed (coded ValueError at
decision/grant/issuance/verification; a ledgered GuardrailRefusal at
execution, effect never run). Record mode is a bookkeeping library, not an
execution gate.

## Scope honesty

This layer enforces the guardrails at ITS choke points with firing tests.
It does not rewrite every module's internal paths: adoption by other
runtime surfaces is separate integration work, and each gate's own LIMITS
(lexical scope, caller-attested verification, tamper-evidence) stand.
