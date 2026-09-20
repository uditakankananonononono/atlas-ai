"""Calendar Intelligence module registration."""

from app.modules.types import ModuleSpec

from .routes import router
from .service import Service

spec = ModuleSpec(
    id=11,
    slug="calendar-intelligence",
    name="Calendar Intelligence",
    router=router,
    service_type=Service,
)

__all__ = ["Service", "router", "spec"]
