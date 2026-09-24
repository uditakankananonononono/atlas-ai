"""Email Assistant module registration."""

from app.modules.types import ModuleSpec

from .routes import router
from .service import Service
from .drift_probe import register as _register_drift_probe

# First real M00 impact-preview probe: approved replies are re-checked against
# the live Gmail thread and stored draft before any send permit is issued.
_register_drift_probe()

spec = ModuleSpec(
    id=10,
    slug="email-assistant",
    name="Email Assistant",
    router=router,
    service_type=Service,
)

__all__ = ["Service", "router", "spec"]
