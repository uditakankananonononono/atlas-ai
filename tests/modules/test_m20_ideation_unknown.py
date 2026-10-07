import pytest
from app.core.providers import ProviderOutcomeUnknown
from app.modules.m20_general_cognitive_worker.reflection import ModelIdeationEngine


def test_model_ideation_preserves_invoked_unknown_not_unavailable():
    calls=[]
    class Model:
        def complete(self,*args):
            calls.append(args)
            return {'available':False,'failure_kind':'outcome_unknown','outcome':'unknown','retry_allowed':False,'error':'fixture dispatched result lost'}
    with pytest.raises(ProviderOutcomeUnknown) as error:
        ModelIdeationEngine(Model()).generate('fixture',count=1)
    assert error.value.outcome=='unknown' and len(calls)==1


def test_mounted_ideation_unknown_is_conflict_with_no_retry_not_503():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.modules.m20_general_cognitive_worker.routes import router,get_service
    calls=[]
    class Model:
        def complete(self,*args):calls.append(args);return {'available':False,'outcome':'unknown'}
    class Service:model_ideation=ModelIdeationEngine(Model())
    app=FastAPI();app.include_router(router);app.dependency_overrides[get_service]=lambda:Service()
    response=TestClient(app).post('/api/modules/20/meta/ideation/generate',json={'objective':'fixture','count':1})
    assert response.status_code==409 and response.json()['detail']['outcome']=='unknown'
    assert response.json()['detail']['retry_allowed'] is False and len(calls)==1
