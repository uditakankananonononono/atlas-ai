# Modules 12 and 13

Module 12 adds a capability/cost/latency/quality router, validated YAML DAGs, concurrent ready-node execution, declared dependency passing, bounded retries, log-prob confidence, fallback models, and self-critique. Bind its model provider and Celery-backed node runner in application dependency overrides.

Module 13 adds Playwright session contexts, HAR recording, navigate/fill/screenshot/extract routes, heuristic form matching, an allow-listed VLM loop with a hard step cap, public-network URL validation, durable tenant-scoped audit records, and Module 0 approval requests. Submit approval binds tenant, session, selector, exact form-value digest, and screenshot. Changed content, denied/pending approvals, or reused approvals fail closed.

Production setup: add PyYAML and Playwright, install Chromium, start/close `PlaywrightSessions` in FastAPI lifespan, and configure an explicit host allow-list. Persistent sessions default off and the caller may enable them only for legally permitted sites. Store HAR/screenshots in tenant-isolated object storage with retention and redaction.
