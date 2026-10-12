"""Deepening tests for the c31 clicky and okara plan layer (rows 57 and 58). Hermetic: no network, no live call.
They pin two behaviors that the existing a3 tests did not pin: planned parameter order and base-URL joining."""
import importlib.util, pathlib, sys

_ROOT = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/c31"


def _load(name):
    spec = importlib.util.spec_from_file_location("c31_deep_" + name, _ROOT / (name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["c31_deep_" + name] = mod
    spec.loader.exec_module(mod)
    return mod


def _desc(name, base):
    return {"name": name, "docs_url": "https://example.test/help/api", "api_base": base, "free_tier": True,
            "pricing_evidence": "supplied snapshot: free tier listed", "key_ref": name.upper() + "_API_KEY",
            "endpoints": {"stats": {"path": "/api/stats", "method": "GET"}}}


def _check(name):
    m = _load(name)
    ident = m.identify(_desc(name, "https://api.example.test/"))["descriptor"]
    plan = m.plan_request(ident, "stats", {"z": "3", "a": "1", "m": "2"})
    assert list(plan["params"]) == ["a", "m", "z"]
    assert plan["encoded"] == "a=1&m=2&z=3"
    assert plan["url"] == "https://api.example.test/api/stats"
    ident2 = m.identify(_desc(name, "https://api.example.test"))["descriptor"]
    assert m.plan_request(ident2, "stats", {})["url"] == "https://api.example.test/api/stats"


def test_clicky_plan_orders_params_and_joins_base_url():
    _check("clicky")


def test_okara_plan_orders_params_and_joins_base_url():
    _check("okara")
