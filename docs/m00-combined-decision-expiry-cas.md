# Combined decision and expiry transitions

This tree retains decision-path CAS from ded53a4a and the peer-authored lazy-expiry
helper from 1e4ebf2746c506417b36d5713e3242b88b285bcc (Instinct Agent).
Neither standalone repair substitutes for the other. The imported helper refreshes
competing committed state, conditionally expires pending overdue rows and reports
only successful transitions to the sweep. Decision updates also require pending,
not-overdue state and one changed row before adding their audit event.

Both original race controls remain. Combined deterministic SQLite controls cover
get, list, sweep and overdue-decision reads losing to a committed denial, plus a
stale decision losing to committed expiry. Losing paths add no duplicate event or
callback in those controls. M03 corpus, destination and temporal tests run on this
same tree. These are controlled sequential interleavings, not production stress.

The standalone decision document describes its original candidate, not the
combined tree. Lazy expiry now has conditional updates in this tree, but no claim
of universal race safety, exactly-once notification, durable cross-process
callbacks, PostgreSQL lock/deadlock correctness or consumption/dispatch safety.
Pending-review TTL has not been reinterpreted as an approved-permit deadline.
