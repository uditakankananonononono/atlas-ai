# M18 shared (process-global) state: assessed scope, 2026-10-04 (UNREVIEWED)

Tenant-isolated (keyed by tenant in SQLite repository, routes pass require_tenant's tenant): collected documents, ranking
input, freshness watch list, events. HTTP-tested in tests/modules/test_m18_core_route_flow.py (dev headers = TEST MODE).

Shared across ALL tenants in one process (the module-level Service built by routes.get_service):
1. Collector credentials: ATLAS_YOUTUBE_API_KEY, ATLAS_PINTEREST_ACCESS_TOKEN, ATLAS_X_BEARER_TOKEN,
   ATLAS_INSTAGRAM_GRAPH_TOKEN come from process env (wiring.build_collectors). Every tenant's /collect uses the OPERATOR's
   credentials and quota; this is an operator-owned shared account, not per-user credentials. No per-tenant credential
   model exists, so a multi-user deployment would charge/limit all users to one account. Not fixed.
2. Per-host pacing/backoff/circuit state (lane_rate_limit.HostRateLimiter): shared on purpose (it protects the remote host
   from this server's IP) but one tenant's failures can open a host circuit (5 failures, 300s cooldown) for every tenant.
   An availability coupling, not a data leak. Not fixed.
3. Model provider/model choice (Service._provider/_model): process-wide.
4. The default document repository is in-memory SQLite (":memory:"): lost on restart; deployments must inject a shared one.
Not tested: concurrent multi-tenant load on the shared limiter.

## Update WIP44 (UNREVIEWED)
- Operator credentials: credentialed collectors (youtube, pinterest, x, instagram) now FAIL CLOSED per tenant: usable only if the
  tenant id is listed exactly in ATLAS_M18_OPERATOR_ACCOUNT_TENANTS (no wildcard). /blueprints -> 403; /collect reports
  `operator_account_not_granted:<platform>` and never calls the collector. Env key presence is not a grant. Existing tests that
  used youtube without a grant were changed (contract change, commented in each).
- Legacy /runs: previously ONE process-global runner with no tenant dependency at all (any caller could read/modify any run id).
  Now run ownership is recorded at create; other tenants get 404. Receipts route still 409 (unchanged). Runs remain process memory.
- request-approval (legacy and durable): approval owner was a client body field defaulting to 'default'; now the authenticated
  tenant, and a differing body user_id is 422. No exploit was executed against the old code; defects are from reading it.
- Durable run store: file now chmod 0600 and parent dir created; default path honors ATLAS_RUNTIME_DATA_DIR/ATLAS_M18_RUN_DB, with the
  old shared /tmp path kept only as the fallback (deployment must set one). Not assessed: sqlite file at rest unencrypted.
