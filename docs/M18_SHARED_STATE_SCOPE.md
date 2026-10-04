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
