# Builder claims

One line per active builder lane. Claim a component before building it; release it when merged.

| Lane | Component | Files | Status |
|---|---|---|---|
| atlas-builder-2026-09-24 | Core model layer: free-first routing, named-model catalog (Inkling/Fugu/Ultron), Inkling via HF router + self-hosted Inkling-Small | backend/app/core/providers.py, model_catalog.py, model_routes.py, scripts/inkling/, docs/OPEN_MODELS.md | shipped |
| atlas-builder-2026-09-24 | M20 planner/executive bound to free-first models | backend/app/modules/m20_general_cognitive_worker/model_adapters.py, routes.py binding | shipped |
| atlas-builder-2026-09-24 | M00 approval impact preview (drift check before consume) | backend/app/modules/m00_approval_center/impact.py, routes.py, workers/tasks.py | shipped |
| atlas-builder-2026-09-24 | M02 evidence completeness score | backend/app/modules/m02_competition_manager/evidence.py, integrated_application.py, routes.py | shipped |
| PB2 (branch `pb2`) | M1 Opportunity Discovery live NLP wiring: production routes use spaCy NER + dateparser deadlines and real embedding match scores (free in-process fastembed/BGE default, Ollama or BYOK OpenAI as config), per-opportunity engine provenance, honest fallback only on missing optional deps | backend/app/modules/m01_opportunity_discovery/nlp_stack.py, service.py/routes.py/schemas.py wiring, tests/modules/test_m01_nlp_stack.py | shipped on pb2 (2026-09-24 11:18 IST), awaiting integrator merge (M1 only) |
| PB2 (branch `pb2`) | M10 Email Assistant: first real M00 drift probe (send/outreach state: thread latest message, recipients, draft body hash, already-sent check) registered for M10 reply approvals, then M10 Next items | backend/app/modules/m10_email_assistant/drift_probe.py, M10 registration, tests/modules/test_m10_drift_probe.py | drift probe shipped on pb2 (11:25 IST); M10 Next items in progress |
| PB5 | M22 Tools Hub durable install pipeline | backend/app/modules/m22_* | claimed |
