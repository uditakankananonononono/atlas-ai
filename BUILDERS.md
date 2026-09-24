# Builder claims

One line per active builder lane. Claim a component before building it; release it when merged.

| Lane | Component | Files | Status |
|---|---|---|---|
| atlas-builder-2026-09-24 | Core model layer: free-first routing, named-model catalog (Inkling/Fugu/Ultron), Inkling via HF router + self-hosted Inkling-Small | backend/app/core/providers.py, model_catalog.py, model_routes.py, scripts/inkling/, docs/OPEN_MODELS.md | shipped |
| atlas-builder-2026-09-24 | M20 planner/executive bound to free-first models | backend/app/modules/m20_general_cognitive_worker/model_adapters.py, routes.py binding | shipped |
| atlas-builder-2026-09-24 | M00 approval impact preview (drift check before consume) | backend/app/modules/m00_approval_center/impact.py, routes.py, workers/tasks.py | shipped |
| atlas-builder-2026-09-24 | M02 evidence completeness score | backend/app/modules/m02_competition_manager/evidence.py, integrated_application.py, routes.py | shipped |
| atlas-builder-2026-09-24 | M02 evidence sources from stored profile corpus | evidence.py (resolve_sources, score_from_corpus), profile_corpus.py (get_many), routes.py | shipped |
| PB2 | M1 Opportunity Discovery live normalization | backend/app/modules/m01_opportunity_discovery/ | claimed |
| PB5 | M22 Tools Hub durable install pipeline | backend/app/modules/m22_* | claimed |
