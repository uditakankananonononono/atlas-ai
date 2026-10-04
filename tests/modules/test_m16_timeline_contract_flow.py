"""m16 timeline contract through the booted app (dev headers = TEST MODE): the snapshot timeline is filled ONLY by
topic 'timeline.upsert' events with payload.item; a malformed one is refused (422), not silently dropped."""
from fastapi.testclient import TestClient
from app.main import app
E="/api/v1/executive-dashboard"; H={"x-atlas-tenant":"m16tl","x-atlas-actor":"u"}
c=TestClient(app,raise_server_exceptions=False)
def ev(item): return {"topic":"timeline.upsert","aggregate_type":"timeline","aggregate_id":"t1","payload":{"item":item}}
ITEM={"id":"i1","title":"FIXTURE milestone","start":"2026-10-01T00:00:00","end":"2026-10-02T00:00:00","progress":0.2}

def test_timeline_upsert_appears_in_snapshot_and_other_topics_do_not():
    assert c.post(E+"/events",json={"topic":"opportunity.discovered","aggregate_type":"o","aggregate_id":"x"},headers=H).status_code==201
    assert c.get(E+"/snapshot",headers=H).json()["data"]["timeline"]==[]  # documented contract: not an event-derived feed
    r=c.post(E+"/events",json=ev(ITEM),headers=H); assert r.status_code==201,r.text
    tl=c.get(E+"/snapshot",headers=H).json()["data"]["timeline"]
    assert [t["id"] for t in tl]==["i1"] and tl[0]["title"]=="FIXTURE milestone"
def test_malformed_timeline_item_is_refused_not_silently_dropped():
    for bad in ({}, {"id":"i2"}, {"id":"i2","title":"t","start":"nope","end":"2026-10-02T00:00:00"}):
        assert c.post(E+"/events",json=ev(bad),headers=H).status_code==422
    assert c.post(E+"/events",json={"topic":"timeline.upsert","aggregate_type":"t","aggregate_id":"t"},headers=H).status_code==422  # no item at all
    assert c.post(E+"/events/batch",json=[ev({"id":"z"})],headers=H).status_code==422
def test_timeline_is_tenant_scoped():
    c.post(E+"/events",json=ev(ITEM),headers=H)
    assert c.get(E+"/snapshot",headers={"x-atlas-tenant":"m16other","x-atlas-actor":"u"}).json()["data"]["timeline"]==[]
