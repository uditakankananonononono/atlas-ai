import os
from dataclasses import dataclass
from fastapi import Header, HTTPException

@dataclass(frozen=True)
class TenantContext:
    tenant_id: str
    actor_id: str

async def require_tenant(
    x_atlas_tenant: str | None = Header(default=None),
    x_atlas_actor: str | None = Header(default=None),
) -> TenantContext:
    """Development auth boundary; production swaps headers for verified OIDC claims."""
    if os.getenv("ATLAS_ENV", "development") == "development":
        return TenantContext(x_atlas_tenant or "local", x_atlas_actor or "local-user")
    if not x_atlas_tenant or not x_atlas_actor:
        raise HTTPException(status_code=401, detail="authenticated tenant and actor are required")
    return TenantContext(x_atlas_tenant, x_atlas_actor)
