# Consumption refusal retains lazy expiry

Overdue pending consumption now commits expiry and its event before raising
conflict. Previously the raise inside the transaction rolled both back. Direct
SQLite state/audit tests demonstrate this without get reapplying lazy expiry.
Approved permit TTL semantics, permit replay and effects are unchanged. Lazy
consume does not add broadcaster/callback behavior; existing lazy read behavior
is preserved. No external execution, distributed signal or full M00 claim.
