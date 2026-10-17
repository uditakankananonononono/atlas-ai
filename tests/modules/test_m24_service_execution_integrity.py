"""M24 service-level integrity regressions (real deps, stub persistence only).

Covers: approved-unknown-plan checkout refusal, reviewed-preview execution
reaching the locked durable boundary, plain approved checkout catalog binding,
the absence of the legacy repo.record_execution receipt path, and cancel
proposal tenant-mismatch HTTP mapping. Only the approval repo, approvals
center handle, tenant row, and dispatchers are stubbed; schemas, precommit,
routes and service logic are the real modules.
"""
import asyncio,inspect
from types import SimpleNamespace
import pytest
from app.modules.m24_billing.service import Service,PLANS
from app.modules.m24_billing.schemas import CheckoutIn,CancelIn,InvoiceIn,PreviewedCheckoutIn
from app.modules.m24_billing.precommit import preview_commitment
import app.modules.m24_billing.write_ahead as wa


class Approvals:
    def __init__(self):self.created=[]
    def put(self,request):self.created.append(request);return request


class Repo:
    def __init__(self,view=None,billing=None):
        self.view=view;self.billing=billing;self.executions=[]
    def approval(self,aid):return self.view
    def tenant_billing(self,tenant):return self.billing
    def record_execution(self,aid,result):
        self.executions.append(aid)
        raise AssertionError('legacy receipt not authoritative')


class StripeStub:
    async def create_checkout(self,*a):raise AssertionError('legacy direct provider call must not execute')
    async def cancel_subscription(self,*a):raise AssertionError('legacy direct provider call must not execute')
    async def create_invoice(self,*a):raise AssertionError('legacy direct provider call must not execute')


def approved(payload):return {"status":"approved","payload":payload}

PLAIN_PAYLOAD={"tenant_id":"t","plan":PLANS["pro"].model_dump(),"success_url":"https://ok.example","cancel_url":"https://no.example","mode":"subscription","provider":"stripe"}


def test_execute_checkout_unknown_approved_plan_refuses_named_error():
    view=approved({**PLAIN_PAYLOAD,"plan":{"id":"ghost","name":"Ghost","monthly_price_usd":5,"included_seats":1,"included_runs":1,"features":[]}})
    s=Service(Approvals(),Repo(view=view),StripeStub())
    with pytest.raises(ValueError,match="approved plan not in catalog"):
        asyncio.run(s.execute_checkout("a1","t"))


def test_reviewed_preview_checkout_reaches_locked_dispatch_boundary():
    plan=PLANS["pro"].model_dump()
    preview=preview_commitment(plan=plan,cancellation_policy="cancel anytime; access until period end")
    approvals=Approvals()
    s=Service(approvals,Repo(),StripeStub())
    proposal=s.propose_previewed_checkout("t",PreviewedCheckoutIn(success_url="https://ok.example",cancel_url="https://no.example",commitment_preview=preview))
    assert proposal.payload["expected_charge_cents"]==2900
    s.repo.view=approved(proposal.payload)
    with pytest.raises(wa.DispatchRefused,match="dispatch disabled"):
        asyncio.run(s.execute_checkout(proposal.approval_id,"t"))
    assert s.repo.executions==[]


def test_plain_approved_checkout_binds_exact_catalog_charge():
    # The plain approval payload carries the full plan snapshot; the durable
    # form refuses any drift between snapshot and catalog before dispatch.
    from app.modules.m24_billing.checkout_dispatcher import form_for
    s=Service(Approvals(),Repo(view=approved(PLAIN_PAYLOAD)),StripeStub())
    with pytest.raises(wa.DispatchRefused,match="dispatch disabled"):
        asyncio.run(s.execute_checkout("a1","t"))
    op=SimpleNamespace(action_type="create_subscription_checkout",tenant_id="t",approval_id="a1",id="op1",request=PLAIN_PAYLOAD)
    assert form_for(op)["line_items[0][price_data][unit_amount]"]=="2900"
    tampered=SimpleNamespace(action_type="create_subscription_checkout",tenant_id="t",approval_id="a1",id="op1",
        request={**PLAIN_PAYLOAD,"plan":{**PLAIN_PAYLOAD["plan"],"monthly_price_usd":1}})
    with pytest.raises(wa.DispatchRefused,match="catalog differs"):
        form_for(tampered)


def test_execute_approved_never_uses_legacy_receipt(monkeypatch):
    monkeypatch.setattr(wa,"require_dispatch_ready",lambda:None)
    class DispatcherRepo:
        def prepare(self,*a,**k):return {"id":"op1"}
    class Adapter:provider_account="acct_test"
    class Dispatcher:
        repo=DispatcherRepo();adapter=Adapter()
        async def dispatch(self,operation_id,tenant_id):return {"id":operation_id,"state":"succeeded"}
    view=approved({"tenant_id":"t","effect":"cancel_subscription","subscription_id":"sub_12345","customer_id":"cus_12345"})
    s=Service(Approvals(),Repo(view=view),StripeStub(),cancellation_dispatcher=Dispatcher())
    result=asyncio.run(s.execute_approved("a1","t"))
    assert result=={"id":"op1","state":"succeeded"}
    assert s.repo.executions==[]
    view=approved({"tenant_id":"t","effect":"create_draft_invoice","customer_id":"cus_12345"})
    s=Service(Approvals(),Repo(view=view),StripeStub(),invoice_dispatcher=Dispatcher())
    assert asyncio.run(s.execute_approved("a2","t"))=={"id":"op1","state":"succeeded"}
    assert s.repo.executions==[]


def test_service_has_no_legacy_record_execution_path():
    assert "record_execution" not in inspect.getsource(Service)


def test_cancel_proposal_tenant_mismatch_is_403_not_500():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.modules.m24_billing.routes import router,require_tenant,get_service
    billing=SimpleNamespace(subscription_id="sub_12345",customer_id="cus_12345",status="active",cancel_at_period_end=False)
    app=FastAPI();app.include_router(router)
    app.dependency_overrides[require_tenant]=lambda:SimpleNamespace(tenant_id="t")
    app.dependency_overrides[get_service]=lambda:Service(Approvals(),Repo(billing=billing),StripeStub())
    with TestClient(app,raise_server_exceptions=False) as client:
        mismatch=client.post("/billing/cancel-proposals",json={"subscription_id":"sub_other"})
        assert mismatch.status_code==403,mismatch.text
        ok=client.post("/billing/cancel-proposals",json={"subscription_id":"sub_12345"})
        assert ok.status_code==201 and ok.json()["payload"]["cancellation_terms"]["timing"]=="immediate"
