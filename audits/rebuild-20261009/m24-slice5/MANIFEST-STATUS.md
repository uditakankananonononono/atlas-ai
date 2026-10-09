# Slice5 manifest status after independent reproduction

- acceptance-nodes-repaired96.txt:96 collected slice5 nodes, independently reproduced96/96PASS by executor, including SQLite+PG/SIGKILL/migrations.
- affected-nodes-repaired669.txt:669 collected affected nodes, not acombinedexecutedPASSresult. Builder's completedsets cover667distinctpassingnodes across runs; executor's fresh96-node run is overlapping, not additive.
- tests/test_billing.py::test_money_requires_proposal_and_approved_execution: independently confirmed pre-existing failure on clean base1c28cd3c, same error lines as candidate (legacy direct checkout vs fail-closed readiness).
- tests/test_billing.py::test_cancel_and_invoice_are_separate_tenant_bound_approval_actions: independently confirmed pre-existing failure on clean base1c28cd3c, same error lines as candidate (fixture Repo lacks tenant_billing).

Neither failure erased, silently fixed, or counted asPASS. No fullsuite/CI claim. Sourcecandidatebbb112de9528ea5a2dc0f56417342e46bee0cba8; merged with audit-onlymainbeaa05c7. INACTIVE only, no worker/readiness/defaultadmission/providertraffic.
