from app.modules.types import ModuleSpec
from .routes import router
from .service import Service
spec=ModuleSpec(id=7,slug="brand-collaboration",name="Brand Collaboration Manager",router=router,service_type=Service)
