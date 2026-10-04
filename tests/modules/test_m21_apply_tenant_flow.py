"""Claire request -> approve -> apply with a real Meemee adapter + simulator (labeled simulator, no real device).
Shows the apply path honors tenant ownership end to end now that Service-created approvals carry tenant_id."""
import pytest
from app.core.models import ApprovalStatus
from app.modules.m21_claire.meemee_local_client import AdapterError
from tests.modules.test_m21_meemee_adapter import rig

A={"id":"a9","kind":"run_command","arguments":{"cmd":"ls"},"idempotency_key":"k9"}

@pytest.mark.asyncio
async def test_service_created_approval_for_owner_tenant_is_applied_once(tmp_path):
    reg,sim,ap,cl,s,g,calls=rig(tmp_path,"tenant-a")
    s.tenant_id="tenant-a"
    req=await s.local_action(g.id,A)
    assert req.status.value=="pending" and calls==[]
    with pytest.raises(AdapterError):await cl.execute(A,req.id)            # pending: not applied
    assert ap.decide(req.id,ApprovalStatus.APPROVED,user_id="tenant-b") is None  # foreign tenant cannot approve
    with pytest.raises(AdapterError):await cl.execute(A,req.id)
    ap.decide(req.id,ApprovalStatus.APPROVED,user_id="tenant-a")
    r=await s.local_action(g.id,A,req.id)
    assert r["result"]=={"ran":"ls"} and calls==["ls"]
    with pytest.raises(AdapterError):await cl.execute(dict(A,idempotency_key="k10"),req.id)  # single use

@pytest.mark.asyncio
async def test_approval_created_by_another_tenants_service_cannot_apply_on_this_tenants_device(tmp_path):
    reg,sim,ap,cl,s,g,calls=rig(tmp_path,"tenant-a")
    s.tenant_id="tenant-b"                       # a request made under tenant B
    req=await s.local_action(g.id,A)
    ap.decide(req.id,ApprovalStatus.APPROVED,user_id="tenant-b")
    with pytest.raises(AdapterError):await cl.execute(A,req.id)   # A's device refuses B's approved approval
    assert calls==[]
