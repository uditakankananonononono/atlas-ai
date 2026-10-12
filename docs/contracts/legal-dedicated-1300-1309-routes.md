# Dedicated legal supplied-record routes

Ten authenticated POST endpoints: `/api/v1/api/modules/20/legal/{row}/run`, for rows 1300 through 1309.

Each endpoint accepts an object containing `data` and optional owner metadata (`tenant_id`, `actor_id`, `resource_refs`). The data object is passed unchanged to the dedicated engine. Nine engines expose `run(request)`; row 1305 exposes `prepare_invoices(payload)`. Authenticated tenant and actor identifiers are added to the response. Cross-owner claims or references are rejected. Engine ValueError, TypeError and KeyError become HTTP 422. Invalid Unicode surrogates, oversized nesting and nonfinite inputs are rejected before computation.

Rows 1300-1304 and 1306-1309 perform declared-element reference bookkeeping only. A reference string is not verified evidence. They reach no legal conclusion, compute no legal deadline, and advise no legal action. Row 1305 groups supplied decimal-string time and fee records into draft invoices. Subtotals use 64 significant digits; batch totals may round at 28. It does not pay, post to a ledger, perform trust accounting or verify records as true.

The module router includes all ten dedicated adapters; tests use the mounted application client and the production RS256 identity fixture. Existing engine tests remain separate. Ledger evidence points to the dedicated engine, adapter and tests. Broad feature status remains PARTIAL.

## Restricted scope

closed-scoped, NOT literal breadth. Accepted only as what the engine's own module docstring states it does, over caller-supplied inputs, and only to the extent its own tests prove. It does not establish the row's literal capability and authorizes, executes, merges, releases or approves nothing.

FULL-SUITE UNVERIFIED. Targeted engine and mounted-route tests do not establish correctness of every application module.
