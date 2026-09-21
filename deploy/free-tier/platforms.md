# Free-first deployment targets

The default target is the owner's paired PC using `deploy/local/docker-compose.yml`. It keeps the API, PostgreSQL and Redis on hardware the owner controls and incurs no cloud bill beyond the owner's existing electricity/network.

Optional public hosting must be selected only after checking the provider's current free-tier terms. Atlas does not claim an account, capacity, uptime or zero cost until deployment is observed.

- Render/Railway: deploy the Dockerfile when a suitable free allocation is available; attach provider PostgreSQL only within a confirmed free allowance. Sleeping, quotas and terms can change.
- Oracle Cloud Always Free: acceptable only if the owner creates an eligible account and free resources are actually available. Use the same container and local data services; never silently upgrade to paid capacity.
- Cloud Run: optional only within a confirmed free allowance, with billing guards. The user declined paid GCP, so it is not the default and no paid GCP dependency may block local operation.

Every target must retain final-submit approval gates, secrets outside Git, backups, tenant isolation and honest capacity reporting. When a free tier is unavailable or exhausted, stop and offer local paired-PC operation instead of spending.
