"""SQL-authoritative facts with an explicit asynchronous durable Chroma index."""
import hashlib
import math
import sqlalchemy as sa
from sqlalchemy.orm import Session

from .sql_repository import Base, FactRow
from .persistence import DurableSemanticMemory
from .embeddings import embed_snapshot
from .schemas import SemanticFact


class ChromaIndexJob(Base):
    __tablename__ = 'm20_chroma_index_jobs'
    tenant_id = sa.Column(sa.String(120), primary_key=True)
    fact_id = sa.Column(sa.String(120), primary_key=True)
    model_id = sa.Column(sa.String(200), nullable=False)
    content_hash = sa.Column(sa.String(64), nullable=False)
    complete = sa.Column(sa.Boolean, nullable=False, default=False, server_default=sa.false())


class FactIndexPending(ValueError):
    status = 'facts_pending_index'


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def collection_identity(tenant_id, model_id):
    return 'm20-' + digest(f'{len(tenant_id)}:{tenant_id}:{model_id}')


def fact_from(row):
    return SemanticFact(id=row.id,content=row.content,kind=row.kind,confidence=row.confidence,
                        decay_rate=row.decay_rate,provenance=row.provenance_json or {},
                        created_at=row.created_at,last_confirmed_at=row.last_confirmed_at)


class ChromaSemanticMemory(DurableSemanticMemory):
    def __init__(self, repo, embedder, path):
        if repo.engine.dialect.name != 'postgresql':
            raise ValueError('Chroma semantic index jobs require PostgreSQL')
        if embedder is None or not isinstance(getattr(embedder, 'model_id', None),str) or not 1 <= len(embedder.model_id) <= 200:
            raise ValueError('Chroma requires an explicit embedder with stable model_id')
        if not isinstance(path,str) or not path:
            raise ValueError('Chroma requires an explicit persistent path')
        super().__init__(repo,embedder)
        self.model_id=embedder.model_id
        with repo._session() as db:
            jobs={row.fact_id:row for row in db.scalars(sa.select(ChromaIndexJob).where(ChromaIndexJob.tenant_id==repo.tenant_id))}
            for fact in repo.list_facts():
                job=jobs.get(fact.id)
                if job is None or job.model_id!=self.model_id or job.content_hash!=digest(fact.content):
                    raise ValueError('existing facts require explicit Chroma reindex before binding')
                self._facts[fact.id]=fact
        import chromadb
        self.client=chromadb.PersistentClient(path=path)
        self.collection=self.client.get_or_create_collection(collection_identity(repo.tenant_id,self.model_id),
                                                            metadata={'hnsw:space':'cosine'})
        self._edges=repo.list_edges()

    def _embed(self,text):
        if self.embedder.model_id!=self.model_id:
            raise ValueError('Chroma embedding model changed; explicit reindex required')
        vector=embed_snapshot(self.embedder,text)
        if not any(vector):raise ValueError('Chroma requires nonzero embeddings')
        # Stable normalization preserves cosine direction at extreme scales.
        scale=max(abs(value) for value in vector)
        scaled=[value/scale for value in vector]
        norm=math.sqrt(math.fsum(value*value for value in scaled))
        return [value/norm for value in scaled]

    def store(self,fact):
        fact=fact.model_copy(deep=True)
        self._embed(fact.content) # reject invalid provider output before fact write
        with self.repo._session_factory() as db:
            token=self.repo._execution_session.set(db)
            try:
                self.repo.save_fact(fact)
                job=db.get(ChromaIndexJob,(self.repo.tenant_id,fact.id))
                if job is None:
                    job=ChromaIndexJob(tenant_id=self.repo.tenant_id,fact_id=fact.id)
                    db.add(job)
                job.model_id=self.model_id;job.content_hash=digest(fact.content);job.complete=False
                db.commit()
            finally:self.repo._execution_session.reset(token)
        self._facts[fact.id]=fact
        return fact.model_copy(deep=True)

    def index_pending(self,*,limit=100):
        if type(limit) is not int or not 1<=limit<=1000:raise ValueError('index limit must be 1..1000')
        indexed=0
        # Fact writer and indexer lock fact before job in the same order.
        with Session(self.repo.engine) as db,db.begin():
            ids=list(db.scalars(sa.select(ChromaIndexJob.fact_id).where(
                ChromaIndexJob.tenant_id==self.repo.tenant_id,ChromaIndexJob.complete.is_(False))
                .order_by(ChromaIndexJob.fact_id).limit(limit)))
            for ident in ids:
                fact=db.scalar(sa.select(FactRow).where(FactRow.id==ident,FactRow.tenant_id==self.repo.tenant_id).with_for_update())
                job=db.scalar(sa.select(ChromaIndexJob).where(ChromaIndexJob.fact_id==ident,
                    ChromaIndexJob.tenant_id==self.repo.tenant_id).with_for_update())
                if fact is None or job is None:raise ValueError('index job has no SQL fact authority')
                if job.complete:continue
                if job.model_id!=self.model_id or job.content_hash!=digest(fact.content):
                    raise ValueError('index job diverged; explicit reindex required')
                vector=self._embed(fact.content)
                metadata={'content_hash':job.content_hash,'model_id':self.model_id}
                self.collection.upsert(ids=[ident],documents=[fact.content],embeddings=[vector],metadatas=[metadata])
                stored=self.collection.get(ids=[ident],include=['documents','metadatas','embeddings'])
                if stored['ids']!=[ident] or stored['documents']!=[fact.content] or stored['metadatas']!=[metadata]:
                    raise ValueError('Chroma index readback differs from authoritative snapshot')
                actual=list(stored['embeddings'][0])
                if len(actual)!=len(vector) or any(not math.isfinite(float(a)) or abs(float(a)-b)>1e-6 for a,b in zip(actual,vector)):
                    raise ValueError('Chroma embedding readback mismatch')
                job.complete=True;indexed+=1
        return {'indexed':indexed}

    def query(self,text,*,limit=5,min_score=0.0):
        if not text.strip():return []
        if type(limit) is not int or not 1<=limit<=50 or type(min_score) not in (int,float) or not math.isfinite(min_score) or not -1<=min_score<=1:
            raise ValueError('invalid Chroma recall bounds')
        with self.repo._session() as db:
            facts={row.id:row for row in db.scalars(sa.select(FactRow).where(FactRow.tenant_id==self.repo.tenant_id))}
            jobs={row.fact_id:row for row in db.scalars(sa.select(ChromaIndexJob).where(ChromaIndexJob.tenant_id==self.repo.tenant_id))}
            if set(facts)!=set(jobs):raise ValueError('Chroma SQL job set diverged; explicit reindex required')
            for ident,fact in facts.items():
                job=jobs[ident]
                if job.model_id!=self.model_id or job.content_hash!=digest(fact.content):
                    raise ValueError('Chroma SQL snapshot diverged; explicit reindex required')
            if any(not job.complete for job in jobs.values()):
                raise FactIndexPending('SQL facts exist but Chroma index is pending; run explicit index worker')
            stored=self.collection.get(include=['metadatas'])
            if set(stored['ids'])!=set(facts):
                raise ValueError('Chroma index identity set diverged; explicit repair required')
            for ident,metadata in zip(stored['ids'],stored['metadatas']):
                if metadata!={'content_hash':digest(facts[ident].content),'model_id':self.model_id}:
                    raise ValueError('Chroma index snapshot diverged; explicit repair required')
            if not facts:return [] # fact-absent is distinct from pending error
            result=self.collection.query(query_embeddings=[self._embed(text)],n_results=min(limit,len(facts)),
                                         include=['metadatas','distances'])
            hits=[]
            for ident,metadata,distance in zip(result['ids'][0],result['metadatas'][0],result['distances'][0]):
                fact=facts.get(ident)
                if fact is None or metadata!={'content_hash':digest(fact.content),'model_id':self.model_id}:
                    raise ValueError('Chroma candidate has no matching SQL authority')
                score=1-float(distance)
                if not math.isfinite(score):raise ValueError('nonfinite Chroma recall score')
                if score>=min_score:hits.append((fact_from(fact),score))
            return hits
