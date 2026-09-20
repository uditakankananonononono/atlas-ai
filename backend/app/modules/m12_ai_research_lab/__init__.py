"""Module 12 - AI Research Lab."""
from app.modules.types import ModuleSpec
from .service import Service
from .routes import router
spec=ModuleSpec(id=12,slug="ai-research-lab",name="AI Research Lab",router=router,service_type=Service)
