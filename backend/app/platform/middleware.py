from __future__ import annotations
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import HTTPException
from app.auth.context import require_tenant
from starlette.responses import JSONResponse
from app.platform.reliability import TenantRateLimiter,RateLimitExceeded
from app.platform.observability import bind_trace
class ProductionBoundaryMiddleware(BaseHTTPMiddleware):
 def __init__(self,app,limit_per_minute:int=120):super().__init__(app);self.limiter=TenantRateLimiter(limit_per_minute)
 async def dispatch(self,request,call_next):
  trace=bind_trace(request.headers.get('traceparent'))
  if request.url.path not in {'/health','/ready'}:
   try:
    principal=await require_tenant(authorization=request.headers.get('authorization'),x_atlas_tenant=request.headers.get('x-atlas-tenant'),x_atlas_actor=request.headers.get('x-atlas-actor'))
    tenant,actor=principal.tenant_id,principal.actor_id
   except HTTPException as exc:
    return JSONResponse({'detail':exc.detail},status_code=exc.status_code,headers={'traceparent':trace})
   try:self.limiter.check(tenant,actor)
   except RateLimitExceeded:return JSONResponse({'detail':'rate limit exceeded'},status_code=429,headers={'traceparent':trace})
  response=await call_next(request);response.headers['traceparent']=trace;return response
