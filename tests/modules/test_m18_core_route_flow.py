"""m18 booted-app blueprint/feasibility routes with the REAL lane collector shape (sync, tuple return) and no model.
Dev-mode headers = TEST MODE. A stub 'generate' below is a LABELED FIXTURE, not a model."""
import json, pytest
from fastapi.testclient import TestClient
from app.main import app
import app.modules.m18_side_hustle_scraper.routes as R
from app.modules.m18_side_hustle_scraper.service import Service
from app.modules.m18_side_hustle_scraper.lane_models import RawDocument, SourceKind, RightsClass

H={"x-atlas-tenant":"m18a","x-atlas-actor":"u"}
class RealShapeCollector:  # blocking, returns (docs, errors) like lane_sources collectors
    def __init__(self, docs, errors=()): self.docs, self.errors = docs, list(errors)
    def collect(self, q, limit): return self.docs, self.errors
def _doc():
    kind=list(SourceKind)[0]; rights=list(RightsClass)[0]
    return RawDocument(url="https://example.com/post",platform="reddit",kind=kind,rights=rights,title="FIXTURE title",text="Interview students first.")
async def fixture_generate(prompt,*a): return "FIXTURE-NOT-A-MODEL", json.dumps([{"title":"Tutoring","steps":["Interview 5"],"tools":["calendar"],"complexity":2,"time_to_first_dollar_days":14,"automation_level":10,"monetisation":["fees"],"source_urls":["https://example.com/post"]}])
@pytest.fixture
def client(monkeypatch):
    return TestClient(app,raise_server_exceptions=False)
def _use(monkeypatch, svc): monkeypatch.setattr(R,"_service",svc)

def test_blueprints_real_collector_shape_does_not_500(client,monkeypatch):
    _use(monkeypatch, Service(generate=fixture_generate,collectors={"reddit":RealShapeCollector([_doc()])}))
    r=client.post("/api/v1/side-hustle-scraper/blueprints",json={"query":"student tutoring","platforms":["reddit"]},headers=H)
    assert r.status_code==200,r.text
    assert r.json()[0]["source_urls"]==["https://example.com/post"]
def test_collector_errors_with_no_docs_is_502_not_empty_success(client,monkeypatch):
    _use(monkeypatch, Service(generate=fixture_generate,collectors={"reddit":RealShapeCollector([],["boom"])}))
    r=client.post("/api/v1/side-hustle-scraper/blueprints",json={"query":"student tutoring","platforms":["reddit"]},headers=H)
    assert r.status_code==502, r.text
def test_no_model_configured_is_503_not_500(client,monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY",raising=False)
    from app.core.providers import generate
    _use(monkeypatch, Service(generate=generate,collectors={"reddit":RealShapeCollector([_doc()])}))
    r=client.post("/api/v1/side-hustle-scraper/blueprints",json={"query":"student tutoring","platforms":["reddit"]},headers=H)
    assert r.status_code==503 and "provider unavailable" in r.json()["detail"], r.text
