import asyncio
import json
from pathlib import Path

import pytest

from app.core.retrieval import RetrievalPipeline,SourceDocument
from app.core.vector_store import Base
from app.platform.integrations import LangChainPipeline
from app.workers import tasks


class Embedder:
    async def embed(self,texts):
        return [[1.0 if 'atlas' in text.lower() else 0.0]+[0.0]*1023 for text in texts]


def test_a14_real_langchain_runnable_sequence_transforms_shared_state():
    pipeline=LangChainPipeline([
        lambda state:{**state,'draft':state['topic'].upper()},
        lambda state:{**state,'review':f"checked:{state['draft']}"},
    ])
    assert pipeline.invoke({'topic':'atlas'})=={'topic':'atlas','draft':'ATLAS','review':'checked:ATLAS'}
    with pytest.raises(KeyError): LangChainPipeline([lambda state:{'x':state['missing']}]).invoke({})


def test_a31_real_celery_task_registry_contains_bound_execution_and_collection_jobs():
    app=tasks.celery_app;app.loader.import_default_modules()
    assert {'atlas.modules.execute_approved','atlas.collection.dispatch_due','atlas.collection.collect_source'} <= set(app.tasks)
    execution=app.tasks['atlas.modules.execute_approved']
    collection=app.tasks['atlas.collection.collect_source']
    assert execution.name=='atlas.modules.execute_approved'
    assert collection.max_retries==5 and collection.autoretry_for==(ConnectionError,)
    routes=app.conf.task_routes
    assert routes['atlas.collection.*']['queue']=='collection' and routes['atlas.m13.*']['queue']=='browser'


@pytest.mark.asyncio
async def test_a33_real_ltm_ingestion_is_tenant_scoped_cited_and_retrievable(tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    engine=create_engine(f"sqlite:///{tmp_path/'memory.sqlite'}")
    Base.metadata.create_all(engine);sessions=sessionmaker(bind=engine,expire_on_commit=False)
    a=RetrievalPipeline('tenant-a','ltm',Embedder(),sessions)
    b=RetrievalPipeline('tenant-b','ltm',Embedder(),sessions)
    document=SourceDocument('doc-a','Atlas Note','Atlas evidence supports retrieval','doc://a',{'kind':'note'})
    assert await a.ingest([document])=={'documents':1,'chunks':1}
    hits=await a.retrieve('atlas evidence',limit=1,candidates=2)
    assert len(hits)==1 and hits[0]['citation']['source_id']=='doc-a' and hits[0]['citation']['locator']=='doc://a'
    assert len(hits[0]['citation']['sha256'])==64
    assert await b.retrieve('atlas evidence',limit=1,candidates=2)==[]
