import pytest

from app.modules.catalog import MODULES
from app.self_improve.gate import APPROVED, ManualApprovalGate
from app.self_improve.mixin import SelfImprovingMixin
from app.self_improve.wiring import attach_all


class DummyService(SelfImprovingMixin):
    pass


def test_attach_all_covers_every_catalog_module(tmp_path):
    engines = attach_all(state_dir=tmp_path,
                         gate_factory=lambda slug: ManualApprovalGate(tmp_path / f"{slug}.json"))
    assert set(engines) == {m.slug for m in MODULES}
    assert len(engines) == 26
    assert len({e.module_id for e in engines.values()}) == 26


def test_mixin_requires_attachment():
    service = DummyService()
    with pytest.raises(RuntimeError, match="not attached"):
        service.self_improve()


def test_mixin_end_to_end(tmp_path):
    engines = attach_all(state_dir=tmp_path, gate_factory=lambda slug: ManualApprovalGate(
        tmp_path / f"{slug}.json", auto_approve=True))
    service = DummyService()
    engine = engines["grant-writer"]
    service.attach_self_improvement(engine)
    for _ in range(2):
        service.report_capability_gap("filter only biology grants",
                                      exemplar="a biology grant for phd students")
    report = service.self_improve()
    proposal = report["proposals"][0]
    engine.activate(proposal["key"], approval_id=proposal["approval_id"])
    out = service.dispatch_self_feature(proposal["name"],
                                        ["a biology grant for phd students", "pizza night"])
    assert out["count"] >= 1
    status = service.self_improvement_status()
    assert status["features"]
