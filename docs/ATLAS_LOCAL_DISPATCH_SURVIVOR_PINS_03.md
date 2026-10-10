# LOCAL-DISPATCH-03 guard pins

Test-only follow-up on7f650e04. Product/migration bytes unchanged. Ten paired
SQLite/PostgreSQL nodes pin resource CPU reservation, claim-time source drift,
job-count cap with three one-task jobs (task cap does not mask it), local wave
maximum with three real approved tasks, and enqueue-time slot expiry.

Green10 PASS18.11s. Five named isolated mutations each produce2 FAIL, one per
SQL backend; restored source afterward. Enqueue expiry is now a clean real-PG
mutation receipt, not a survivor inferred from the prior initdb failure.

Claim-source control self-consistently updates wave/job digests and execution
approval payload while retaining the original admission source snapshot. This
isolates that boundary without a misleading fail at an earlier digest check.
No execution/provider/deployment scale claim is added. Operational1000 remains
OPEN. Other survivor guards (finish slot token/expiry, publication state/fence)
remain documented and not claimed closed by this unit. Full regression receipts
on7f650e04 are historical, not relabeled as this candidate's new replay.
