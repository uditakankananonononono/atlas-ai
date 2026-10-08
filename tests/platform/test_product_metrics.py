import asyncio
from types import SimpleNamespace
from prometheus_client import CollectorRegistry, generate_latest
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from app.platform import metrics


def test_scrape_private_and_no_self_metric(monkeypatch):
    app = FastAPI(); app.add_middleware(metrics.MetricsMiddleware)
    app.add_api_route('/metrics', metrics.scrape, methods=['GET'])
    @app.get('/item/{secret}')
    def item(secret): return {'ok': True}
    client = TestClient(app)
    monkeypatch.delenv('ATLAS_METRICS_TOKEN', raising=False)
    assert client.get('/metrics').status_code == 404
    monkeypatch.setenv('ATLAS_METRICS_TOKEN', 'synthetic-test-token')
    assert client.get('/metrics').status_code == 404
    assert client.get('/metrics',headers={'Authorization':'Bearer wrong'}).status_code == 404
    client.get('/item/private-canary');client.get('/missing-canary')
    response=client.get('/metrics', headers={'Authorization':'Bearer synthetic-test-token'})
    assert response.status_code == 200 and 'text/plain' in response.headers['content-type']
    assert 'route="/item/{secret}"' in response.text
    assert 'private-canary' not in response.text and 'missing-canary' not in response.text
    assert 'route="/metrics"' not in response.text
    assert 'process_cpu_seconds_total' in response.text


def test_queue_depth_failure_has_no_fake_zero():
    class App:
        conf=SimpleNamespace(task_default_queue='celery',task_routes={})
        def connection_for_read(self,**kwargs): raise OSError('broker unavailable')
    registry=CollectorRegistry();registry.register(metrics.QueueDepthCollector(App()))
    text=generate_latest(registry).decode()
    assert 'atlas_celery_queue_scrape_success 0.0' in text
    assert 'atlas_celery_queue_depth{' not in text


def test_provider_observations_reported_tokens_only(monkeypatch):
    from app.core import shared_model_layer as layer
    from instinct_models.providers import ChatResult
    from instinct_models import Router
    class Provider:
        name='private-provider-canary';locality='local'
        def available(self): return True
        def chat(self,*a,**k): return ChatResult(self.name,'private-model','private-prompt',[],{'usage':{'prompt_tokens':7,'completion_tokens':3}})
    observed=[]
    monkeypatch.setattr(metrics,'observe_provider',lambda *a:observed.append(a))
    result=layer.run([{'role':'user','content':'sensitive'}],router=Router([Provider()]))
    assert result.ok and observed[0][2]=='success'
    asyncio.run(layer.generate('sensitive',router=Router([Provider()])))
    assert len(observed)==2


def test_provider_failure_semantics_retained(monkeypatch):
    from app.core import shared_model_layer as layer
    from instinct_models.providers import ProviderError
    from instinct_models import Router
    class Provider:
        name='hermes';locality='local'
        def available(self): return True
        def chat(self,*a,**k):raise ProviderError('fixture failure')
    observed=[];monkeypatch.setattr(metrics,'observe_provider',lambda *a:observed.append(a))
    with pytest.raises(layer.SharedAttemptUnknown):
        asyncio.run(layer.generate('fixture',router=Router([Provider()])))
    assert len(observed)==1 and observed[0][2]=='error'


def test_measured_wrapper_preserves_vendor_type_dispatch():
    from app.core.shared_model_layer import _MeasuredProvider, run
    from instinct_models.providers import NeedleLocal
    from instinct_models.lexical import LexicalLocal
    from instinct_models import Router
    needle=NeedleLocal(None)
    assert isinstance(_MeasuredProvider(needle), NeedleLocal)
    result=run([{'role':'user','content':'plain prose'}], router=Router([needle]))
    assert result.attempts[0].outcome=='skipped'
    lexical=LexicalLocal(None)
    assert isinstance(_MeasuredProvider(lexical), LexicalLocal)


def test_usage_invalid_fields_never_invent_tokens():
    registry=CollectorRegistry()
    # Invalid usage must not introduce arbitrary provider names or estimated tokens.
    before=generate_latest(metrics.REGISTRY)
    metrics.observe_provider('private-name-canary',0.1,'success',{'usage':{'prompt_tokens':True,'completion_tokens':-2}})
    after=generate_latest(metrics.REGISTRY).decode()
    assert 'private-name-canary' not in after
    assert 'atlas_provider_tokens_total{kind="input",provider="other"}' not in after


def test_exception_records_500_without_leaking_raw_path():
    app=FastAPI();app.add_middleware(metrics.MetricsMiddleware)
    @app.get('/crash/{private}')
    def crash(private):raise RuntimeError('fixture')
    client=TestClient(app,raise_server_exceptions=False)
    assert client.get('/crash/private-canary').status_code==500
    text=generate_latest(metrics.REGISTRY).decode()
    assert 'route="/crash/{private}",status="500"' in text
    assert 'private-canary' not in text


def test_private_hosted_provider_still_skipped():
    from app.core.shared_model_layer import run
    from instinct_models import Router
    class Hosted:
        name='inkling_hf';locality='hosted'
        def available(self):return True
        def chat(self,*a,**kw):pytest.fail('private request reached hosted provider')
    assert run([{'role':'user','content':'private'}],router=Router([Hosted()])).attempts[0].outcome=='skipped'
