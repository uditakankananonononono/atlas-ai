"""Explicit router factory. Integration owner must mount it once.

No global live connectors. Body tenant fields and effect parameters rejected.
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict, Field
from app.auth.context import TenantContext, require_tenant
from .core import Scanner, Refusal


class SanitizedRoute(APIRoute):
    """Do not echo untrusted invalid payloads in validation-error responses."""
    def get_route_handler(self):
        handler = super().get_route_handler()
        async def safe_handler(request):
            try:
                return await handler(request)
            except RequestValidationError as exc:
                raise HTTPException(422, 'SOCIAL_REFUSED_SCHEMA') from exc
        return safe_handler


class ExportRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    connector: str = Field(min_length=1, max_length=80)
    payload: str = Field(min_length=1, max_length=2_000_000)
    as_of: str = Field(min_length=1, max_length=80)


def make_router(scanner: Scanner | None = None) -> APIRouter:
    service = scanner if scanner is not None else Scanner()
    router = APIRouter(prefix='/api/v1/c33/self-feed', tags=['c33-self-feed'], route_class=SanitizedRoute)

    @router.post('/run')
    def run(body: ExportRequest, tenant: TenantContext = Depends(require_tenant)):
        try:
            return service.run(tenant_id=tenant.tenant_id, connector=body.connector,
                               payload=body.payload.encode('utf-8'), as_of=body.as_of)
        except UnicodeError as exc:
            raise HTTPException(422, 'SOCIAL_REFUSED_SCHEMA') from exc
        except Refusal as exc:
            raise HTTPException(422, exc.code) from exc

    @router.get('/report')
    def report(report_id: str, tenant: TenantContext = Depends(require_tenant)):
        try:
            return service.report(tenant.tenant_id, report_id)
        except Refusal as exc:
            raise HTTPException(404, exc.code) from exc

    return router
