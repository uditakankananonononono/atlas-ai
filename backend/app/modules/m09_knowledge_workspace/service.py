from __future__ import annotations
import math,re
from datetime import datetime,timezone
from uuid import uuid4
from .schemas import *
class ConflictError(RuntimeError):pass
class Service:
    def __init__(self,repository,embed=lambda text:None,extract_entities=lambda text:[]):self.repository=repository;self.embed=embed;self.extract_entities=extract_entities
    def create_node(self,data:NodeCreate):
        now=datetime.now(timezone.utc);node=Node(id=str(uuid4()),version=1,embedding=self.embed(f"{data.title}\n{data.body or ''}"),created_at=now,updated_at=now,**data.model_dump());self.repository.save_node(node);self._suggest(node);return node
    def update_node(self,node_id,data:NodeUpdate):
        n=self._node(node_id)
        if n.version!=data.expected_version:raise ConflictError("node changed; refresh before editing")
        changes=data.model_dump(exclude_none=True,exclude={"expected_version"});updated=n.model_copy(update={**changes,"version":n.version+1,"updated_at":datetime.now(timezone.utc)});updated.embedding=self.embed(f"{updated.title}\n{updated.body or ''}");self.repository.save_node(updated,"node.updated");self._suggest(updated);return updated
    def create_edge(self,data:EdgeCreate,confidence=1):
        self._node(data.source_id);self._node(data.target_id)
        if data.source_id==data.target_id:raise ConflictError("self edge")
        if data.relationship in {Relationship.CHILD_OF,Relationship.BLOCKS,Relationship.DEPENDS_ON} and self._reachable(data.target_id,data.source_id,data.relationship):raise ConflictError("edge would create a cycle")
        return self.repository.save_edge(Edge(id=str(uuid4()),confidence=confidence,created_at=datetime.now(timezone.utc),**data.model_dump()))
    def neighborhood(self,node_id,depth=1,limit=250):
        self._node(node_id);ids={node_id};edges=[];frontier={node_id};truncated=False
        for _ in range(min(depth,5)):
            batch=self.repository.edges_for(frontier,limit-len(edges)+1)
            if len(edges)+len(batch)>limit:batch=batch[:limit-len(edges)];truncated=True
            edges.extend(e for e in batch if e.id not in {x.id for x in edges});nxt={x for e in batch for x in (e.source_id,e.target_id)}-ids;ids|=nxt;frontier=nxt
            if not frontier or truncated:break
        return Neighborhood(nodes=[n for n in self.repository.list_nodes() if n.id in ids],edges=edges,truncated=truncated)
    def review(self,sid,accept):
        s=self.repository.get_suggestion(sid)
        if not s or s.status!=SuggestionStatus.PENDING:raise LookupError(sid)
        if accept:self.create_edge(EdgeCreate(source_id=s.source_id,target_id=s.target_id,relationship=s.relationship,rationale="Approved suggestion",evidence={"suggestion_id":s.id,"reasons":s.reasons}),s.score)
        return self.repository.review_suggestion(sid,SuggestionStatus.ACCEPTED if accept else SuggestionStatus.REJECTED,datetime.now(timezone.utc))
    def planner_context(self,ids):
        nodes=[n for n in self.repository.list_nodes() if n.id in ids];edges=self.repository.edges_for(set(ids));return {"nodes":[{"id":n.id,"type":n.node_type.value,"title":n.title,"summary":(n.body or "")[:1000],"metadata":n.metadata,"version":n.version} for n in nodes],"edges":[{"from":e.source_id,"to":e.target_id,"type":e.relationship.value} for e in edges]}
    def _suggest(self,node):
        now=datetime.now(timezone.utc)
        for other in self.repository.list_nodes():
            if other.id==node.id:continue
            score=self._cosine(node.embedding,other.embedding)
            if score>=.78:self.repository.save_suggestion(LinkSuggestion(id=str(uuid4()),source_id=node.id,target_id=other.id,relationship=Relationship.RELATED_TO,score=score,reasons=[{"kind":"embedding_similarity","score":round(score,4)}],created_at=now))
        entities=self.extract_entities(f"{node.title}\n{node.body or ''}")
        for entity in entities:
            for other in self.repository.list_nodes():
                if other.id!=node.id and other.title.casefold()==entity["text"].casefold():self.repository.save_suggestion(LinkSuggestion(id=str(uuid4()),source_id=node.id,target_id=other.id,relationship=Relationship.MENTIONS,score=float(entity.get("confidence",.8)),reasons=[{"kind":"named_entity","text":entity["text"],"entity_type":entity.get("type")}],created_at=now))
    def _reachable(self,start,target,rel):
        frontier={start};seen=set()
        for _ in range(50):
            if target in frontier:return True
            seen|=frontier;frontier={e.target_id for e in self.repository.edges_for(frontier) if e.source_id in frontier and e.relationship==rel}-seen
            if not frontier:return False
        return True
    def _node(self,nid):
        n=self.repository.get_node(nid)
        if not n:raise LookupError(nid)
        return n
    @staticmethod
    def _cosine(a,b):
        if not a or not b or len(a)!=len(b):return 0
        d=math.sqrt(sum(x*x for x in a))*math.sqrt(sum(x*x for x in b));return sum(x*y for x,y in zip(a,b))/d if d else 0
