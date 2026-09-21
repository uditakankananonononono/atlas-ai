# Cloud SQL backup and restore runbook

No backup claim is made by this repository. Production proof needs a real project, instance, retention policy and restore drill.

1. Record project, instance, source backup ID, operator and incident/change ticket.
2. Confirm automated backups, point-in-time recovery and deletion protection are enabled in Cloud SQL.
3. Restore into a new instance. Never overwrite the only production database.
4. Run migration revision check, row-count checks, tenant-isolation probes and application smoke tests.
5. Freeze writes, take a final backup, switch the database secret to the restored instance, deploy a new revision and observe error/latency SLIs.
6. Roll back by restoring the prior secret version and sending traffic to the prior Cloud Run revision.
7. Attach timestamps and provider operation IDs to the drill record. Redact secrets and personal data.
