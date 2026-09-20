"""Module 6 - Social Media Manager."""

from .routes import router
from .service import Service
from app.modules.types import ModuleSpec

spec = ModuleSpec(id=6, slug="social-media-manager", name="Social Media Manager", router=router, service_type=Service)
