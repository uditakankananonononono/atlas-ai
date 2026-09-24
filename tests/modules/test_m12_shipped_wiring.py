from app.modules.m12_ai_research_lab import routes
from app.modules.m12_ai_research_lab.service import Service
from app.modules.m12_ai_research_lab.workflow import DagEngine
def test_shipped_service_and_dag_construct_without_dependency_overrides():
 routes._service=None;routes._dag=None
 assert isinstance(routes.get_service(),Service)
 assert isinstance(routes.get_dag_engine(),DagEngine)
 cat=routes.get_service().router.catalog
 assert len(cat)>=2 and all(m.cents_per_1k_tokens==0 for m in cat)  # free-first: paid models need ATLAS_ALLOW_PAID
