from app.modules.types import ModuleSpec
from .routes import router
from .service import Service
spec=ModuleSpec(id=8,slug="startup-growth",name="Startup Growth",router=router,service_type=Service)
