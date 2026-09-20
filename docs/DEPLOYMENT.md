# Production deployment and scaling

`docker-compose.prod.yml` separates API, collection, AI/document and browser queues so one expensive workload cannot starve approvals or calendar/email work. Workers acknowledge after completion, reject jobs lost with a worker, prefetch one task, and retry broker connection at startup. Scale replicas independently. The browser lane stays low-concurrency; collection uses quotas and source cadence; AI workers get larger memory limits.

Production configuration is fail-closed: database, Redis, encryption keys and datastore passwords are required through `.env.production` or an orchestrator secret store. Never commit the real file. PostgreSQL and Redis have durable volumes and health checks; API/workers restart automatically. Use managed PostgreSQL backups/PITR, TLS at ingress and databases, Redis TLS/private networking, image digest pinning, log/metric aggregation, migration jobs, alerting, and at least two availability zones before claiming high availability.

Compose is a single-host reference. At larger scale, map each service to Kubernetes Deployments, autoscale on queue depth/CPU, keep Celery Beat single-replica with a lease, and use managed Postgres/Redis/object storage. Browser workers require isolated sandboxes and egress policy. Paid providers remain disabled until their live quotas and costs are configured in Atlas.
