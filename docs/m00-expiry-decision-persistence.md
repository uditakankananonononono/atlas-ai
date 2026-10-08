# Expired decision persists refusal state

Deciding an overdue pending approval used to apply expiry and then raise inside
the database transaction. The conflict rolled back both expiry and its audit
event. A later get silently reapplied expiry, masking this state loss.

The decision path now commits expiry/event, publishes expiry and fires registered
callbacks with the expired view before returning conflict. Direct SQLite row/audit
checks, callback and event assertions verify this without get-triggered repair.
Repeated decisions remain conflicts and add no expiry event or callback.

This is not a concurrent decision CAS repair. Lazy get/list/sweep races, consumed
permit semantics, post-commit broadcaster failure and cross-process callbacks
remain unchanged. No effects execute in this module. No full M00 closure.
