from datetime import datetime,timezone
from app.modules.m09_knowledge_workspace.schemas import *
from app.modules.m09_knowledge_workspace.service import ConflictError,Service
class Repo:
 def __init__(self):self.nodes={};self.edges=[];self.suggestions={}
 def save_node(self,n,action="node.created",expected_version=None):
  if expected_version is not None and (n.id not in self.nodes or self.nodes[n.id].version!=expected_version):return None
  self.nodes[n.id]=n;return n
 def get_node(self,i):return self.nodes.get(i)
 def list_nodes(self,limit=500):return list(self.nodes.values())
 def save_edge(self,e):self.edges.append(e);return e
 def edges_for(self,ids,limit=1000):return [e for e in self.edges if e.source_id in ids or e.target_id in ids][:limit]
 def save_suggestion(self,s):self.suggestions[s.id]=s;return s
 def get_suggestion(self,i):return self.suggestions.get(i)
 def review_suggestion(self,i,status,at):s=self.suggestions[i];self.suggestions[i]=s.model_copy(update={"status":status,"reviewed_at":at});return self.suggestions[i]
def test_graph_suggest_review_cycle_and_version():
 r=Repo();svc=Service(r,embed=lambda text:[1,0] if "Atlas" in text else [.99,.01],extract_entities=lambda text:[])
 a=svc.create_node(NodeCreate(node_type="project",title="Atlas"));b=svc.create_node(NodeCreate(node_type="research",title="Research"))
 assert r.suggestions
 suggestion=next(iter(r.suggestions.values()));svc.review(suggestion.id,True);assert len(r.edges)==1
 parent=svc.create_node(NodeCreate(node_type="task",title="Parent"));child=svc.create_node(NodeCreate(node_type="task",title="Child"));svc.create_edge(EdgeCreate(source_id=child.id,target_id=parent.id,relationship="child_of"))
 try:svc.create_edge(EdgeCreate(source_id=parent.id,target_id=child.id,relationship="child_of"))
 except ConflictError:pass
 else:raise AssertionError("cycle accepted")
 try:svc.update_node(a.id,NodeUpdate(title="Lost update",expected_version=99))
 except ConflictError:pass
 else:raise AssertionError("stale write accepted")
def test_graph_is_tenant_repository_boundary_and_planner_export():
 r=Repo();svc=Service(r);n=svc.create_node(NodeCreate(node_type="note",title="Evidence",body="Grounded note"));ctx=svc.planner_context([n.id]);assert ctx["nodes"][0]["summary"]=="Grounded note"

def test_service_maps_repository_lost_race_to_conflict_without_suggestions():
 import pytest
 class RacedRepo(Repo):
  def save_node(self,n,action="node.created",expected_version=None):
   if expected_version is not None:return None
   return super().save_node(n,action)
 r=RacedRepo();svc=Service(r);n=svc.create_node(NodeCreate(node_type="note",title="Original"))
 with pytest.raises(ConflictError,match="node changed"):
  svc.update_node(n.id,NodeUpdate(title="Lost race",expected_version=1))
 assert r.get_node(n.id).title=="Original"


def _sql_service():
 from sqlalchemy import create_engine
 from sqlalchemy.orm import sessionmaker
 from sqlalchemy.pool import StaticPool
 from app.core.database import Base
 from app.modules.m09_knowledge_workspace.repository import SqlGraphRepository
 e=create_engine("sqlite://",connect_args={"check_same_thread":False},poolclass=StaticPool)
 Base.metadata.create_all(e)
 sf=sessionmaker(bind=e,expire_on_commit=False)
 return Service(SqlGraphRepository("t","u",sf))

def test_duplicate_edge_maps_to_conflict_not_integrity_error():
 # The m09_edges unique constraint (tenant, source, target, relationship) must
 # surface as the service's ConflictError, which the route maps to 409; a raw
 # IntegrityError escapes as a 500.
 svc=_sql_service()
 a=svc.create_node(NodeCreate(node_type="note",title="A"));b=svc.create_node(NodeCreate(node_type="note",title="B"))
 svc.create_edge(EdgeCreate(source_id=a.id,target_id=b.id,relationship="related_to"))
 import pytest
 with pytest.raises(ConflictError,match="edge already exists"):
  svc.create_edge(EdgeCreate(source_id=a.id,target_id=b.id,relationship="related_to"))
 # A different relationship between the same nodes is a different edge and stays allowed.
 svc.create_edge(EdgeCreate(source_id=a.id,target_id=b.id,relationship="references"))

def test_duplicate_edge_route_returns_409():
 from fastapi.testclient import TestClient
 from app.main import app
 from app.modules.m09_knowledge_workspace import routes
 svc=_sql_service()
 app.dependency_overrides[routes.get_service]=lambda:svc
 try:
  c=TestClient(app);H={"X-Atlas-Tenant":"t","X-Atlas-Actor":"u"};base="/api/v1/knowledge-workspace"
  na=c.post(f"{base}/nodes",json={"node_type":"note","title":"A"},headers=H).json()
  nb=c.post(f"{base}/nodes",json={"node_type":"note","title":"B"},headers=H).json()
  body={"source_id":na["id"],"target_id":nb["id"],"relationship":"related_to"}
  assert c.post(f"{base}/edges",json=body,headers=H).status_code==201
  r=c.post(f"{base}/edges",json=body,headers=H)
  assert r.status_code==409,r.text
 finally:
  app.dependency_overrides.clear()
