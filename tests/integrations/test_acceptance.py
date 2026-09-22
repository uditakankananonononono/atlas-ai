import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.integrations.acceptance import AcceptanceCatalog, AcceptanceStore, AdapterSpec, ExactWriteApproval, UnsafeWriteProbe
from app.integrations import acceptance_routes

@pytest.mark.asyncio
async def test_configuration_never_counts_as_acceptance_and_tenants_are_isolated(monkeypatch):
    monkeypatch.setenv("FAKE_TOKEN", "yes")
    seen=[]
    async def read(tenant): seen.append(tenant)
    catalog=AcceptanceCatalog([AdapterSpec("fake","Fake",("FAKE_TOKEN",),("read",),"/reconnect",read)],AcceptanceStore())
    assert catalog.status("a","fake")["configured"] is True
    assert catalog.status("a","fake")["live_accepted"] is False
    result=await catalog.probe_read("a","fake")
    assert result["live_accepted"] is True and result["last_successful_read"]
    assert catalog.status("b","fake")["live_accepted"] is False
    assert seen == ["a"]

@pytest.mark.asyncio
async def test_failed_probe_records_reason_without_accepting(monkeypatch):
    monkeypatch.setenv("FAKE_TOKEN", "yes")
    def broken(_): raise ConnectionError("vendor unavailable")
    catalog=AcceptanceCatalog([AdapterSpec("fake","Fake",("FAKE_TOKEN",),(),"/reconnect",broken)])
    with pytest.raises(Exception,match="vendor unavailable"): await catalog.probe_read("a","fake")
    status=catalog.status("a","fake")
    assert status["live_accepted"] is False
    assert "vendor unavailable" in status["failure_reason"]

@pytest.mark.asyncio
async def test_write_probe_requires_exact_approval_and_sandbox(monkeypatch):
    monkeypatch.setenv("FAKE_TOKEN", "yes"); writes=[]
    def write(tenant,resource,payload): writes.append((tenant,resource,payload))
    catalog=AcceptanceCatalog([AdapterSpec("fake","Fake",("FAKE_TOKEN",),("write",),"/reconnect",lambda _:None,write,("sandbox:test",))])
    wrong=ExactWriteApproval(True,"fake","create","production")
    with pytest.raises(UnsafeWriteProbe): await catalog.probe_write("a","fake","create","production",wrong,{})
    approval=ExactWriteApproval(True,"fake","create","sandbox:test")
    result=await catalog.probe_write("a","fake","create","sandbox:test",approval,{"value":1})
    assert result["write_accepted"] is True and result["last_successful_write"]
    assert writes == [("a","sandbox:test",{"value":1})]


def test_routes_use_authenticated_tenant_and_reject_unapproved_write(monkeypatch):
    monkeypatch.setenv("FAKE_TOKEN", "yes")
    fake=AcceptanceCatalog([AdapterSpec("fake","Fake",("FAKE_TOKEN",),("read","write"),"/reconnect",lambda _:None,lambda *_:None,("sandbox",))])
    monkeypatch.setattr(acceptance_routes,"catalog",fake)
    app=FastAPI();app.include_router(acceptance_routes.router,prefix="/api/v1")
    client=TestClient(app); headers={"X-Atlas-Tenant":"tenant-a","X-Atlas-Actor":"owner"}
    before=client.get("/api/v1/integrations/acceptance",headers=headers).json()["integrations"][0]
    assert before["configured"] is True and before["live_accepted"] is False
    assert client.post("/api/v1/integrations/acceptance/fake/probe/read",headers=headers).status_code==200
    body={"action":"create","resource":"sandbox","approval":{"approved":False,"adapter_id":"fake","action":"create","resource":"sandbox"}}
    assert client.post("/api/v1/integrations/acceptance/fake/probe/write",headers=headers,json=body).status_code==403
