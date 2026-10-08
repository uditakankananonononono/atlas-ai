"""Actual SSE generator: authoritative owner lookup, minimal signals, cleanup."""
import asyncio
import json
import pytest
from fastapi import Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.auth.context import TenantContext
from app.modules.m00_approval_center.service import Service, Base
from app.modules.m00_approval_center.routes import stream_events


def test_actual_sse_filters_foreign_unknown_and_tampered_tenant_then_minimal_signal():
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=__import__('sqlalchemy').pool.StaticPool)
    Base.metadata.create_all(engine)
    service=Service(sessionmaker(bind=engine,expire_on_commit=False))
    own=service.submit(module_id=5,action_type='fixture',payload={'private':'own'},user_id='a')
    foreign=service.submit(module_id=5,action_type='fixture',payload={'private':'foreign'},user_id='b')
    async def journey():
        response=await stream_events(Response(),service,TenantContext('a','alice'))
        assert response.media_type=='text/event-stream'
        service.broadcaster.publish({'type':[], 'approval':own})
        service.broadcaster.publish({'type':{}, 'approval':own})
        service.broadcaster.publish({'type':'unknown','approval':own})
        service.broadcaster.publish({'type':'approval_request'})
        service.broadcaster.publish({'type':'approval_request','approval':{**foreign,'user_id':'a'}})
        service.broadcaster.publish({'type':'approval_expired','approval_id':foreign['id']})
        service.broadcaster.publish({'type':'approval_decision','approval':{**own,'user_id':'b','payload':{'injected':True}}})
        body=await asyncio.wait_for(anext(response.body_iterator),timeout=3)
        value=json.loads(body.removeprefix('data: ').strip())
        assert value=={'type':'approval_decision','approval_id':own['id']}
        await response.body_iterator.aclose()
        assert len(service.broadcaster._subscribers)==0
    try:asyncio.run(journey())
    finally:engine.dispose()
