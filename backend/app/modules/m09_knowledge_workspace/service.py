from __future__ import annotations
import math,re
from datetime import datetime,timezone
from uuid import uuid4
from .schemas import *
from .repository import GraphWriteConflict
from .local_nlp import get_local_nlp, validate_vector, NLPUnavailable
class ConflictError(RuntimeError):pass
class Service:
    def __init__(self,repository,embed=None,extract_entities=None,*,embedding_identity=None):
        self.repository=repository;self.embed=embed;self.extract_entities=extract_entities
        self.embedding_identity=embedding_identity
        if (embed is None) != (extract_entities is None):
            raise ValueError("embedding and entity adapters must be supplied together")
    def _prepare(self,node):
        text=f"{node.title}\n{node.body or ''}"
        if self.embed is None:
            runtime=get_local_nlp();vector=runtime.embed(text);entities=runtime.extract_entities(text)
            identity=runtime.identity;entity_identity=runtime.entity_identity
        else:
            vector=self.embed(text);entities=self.extract_entities(text)
            identity=self.embedding_identity or {"provider":"injected-unverified","dimension":len(vector) if vector else 0}
            entity_identity={"provider":"injected-unverified"}
        validate_vector(vector,identity["dimension"])
        node.embedding=vector
        node.metadata={**node.metadata,"_atlas_m09_nlp":{"embedding":identity,"entities":entity_identity}}
        # All inference and similarity validation finishes before persistence.
        suggestions=self._suggest(node,entities)
        return suggestions
    def _persist(self,node,action,suggestions):
        if hasattr(self.repository,"save_node_with_suggestions"):
            try:return self.repository.save_node_with_suggestions(node,action,suggestions,node.version-1 if action=="node.updated" else None)
            except GraphWriteConflict as e:raise ConflictError(str(e)) from e
        self.repository.save_node(node,action)
        for suggestion in suggestions:self.repository.save_suggestion(suggestion)
        return node
    def create_node(self,data:NodeCreate):
        now=datetime.now(timezone.utc);node=Node(id=str(uuid4()),version=1,embedding=None,created_at=now,updated_at=now,**data.model_dump());suggestions=self._prepare(node);return self._persist(node,"node.created",suggestions)
    def update_node(self,node_id,data:NodeUpdate):
        n=self._node(node_id)
        if n.version!=data.expected_version:raise ConflictError("node changed; refresh before editing")
        changes=data.model_dump(exclude_none=True,exclude={"expected_version"});updated=n.model_copy(update={**changes,"version":n.version+1,"updated_at":datetime.now(timezone.utc)});suggestions=self._prepare(updated);return self._persist(updated,"node.updated",suggestions)
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
        if hasattr(self.repository,"review_with_edge"):
            try:return self.repository.review_with_edge(sid,accept,datetime.now(timezone.utc))
            except GraphWriteConflict as e:raise ConflictError(str(e)) from e
        s=self.repository.get_suggestion(sid)
        if not s or s.status!=SuggestionStatus.PENDING:raise LookupError(sid)
        if accept:self.create_edge(EdgeCreate(source_id=s.source_id,target_id=s.target_id,relationship=s.relationship,rationale="Approved suggestion",evidence={"suggestion_id":s.id,"reasons":s.reasons}),s.score)
        return self.repository.review_suggestion(sid,SuggestionStatus.ACCEPTED if accept else SuggestionStatus.REJECTED,datetime.now(timezone.utc))
    def planner_context(self,ids):
        nodes=[n for n in self.repository.list_nodes() if n.id in ids];edges=self.repository.edges_for(set(ids));return {"nodes":[{"id":n.id,"type":n.node_type.value,"title":n.title,"summary":(n.body or "")[:1000],"metadata":n.metadata,"version":n.version} for n in nodes],"edges":[{"from":e.source_id,"to":e.target_id,"type":e.relationship.value} for e in edges]}
    def _suggest(self,node,entities):
        now=datetime.now(timezone.utc);suggestions=[];skipped=0
        nodes=self.repository.list_nodes()
        identity=node.metadata["_atlas_m09_nlp"]["embedding"]
        for other in nodes:
            if other.id==node.id:continue
            old=other.metadata.get("_atlas_m09_nlp",{}).get("embedding")
            if old!=identity:
                skipped+=1;continue
            validate_vector(other.embedding,identity["dimension"])
            score=self._cosine(node.embedding,other.embedding)
            if score>=.78:suggestions.append(LinkSuggestion(id=str(uuid4()),source_id=node.id,target_id=other.id,relationship=Relationship.RELATED_TO,score=score,reasons=[{"kind":"embedding_similarity","score":round(score,4),"embedding_identity":identity,"threshold":.78,"not_probability":True}],created_at=now))
        node.metadata["_atlas_m09_nlp"]["incompatible_nodes_skipped"]=skipped
        for entity in entities:
            for other in nodes:
                if other.id!=node.id and other.title.casefold()==entity["text"].casefold():
                    suggestions.append(LinkSuggestion(id=str(uuid4()),source_id=node.id,target_id=other.id,relationship=Relationship.MENTIONS,score=1.0,reasons=[{"kind":"named_entity_exact_title_match","text":entity["text"],"entity_type":entity.get("type"),"ner_identity":node.metadata["_atlas_m09_nlp"]["entities"],"not_probability":True}],created_at=now))
        for suggestion in suggestions:
            other=next(n for n in nodes if n.id==suggestion.target_id)
            suggestion.reasons.append({"kind":"node_versions","source_version":node.version,"target_version":other.version})
        return suggestions
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
