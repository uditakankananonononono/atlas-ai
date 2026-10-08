# Lazy expiry compare-and-set

Expiry now conditionally updates only a still-pending overdue row, refreshes its
state, and adds an expiry event only when exactly one row changes. get/list and
decision/consume overdue checks share the helper. The sweep adds only successful
expiry IDs to its published/callback list.

A real SQLite competing transaction approves before deadline after the outer
get fetches its pending row. The clock advances past deadline before lazy expiry.
Old code overwrites approved with expired; repaired get retains the committed
approval and created/approved events without adding expiry.

This is expiry-path CAS only, not the separate pending-decision CAS candidate.
The base decision write still has a stale-update gap. PostgreSQL lock/deadlock
behavior, deletion races and cross-process signal delivery remain unproven.
No effects execute here and no full M00 closure is claimed.
