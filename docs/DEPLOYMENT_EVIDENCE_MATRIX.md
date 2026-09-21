# Deployment evidence matrix

| Capability | Locally proven | Needs credentials | Needs production observation |
|---|---|---|---|
| Cloud Run service shape and config validation | YAML/static and tests | GCP project, Artifact Registry, runtime service account | revision health, autoscaling, cold starts |
| Managed PostgreSQL / Redis references | URL validation and readiness contracts | Cloud SQL, Memorystore, IAM/network | failover, latency, capacity, restore drill |
| Secret providers | injected fake-client tests; no committed values | Secret Manager IAM or a real Vault client/token | rotation and access-log evidence |
| Tenant auth / rate limit / idempotency | isolated keyed behavior tests | production OIDC issuer and shared durable stores | attack traffic, cardinality and contention |
| Timeouts/retries/circuit breaker | deterministic failure tests | dependency endpoints | outage behavior and tuned thresholds |
| Structured logging / trace propagation | formatter/propagation tests | Cloud Logging and OTEL exporter config | trace continuity and sampling cost |
| Backup and rollback | reviewed runbooks | provider backups and deploy permissions | timed restore and rollback drills |
| CI/SBOM/scanning | workflow and local tests | GitHub Actions and registry | signed artifacts and scan history |
| SLO/alerts/load tests | targets and harness | monitoring project and load environment | error budget, alert delivery, capacity curve |

## Nine scale claims deliberately blocked

1. Cloud Run serving production traffic.
2. Kubernetes orchestration.
3. Full service-to-service mTLS.
4. Live HashiCorp Vault operation.
5. Hosted Grafana dashboards.
6. A 32 GB Ollama runtime.
7. Proven autoscaling maximums.
8. Tested Cloud SQL disaster recovery/RPO/RTO.
9. Measured production load capacity.

Each stays blocked until a real GCP project, budget, credentials or hardware evidence and production observations exist. Local manifests do not satisfy them.
