# M22 approval test isolation

Three CWD-dependent M22 tests now opt into isolated_m22_approvals fixture.
Real Module0 service/tables, per-test temporary SQLite and restored singleton.
No product change. Independent111PASS1SKIP in empty CWD, populated CWD, and
env-var nonexistent DB path; mutation confirms fixture makes these hermetic.
Residual: opt-in per test, other ApprovalStore-using tests not scanned. This
fix closes these three nodes, not a repo-wide test database isolation claim.

## Generalized fixture and Claire extension
Fixture renamed isolated_m00_approvals with M22 compatibility alias. Exactly three
Claire nodes now opt in. Independent real rows/events probe confirms1/2/11request
and created-event rows per node; repaired tests assert approval status, NOT event
persistence. Event-loss coverage is a separate optional future unit. Zero product
change, other ApprovalStore tests not scanned. Historical02a75fbd and0dece509
missing-table failures reproduced, then clean/populated repair counts match;
on cursor453dd695 combined391PASS1SKIP opt-in ATLAS_LIVE_REGISTRY.
