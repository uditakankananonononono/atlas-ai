# Proposed production SLOs and alerts

These are configuration targets, not observed achievements. Once production exists: 99.9% successful API requests over 30 days (excluding valid 4xx), p95 latency under 1 s, and 99.95% readiness. Page on multi-window burn rates (14.4x for 5m/1h and 6x for 30m/6h), auth failures above baseline, stale migrations, Cloud SQL saturation, Redis memory pressure and queue age. Every alert needs a runbook and test notification in the real project.
