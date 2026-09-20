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
