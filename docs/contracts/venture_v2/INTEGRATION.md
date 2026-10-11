# V1-V8 integration

Base: a1b859cebf6b0f5bb2dea8d00f530a07433b2e69. Additive package only.

Integrator must import `app.modules.m20_general_cognitive_worker.venture_v2_routes.router` and mount at `/api/v1`. Existing require_tenant authentication is on every route. Set ATLAS_VENTURE_REPORT_DB to a durable SQLite database path accessible only to the service; unconfigured or in-memory storage fails with 503. Store SQL queries are parameterized and scoped to tenant, unit and run ID. Database retention/backup is an operator responsibility.

To verify with Python 3.12+ and repository dependencies:

    PYTHONPATH=backend:tests/venture_v2 python -m unittest discover -s tests/venture_v2 -v
    python scripts/venture_v2/mutation_battery.py
    python scripts/venture_v2/hand_battery.py

No main.py, registry, existing module, external account, remote branch or deployment is modified by this branch. Tests were written before the engines. The initial red run was blocked by missing environment dependencies rather than a clean assertion-red implementation test; evidence does not claim a full test-first red/green proof. Focused tests subsequently run using real package imports and real auth dependency with unauthenticated 401 checks, rather than import stubs.

The bundle is not full delivery against every word of the aspiration. V1/V2/V4/V5/V6 are marked SUBSTITUTE for their narrower implementations. External model reviews are pending. No UI is added and no visual result is claimed. No candy completion condition is satisfied here.

Hand-run inspection caught a generated artifact import collision: naming it app.py shadowed the Atlas app package when executed as a file. The emitted software filename is now prototype.py and the hand battery executes it in a clean subprocess. This is recorded by artifact_execution.process_returncode=0 and mean=20 on fresh input; it is not only exec() within the test process.

Repository-wide pytest fixtures enable insecure dev auth. The route tests explicitly force ATLAS_DEV_NO_AUTH=0 for unauthenticated denial and restore the environment afterwards; the focused pytest run includes the shared repository conftest and passes.

## Supplied URL validation limit

URLs are stored metadata only, never fetched by these engines. The validator checks scheme, hostname presence, credential absence, length and parser validity (including port parsing). Malformed IPv6, invalid netloc normalization, nonnumeric ports and ports outside 0..65535 now refuse with PLAN_REFUSED_SOURCE. It is not a complete DNS/URL syntax or fetch-safety validator: a host containing a space or NUL can still pass and be stored (for example http://a b/ or a NUL-containing host). Any future live-fetch adapter must validate independently before use. The earlier child also accepted nonnumeric/out-of-range ports; this guard-wrap child no longer does because it explicitly accesses url.port.
