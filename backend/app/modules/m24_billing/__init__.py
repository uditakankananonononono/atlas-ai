from app.modules.types import ModuleSpec
from .routes import router
from .service import Service
spec=ModuleSpec(id=24,slug="billing",name="Billing and Subscriptions",router=router,service_type=Service)

from . import write_ahead  # register inactive write-ahead metadata, no provider I/O
