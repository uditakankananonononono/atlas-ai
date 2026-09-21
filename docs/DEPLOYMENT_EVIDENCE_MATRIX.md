# Deployment evidence matrix

Default: paired owner PC, free-first. Paid Google Cloud is declined and is not a dependency.

| Capability | Locally proven | Needs owner/account action | Needs production observation |
|---|---|---|---|
| Paired-PC container stack | Dockerfile and Compose validation | owner PC running Docker | uptime, thermals, network reachability |
| Local PostgreSQL / Redis | health contracts and persistent volumes | owner disk/backup destination | restore drill, capacity and latency |
| Optional free-tier host | portable container/config | owner-selected currently-free provider account | real quota, sleep behavior, uptime and egress |
| Secret providers | injected provider tests; no committed values | local environment/OS vault; optional provider secret store | rotation and access logs |
| Tenant auth / rate limit / idempotency | isolated keyed tests | production issuer/shared durable stores if public | attack traffic and contention |
| Reliability/logging | deterministic failures and structured logs | optional exporter destination | outage behavior, trace continuity |
| Backup/rollback | runbooks | owner backup destination | timed restore/rollback drill |
| CI/SBOM/scanning | scripts/local tests | GitHub workflow permission | signed artifacts and scan history |
| SLO/load tests | targets and bounded harness | chosen runtime | error budget and capacity curve |

## Claims deliberately blocked

1. Any paid GCP deployment or Cloud Run traffic beyond a confirmed free allowance.
2. Kubernetes orchestration.
3. Full service-to-service mTLS.
4. Live HashiCorp Vault operation.
5. Hosted Grafana dashboards.
6. A 32 GB Ollama runtime without verified owner hardware.
7. Proven autoscaling maximums.
8. Managed-cloud disaster recovery/RPO/RTO.
9. Measured production load capacity.

These stay blocked until real free capacity or owner hardware and production observations exist. Local manifests never satisfy them. Atlas must stop rather than incur a paid upgrade.
