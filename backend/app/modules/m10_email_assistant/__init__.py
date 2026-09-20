"""Email Assistant module registration."""

from app.modules.types import ModuleSpec

from .routes import router
from .service import Service

spec = ModuleSpec(
    id=10,
    slug="email-assistant",
    name="Email Assistant",
    router=router,
    service_type=Service,
)

__all__ = ["Service", "router", "spec"]
