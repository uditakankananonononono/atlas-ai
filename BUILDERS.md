# Builder claims

One line per active builder lane. Claim a component before building it; release it when merged.

| Lane | Component | Files | Status |
|---|---|---|---|
| atlas-builder-2026-09-24 | Core model layer: free-first routing, named-model catalog (Inkling/Fugu/Ultron), Inkling via HF router + self-hosted Inkling-Small | backend/app/core/providers.py, model_catalog.py, model_routes.py, scripts/inkling/, docs/OPEN_MODELS.md | shipped |
| atlas-builder-2026-09-24 | M20 planner/executive bound to free-first models | backend/app/modules/m20_general_cognitive_worker/model_adapters.py, routes.py binding | shipped |
| atlas-builder-2026-09-24 | M00 approval impact preview (drift check before consume) | backend/app/modules/m00_approval_center/impact.py, routes.py, workers/tasks.py | shipped |
| atlas-builder-2026-09-24 | M02 evidence completeness score | backend/app/modules/m02_competition_manager/evidence.py, integrated_application.py, routes.py | shipped |
| atlas-builder-2026-09-24 | M02 evidence sources from stored profile corpus | evidence.py (resolve_sources, score_from_corpus), profile_corpus.py (get_many), routes.py | shipped |
| atlas-builder-2026-09-24 | M05 relationship-aware contact cadence | backend/app/modules/m05_outreach_manager/cadence.py, campaigns.py, routes.py | shipped |
| atlas-builder-2026-09-24 | M06 cross-platform adaptation preview (claim/citation parity + limits) | backend/app/modules/m06_social_media_manager/adaptation.py, service.py, routes.py | shipped |
| atlas-builder-2026-09-24 | M06 scheduling gate on adaptation preview | service.py request_schedule, schemas.py ScheduleIn | shipped |
| atlas-builder-2026-09-24 | M07 deliverable obligation tracker | backend/app/modules/m07_brand_collaboration/obligations.py, routes.py | shipped |
| atlas-builder-2026-09-24 | M08 free-first experiment board | backend/app/modules/m08_startup_growth/experiments.py, routes.py | shipped |
| atlas-builder-2026-09-24 | M08 analytics CSV import (Plausible/mapped) | backend/app/modules/m08_startup_growth/analytics_import.py, experiments.py, routes.py | shipped |
| atlas-builder-2026-09-24 | M09 durable contradiction revisions + source-byte and signature checks | backend/app/modules/m09_knowledge_workspace/revision_store.py, routes.py | shipped |
| atlas-builder-2026-09-24 | M11 governed risk-evidence ingest (registry key + signature + provider fetch + immutable store) | backend/app/modules/m11_calendar_intelligence/governed_risk_ingest.py, routes.py | shipped |
| atlas-builder-2026-09-24 | M12 checkpoint worker leases + registry-verified receipts | backend/app/modules/m12_ai_research_lab/checkpoint_worker.py, routes.py | shipped |
| atlas-builder-2026-09-24 | M13 capture-bound single-use submit approvals | backend/app/modules/m13_browser_agent/capture_bound_submit.py, routes.py | shipped |
| atlas-builder-2026-09-24 | M03 agency schema packs (NSF GRFP first) | backend/app/modules/m03_grant_writer/schema_packs.py, data/schema_packs/, routes.py | shipped |
| atlas-builder-2026-09-24 | M05 per-tenant cadence policy + contact timeline | cadence.py (CadencePolicyStore), campaigns.py, routes.py | shipped |
| atlas-builder-2026-09-24 | M07 contract -> draft obligations (local model, owner confirms) + attention digest | contract_extraction.py, obligations.py, routes.py | shipped |
| PB2 | M1 Opportunity Discovery live normalization | backend/app/modules/m01_opportunity_discovery/ | claimed |
| PB5 | M22 Tools Hub durable install pipeline | backend/app/modules/m22_* | claimed |
