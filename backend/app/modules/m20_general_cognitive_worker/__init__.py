"""Module 20: General Cognitive Worker (Universal Intellectual Agent).

Spec section 4. Registry entry for the integrator's module catalog; mount
`router` and call `bind_service()` with a configured CognitiveWorkerService.
"""
from .routes import bind_service, router
from .service import CognitiveWorkerService

MODULE_REGISTRY_ENTRY = {
    "id": 20,
    "slug": "m20_general_cognitive_worker",
    "name": "General Cognitive Worker",
    "description": "Universal intellectual agent: perceives, remembers, plans, acts, and reflects across open-ended domains under constitutional rules and human approval gating.",
    "router_prefix": "/api/modules/20",
}

__all__ = ["CognitiveWorkerService", "bind_service", "router", "MODULE_REGISTRY_ENTRY"]

from .legacy_service import Service
from app.modules.types import ModuleSpec
spec = ModuleSpec(id=20,slug="general-cognitive-worker",name="General Cognitive Worker",router=router,service_type=Service)
__all__ += ["Service","spec"]
