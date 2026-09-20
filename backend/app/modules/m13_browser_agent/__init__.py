"""Module 13 - Browser Agent."""
from app.modules.types import ModuleSpec
from .routes import router
from .service import Service
spec=ModuleSpec(id=13,slug="browser-agent",name="Browser Agent",router=router,service_type=Service)
