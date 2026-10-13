# Row 1272 mounted treaties bookkeeping: supplied-scope review

Base: 134e0dcd8fb5133e816a718831055c9f1e3e0a67, live-fetched and verified.
Canonical row title is Treaties, description empty, as in the existing contract.
Adds a dedicated POST /api/v1/api/modules/20/legal/1272/run on the real app.
The existing shared legal-1260-1309/support route and its schema remain unchanged.
Pure organizer unchanged; new route follows existing dedicated legal-route shape:
signed principal, owner_payload scope/size checks, a retained surrogate guard,
organizer call and fixed 422 refusal mapping. Returns principal tenant and actor.

## Behavioral red and green

New test collected on the exact base before route creation. Real app TestClient
and valid signed test identity: dedicated positive request got HTTP404, producing
one assertion FAILED. No auth/schema/import/collection failure counted as red.
The same test bytes pass after mounting. Fresh full floor: 188 passed, 0 failures,
0 errors/skips, one Starlette TestClient deprecation warning (Python 3.12).
Selectors: test_row1272_mounted.py, test_m20_treaties1272.py and
 test_m20_legal_1260_1309.py in tests/modules. Unchanged real conftest is loaded.

Auth uses oidc_auth_headers from real conftest: locally generated RSA key,
RS256 signature and actual production OIDC verifier code, with dev bypass removed
and ATLAS_ENV=production. It is not proof of an external issuer or deployment.
Missing bearer and identity-header-only calls get401; body tenant/actor and
cross-owner reference attempts get403. Success gets200 before bookkeeping
assertions. No dependencies, handler, engine or real app are stubbed.

The peer's unexecuted draft used noncurrent identity headers and treaty fields
against a different shared authority schema. It was a lead only, not a behavioral
red. This unit rebuilds a dedicated endpoint, not that invalid-schema experiment.

## Production-site mutation replay

15 exact single-site production operators, each CAUGHT with rc1 + FAILED test ids,
no ERROR/collection/SKIP credit. Exact byte SHA restore per operator. Operators
span real include_router wiring, owner scope, returned actor, refusal HTTP code,
unknown classification, missing source, jurisdiction/date flags, authority review
state, false decision/verification labels, vocabulary/conclusion/effect refusal,
and duplicate authority. Exact unified diffs accompany each delivered replay.
All sensitivity runs select only real-app mounted tests, not the pure unit tests.

Reproduce from root using Python3.12:

```
PYTHONPATH=backend PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -p no:cacheprovider tests/modules/test_row1272_mounted.py tests/modules/test_m20_treaties1272.py tests/modules/test_m20_legal_1260_1309.py -q -rf
python audits/row1272-mounted/replay.py NEW_OUTPUT --ids mount_removed,owner_scope_bypass,wrong_identity
```

Repeat the replay with the other four ordered batches in verification.json.
Each batch uses a fresh output, real conftest, no pytest cacheprovider and a fresh
bytecode cache. No plugin auto-loading. 60s child timeout, timeout uncredited.
No-overwrite enforced. FAILED sensitivity includes runtime errors, not assertion
exception classification. Restores in finally protect ordinary exceptions, not
forced process termination; no escaped-descendant isolation claim.
An initial externally interrupted long run left missing_source applied without
final receipt. It receives no credit. Source restored exactly from verified base,
then all15 replayed in fresh bounded batches. Partial logs are retained privately.

## Scope and limits

Records caller declarations only; no treaty status/legal conclusion or legal advice.
No authority/citation verification, network fetch, filing, service, contact, spend,
external side effect or persistence. Counsel review still required. Vocabulary and
text-policy residuals remain those of the original contract, including accepted
surrogate/private-use/unassigned code points inside the pure organizer; The surrogate guard removal survived independent audit; mounted tests do not
pin that guard, so its presence is not credited as tested surrogate rejection. Header auth
success is locally signed fixture proof, not live owner identity/permissions proof.
No held science research project is built. Literal requirement stays PARTIAL.
Whole-repository suite and production deployment are untested.

Receipts record modified precommit checkout identity, not final-tree execution.
Review mailbox separately binds release tree. Raw evidence retained privately;
normalization table binds original/delivered SHA and every changed log line.
Private roots substituted and trailing whitespace stripped, no outcome/test-id
rewriting. Existing historical collection-error logs are not reclassified.

Integrator sequential0f477cb4-based composition: identical full10-case mounted
selector without new mount10 HTTP404 assertion failures, mounted floor188P.
All15 released exact-site operators CAUGHT in five independent three-operator
batches, all original bytes restored. Raw logs retained in handoff only. Shared
spec-router pins await one combined regeneration with the other four new in-router
operations; no green claim for the pin inventory is made before that replay.
