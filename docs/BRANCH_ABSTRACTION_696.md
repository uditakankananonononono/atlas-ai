# Row 696 - Branch by Abstraction: module contract

Source text of the row (feature list): "Branch by Abstraction - Enables large changes".
That is the only specification text. The scope below is an interpretation of it:
the standard technique (put an abstraction in front of the old code, add a new
implementation behind it, migrate callers, switch, then delete the old code).

Module: `backend/app/modules/m20_general_cognitive_worker/branch_abstraction696.py`
Tests: `tests/modules/test_branch_abstraction696.py`
Dependencies: Python standard library only.

## API

`BranchByAbstraction(abstraction, operations, old, new, min_equivalence_cases=1)`
- Both implementations must expose every named operation as a callable, else `BranchAbstractionError`.

Routing
- `set_route("old" | "shadow" | "canary" | "new", canary_percent=0)`
- `call(operation, *args, key=None, **kwargs)` dispatches by route.
  - `shadow`: runs both, returns the old result (or raises the old exception), records any difference in `divergences`.
  - `canary`: sha256 of `abstraction:key` modulo 100 against `canary_percent`; a key is required.
- `rollback()`: route back to old (or new once old is removed).

Evidence
- `verify_equivalence(operation, cases)` calls both implementations on each `(args, kwargs)` case and compares results; an exception counts as an outcome and compares by exception type name.
- `register_caller(name)`, `mark_caller_migrated(name)`.
- `scan_direct_usage(sources, old_symbol, allowed_files=())` parses each source with `ast` and reports imports, names and attribute accesses of `old_symbol`; unparseable files are reported and block removal. Comments and string literals are not findings.

Removal
- `can_remove_old()` returns `(ok, reasons)`. It is false unless: route is `new`; at least one caller is registered and all are migrated; every operation has at least `min_equivalence_cases` compared cases with zero divergent cases; no shadow divergences are recorded; a direct-usage scan was recorded with zero findings.
- `remove_old()` raises unless `can_remove_old()` is true, then drops the old implementation.

Reporting
- `report()` returns phase, route, caller counts (registered / migrated), per-operation `cases_compared` and `divergent_cases`, shadow divergence count, direct usage finding count, and the removal gate result.
- Phases: `introduce`, `migrate_callers`, `dual_implementation`, `switched`, `old_removed`.

## Limits

- The scan is syntactic on a single name; it does not resolve aliases (`import x as y`) or dynamic access (`getattr`).
- Equivalence is only as strong as the supplied cases; the engine does not generate cases.
- Equality uses `==` on results; no tolerance or custom comparison.
- Caller migration is recorded by the caller of this API, not detected.
- State is in memory and not thread-safe. No HTTP route, persistence or ledger wiring is included.

## Qualification (added 2026-10-11)

- Migration is DECLARED, not detected. The route, the list of callers, which callers are migrated, and the old symbol name to scan for are all stated by whoever drives this API. The engine does not discover callers or observe a migration happening; the only thing it finds on its own is syntactic references to one name in sources it is handed.
- Equivalence covers finite cases only. A pass means the old and new implementations agreed on the cases supplied, not that they agree on all inputs.
- NOT thread-safe. Route, caller, equivalence and divergence state is plain in-memory data with no locking.
- Scope is bounded: in-memory old and new implementations, declared migration routing, finite cases and gated removal.
