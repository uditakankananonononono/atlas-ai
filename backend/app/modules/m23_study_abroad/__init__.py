from .routes import router
from .service import Service
from app.modules.types import ModuleSpec
spec=ModuleSpec(id=23,slug='study-abroad',name='Study Abroad Planner & Global Admissions Intelligence',router=router,service_type=Service)
