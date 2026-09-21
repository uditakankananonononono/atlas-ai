from fastapi import Depends, FastAPI
from app.api.routes import router
from app.modules.registry import IMPLEMENTED_SPECS
from app.auth.context import require_tenant
from app.integrations.routes import router as google_grounding_router
from app.runtime.routes import router as runtime_router
from app.modules.m21_claire.personalization_routes import router as claire_personalization_router
from app.modules.m02_competition_manager.profile_routes import router as competition_profile_router
from app.modules.m25_knowledge_copilot.routes import router as knowledge_copilot_router

app = FastAPI(title="Atlas AI", version="0.1.0")
app.include_router(router, prefix="/api/v1")
app.include_router(google_grounding_router,prefix="/api/v1",dependencies=[Depends(require_tenant)])
app.include_router(runtime_router,prefix="/api/v1",dependencies=[Depends(require_tenant)])
app.include_router(claire_personalization_router,prefix="/api/v1",dependencies=[Depends(require_tenant)])
app.include_router(competition_profile_router,prefix="/api/v1",dependencies=[Depends(require_tenant)])
app.include_router(knowledge_copilot_router,prefix="/api/v1",dependencies=[Depends(require_tenant)])
for module_spec in IMPLEMENTED_SPECS:
    app.include_router(module_spec.router, prefix="/api/v1", dependencies=[Depends(require_tenant)])

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

@app.get("/ready")
def ready() -> dict[str, object]:
    """The deployment probe is conservative; deep dependency checks run in the configured adapter."""
    from app.platform.config import ProductionConfig, ConfigError
    try:
        config = ProductionConfig.from_env()
    except ConfigError as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"status": "ready", "environment": config.environment}
