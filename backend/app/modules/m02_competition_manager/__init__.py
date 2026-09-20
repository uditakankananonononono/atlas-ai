"""Competition Manager module export."""

from app.modules.types import ModuleSpec

from .routes import router
from .service import Service

spec = ModuleSpec(
    id=2,
    slug="competition-manager",
    name="Competition Manager",
    router=router,
    service_type=Service,
)

__all__ = ["spec"]
