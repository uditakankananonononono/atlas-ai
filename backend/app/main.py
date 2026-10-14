from fastapi import Depends, FastAPI, HTTPException
import os
from app.platform.metrics import MetricsMiddleware, scrape
from app.platform.middleware import ProductionBoundaryMiddleware
from app.platform.telemetry import configure as configure_telemetry
from app.api.routes import router
from app.modules.registry import IMPLEMENTED_SPECS
from app.auth.context import require_tenant
from app.integrations.routes import router as google_grounding_router
from app.integrations.acceptance_routes import router as acceptance_router
from app.runtime.routes import router as runtime_router
from app.runtime.approved_execution_routes import router as approved_execution_router
from app.modules.m21_claire.personalization_routes import router as claire_personalization_router
from app.modules.m21_claire.owner_interview_routes import router as claire_interview_router
from app.modules.m21_claire.persistent_journal_routes import router as claire_journal_router
from app.modules.m21_claire.opportunity_triage_routes import router as claire_opportunity_router
from app.modules.m21_claire.social_signal_review_routes import router as claire_social_signal_router
from app.modules.m02_competition_manager.profile_routes import router as competition_profile_router
from app.modules.m25_knowledge_copilot.routes import router as knowledge_copilot_router
from app.modules.m20_general_cognitive_worker.agi_routes import router as agi_runtime_router
from app.modules.m20_general_cognitive_worker.product_orchestrator_routes import router as product_orchestrator_router
from app.core.model_routes import router as model_catalog_router
from app.self_improve.routes import router as self_improve_router
from app.modules.m20_general_cognitive_worker.training_data_routes import mount_training_routes

configure_telemetry()
app = FastAPI(title="Atlas AI", version="0.1.0")
app.add_middleware(ProductionBoundaryMiddleware,limit_per_minute=int(os.getenv("ATLAS_RATE_LIMIT_PER_MINUTE","120")))
app.add_middleware(MetricsMiddleware)
app.add_api_route("/metrics", scrape, methods=["GET"], include_in_schema=False)
app.include_router(router, prefix="/api/v1")
app.include_router(google_grounding_router,prefix="/api/v1",dependencies=[Depends(require_tenant)])
app.include_router(acceptance_router,prefix="/api/v1",dependencies=[Depends(require_tenant)])
app.include_router(runtime_router,prefix="/api/v1",dependencies=[Depends(require_tenant)])
app.include_router(approved_execution_router,prefix="/api/v1",dependencies=[Depends(require_tenant)])
app.include_router(claire_personalization_router,prefix="/api/v1",dependencies=[Depends(require_tenant)])
app.include_router(claire_interview_router,prefix="/api/v1",dependencies=[Depends(require_tenant)])
app.include_router(claire_journal_router,prefix="/api/v1",dependencies=[Depends(require_tenant)])
app.include_router(claire_opportunity_router,prefix="/api/v1",dependencies=[Depends(require_tenant)])
app.include_router(claire_social_signal_router,prefix="/api/v1",dependencies=[Depends(require_tenant)])
app.include_router(competition_profile_router,prefix="/api/v1",dependencies=[Depends(require_tenant)])
app.include_router(knowledge_copilot_router,prefix="/api/v1",dependencies=[Depends(require_tenant)])
app.include_router(agi_runtime_router,prefix="/api/v1",dependencies=[Depends(require_tenant)])
app.include_router(product_orchestrator_router,prefix="/api/v1",dependencies=[Depends(require_tenant)])
app.include_router(model_catalog_router,prefix="/api/v1",dependencies=[Depends(require_tenant)])
app.include_router(self_improve_router,prefix="/api/v1",dependencies=[Depends(require_tenant)])
mount_training_routes(app)
from app.modules.m20_general_cognitive_worker.launch_quiz_c2_routes import mount_launch_quiz
mount_launch_quiz(app)
for module_spec in IMPLEMENTED_SPECS:
    app.include_router(module_spec.router, prefix="/api/v1", dependencies=[Depends(require_tenant)])

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

@app.get("/ready")
def ready() -> dict[str, object]:
    """Return 200 only when configuration, database, Redis and migrations are ready."""
    from app.platform.config import ProductionConfig, ConfigError
    from app.platform.health import live_readiness
    try:
        config = ProductionConfig.from_env()
    except ConfigError as exc:
        raise HTTPException(status_code=503, detail={"status": "not_ready", "configuration": False}) from exc
    healthy, checks = live_readiness()
    body = {"status": "ready" if healthy else "not_ready", "environment": config.environment, "checks": checks}
    if not healthy:
        raise HTTPException(status_code=503, detail=body)
    return body

# Row105: stateless bounded bookkeeping only, with route-level authentication.
from app.modules.m20_general_cognitive_worker.pre_suasion105_routes import router as pre_suasion105_router
app.include_router(pre_suasion105_router)
from app.modules.m20_general_cognitive_worker.legal_ethics1290_routes import router as row1290_router
app.include_router(row1290_router)
from app.modules.m20_general_cognitive_worker.professional_responsibility1291_routes import router as row1291_router
app.include_router(row1291_router)
from app.modules.m20_general_cognitive_worker.conflicts_of_interest1292_routes import router as row1292_router
app.include_router(row1292_router)
from app.modules.m20_general_cognitive_worker.jury_selection1284_routes import router as row1284_router
app.include_router(row1284_router)
from app.modules.m20_general_cognitive_worker.legal_malpractice1294_routes import router as row1294_router
app.include_router(row1294_router)

from app.modules.m20_general_cognitive_worker.due_process1265_routes import router as legal_1265_router
app.include_router(legal_1265_router, prefix="/api/v1")

from app.modules.m20_general_cognitive_worker.judicial_review1270_routes import router as legal_1270_router
app.include_router(legal_1270_router, prefix="/api/v1")

from app.modules.m20_general_cognitive_worker.international_law1271_routes import router as legal_1271_router
app.include_router(legal_1271_router, prefix="/api/v1")

from app.modules.m20_general_cognitive_worker.human_rights1273_routes import router as legal_1273_router
app.include_router(legal_1273_router, prefix="/api/v1")

from app.modules.m20_general_cognitive_worker.row849_routes import router as row849_router
app.include_router(row849_router, prefix="/api/v1")

from app.modules.m20_general_cognitive_worker.row1299_routes import router as row1299_router
app.include_router(row1299_router, prefix="/api/v1")

from app.modules.m20_general_cognitive_worker.legal_1295_routes import router as legal_1295_router
app.include_router(legal_1295_router, prefix="/api/v1")

from app.modules.m20_general_cognitive_worker.legal_1296_routes import router as legal_1296_router
app.include_router(legal_1296_router, prefix="/api/v1")

from app.modules.m20_general_cognitive_worker.legal_1297_routes import router as legal_1297_router
app.include_router(legal_1297_router, prefix="/api/v1")

from app.modules.m20_general_cognitive_worker.legal_1298_routes import router as legal_1298_router
app.include_router(legal_1298_router, prefix="/api/v1")


from app.modules.c32.psyche_routes import router as s29_psyche_router
app.include_router(s29_psyche_router,prefix='/api/v1')


from app.modules.c33.niches_routes import router as s210_niches_router
app.include_router(s210_niches_router,prefix='/api/v1')


from app.modules.c33.persona_routes import router as s212_persona_router
app.include_router(s212_persona_router,prefix='/api/v1')


from app.modules.c33.content_routes import router as s211_content_router
app.include_router(s211_content_router,prefix='/api/v1')


from app.modules.c34.industry_routes import router as s34_industry_router
app.include_router(s34_industry_router,prefix='/api/v1')


from app.modules.c34.tool_routes import router as s33_tool_router
app.include_router(s33_tool_router,prefix='/api/v1')
