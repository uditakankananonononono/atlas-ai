"""Module 17 - Social Advice Compiler & College Essay Architect."""
from .routes import router
from .service import Service
from app.modules.types import ModuleSpec
spec=ModuleSpec(id=17,slug="narrative-architect",name="Social Advice Compiler & College Essay Architect",router=router,service_type=Service)
