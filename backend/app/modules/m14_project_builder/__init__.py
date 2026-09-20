from .routes import router
from .service import Service
from app.modules.types import ModuleSpec
spec=ModuleSpec(id=14,slug="project-builder",name="Project Builder",router=router,service_type=Service)
__all__=["spec","router","Service"]
