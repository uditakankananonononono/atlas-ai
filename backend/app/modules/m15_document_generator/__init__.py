from .routes import router
from .service import Service
from app.modules.types import ModuleSpec
spec=ModuleSpec(id=15,slug="document-generator",name="Document Generator",router=router,service_type=Service)
__all__=["spec","router","Service"]
