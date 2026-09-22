# Atlas operations runbook

This runbook covers the owner-controlled Docker deployment. It does not claim public-cloud readiness.

## Start and verify

1. Copy `deploy/local/.env.example` to `.env.local`; replace every `CHANGE_ME` value and keep the file outside version control.
2. Configure a real OIDC issuer, audience and tenant claim. Atlas rejects production requests without verified identity.
3. Run `./scripts/bootstrap_local.sh`.
4. Require both `GET /health` and `GET /ready` to return 200. `/ready` checks configuration, PostgreSQL, Redis and the exact Alembic head.
5. Sign in and complete the first-run checklist. Run one read-only module workflow before enabling provider keys.

## Backup and restore drill

Back up PostgreSQL with `pg_dump -Fc` and the Redis AOF volume while writes are stopped or through a snapshot method documented by the host. Encrypt backups, record the Atlas image digest and Alembic head beside them, and keep at least one copy off the host.

A backup is not accepted until a separate disposable stack restores it, `/ready` passes, the tenant can read known records, and an approval audit record matches the source environment. Record duration and hashes. Never test restore over the only production database.

## Upgrade and rollback

1. Back up and run the restore drill before migrations.
2. Build a digest-pinned image. Run tests and `scripts/module_acceptance.py --check`.
3. Stop workers, run the one-shot migration service, then start API and workers.
4. If `/ready` fails, keep traffic stopped. Roll application code back only when the database revision is compatible. Destructive migration rollback needs an explicit tested downgrade or database restore.

## Incidents

- **API live, readiness failing:** inspect the boolean checks. Do not route traffic until all pass.
- **Database unavailable:** stop workers to prevent retry floods; restore connectivity; verify Alembic head.
- **Redis unavailable:** external effects remain stopped because queues and coordination are uncertain. Restore Redis and inspect pending approvals before workers resume.
- **Suspected credential leak:** disable the affected provider credential, rotate it at the provider, update the secret store, restart affected services, and inspect provider audit logs. Do not paste secrets into issues or chat.
- **Unexpected send, submission or charge:** stop the executor, preserve approval and provider receipts, revoke credentials if needed, and reconcile exact external state before retrying.

## Honest operating limits

Local tests and manifests do not prove uptime, load capacity, backup recovery time, provider behavior, browser selector stability, payment correctness or security under attack. Record each live acceptance separately with version, environment, input hash, result and immutable receipt.
