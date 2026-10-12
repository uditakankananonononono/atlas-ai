# Nine scoped effect boundaries

Base: `6afa448000bb594f2f3854f9429ed62d1f5a23a2`.

These changes make previously unbound effect paths unavailable. They do not
implement a new authorization source or assert universal module coverage.
`EFFECT_UNBOUND_REFUSED` is a hard refusal, not an approval-id or boolean gate.

| Module | Boundary |
|---|---|
| m04 tools/adapters.py | Remote Galaxy workflow invocation refuses before HTTP client construction. Local tool computation is unchanged. |
| m10 gmail.py | Live Gmail watch refuses before provider requests. Profile/history/message reads and refresh support are unchanged. |
| m10 routes.py | Account connect and watch renewal entries refuse before service invocation. |
| m10 service.py | Account connect refuses before OAuth exchange/storage; watch renewal refuses before account/refresh/provider work. |
| m11 google_calendar.py | Watch and stop-channel refuse before provider requests; event reads are unchanged. |
| m11 routes.py | Ensure-watch entry refuses before service invocation. Local plans and proposals are unchanged. |
| m13 pc_daemon/daemon.py | Pairing refuses before key/network/account work. Generic FILL/CLICK_NAV return a policy-blocked result at command entry and also refuse in the driver entry. Token-checked CLICK_SUBMIT remains unchanged. |
| m13 playwright_adapter.py | Manager exposes a read-only page wrapper. Locator click/fill refuse; raw page, mouse, keyboard, context and arbitrary delegation are not exposed. Read values/content, origin-checked navigation and screenshots remain available. |
| m24 stripe_client.py | Legacy checkout, invoice and subscription cancellation primitives refuse before HTTP work. Existing durable billing dispatchers are unchanged. |

## Browser limitation

The local Playwright manager has no bound transport-authority hook. Its local
submit click therefore also refuses even after service-level approval checks.
The service currently consumes such an approval before its click; a refused
local submit needs fresh review, not replay. This is an unavailable local path,
not a claim that approved local submission works. The separate daemon's
existing signed-token submit path is unchanged. Navigation is not classified
as universally side-effect-free: only the named generic click/fill paths and
raw mutation exposure are covered here.

## Verification

Python 3.12, declared Playwright package installed locally; no browser launched
and no provider mutation or payment executed.

- Historical old-base inclusive selector (integrator reference `8ab6542c`):
  **103 passed** with explicit local development
  auth test opt-in (`ATLAS_DEV_NO_AUTH=1 ATLAS_ENV=development`) and
  `PYTHONPATH=backend`, Python 3.12, `--noconftest`. Includes scoped entry tests,
  imported HTTP adapters with zero MockTransport calls, imported browser
  wrapper tests with zero driver writes and preserved reads, existing daemon
  and browser-service capture/submit tests, and email/calendar offline tests.
- Mutation checks: removal of each of 15 exact source-entry refusals is caught
  by its same refusal assertion; manager wrapper removal, daemon driver guard
  condition removal, and shared refusal-helper replacement are caught too.
  Source-entry extraction executes actual AST function bodies with isolated
  spies. This is scoped unit evidence, not full-stack endpoint execution.
- Two previous Gmail connect/watch success tests now assert refusal.
- Initial run without local auth test opt-in: 102 passed, 1 deselected.
  The pubsub test expected 403 and got 401 on both patch and clean base in
  that environment, because `--noconftest` disables the normal autouse
  development-auth fixture. This is environment-specific, not a baseline
  defect. Reinstating both fixture environment values yields 103 passed
  inclusive on the old base. The test itself was not changed.
- Broader billing regression attempts are incomplete: full selector stalls in
  embedded Postgres setup, no-conftest loses fixture availability, and a
  SQLite-filtered selector also exceeds its 35-second bound. No passing total
  is claimed for those attempts. Durable billing gates were not modified.
- `compileall` and `git diff --check` pass.

These are scoped fail-closed paths. No live end-to-end provider evidence,
aggregate coverage promotion or new standing authorization is claimed.

Inclusive bounded reproduction command from repository root (no deselection):

```sh
PYTHONPATH=backend ATLAS_DEV_NO_AUTH=1 ATLAS_ENV=development python -m pytest --noconftest tests/runtime/guardrails/test_nine_scoped_effect_refusals.py tests/modules/test_m13_pc_daemon.py tests/modules/test_m13_browser_agent.py tests/modules/test_m13_capture_bound_submit.py tests/modules/test_m10_email_assistant.py tests/modules/test_m11_calendar_intelligence.py -q
```

The development-auth opt-in is test-only, replicating the existing fixture;
production authentication defaults are unchanged. The local browser wrapper
intentionally omits locator.evaluate too: a composed fill path using it
refuses before any driver write rather than acquiring a new effect permit.

## Current composition status

On current tip `3db0a1e8` plus the nine-gate code and docs patches, the same
inclusive command reports **102 passed, 1 failed**, not 103 passed. The failure
is `tests/modules/test_m13_browser_agent.py::test_fill_does_not_put_values_in_audit`:
the fake locator lacks evaluate, required by B3's landed read-only control-type
probe before fill. The same failure is present on bare current main, so this
is pre-existing B3 fixture debt, not a nine-gate regression. B3 owns its repair.
The old-base 103-pass result above is historical evidence only and does not
claim the current composition is green. Keep this test included; no guard
weakening or deselection is used to change that result.

With B3's r1 fixture repair applied, the full current composition (`3db0a1e8`
+ r1 + nine-gate code + docs + annotation) is **103 passed, 0 failed**,
independently reproduced in 7.43 seconds using the inclusive selector above. This
closes the fixture debt; the without-r1 102P/1F result remains recorded as the
earlier red checkpoint, and the old-base 103P result remains historical.
