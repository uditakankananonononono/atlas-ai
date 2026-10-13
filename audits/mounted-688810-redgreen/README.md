# Rows 688 and 810: mounted behavioral red/green evidence

Fresh execution from current main 5886edfc, not credit transferred from earlier
engine-only probes. Added one dedicated HTTP test per row. Test collection
imports neither engine nor application; the fixture imports the real app and
uses its complete mounted routing through FastAPI TestClient. No dependency,
engine, route or app stub and no direct-engine expected-output oracle.
Runtime/module/route code is unchanged: both routes already exist on main.
This patch closes the missing scoped behavioral evidence, not literal capability
acceptance or global program completion.

## Historical parents and landings, identical overlaid test bytes

- Row 688: parent 43a4a56c5c40f5909b5dc7f73ef96a51f234c3cc responds HTTP404
  at `/api/v1/api/modules/20/acceptance-test-driven-development/688/bookkeeping`.
  Dedicated test collects and FAILS its HTTP200 assertion. Landing
  9b3dc4432120af4667426b108b050d2cc3fd4bcd PASSES. It checks an incomplete
  declared agreement, pending developer, uncovered AC2, tests_executed=False,
  plus response tenant/actor. No ATDD tests are actually executed by the helper.
- Row 810: parent 7ce3bb3a14edfc5c4ed8023c7b0748d4e8660687 responds HTTP200,
  but its old scaffold computes 3 days for a second successful repetition,
  versus the dedicated assertion of 6. Test collects and behaviorally FAILS.
  Landing 46cdb238350583d51889111c23ed406ae4ca016f PASSES with repetitions2,
  interval6, prior-state preservation, evidence id, ease2.7 and timestamp-based
  due date 2026-10-13T00:00:00+05:30. No collection-error credit is used.

The test file is overlaid untracked onto each checkout, not claimed to have
existed historically. These are new executions of historical code with new
sensitivity tests. Historical missing-engine collection errors remain invalid
as behavioral reds. The old 688 69P/69P engine probes remain no-red evidence.

## Route removal on current base

Independently remove only `router.include_router(atdd688_routes_router)` or
`router.include_router(learning_reasoning_router_810_859)` in m20/routes.py.
Each corresponding dedicated HTTP test collects and FAILS on HTTP404. App,
route imports and engines still load. Restore exact original source bytes
and SHA256 after each probe. Receipts bind changed path/line, original and
restored SHA256, checkout and log hashes. No removal is retained in this patch.

## Commands and fresh floor

Python3.12; PYTHONPATH=backend; PYTEST_DISABLE_PLUGIN_AUTOLOAD=1. Historical
runs each select their dedicated node with --noconftest -p no:cacheprovider
-q -rf. The test fixture explicitly sets ATLAS_DEV_NO_AUTH=1,
ATLAS_ENV=development and ATLAS_M10_TIMESTAMP_SCHEME=off before app import.

Current four-file floor additionally sets those three environment values
for legacy route tests; selectors:

```
tests/modules/test_m20_rows688810_mounted_redgreen.py
tests/modules/test_m20_acceptance_test_driven_development688.py
tests/modules/test_m20_spaced_review.py
tests/modules/test_m20_learning_reasoning_810_859.py
```

166 passed, 0 failed/error/skipped, 1 Starlette deprecation warning. Repeated
with unchanged real tests/conftest.py: 166 passed, same warning. An earlier
wider noconftest run without explicit dev-auth env had legacy route401
(1 failed/165 passed); it is not the released floor. An early draft assertion
used the wrong 688 output key; corrected before all recorded release probes.
Neither attempt counts as product red evidence.

## Limits

Development identity-header bypass only, not production OIDC, verified user
identity, authorization or deployment proof. Supplied declarations are not
real agreement or observed human review evidence. This HTTP computation
retrieves no cited URL. SM-2 state calculation is not empirical retention,
mastery, optimal scheduling or a dispatched reminder. Existing lapse-repair
unit tests are included in the floor; the mounted historical test exercises
one successful second-repetition state, not all scheduling states. This
assignment builds no held science research project. Whole-repository testing,
providers and external effects are untested; broad/literal groups stay PARTIAL.

Review package includes exact test SHA, checkout/tree and log SHA receipts,
case inventory, Python distribution inventory and reproduction scripts.
Raw logs are retained privately; delivered logs replace declared private
workspace roots and strip trailing whitespace. Every changed line and both
original/delivered hashes are recorded. Timing, test ids, responses and outcomes
are unchanged. Receipts' log hashes bind originals, not normalized delivery.
