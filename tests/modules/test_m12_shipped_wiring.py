from app.modules.m12_ai_research_lab import routes
from app.modules.m12_ai_research_lab.service import Service
from app.modules.m12_ai_research_lab.workflow import DagEngine
def test_shipped_service_and_dag_construct_without_dependency_overrides():
 routes._service=None;routes._dag=None
 assert isinstance(routes.get_service(),Service)
 assert isinstance(routes.get_dag_engine(),DagEngine)
 assert len(routes.get_service().router.catalog)>=4
