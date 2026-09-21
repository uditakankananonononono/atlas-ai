from app.modules.types import ModuleSpec
from .routes import router
from .pipeline import LocalKnowledgePipeline
spec=ModuleSpec(id=25,slug='knowledge-copilot-training',name='Knowledge Copilot & Training',router=router,service_type=LocalKnowledgePipeline)
