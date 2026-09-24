# Builder claims

One line per active builder lane. Claim a component before building it; release it when merged.

| Lane | Component | Files | Status |
|---|---|---|---|
| atlas-builder-2026-09-24 | Core model layer: free-first routing, named-model catalog (Inkling/Fugu/Ultron), Inkling via HF router + self-hosted Inkling-Small | backend/app/core/providers.py, model_catalog.py, model_routes.py, scripts/inkling/, docs/OPEN_MODELS.md | shipped |
| atlas-builder-2026-09-24 | M20 planner/executive bound to free-first models | backend/app/modules/m20_general_cognitive_worker/model_adapters.py, routes.py binding | shipped |
| PB2 | M1 Opportunity Discovery live normalization | backend/app/modules/m01_opportunity_discovery/ | claimed |
| PB5 | M22 Tools Hub durable install pipeline | backend/app/modules/m22_* | claimed |
