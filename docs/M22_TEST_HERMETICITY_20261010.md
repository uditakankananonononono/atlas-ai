# M22 approval test isolation

Three CWD-dependent M22 tests now opt into isolated_m22_approvals fixture.
Real Module0 service/tables, per-test temporary SQLite and restored singleton.
No product change. Independent111PASS1SKIP in empty CWD, populated CWD, and
env-var nonexistent DB path; mutation confirms fixture makes these hermetic.
Residual: opt-in per test, other ApprovalStore-using tests not scanned. This
fix closes these three nodes, not a repo-wide test database isolation claim.
