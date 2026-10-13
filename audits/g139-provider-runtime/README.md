# Group 139 provider identity runtime delta

Source: live instinct doc, paragraph 1, "use my account for all external services".
Current group verdict: PARTIAL. This delta is not independently verified or
landed when written. Source-code existence is not group completion.

## Implemented behavior

OwnerAccountRuntime performs authenticated GitHub `/user` or Google OpenID
UserInfo reads immediately before each explicitly routed service GET. It compares
the durable provider user ID/sub, not email, login, display name or caller label.
It rechecks an exact tenant/service/subject owner-authority digest every time and
separately requires exact-resource read/disclosure authority. Missing, revoked,
drifted, malformed, unavailable or unauthorized identities never dispatch the
resource request. A single credential snapshot is used for both requests.

SQLite bindings and dispatch receipts survive instance restart. BEGIN IMMEDIATE
serializes binding changes and in-flight dispatch across instances/processes.
Refused/ambiguous/dispatched receipts commit before the method returns. No secrets
or provider bodies enter these receipts. Redirects, environment proxies, arbitrary
hosts, query strings, percent encoding and writes are not supported. Response
sizes are capped at 64 KiB identity / 10 MiB resource (decompressed bytes).
Returned response request metadata drops the bearer header.

register_owner_account_reads mounts a Module 22 owner_account_read handler on the
real AtlasRuntime. Handoffs cannot supply tenant, credentials or authority; tenant
is taken from RuntimeContext. Instantiate it with a private writable DB and
trusted callbacks in the authenticated control plane. Mounting into a caller's
runtime is explicit, not an automatic global adoption claim.

## Reproduce

Python 3.12, httpx 0.28.1, pytest 9.1.1, pydantic 2.14.1:

```
PYTHONPATH=backend ATLAS_DEV_NO_AUTH=1 ATLAS_ENV=development python -m pytest --noconftest -p no:cacheprovider tests/modules/test_owner_account_runtime_g139.py tests/runtime/guardrails/test_owner_account_gate.py tests/runtime/guardrails/test_authority_binding.py -q
```

Tests use MockTransport except one real HTTP socket loopback test whose explicit
transport maps the fixed provider URLs to localhost. This is protocol behavior,
not live provider acceptance or TLS identity proof. The additive runtime handler
is dispatched through real AtlasRuntime, with offline provider responses.

## Remaining literal scope

No credentialed user-account provider probes were run. Trusted enrollment,
credential retrieval and per-resource permission callbacks require production
control-plane binding. This is a library and AtlasRuntime handler, not a mounted
HTTP API or universal interceptor. Existing service adapters do not automatically
use it. Only GitHub and Google GETs are covered; no account writes, refresh-token
flow, all-service identity support, Postgres migration, deployment or external
facade review is established. Process crash can lose an uncommitted dispatch
receipt, so it is not exactly-once execution. Locks serialize a local DB and can
block revocation behind a running request; read/socket timeouts are not a global
wall-clock deadline. HTTP DISPATCHED is not semantic success. File-system access
to the private SQLite file and callback replacement are outside this trust boundary.
Owner identity never replaces disclosure scope or spend/send approval.

## Provider contracts checked

- https://docs.github.com/rest/users/users : GET /user returns authenticated user's durable numeric ID and account type.
- https://developers.google.com/identity/openid-connect/reference : UserInfo endpoint https://openidconnect.googleapis.com/v1/userinfo and stable sub identifier, not email as key.

## Builder-run results

82 selected tests passed: 48 new provider-runtime tests plus 34 existing owner
binding/authority gate tests. No full-repository regression was run.
9 exact-site mutants were tested. First run: 8 caught, 1 survived (Google subject
validation was redundant under the original selected bindings). Added matching
malformed-subject tests; final run: 9 caught, 0 survived, 0 invalid. Original source
bytes were SHA-256 checked after each restore. These are builder-run test
sensitivities, not independent audit or mutation completeness.

## Independent audit follow-up

Two initially surviving auditor mutations (operation redirect following and
proxy environment use) now have explicit sensitivity tests. The proxy test sets
HTTP_PROXY, HTTPS_PROXY and ALL_PROXY to an observed localhost server; the
operation redirect test observes that no request reaches the redirect host.
get() holds BEGIN IMMEDIATE's database write lock for the entire identity probe
and operation HTTP request. SQLite OperationalError, including the 15-second
lock wait timeout, is sanitized to AccountRefusal. A lock failure before starting
the transaction cannot write a receipt. This remains an availability limitation,
not unblocked revocation or exactly-once evidence.

Revised builder run: 86 selected tests pass (52 new plus 34 existing). Expanded
11-mutation battery: 11 caught, 0 survived, 0 invalid. The first revised proxy test
used MockTransport, which httpx exempted from proxy mounting; that test alone did
not catch trust_env=True. Added a no-injected-transport test with real origin and
proxy loopback servers and a test-only provider destination override; it catches
the proxy mutation. The lock-timeout test is excluded from the mutation selector
to avoid nine unnecessary 15-second waits; it runs in the full selected baseline.
No live provider/TLS verification is claimed by loopback tests.

## Egress composition repair

Both the provider identity GET and resource GET now route through
GuardrailEnforcer.dispatch_outbound before client.stream. A trusted operator
outbound_declarations(tenant, exact_url) callback must supply read/automation/rate
policy per destination; absent policy defaults to denial before any transport.
It does not grant owner identity or read/disclosure authority. No public-host
blanket allowlist is supplied. Effect callbacks use the gate's isolated canonical
URL. Outbound rate history is persisted per tenant in SQLite and loaded on each
GET, so both requests count and instance restarts do not reset the history.
The same transaction/write-lock scope and crash limits apply to this ledger.
A declared policy is not legal compliance or provider ToS verification.
The static binding snapshot changes only the newly added g139 path to GATED;
this is declared AST wiring evidence, not global completeness or domination.

Builder composition run against main c95aba26 plus repaired g139: 303 selected
tests passed (245 guardrail tests collected by this selector plus 58 g139 runtime
tests). Two first-run failures were missing asn1crypto/playwright dependencies;
installing them cleared those imports. No baseline changes were made. The final
11 exact-site mutation runs all caught, including operation redirect and proxy.
This is a local builder run, not full-repo or independent audit acceptance.
