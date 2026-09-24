"""M20 planner/executive bound to the free-first model layer."""
from __future__ import annotations

import asyncio

import pytest

from app.core import model_catalog
from app.core.providers import ProviderError
from app.modules.m20_general_cognitive_worker import model_adapters as ma
from app.modules.m20_general_cognitive_worker.htn_planner import HTNPlanner, PlanError
from app.modules.m20_general_cognitive_worker.schemas import Risk


def _reply(monkeypatch, text=None, exc=None, seen=None):
    async def fake(prompt, model_name=None):
        if seen is not None:
            seen.append((prompt, model_name))
        if exc:
            raise exc
        return "ollama", "llama3.1:8b", text
    monkeypatch.setattr(model_catalog, "generate_free_first", fake)


PLAN = '''Sure:
```json
[{"id":"s1","title":"Find scholarships","tool":"web_search","risk":"read"},
 {"id":"s2","title":"Email the coordinator","tool":"send_email","risk":"read","depends_on":["s1"]},
 {"id":"s3","title":"Summarise","tool":null,"depends_on":["s2"]}]
```'''


def test_planner_decomposes_through_real_htn_validation(monkeypatch):
    seen = []
    _reply(monkeypatch, PLAN, seen=seen)
    model = ma.FreeFirstPlannerModel({"web_search": Risk.READ, "send_email": Risk.EXTERNAL}, model_name="inkling")
    nodes = HTNPlanner(model=model).decompose("apply for three scholarships")
    assert [n.title for n in nodes] == ["Find scholarships", "Email the coordinator", "Summarise"]
    assert nodes[1].risk == Risk.EXTERNAL, "model may not label a sending tool as read"
    assert nodes[2].tool is None and nodes[1].depends_on == [nodes[0].id]
    assert seen[0][1] == "inkling" and "send_email (external)" in seen[0][0]
    assert model.last_route == ("ollama", "llama3.1:8b")


def test_planner_uses_live_registry_risks(monkeypatch):
    class Reg:
        def describe(self):
            return [{"name": "send_email", "risk": "irreversible"}]
    _reply(monkeypatch, PLAN)
    model = ma.FreeFirstPlannerModel(model_name="")
    model.bind_registry(Reg())
    steps = model.decompose("x")
    assert steps[1]["risk"] == "irreversible"


def test_planner_turns_provider_stop_into_plan_error(monkeypatch):
    _reply(monkeypatch, exc=ProviderError("no free model route succeeded; Atlas stopped instead of using a paid provider."))
    with pytest.raises(PlanError, match="planner model unavailable: no free model route"):
        HTNPlanner(model=ma.FreeFirstPlannerModel(model_name="")).decompose("brand new goal")


def test_planner_rejects_non_json(monkeypatch):
    _reply(monkeypatch, "I think you should just do it.")
    with pytest.raises(PlanError, match="no parseable JSON"):
        ma.FreeFirstPlannerModel(model_name="").decompose("x")


def test_executive_reflect_returns_dict_and_degrades_without_models(monkeypatch):
    _reply(monkeypatch, '{"cause":"timeout","fix":"retry later","retry":true}')
    out = ma.FreeFirstExecutiveModel(model_name="").complete("reflect", {"goal": "g", "error": "timeout"})
    assert out["cause"] == "timeout" and out["route"] == "ollama/llama3.1:8b"
    _reply(monkeypatch, exc=ProviderError("stopped"))
    assert ma.FreeFirstExecutiveModel(model_name="").complete("reflect", {})["available"] is False


def test_adapter_works_inside_a_running_event_loop(monkeypatch):
    _reply(monkeypatch, '{"ok": true}')
    async def inside():
        return ma.FreeFirstExecutiveModel(model_name="").complete("reflect", {})
    assert asyncio.run(inside())["ok"] is True


def test_routing_can_be_turned_off(monkeypatch):
    monkeypatch.setenv("ATLAS_GCW_MODEL_ROUTING", "off")
    assert ma.bound_models() == {}
    monkeypatch.delenv("ATLAS_GCW_MODEL_ROUTING")
    assert set(ma.bound_models()) == {"planner_model", "executive_model"}
