from .routes import router
from .service import Service
from app.modules.types import ModuleSpec
spec=ModuleSpec(id=22,slug="tools-hub",name="Tools Discovery & Integration Hub",router=router,service_type=Service)
