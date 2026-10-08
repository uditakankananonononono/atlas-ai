# Pending approval decision compare-and-set

A decision now updates only a still-pending, not-overdue row using a conditional
SQL update, checks one changed row, refreshes it and adds the decision event in
the same transaction. A competing committed decision cannot be overwritten using
a stale fetched ORM row. Conflict produces no losing event/callback.

The test opens a real SQLite competing service transaction after the outer fetch
and commits denial before the outer approval update. The old code overwrites it;
the repaired code refuses and retains only created/denied audit events.

This is decision-path CAS only. Lazy get/list/sweep expiry still uses ORM writes
and can race; expired-decision branch likewise unchanged. PostgreSQL concurrent
lock/deadlock outcomes, consumption races and dispatch are unproven. No full M00
closure. The approval TTL appears to govern pending review; this patch does not
reinterpret it as an approved permit deadline.
