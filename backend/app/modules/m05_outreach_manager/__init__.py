"""Outreach Manager module registration."""

from app.modules.types import ModuleSpec

from .routes import router
from .service import Service

spec = ModuleSpec(
    id=5,
    slug="outreach-manager",
    name="Outreach Manager",
    router=router,
    service_type=Service,
)

__all__ = ["Service", "router", "spec"]
