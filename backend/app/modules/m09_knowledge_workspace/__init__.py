from app.modules.types import ModuleSpec
from .routes import router
from .service import Service
spec=ModuleSpec(id=9,slug="knowledge-workspace",name="Knowledge Workspace",router=router,service_type=Service)
