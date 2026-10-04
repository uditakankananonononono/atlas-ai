"""m18 legacy /runs and /durable-runs through the booted app: tenant ownership and approval owner. Dev headers = TEST MODE."""
import os, stat
from fastapi.testclient import TestClient
from app.main import app
import app.modules.m18_side_hustle_scraper.routes as R
from app.modules.m18_side_hustle_scraper.runner import DurableRunStore
S="/api/v1/side-hustle-scraper"
A={"x-atlas-tenant":"run-A","x-atlas-actor":"a"}; B={"x-atlas-tenant":"run-B","x-atlas-actor":"b"}
RUN={"title":"FIXTURE tutoring test","first_experiment":"Ask 5 students","max_budget":0}
c=TestClient(app,raise_server_exceptions=False)

def _step(run):  # first step with an external action
    return next(x["id"] for x in run["steps"] if x.get("external_action"))

def test_legacy_runs_are_owned_by_the_creating_tenant():
    r=c.post(S+"/runs",json=RUN,headers=A); assert r.status_code==200,r.text
    run=r.json(); rid=run["id"]; sid=_step(run)
    assert c.get(f"{S}/runs/{rid}",headers=A).status_code==200
    for call in (lambda: c.get(f"{S}/runs/{rid}",headers=B),
                 lambda: c.post(f"{S}/runs/{rid}/steps/{sid}/request-approval",json={},headers=B),
                 lambda: c.post(f"{S}/runs/{rid}/outcomes",json={"metric":"m","value":1,"unit":"u","observed_at":"2026-10-04T00:00:00Z"},headers=B),
                 lambda: c.post(f"{S}/runs/{rid}/steps/{sid}/receipts",json={},headers=B)):
        assert call().status_code==404
def test_approval_owner_is_the_authenticated_tenant_and_a_claimed_user_id_is_refused():
    run=c.post(S+"/runs",json=RUN,headers=A).json(); rid=run["id"]; sid=_step(run)
    assert c.post(f"{S}/runs/{rid}/steps/{sid}/request-approval",json={"user_id":"somebody-else"},headers=A).status_code==422
    ok=c.post(f"{S}/runs/{rid}/steps/{sid}/request-approval",json={},headers=A); assert ok.status_code==200,ok.text
    from app.core.approvals import default_service
    aid=c.get(f"{S}/runs/{rid}",headers=A).json()["steps"][[x["id"] for x in run["steps"]].index(sid)]["approval_id"]
    assert R._runner.approvals.get(aid)["user_id"]=="run-A"          # not 'default'
def test_durable_runs_tenant_keyed_and_approval_owner_authenticated():
    run=c.post(S+"/durable-runs",json=RUN,headers=A).json(); rid=run["id"]; sid=_step(run)
    assert c.get(f"{S}/durable-runs/{rid}",headers=B).status_code==404
    assert c.post(f"{S}/durable-runs/{rid}/steps/{sid}/request-approval",json={"user_id":"x"},headers=A).status_code==422
    assert c.post(f"{S}/durable-runs/{rid}/steps/{sid}/request-approval",json={},headers=B).status_code==404
    assert c.post(f"{S}/durable-runs/{rid}/steps/{sid}/request-approval",json={},headers=A).status_code==200
def test_durable_store_file_is_owner_only(tmp_path):
    p=tmp_path/"sub"/"runs.sqlite3"; DurableRunStore(p)
    assert stat.S_IMODE(os.stat(p).st_mode)==0o600
