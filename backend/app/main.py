from fastapi import FastAPI
from app.api.routes import router

app = FastAPI(title="Atlas AI", version="0.1.0")
app.include_router(router, prefix="/api/v1")

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
