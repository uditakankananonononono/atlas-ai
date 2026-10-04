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

configure_telemetry()
app = FastAPI(title="Atlas AI", version="0.1.0")
app.add_middleware(ProductionBoundaryMiddleware,limit_per_minute=int(os.getenv("ATLAS_RATE_LIMIT_PER_MINUTE","120")))
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
for module_spec in IMPLEMENTED_SPECS:
    app.include_router(module_spec.router, prefix="/api/v1", dependencies=[Depends(require_tenant)])

class M20CleanAliasMiddleware:
    """Compat-preserving alias. The legacy doubled path /api/v1/api/modules/20/... (used by the shipped frontend) is
    unchanged. A request to /api/v1/modules/20/... is rewritten to it BEFORE routing, so it runs the identical handlers
    and the identical require_tenant / rate-limit dependencies and middleware. Limits: the alias is NOT listed in
    OpenAPI, and only the m20 prefix is aliased (inner doubled segments such as .../api/modules/20/runtime remain)."""
    OLD, NEW = "/api/v1/api/modules/20", "/api/v1/modules/20"

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            path = scope["path"]
            if path == self.NEW or path.startswith(self.NEW + "/"):
                scope = dict(scope)
                scope["path"] = self.OLD + path[len(self.NEW):]
                if scope.get("raw_path"):
                    scope["raw_path"] = scope["path"].encode()
        await self.app(scope, receive, send)


app.add_middleware(M20CleanAliasMiddleware)  # added last = outermost


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
