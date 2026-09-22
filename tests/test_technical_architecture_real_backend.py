import importlib.metadata
from pathlib import Path

import chromadb
from fastapi import FastAPI
from pydantic import BaseModel
from pgvector.sqlalchemy import Vector

from app.core.vector_store import EMBEDDING_DIMENSIONS, MemoryEmbeddingRow
from app.platform.integrations import ChromaMemory
from app.workers.celery_app import celery_app


def major(distribution):
    return int(importlib.metadata.version(distribution).split('.')[0])


def test_a07_running_python_fastapi_and_pydantic_match_backend_contract():
    pyproject=Path('pyproject.toml').read_text()
    assert 'requires-python = ">=3.12"' in pyproject
    assert major('fastapi')==0 and major('pydantic')==2
    app=FastAPI()
    class Payload(BaseModel): value:int
    @app.post('/typed')
    def typed(payload:Payload): return payload
    route=next(r for r in app.routes if getattr(r,'path','')=='/typed')
    assert route.body_field is not None and route.endpoint(Payload(value=4)).value==4


def test_a08_real_celery_uses_redis_for_broker_results_and_json_only():
    assert celery_app.connection().as_uri(include_password=False).startswith('redis://')
    assert celery_app.backend.as_uri().startswith('redis://')
    assert celery_app.conf.task_serializer=='json' and celery_app.conf.result_serializer=='json'
    assert celery_app.conf.accept_content==['json']
    assert celery_app.conf.task_acks_late and celery_app.conf.task_reject_on_worker_lost
    assert celery_app.conf.task_routes['atlas.collection.*']['queue']=='collection'


def test_a10_memory_embedding_is_real_pgvector_1024_column():
    column=MemoryEmbeddingRow.__table__.c.embedding
    assert isinstance(column.type,Vector)
    assert column.type.dim==EMBEDDING_DIMENSIONS==1024
    assert {'tenant_id','namespace','text','metadata_json','embedding'} <= set(MemoryEmbeddingRow.__table__.c.keys())


def test_a11_real_chromadb_client_upserts_and_tenant_collections_are_isolated():
    client=chromadb.EphemeralClient()
    a=ChromaMemory('tenant-a',client=client); b=ChromaMemory('tenant-b',client=client)
    assert a.upsert([{'id':'one','text':'alpha','embedding':[1.0,0.0],'metadata':{'kind':'note'}}])==1
    assert b.upsert([{'id':'two','text':'beta','embedding':[0.0,1.0],'metadata':{'kind':'note'}}])==1
    assert a.query([1.0,0.0],limit=2)['ids']==[['one']]
    assert b.query([1.0,0.0],limit=2)['ids']==[['two']]
