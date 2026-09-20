"""Research Scientist module registration contract."""

from .routes import router
from .service import Service
from app.modules.types import ModuleSpec

spec = ModuleSpec(
    id=4,
    slug="research-scientist",
    name="Research Scientist",
    router=router,
    service_type=Service,
)

__all__ = ["spec", "router", "Service"]
