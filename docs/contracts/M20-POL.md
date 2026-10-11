# M20-POL (map unit P1 "policy-adopt-m20")

## Source pin (her standing rules, as delegated)

> "You can do anything except emailing people from my side" + the no-spend rule.

Canonical guard: `app.modules.c30.policy` (auditor-4 canonical surface, landed
9782a593+). This unit adopts it inside the m20 general cognitive worker.

## Scope

- implemented:
  - `RegisteredTool.check_preconditions` is strict fail-closed: a precondition key is
    satisfied only by the bool `True` (1, "yes", "true", [] no longer pass). Narrows
    only; route trust never widened.
  - Policy gate in `ToolDispatcher.dispatch` BEFORE the precondition check: the
    ToolSpec's declared `effect_class` (new optional schemas field) maps
    spend/outreach/account/post/trade/scrape onto the canonical c30.policy standing
    rules and the guard's `POLICY_REFUSED_*` code is raised as ToolBlockedError.
    No declared class (None or "none") makes no policy call. An unknown declared
    class refuses closed (`POLICY_REFUSED_UNKNOWN:<class>`). Deny-only: the gate
    can never turn a failed precondition into a pass.
  - `GCWRuntime.preflight_task` reports the refusal code inside the existing
    `issues` list (row keys unchanged).
  - `ToolSelector.score_all` never raises: a policy refusal scores as blocked
    (same 0.5 penalty as a missing precondition; the code is appended to
    `missing_preconditions`).
- not_implemented / LIMITS:
  - deny-only at this layer: via legacy `c30.policy.check()` spend and outreach are
    hard refusals; there is no needs_approval path here (the descriptor-classify
    surface needs full spend/outreach payloads a dispatcher does not hold). The
    existing m00/safety approval flow is untouched and remains the only approval path.
  - the descriptor is the ToolSpec's DECLARED effect_class; an undeclared or
    misdeclared tool is outside this gate's view (registry honesty is the bound).
  - route auth and request schema untouched; no wiring changes.
- data_source: supplied
- interpretation choices:
  - effect_class added to ToolSpec (schemas.py) - the field did not exist on main;
    additive optional, default None (no policy call for every existing tool).
  - class mapping account->fakeacct, post->autopost (c30 rule names).
  - preflight carries the refusal in `issues`; score_all carries it in
    `missing_preconditions` - both keep their existing shapes.
  - no compat shim: every c30.policy importer on main uses check/check_account/
    clean_text/scope, all present in the landed guard.

## Explicit registrar limit

This gate is honour-system. The default effect_class is None, so every existing
tool bypasses the new policy call until its registrar declares an effect class.
It does not infer effects from a tool's handler, arguments, name or runtime behavior.
