from datetime import datetime,timezone
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.modules.m19_idea_incubator.routes import get_ledger,router
from app.modules.m19_idea_incubator.repository import MemoryIdeaRepository
from app.modules.m19_idea_incubator.ledger import LedgerService

def client():
 app=FastAPI();app.include_router(router);ledger=LedgerService(MemoryIdeaRepository(),"route-actor");app.dependency_overrides[get_ledger]=lambda:ledger;return TestClient(app)
def created(c):return c.post("/idea-incubator/portfolio/ideas",json={"title":"Idea","problem":"Problem","proposed_solution":"Solution"})

def test_portfolio_create_list_and_dossier_routes():
 c=client();r=created(c);assert r.status_code==201;i=r.json()["id"];assert c.get("/idea-incubator/portfolio/ideas").json()[0]["id"]==i;d=c.get(f"/idea-incubator/portfolio/ideas/{i}");assert d.status_code==200 and d.json()["evidence_summary"]["supporting_count"]==0

def test_route_error_statuses():
 c=client();assert c.get("/idea-incubator/portfolio/ideas/missing").status_code==404;i=created(c).json()["id"]
 invalid=c.post(f"/idea-incubator/portfolio/ideas/{i}/decisions",json={"to_stage":"approved","rationale":"too soon"});assert invalid.status_code==422
 c.post(f"/idea-incubator/portfolio/ideas/{i}/decisions",json={"to_stage":"discovery","rationale":"explore","expected_version":1})
 conflict=c.post(f"/idea-incubator/portfolio/ideas/{i}/decisions",json={"to_stage":"validation","rationale":"stale","expected_version":1});assert conflict.status_code==409

def test_evidence_feasibility_experiment_routes():
 c=client();i=created(c).json()["id"]
 evidence=c.post(f"/idea-incubator/portfolio/ideas/{i}/evidence",json={"kind":"market_data","claim":"Demand","source":"study","polarity":"supports","strength":.8,"confidence":.7,"observed_at":datetime.now(timezone.utc).isoformat()});assert evidence.status_code==201
 dimension={"score":80,"confidence":.8,"notes":"measured"};feas=c.post(f"/idea-incubator/portfolio/ideas/{i}/feasibility-tests",json={k:dimension for k in ("desirability","technical","viability","strategic_fit","compliance")});assert feas.status_code==201 and feas.json()["outcome"]=="pass"
 exp=c.post(f"/idea-incubator/portfolio/ideas/{i}/experiments",json={"name":"Pilot","hypothesis":"Converts","method":"Run it","metric":"conversion","target":10});assert exp.status_code==201;e=exp.json()["id"]
 assert c.patch(f"/idea-incubator/portfolio/ideas/{i}/experiments/{e}",json={"status":"running"}).status_code==200

def test_persist_luxury_venture_invalid_brief_is_422_not_500():
    # A structurally valid brief that fails build_luxury_venture's semantic
    # checks (duplicate source_id) must map to 422 like the sibling studio
    # endpoints, not leak as an unhandled 500.
    app=FastAPI();app.include_router(router)
    app.dependency_overrides[get_ledger]=lambda:LedgerService(MemoryIdeaRepository(),"route-actor")
    c=TestClient(app,raise_server_exceptions=False)
    def source(sid,title):return {"source_id":sid,"url":"https://example.test/"+title,"title":title,"observed_at":"2026-01-01T00:00:00Z","finding":"finding "+title}
    def signal(sid):return {"signal_id":sid,"statement":"signal statement","source_ids":["s1"],"importance":0.5}
    brief={"brand_or_segment":"Segment","sector":"other","customer_job":"a real customer job","constraints":["c1"],
           "sources":[source("s1","Alpha"),source("s1","Beta")],
           "signals":[signal("g1"),signal("g2")],
           "capabilities":[{"capability_id":"cap1","description":"capability","readiness":0.5}]}
    r=c.post("/idea-incubator/luxury-venture-studio/portfolio",json={"brief":brief,"owner_id":"owner-1"})
    assert r.status_code==422,r.status_code
