from fastapi import Depends, FastAPI, HTTPException
import os
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
from app.modules.m02_competition_manager.profile_routes import router as competition_profile_router
from app.modules.m25_knowledge_copilot.routes import router as knowledge_copilot_router
from app.modules.m20_general_cognitive_worker.agi_routes import router as agi_runtime_router
from app.modules.m20_general_cognitive_worker.product_orchestrator_routes import router as product_orchestrator_router

configure_telemetry()
app = FastAPI(title="Atlas AI", version="0.1.0")
app.add_middleware(ProductionBoundaryMiddleware,limit_per_minute=int(os.getenv("ATLAS_RATE_LIMIT_PER_MINUTE","120")))
app.include_router(router, prefix="/api/v1")
app.include_router(google_grounding_router,prefix="/api/v1",dependencies=[Depends(require_tenant)])
app.include_router(acceptance_router,prefix="/api/v1",dependencies=[Depends(require_tenant)])
app.include_router(runtime_router,prefix="/api/v1",dependencies=[Depends(require_tenant)])
app.include_router(approved_execution_router,prefix="/api/v1",dependencies=[Depends(require_tenant)])
app.include_router(claire_personalization_router,prefix="/api/v1",dependencies=[Depends(require_tenant)])
app.include_router(competition_profile_router,prefix="/api/v1",dependencies=[Depends(require_tenant)])
app.include_router(knowledge_copilot_router,prefix="/api/v1",dependencies=[Depends(require_tenant)])
app.include_router(agi_runtime_router,prefix="/api/v1",dependencies=[Depends(require_tenant)])
app.include_router(product_orchestrator_router,prefix="/api/v1",dependencies=[Depends(require_tenant)])
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
