# C4 meemee-merge: meemee capabilities ported into Claire

Scope: capability diff of meemee vs Claire (code
inventory), port missing capabilities with tests; ledger of ported vs rejected
with reason. (Existing meemee-into-claire workstream feeds this.)

## Inventory

Read-only inventory of [repo path removed] pinned at
commit [hash removed] (tip at inventory time, 2026-10-11). The meemee repo was NOT
modified (peer-gated). The machine-checked ledger lives in
`backend/app/modules/m21_claire/meemee_merge_inventory.py`; counts are computed
from the rows, never asserted. Result: 45 capabilities inventoried -

- 15 PORTED (new additive Claire modules, `meemee_*.py` in `m21_claire`)
- 15 ALREADY_PRESENT (Claire or Atlas core already covers them)
- 12 REJECTED (recorded reasons: non-hermetic weights, platform/host scope,
  provider-account blocking, other modules' ownership)
- 3 DEFERRED (personal-model/reflection to unit C2, monitor registry to A5,
  outbound webhook dispatcher to host platform)

(Each ledger row has one disposition; the computed buckets sum to45.)



## Ledger rows (from meemee_merge_inventory.MEEMEE_CAPABILITIES, 45 rows)

row type: dict ['id', 'meemee_source', 'category', 'disposition', 'target', 'reason']
goal-leasing | meemee/goals.py | agency | PORTED | app.modules.m21_claire.meemee_goal_leasing:GoalStore | Durable goal graph with expiring work leases; Claire had goal intake but no leasing.
job-queue | meemee/jobs.py+meemee/worker.py | agency | PORTED | app.modules.m21_claire.meemee_job_queue:JobQueue | Failure-surviving queue: bounded attempts, retry, cooperative cancel, event log.
checkpoints | meemee/checkpoints.py | agency | PORTED | app.modules.m21_claire.meemee_checkpoints:CheckpointStore | Append-only resumable run checkpoints with checksums and idempotency keys.
checkin-quiet-hours | meemee/companion/checkins.py | companion | PORTED | app.modules.m21_claire.meemee_checkins:CheckInScheduler | Proactive check-in planning with quiet hours; Claire had nothing proactive.
device-command-protocol | meemee/device_protocol.py | devices | PORTED | app.modules.m21_claire.meemee_device_protocol:verify_command | Signed, replay-guarded device commands; Claire's pairing/audit chain lacked the command layer.
webhook-security | meemee/webhook_verify.py+meemee/webhooks.py | webhooks | PORTED | app.modules.m21_claire.meemee_webhook_security:verify_signature | Timestamped HMAC with replay tolerance + HTTPS/global-address URL guard.
semantic-memory-hashing | meemee/semantic_memory.py | memory | PORTED | app.modules.m21_claire.meemee_semantic_memory:SemanticMemory | Offline hashing embeddings + cosine; Atlas's other embedders need network/API.
daily-briefing | meemee/briefing.py | companion | PORTED | app.modules.m21_claire.meemee_briefing:BriefingBuilder | Deterministic daily briefing assembly over timeline + priorities.
cancellation-and-run-gate | meemee/cancellation.py+meemee/shutdown.py | runtime | PORTED | app.modules.m21_claire.meemee_cancellation:RunGate | Cooperative job cancellation registry + bounded graceful shutdown gate.
secret-scrub | meemee/sensitive.py | security | PORTED | app.modules.m21_claire.meemee_secret_scrub:scrub_text | Credential scrubbing with stable correlation markers for logs/journals.
monitor-event-identity | meemee/monitor_event_identity.py | monitors | PORTED | app.modules.m21_claire.meemee_event_identity:identify_event | Pure replay preparation (new/replay/conflict) for monitor event streams.
rate-limit-and-quota | meemee/rate_limit.py+meemee/quotas.py | runtime | PORTED | app.modules.m21_claire.meemee_rate_quota:FixedWindowLimiter | Fixed-window limiter + per-principal daily quotas with UTC rollover.
pagination-cursors | meemee/cursors.py | api | PORTED | app.modules.m21_claire.meemee_cursors:encode_cursor | Keyset pagination cursor encode/decode with strict validation.
approval-grants | meemee/approvals.py | approvals | PORTED | app.modules.m21_claire.meemee_approval_grants:ApprovalGrantStore | Standing expiring grants with exact argument constraints; Atlas core only queues one-shot approvals.
subagent-delegation | meemee/team.py+meemee/tools/delegate.py | agency | PORTED | app.modules.m21_claire.meemee_delegation:AgentTeam | Bounded-concurrency sub-agent fan-out with per-child reports and cleanup shielding.
idempotency-store | meemee/idempotency.py | runtime | ALREADY_PRESENT | app.modules.m21_claire.execution:IdempotencyStore | Claire execution has one.
pairing-and-audit-chain | meemee/devices.py | devices | ALREADY_PRESENT | app.modules.m21_claire.local_client_protocol:PairingService | Pairing challenge + hash-chain audit exist.
decision-memory | meemee/memory.py | memory | ALREADY_PRESENT | app.modules.m21_claire.memory:DecisionStore | Consent-scoped decision store.
persistent-journal | meemee/context.py | memory | ALREADY_PRESENT | app.modules.m21_claire.persistent_journal:PersistentJournal | Provenance journal with bounded retrieval exists.
policy-engine | meemee/policy.py | policy | ALREADY_PRESENT | app.modules.m21_claire.policy:ActionPolicy | Claire policy with hard boundaries.
approval-queue | meemee/api.py(approvals surface) | approvals | ALREADY_PRESENT | app.core.approvals:ApprovalStore | Atlas approval queue.
audit-journal | meemee/audit.py+meemee/audit_anchor.py | audit | ALREADY_PRESENT | app.modules.m21_claire.audit:AuditJournal | Tamper-evident audit.
planner | meemee/planner.py | agency | ALREADY_PRESENT | app.modules.m21_claire.planner:CrossModulePlanner | Cross-module planner with cycle checks.
orchestrator | meemee/agent.py | agency | ALREADY_PRESENT | app.modules.m21_claire.orchestrator:ExecutionOrchestrator | Bounded executor + orchestrator + durable execution.
webhook-intake-verify | meemee/context.py(verify_webhook_signature) | webhooks | ALREADY_PRESENT | app.core.webhooks:verify_webhook | Atlas core HMAC body verify; meemee's timestamped variant ported.
model-routing | meemee/model_profiles.py | models | ALREADY_PRESENT | app.core.model_catalog | Atlas model catalog/routes + shared model layer.
tools-hub | meemee/tools/ | tools | ALREADY_PRESENT | app.modules.m22_tools_hub | M22 owns tool discovery/integration.
browser-agent | meemee/tools/browser.py | tools | ALREADY_PRESENT | app.modules.m13_browser_agent | M13 owns browser use.
secret-encryption | meemee/secret_cipher.py+meemee/vault.py+meemee/key_rotation.py | security | ALREADY_PRESENT | app.core.token_crypto | Atlas token crypto + secrets module.
embeddings-providers | meemee/providers.py+meemee/llm.py | models | ALREADY_PRESENT | app.core.embeddings | Atlas embedding providers (network); offline hashing ported separately.
minilm-embedder | meemee/semantic_memory.py:MiniLMEmbedder | models | REJECTED |  | Requires external weight download + ONNX runtime; not hermetic. Hashing embedder is the offline substitute.
inkling-local | meemee/inkling_local.py | models | REJECTED |  | Hardware-specific model launcher; Atlas scripts/inkling owns local model launch.
identity-stack | meemee/auth.py+meemee/oidc.py+meemee/web_login.py+meemee/email_verification.py | identity | REJECTED |  | Platform identity owned by Atlas core auth; not a Claire capability.
entitlements | meemee/entitlements.py | billing | REJECTED |  | Billing is module m24's scope.
account-export-deletion | meemee/account_export.py+meemee/account_deletion.py | platform | REJECTED |  | Platform-wide data operations, not a Claire runtime capability.
connectors | meemee/connectors.py | ingestion | REJECTED |  | RSS/ICS/Gmail ingestion belongs to trend/ingest units (c32/S2), not the merge.
browser-sessions-takeover | meemee/browser_sessions.py+meemee/browser_notices.py+meemee/browser_api.py | tools | REJECTED |  | Live Chromium sessions + human takeover need provider infra; m13 owns browser.
companion-channels | meemee/companion/channels.py+meemee/companion/engine.py | companion | REJECTED |  | WhatsApp/iMessage adapters need provider accounts (blocked-on-provider, meemee's own ledger).
platform-ops | meemee/backup.py+meemee/retention.py+meemee/migrations.py+meemee/postgres_copy.py+meemee/observability.py+meemee/loadcheck.py+meemee/preflight.py+meemee/package_audit.py+meemee/release_audit.py | platform | REJECTED |  | Host/platform operations, not Claire capabilities; retention pruning needs signed-anchor infra.
persistence-shapes | meemee/persistence.py+meemee/plan_store.py+meemee/runs.py+meemee/source_health.py+meemee/schema_registry.py | platform | REJECTED |  | Meemee-specific persistence shapes; Claire uses her own journal/execution stores.
api-wiring | meemee/api.py+meemee/runtime.py+meemee/cli.py+meemee/composition.py+meemee/config.py+meemee/streaming.py | platform | REJECTED |  | Meemee app wiring, not a portable capability.
isolation | meemee/isolation.py | runtime | REJECTED |  | Process-isolated tool execution is host sandbox policy; Atlas workers own it.
personal-model-reflection | meemee/personal_model.py+meemee/reflection.py+meemee/reflection_schedule.py | companion | DEFERRED | unit C2 (launch-quiz thinking layer) | Preference/decision profiling is C2's scope; double-booking refused.
monitors-store | meemee/monitors.py+meemee/monitor_event_identity.py(store half) | monitors | DEFERRED | unit A5 (important-events detector) | Durable monitor registry belongs to the events unit; the pure replay decision is ported.
webhook-dispatcher | meemee/webhooks.py(WebhookStore/Dispatcher) | webhooks | DEFERRED | host platform | Outbound delivery dispatcher needs host networking + encryption keys; security guard ported.
