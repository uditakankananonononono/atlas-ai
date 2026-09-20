from fastapi import Depends, FastAPI
from app.api.routes import router
from app.modules.registry import IMPLEMENTED_SPECS
from app.auth.context import require_tenant
from app.integrations.routes import router as google_grounding_router
from app.runtime.routes import router as runtime_router

app = FastAPI(title="Atlas AI", version="0.1.0")
app.include_router(router, prefix="/api/v1")
app.include_router(google_grounding_router,prefix="/api/v1",dependencies=[Depends(require_tenant)])
app.include_router(runtime_router,prefix="/api/v1",dependencies=[Depends(require_tenant)])
for module_spec in IMPLEMENTED_SPECS:
    app.include_router(module_spec.router, prefix="/api/v1", dependencies=[Depends(require_tenant)])

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
