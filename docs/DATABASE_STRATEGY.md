# Database and vector test strategy

- Production is PostgreSQL 16 with pgvector. `ProductionConfig` rejects SQLite.
- Production startup runs Alembic and readiness must reject a stale migration.
- Unit tests may use isolated SQLite only for domain/repository logic that does not depend on PostgreSQL semantics.
- CI's full backend job runs on PostgreSQL + pgvector. Vector integration tests must use PostgreSQL and verify tenant predicates plus ANN ordering.
- Schema creation through `Base.metadata.create_all` is development/test-only. New production changes require an Alembic revision.
- Embeddings are fixed at 1024 dimensions. Ingestion must retain tenant, namespace, source locator and citation metadata; retrieval must preserve those fields through ranking.
