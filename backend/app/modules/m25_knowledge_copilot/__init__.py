from app.modules.types import ModuleSpec
from .routes import router
from .service import Service
spec=ModuleSpec(id=25,slug='knowledge-copilot',name='Real-time Knowledge Copilot',router=router,service_type=Service)
