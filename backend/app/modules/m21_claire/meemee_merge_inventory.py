"""C4 meemee-merge: capability inventory of meemee vs Claire, and the port ledger.

Spec unit C4 ("Merge meemee to claire if she has some extra capabilities"):
code inventory of meemee (repo uditakankananonononono/meemee, read-only,
pinned at commit 50e7605), each capability classified as:

  PORTED          - implemented for Claire in this unit (target module listed)
  ALREADY_PRESENT - Claire or Atlas core already covers it (covering module listed)
  REJECTED        - deliberately not ported (reason recorded)
  DEFERRED        - belongs to another unit's scope (owning unit recorded)

Counts are computed from the rows, never asserted. The meemee repo was not
modified (peer-gated, read-only inventory).
"""
from __future__ import annotations

import importlib
from typing import Literal

MEEMEE_REPO = "https://github.com/uditakankananonononono/meemee"
MEEMEE_PIN = "50e7605"
CLAIRE_MODULE = "m21_claire"

Disposition = Literal["PORTED", "ALREADY_PRESENT", "REJECTED", "DEFERRED"]

_P = "app.modules.m21_claire"

# (capability_id, meemee source, category, disposition, target-or-covering module, reason)
MEEMEE_CAPABILITIES: list[dict] = [
    # ---- ported: capabilities meemee proved and Claire lacked
    {"id": "goal-leasing", "meemee_source": "meemee/goals.py", "category": "agency",
     "disposition": "PORTED", "target": f"{_P}.meemee_goal_leasing:GoalStore",
     "reason": "Durable goal graph with expiring work leases; Claire had goal intake but no leasing."},
    {"id": "job-queue", "meemee_source": "meemee/jobs.py+meemee/worker.py", "category": "agency",
     "disposition": "PORTED", "target": f"{_P}.meemee_job_queue:JobQueue",
     "reason": "Failure-surviving queue: bounded attempts, retry, cooperative cancel, event log."},
    {"id": "checkpoints", "meemee_source": "meemee/checkpoints.py", "category": "agency",
     "disposition": "PORTED", "target": f"{_P}.meemee_checkpoints:CheckpointStore",
     "reason": "Append-only resumable run checkpoints with checksums and idempotency keys."},
    {"id": "checkin-quiet-hours", "meemee_source": "meemee/companion/checkins.py", "category": "companion",
     "disposition": "PORTED", "target": f"{_P}.meemee_checkins:CheckInScheduler",
     "reason": "Proactive check-in planning with quiet hours; Claire had nothing proactive."},
    {"id": "device-command-protocol", "meemee_source": "meemee/device_protocol.py", "category": "devices",
     "disposition": "PORTED", "target": f"{_P}.meemee_device_protocol:verify_command",
     "reason": "Signed, replay-guarded device commands; Claire's pairing/audit chain lacked the command layer."},
    {"id": "webhook-security", "meemee_source": "meemee/webhook_verify.py+meemee/webhooks.py", "category": "webhooks",
     "disposition": "PORTED", "target": f"{_P}.meemee_webhook_security:verify_signature",
     "reason": "Timestamped HMAC with replay tolerance + HTTPS/global-address URL guard."},
    {"id": "semantic-memory-hashing", "meemee_source": "meemee/semantic_memory.py", "category": "memory",
     "disposition": "PORTED", "target": f"{_P}.meemee_semantic_memory:SemanticMemory",
     "reason": "Offline hashing embeddings + cosine; Atlas's other embedders need network/API."},
    {"id": "daily-briefing", "meemee_source": "meemee/briefing.py", "category": "companion",
     "disposition": "PORTED", "target": f"{_P}.meemee_briefing:BriefingBuilder",
     "reason": "Deterministic daily briefing assembly over timeline + priorities."},
    {"id": "cancellation-and-run-gate", "meemee_source": "meemee/cancellation.py+meemee/shutdown.py", "category": "runtime",
     "disposition": "PORTED", "target": f"{_P}.meemee_cancellation:RunGate",
     "reason": "Cooperative job cancellation registry + bounded graceful shutdown gate."},
    {"id": "secret-scrub", "meemee_source": "meemee/sensitive.py", "category": "security",
     "disposition": "PORTED", "target": f"{_P}.meemee_secret_scrub:scrub_text",
     "reason": "Credential scrubbing with stable correlation markers for logs/journals."},
    {"id": "monitor-event-identity", "meemee_source": "meemee/monitor_event_identity.py", "category": "monitors",
     "disposition": "PORTED", "target": f"{_P}.meemee_event_identity:identify_event",
     "reason": "Pure replay preparation (new/replay/conflict) for monitor event streams."},
    {"id": "rate-limit-and-quota", "meemee_source": "meemee/rate_limit.py+meemee/quotas.py", "category": "runtime",
     "disposition": "PORTED", "target": f"{_P}.meemee_rate_quota:FixedWindowLimiter",
     "reason": "Fixed-window limiter + per-principal daily quotas with UTC rollover."},
    {"id": "pagination-cursors", "meemee_source": "meemee/cursors.py", "category": "api",
     "disposition": "PORTED", "target": f"{_P}.meemee_cursors:encode_cursor",
     "reason": "Keyset pagination cursor encode/decode with strict validation."},
    {"id": "approval-grants", "meemee_source": "meemee/approvals.py", "category": "approvals",
     "disposition": "PORTED", "target": f"{_P}.meemee_approval_grants:ApprovalGrantStore",
     "reason": "Standing expiring grants with exact argument constraints; Atlas core only queues one-shot approvals."},
    {"id": "subagent-delegation", "meemee_source": "meemee/team.py+meemee/tools/delegate.py", "category": "agency",
     "disposition": "PORTED", "target": f"{_P}.meemee_delegation:AgentTeam",
     "reason": "Bounded-concurrency sub-agent fan-out with per-child reports and cleanup shielding."},
    # ---- already present in Claire / Atlas core
    {"id": "idempotency-store", "meemee_source": "meemee/idempotency.py", "category": "runtime",
     "disposition": "ALREADY_PRESENT", "target": f"{_P}.execution:IdempotencyStore", "reason": "Claire execution has one."},
    {"id": "pairing-and-audit-chain", "meemee_source": "meemee/devices.py", "category": "devices",
     "disposition": "ALREADY_PRESENT", "target": f"{_P}.local_client_protocol:PairingService", "reason": "Pairing challenge + hash-chain audit exist."},
    {"id": "decision-memory", "meemee_source": "meemee/memory.py", "category": "memory",
     "disposition": "ALREADY_PRESENT", "target": f"{_P}.memory:DecisionStore", "reason": "Consent-scoped decision store."},
    {"id": "persistent-journal", "meemee_source": "meemee/context.py", "category": "memory",
     "disposition": "ALREADY_PRESENT", "target": f"{_P}.persistent_journal:PersistentJournal", "reason": "Provenance journal with bounded retrieval exists."},
    {"id": "policy-engine", "meemee_source": "meemee/policy.py", "category": "policy",
     "disposition": "ALREADY_PRESENT", "target": f"{_P}.policy:ActionPolicy", "reason": "Claire policy with hard boundaries."},
    {"id": "approval-queue", "meemee_source": "meemee/api.py(approvals surface)", "category": "approvals",
     "disposition": "ALREADY_PRESENT", "target": "app.core.approvals:ApprovalStore", "reason": "Atlas approval queue."},
    {"id": "audit-journal", "meemee_source": "meemee/audit.py+meemee/audit_anchor.py", "category": "audit",
     "disposition": "ALREADY_PRESENT", "target": f"{_P}.audit:AuditJournal", "reason": "Tamper-evident audit."},
    {"id": "planner", "meemee_source": "meemee/planner.py", "category": "agency",
     "disposition": "ALREADY_PRESENT", "target": f"{_P}.planner:CrossModulePlanner", "reason": "Cross-module planner with cycle checks."},
    {"id": "orchestrator", "meemee_source": "meemee/agent.py", "category": "agency",
     "disposition": "ALREADY_PRESENT", "target": f"{_P}.orchestrator:ExecutionOrchestrator", "reason": "Bounded executor + orchestrator + durable execution."},
    {"id": "webhook-intake-verify", "meemee_source": "meemee/context.py(verify_webhook_signature)", "category": "webhooks",
     "disposition": "ALREADY_PRESENT", "target": "app.core.webhooks:verify_webhook", "reason": "Atlas core HMAC body verify; meemee's timestamped variant ported."},
    {"id": "model-routing", "meemee_source": "meemee/model_profiles.py", "category": "models",
     "disposition": "ALREADY_PRESENT", "target": "app.core.model_catalog", "reason": "Atlas model catalog/routes + shared model layer."},
    {"id": "tools-hub", "meemee_source": "meemee/tools/", "category": "tools",
     "disposition": "ALREADY_PRESENT", "target": "app.modules.m22_tools_hub", "reason": "M22 owns tool discovery/integration."},
    {"id": "browser-agent", "meemee_source": "meemee/tools/browser.py", "category": "tools",
     "disposition": "ALREADY_PRESENT", "target": "app.modules.m13_browser_agent", "reason": "M13 owns browser use."},
    {"id": "secret-encryption", "meemee_source": "meemee/secret_cipher.py+meemee/vault.py+meemee/key_rotation.py", "category": "security",
     "disposition": "ALREADY_PRESENT", "target": "app.core.token_crypto", "reason": "Atlas token crypto + secrets module."},
    {"id": "embeddings-providers", "meemee_source": "meemee/providers.py+meemee/llm.py", "category": "models",
     "disposition": "ALREADY_PRESENT", "target": "app.core.embeddings", "reason": "Atlas embedding providers (network); offline hashing ported separately."},
    # ---- rejected with reason
    {"id": "minilm-embedder", "meemee_source": "meemee/semantic_memory.py:MiniLMEmbedder", "category": "models",
     "disposition": "REJECTED", "target": "",
     "reason": "Requires external weight download + ONNX runtime; not hermetic. Hashing embedder is the offline substitute."},
    {"id": "inkling-local", "meemee_source": "meemee/inkling_local.py", "category": "models",
     "disposition": "REJECTED", "target": "",
     "reason": "Hardware-specific model launcher; Atlas scripts/inkling owns local model launch."},
    {"id": "identity-stack", "meemee_source": "meemee/auth.py+meemee/oidc.py+meemee/web_login.py+meemee/email_verification.py", "category": "identity",
     "disposition": "REJECTED", "target": "", "reason": "Platform identity owned by Atlas core auth; not a Claire capability."},
    {"id": "entitlements", "meemee_source": "meemee/entitlements.py", "category": "billing",
     "disposition": "REJECTED", "target": "", "reason": "Billing is module m24's scope."},
    {"id": "account-export-deletion", "meemee_source": "meemee/account_export.py+meemee/account_deletion.py", "category": "platform",
     "disposition": "REJECTED", "target": "", "reason": "Platform-wide data operations, not a Claire runtime capability."},
    {"id": "connectors", "meemee_source": "meemee/connectors.py", "category": "ingestion",
     "disposition": "REJECTED", "target": "", "reason": "RSS/ICS/Gmail ingestion belongs to trend/ingest units (c32/S2), not the merge."},
    {"id": "browser-sessions-takeover", "meemee_source": "meemee/browser_sessions.py+meemee/browser_notices.py+meemee/browser_api.py", "category": "tools",
     "disposition": "REJECTED", "target": "", "reason": "Live Chromium sessions + human takeover need provider infra; m13 owns browser."},
    {"id": "companion-channels", "meemee_source": "meemee/companion/channels.py+meemee/companion/engine.py", "category": "companion",
     "disposition": "REJECTED", "target": "", "reason": "WhatsApp/iMessage adapters need provider accounts (blocked-on-provider, meemee's own ledger)."},
    {"id": "platform-ops", "meemee_source": "meemee/backup.py+meemee/retention.py+meemee/migrations.py+meemee/postgres_copy.py+meemee/observability.py+meemee/loadcheck.py+meemee/preflight.py+meemee/package_audit.py+meemee/release_audit.py", "category": "platform",
     "disposition": "REJECTED", "target": "", "reason": "Host/platform operations, not Claire capabilities; retention pruning needs signed-anchor infra."},
    {"id": "persistence-shapes", "meemee_source": "meemee/persistence.py+meemee/plan_store.py+meemee/runs.py+meemee/source_health.py+meemee/schema_registry.py", "category": "platform",
     "disposition": "REJECTED", "target": "", "reason": "Meemee-specific persistence shapes; Claire uses her own journal/execution stores."},
    {"id": "api-wiring", "meemee_source": "meemee/api.py+meemee/runtime.py+meemee/cli.py+meemee/composition.py+meemee/config.py+meemee/streaming.py", "category": "platform",
     "disposition": "REJECTED", "target": "", "reason": "Meemee app wiring, not a portable capability."},
    {"id": "isolation", "meemee_source": "meemee/isolation.py", "category": "runtime",
     "disposition": "REJECTED", "target": "", "reason": "Process-isolated tool execution is host sandbox policy; Atlas workers own it."},
    # ---- deferred to owning units
    {"id": "personal-model-reflection", "meemee_source": "meemee/personal_model.py+meemee/reflection.py+meemee/reflection_schedule.py", "category": "companion",
     "disposition": "DEFERRED", "target": "unit C2 (launch-quiz thinking layer)",
     "reason": "Preference/decision profiling is C2's scope; double-booking refused."},
    {"id": "monitors-store", "meemee_source": "meemee/monitors.py+meemee/monitor_event_identity.py(store half)", "category": "monitors",
     "disposition": "DEFERRED", "target": "unit A5 (important-events detector)",
     "reason": "Durable monitor registry belongs to the events unit; the pure replay decision is ported."},
    {"id": "webhook-dispatcher", "meemee_source": "meemee/webhooks.py(WebhookStore/Dispatcher)", "category": "webhooks",
     "disposition": "DEFERRED", "target": "host platform",
     "reason": "Outbound delivery dispatcher needs host networking + encryption keys; security guard ported."},
]

_VALID = {"PORTED", "ALREADY_PRESENT", "REJECTED", "DEFERRED"}


def inventory_rows() -> list[dict]:
    return [dict(row) for row in MEEMEE_CAPABILITIES]


def inventory_report() -> dict:
    """Computed counts by disposition and category; nothing asserted by hand."""
    by_disposition: dict[str, int] = {key: 0 for key in sorted(_VALID)}
    by_category: dict[str, int] = {}
    for row in MEEMEE_CAPABILITIES:
        if row["disposition"] not in _VALID:
            raise ValueError(f"invalid disposition: {row['disposition']}")
        by_disposition[row["disposition"]] += 1
        by_category[row["category"]] = by_category.get(row["category"], 0) + 1
    return {
        "unit": "C4",
        "meemee_repo": MEEMEE_REPO,
        "meemee_pin": MEEMEE_PIN,
        "claire_module": CLAIRE_MODULE,
        "total_capabilities": len(MEEMEE_CAPABILITIES),
        "by_disposition": by_disposition,
        "by_category": dict(sorted(by_category.items())),
        "ported_ids": [row["id"] for row in MEEMEE_CAPABILITIES if row["disposition"] == "PORTED"],
        "scope": {
            "implemented": "In-memory, hermetic, stdlib ports of the PORTED capabilities with meemee semantics preserved.",
            "not_implemented": "Durable SQLite/PostgreSQL backing (host-owned), HTTP routes (c31 host belongs to sibling units), MiniLM/ONNX, live browser/companion channels, dispatcher networking.",
            "data_source": f"meemee repo read-only inventory at {MEEMEE_PIN}",
            "as_of": "2026-10-11",
        },
    }


def validate_ported_targets() -> list[str]:
    """Import each PORTED target and return any that fail; empty list means all resolve."""
    failures = []
    for row in MEEMEE_CAPABILITIES:
        if row["disposition"] != "PORTED":
            continue
        module_name, _, symbol = row["target"].partition(":")
        try:
            module = importlib.import_module(module_name)
            if symbol and not hasattr(module, symbol):
                failures.append(f"{row['id']}: {module_name} has no {symbol}")
        except Exception as exc:  # pragma: no cover - exercised only on breakage
            failures.append(f"{row['id']}: import failed: {exc}")
    return failures
