from app.modules.types import ModuleSpec
from .routes import router
from .service import Service
spec=ModuleSpec(id=16,slug="executive-dashboard",name="Executive Dashboard",router=router,service_type=Service)
