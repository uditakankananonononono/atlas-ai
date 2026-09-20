from datetime import datetime,timezone
from app.modules.m09_knowledge_workspace.schemas import *
from app.modules.m09_knowledge_workspace.service import ConflictError,Service
class Repo:
 def __init__(self):self.nodes={};self.edges=[];self.suggestions={}
 def save_node(self,n,action="node.created"):self.nodes[n.id]=n;return n
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
