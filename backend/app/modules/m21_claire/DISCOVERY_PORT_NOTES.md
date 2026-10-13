# Cognitive discovery port: status and limits

- Routers (`cognitive_discovery_routes`, `research_lab_routes`) are NOT mounted in the Atlas app and Celery beat is not configured. Nothing here is live until that integration lands.
- Owner approval is fail-closed and not live until integration. The approve and execute routes require an authenticated actor plus one of the roles `owner`, `admin`, `approver` (approve) or `owner`, `admin`, `executor`, `worker` (execute), or the scopes `actions:approve` / `actions:execute`. Atlas's `TenantContext` carries `actor_id` and `roles`; no scopes. Until Atlas's auth actually issues those roles, these routes return 403.
- Approval permits are issued once per approval row (atomic status flip). The returned permit is plain JSON; no adapter in this package consumes or verifies it. Do not claim execution is single-use: an external adapter must re-check the approval record immediately before acting.
- Stores are single-node SQLite, not Postgres.
- The closed-loop research engine rejects splits that share inputs (hash of input only, labels and ids ignored). This is exact-match only; near-duplicate leakage is not detected.
