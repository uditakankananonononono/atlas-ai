"""Grant & Fellowship Writer module registration."""

from app.modules.types import ModuleSpec

from .routes import router
from .service import Service

spec = ModuleSpec(
    id=3,
    slug="grant-writer",
    name="Grant & Fellowship Writer",
    router=router,
    service_type=Service,
)

__all__ = ["Service", "router", "spec"]
