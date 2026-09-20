from fastapi import Depends, FastAPI
from app.api.routes import router
from app.modules.registry import IMPLEMENTED_SPECS
from app.auth.context import require_tenant

app = FastAPI(title="Atlas AI", version="0.1.0")
app.include_router(router, prefix="/api/v1")
for module_spec in IMPLEMENTED_SPECS:
    app.include_router(module_spec.router, prefix="/api/v1", dependencies=[Depends(require_tenant)])

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
