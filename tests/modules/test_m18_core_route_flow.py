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


def test_partial_collector_failure_is_exposed_not_dropped(client,monkeypatch):
    class Two:
        def collect(self,q,l): return [_doc()],["e1","e2"]
    _use(monkeypatch, Service(generate=fixture_generate,collectors={"reddit":Two()}))
    r=client.post("/api/v1/side-hustle-scraper/blueprints",json={"query":"student tutoring","platforms":["reddit"]},headers=H)
    assert r.status_code==200
    assert json.loads(r.headers["X-Atlas-Collection-Partial-Failures"])==[{"platform":"reddit","errors":2,"docs":1}]
    assert "e1" not in r.headers["X-Atlas-Collection-Partial-Failures"]  # counts only, no raw error text

def test_two_document_tuple_is_not_misread_as_docs_errors_pair(client,monkeypatch):
    class TwoDocs:
        async def collect(self,q,l): return ({"url":"https://example.com/1","text":"a"},{"url":"https://example.com/2","text":"b"})
    _use(monkeypatch, Service(generate=fixture_generate,collectors={"reddit":TwoDocs()}))
    r=client.post("/api/v1/side-hustle-scraper/blueprints",json={"query":"student tutoring","platforms":["reddit"]},headers=H)
    assert r.status_code==200 and "X-Atlas-Collection-Partial-Failures" not in r.headers

def test_provider_error_text_is_not_echoed(client,monkeypatch):
    from app.core.providers import ProviderError
    async def boom(*a): raise ProviderError("SECRET-KEY-sk-123 upstream detail")
    _use(monkeypatch, Service(generate=boom,collectors={"reddit":RealShapeCollector([_doc()])}))
    r=client.post("/api/v1/side-hustle-scraper/blueprints",json={"query":"student tutoring","platforms":["reddit"]},headers=H)
    assert r.status_code==503 and "SECRET" not in r.text

def test_collected_documents_are_tenant_isolated_through_the_http_routes(client,monkeypatch):
    from app.modules.m18_side_hustle_scraper.lane_pipeline import CollectionPipeline
    from app.modules.m18_side_hustle_scraper.lane_repository import SQLiteDocumentRepository
    from app.modules.m18_side_hustle_scraper.lane_validation import DocumentValidator
    from app.modules.m18_side_hustle_scraper.lane_ranking import BlueprintRanker
    from app.modules.m18_side_hustle_scraper.lane_freshness import FreshnessMonitor
    repo=SQLiteDocumentRepository(":memory:")
    d=_doc(); d.text="Tutoring students online: interview five students, set a price, and run a trial lesson. "*8
    cols={"reddit":RealShapeCollector([d])}
    pipe=CollectionPipeline(repository=repo,validator=DocumentValidator(),ranker=BlueprintRanker(),monitor=FreshnessMonitor(repo),collectors=cols)
    _use(monkeypatch, Service(generate=fixture_generate,collectors=cols,pipeline=pipe))
    A={"x-atlas-tenant":"m18-A","x-atlas-actor":"a"}; B={"x-atlas-tenant":"m18-B","x-atlas-actor":"b"}
    rc=client.post("/api/v1/side-hustle-scraper/collect",json={"query":"student tutoring","platforms":["reddit"]},headers=A)
    assert rc.status_code==200 and rc.json()["documents_new"]==1, rc.text
    ra=client.post("/api/v1/side-hustle-scraper/rank",json={"query":"student tutoring"},headers=A).json()
    rb=client.post("/api/v1/side-hustle-scraper/rank",json={"query":"student tutoring"},headers=B).json()
    assert len(ra)==1 and rb==[]
    assert client.get("/api/v1/side-hustle-scraper/freshness",headers=B).json()["watched"]==0


def test_partial_failure_header_is_always_valid_json_with_many_long_platform_names(client,monkeypatch):
    from app.modules.m18_side_hustle_scraper.service import ALLOWED
    cols={}
    class E:
        def collect(self,q,l): return [_doc()],["x"]
    monkeypatch.setenv('ATLAS_M18_OPERATOR_ACCOUNT_TENANTS','m18a')  # ALLOWED includes credentialed platforms
    names=sorted(ALLOWED)[:8]
    for n in names: cols[n]=E()
    _use(monkeypatch, Service(generate=fixture_generate,collectors=cols))
    r=client.post("/api/v1/side-hustle-scraper/blueprints",json={"query":"student tutoring","platforms":names},headers=H)
    assert r.status_code==200,r.text
    parsed=json.loads(r.headers["X-Atlas-Collection-Partial-Failures"])
    assert len(parsed)==len(names) and len(r.headers["X-Atlas-Collection-Partial-Failures"])<1200


class _Counting:
    def __init__(self): self.calls=0
    def collect(self,q,l): self.calls+=1; return [_doc()],[]

def test_credentialed_collectors_fail_closed_for_tenants_without_an_operator_account_grant(client,monkeypatch):
    monkeypatch.delenv("ATLAS_M18_OPERATOR_ACCOUNT_TENANTS",raising=False)
    yt=_Counting(); pub=_Counting()
    _use(monkeypatch, Service(generate=fixture_generate,collectors={"youtube":yt,"reddit":pub}))
    # /blueprints: 403, collector never called
    r=client.post("/api/v1/side-hustle-scraper/blueprints",json={"query":"student tutoring","platforms":["youtube"]},headers=H)
    assert r.status_code==403 and yt.calls==0, r.text
    # service.collect default platform list includes youtube: reported as not granted, never called; public collector still ran
    import asyncio
    from app.modules.m18_side_hustle_scraper.schemas import CollectIn
    from app.modules.m18_side_hustle_scraper.lane_pipeline import CollectionPipeline
    from app.modules.m18_side_hustle_scraper.lane_repository import SQLiteDocumentRepository
    from app.modules.m18_side_hustle_scraper.lane_validation import DocumentValidator
    from app.modules.m18_side_hustle_scraper.lane_ranking import BlueprintRanker
    from app.modules.m18_side_hustle_scraper.lane_freshness import FreshnessMonitor
    repo=SQLiteDocumentRepository(":memory:"); cols={"youtube":yt,"reddit":pub}
    svc=Service(generate=fixture_generate,collectors=cols,pipeline=CollectionPipeline(repository=repo,validator=DocumentValidator(),ranker=BlueprintRanker(),monitor=FreshnessMonitor(repo),collectors=cols))
    rep=asyncio.run(svc.collect(CollectIn(query="student tutoring",platforms=["reddit","youtube"]),tenant_id="t-no-grant"))
    by={p.platform:p for p in rep.platforms}
    assert by["youtube"].errors==("operator_account_not_granted:youtube",) and yt.calls==0 and pub.calls==1
    # explicit grant (exact tenant id) allows it; a different tenant still does not
    monkeypatch.setenv("ATLAS_M18_OPERATOR_ACCOUNT_TENANTS","t-granted")
    asyncio.run(svc.collect(CollectIn(query="student tutoring",platforms=["youtube"]),tenant_id="t-granted")); assert yt.calls==1
    asyncio.run(svc.collect(CollectIn(query="student tutoring",platforms=["youtube"]),tenant_id="t-other")); assert yt.calls==1
