# Technical-spec gap acceptance status

Implemented code/config paths in this patch: shadcn-style owned components and Radix dependencies, Recharts, ChromaDB, Redis Streams, RabbitMQ/Kombu, LangChain Runnable pipeline, Selenium fallback, PyMuPDF/Tesseract/unstructured document pipeline, APScheduler, DeepSeek and Ollama providers, gateway rate limiting, refresh-token rotation/replay prevention, Kubernetes/HPA/network policy, strict Istio mTLS policy, authenticated Vault client, API-key envelope encryption, OpenTelemetry collector/exporter setup, Google Cloud Logging exporter, Grafana dashboard, Cloud Storage runtime adapter, Cloud Run/Cloud SQL configuration, local 32GB Ollama profile, Compose acceptance script, and Celery scaling benchmark.

Still requires live-environment acceptance before a COVERED verdict:

- Supabase or Cloud SQL live connectivity, migration and backup/restore drill.
- Browserless/custom Chrome farm and Selenium Grid live session tests.
- Google/GitHub IdP end-to-end login and refresh session integration.
- HashiCorp Vault live authentication, rotation and revocation test.
- Cloud Storage live upload/version/retention test.
- Kubernetes/GKE apply, readiness, HPA and rollback test.
- Service-mesh proof that plaintext east-west traffic is rejected.
- OTLP trace arrival in Google Cloud Logging and metric arrival in Grafana.
- Docker Compose full-stack acceptance on the target 32GB paired PC.
- Horizontal Celery benchmark on actual worker nodes, Redis and representative jobs.
- Universal-LTM proof that every module's generated and ingested artifacts traverse the common ingestion pipeline.

Version mismatches remain explicit: the repo uses Next.js 15 and React 19, newer than the literal Next.js 14/React 18 requirements. They are not exact-version matches.
