from .routes import router
from .service import Service
try:
 from app.modules.types import ModuleSpec
 spec=ModuleSpec(id=21,slug="claire",name="Claire Personal Assistant / Idea Realisation Engine",router=router,service_type=Service)
except ImportError:
 spec={"id":21,"slug":"claire","name":"Claire Personal Assistant / Idea Realisation Engine","router":router,"service_type":Service}
