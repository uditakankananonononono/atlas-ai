# Approval lists classify pending expiry before the row limit

Pending-filter queries exclude overdue pending rows; expired-filter queries also
include overdue pending rows, then persist selected expiries using the existing
CAS helper. Filtering occurs before limit, so an overdue newest row no longer
occupies the sole pending result. A final status check excludes rows that changed
status during lazy expiry. Tests use actual SQLite rows and an injected clock.

Pending-only list calls do not persist excluded overdue rows. Expired/unfiltered
reads or the sweeper can do that. Concurrent changes can still underfill a page;
no snapshot/pagination consistency is promised. Tenant/module filters stay in SQL.
No new signals/callbacks, external effects, or full M00 closure.
