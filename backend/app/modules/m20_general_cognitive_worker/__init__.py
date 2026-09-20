from .routes import router
from .service import Service
try:
    from app.modules.types import ModuleSpec
    spec=ModuleSpec(id=20,slug="general-cognitive-worker",name="General Cognitive Worker",router=router,service_type=Service)
except ImportError:
    spec={"id":20,"slug":"general-cognitive-worker","name":"General Cognitive Worker","router":router,"service_type":Service}
