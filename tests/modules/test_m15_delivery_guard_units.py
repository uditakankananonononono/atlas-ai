"""Focused negative unit tests, one per delivery guard, each isolating that guard from the layers that normally also
block (found by mutation: the HTTP/flow tests did not pin these). Uses the env fixture of test_m15_approved_delivery."""
import pytest

from app.core.models import ApprovalStatus
from app.modules.m15_document_generator.delivery import DeliveryConflict, DeliveryForbidden, DeliveryNotFound
from tests.modules.test_m15_approved_delivery import REPORT, approve, env  # noqa: F401


def test_payload_tenant_binding_refuses_approval_whose_payload_names_another_tenant(env):  # noqa: F811
    good, version = approve(env, "docx", REPORT, approve=False)
    payload = dict(env.center.get(good)["payload"])
    assert payload["tenant_id"] == "tenant-a"
    forged = env.center.submit(module_id=15, action_type="render_document", user_id="tenant-a",
                               payload={**payload, "tenant_id": "tenant-b"})  # owned by A, payload bound to B
    env.center.decide(forged["id"], ApprovalStatus.APPROVED, decided_by="udita")
    with pytest.raises(DeliveryForbidden, match="another tenant"):
        env.svc("tenant-a").deliver(forged["id"])
    assert env.svc("tenant-a").list() == []  # nothing was delivered


def test_already_delivered_precheck_answers_conflict_with_readback_hint_before_any_permit_logic(env):  # noqa: F811
    aid, _ = approve(env, "docx", REPORT)
    svc = env.svc()
    svc.deliver(aid)
    with pytest.raises(DeliveryConflict, match="read it back"):
        svc.deliver(aid)


def test_download_rejects_a_validly_signed_token_whose_tenant_claim_is_another_tenant(env):  # noqa: F811
    aid_b, _ = approve(env, "docx", REPORT, tenant="tenant-b")
    receipt_b = env.svc("tenant-b").deliver(aid_b)
    # a token validly signed for tenant-a but naming B's approval + B's real sha: only the tenant claim check can refuse it
    token, _ = env.store.sign("tenant-a", aid_b, receipt_b["sha256"], 60)
    with pytest.raises(DeliveryNotFound):
        env.svc("tenant-b").download(token)
    data, _ = env.svc("tenant-b").download(env.store.sign("tenant-b", aid_b, receipt_b["sha256"], 60)[0])
    assert data  # control: the same shape with the right tenant claim works
