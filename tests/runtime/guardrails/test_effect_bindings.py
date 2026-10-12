"""Row 137/142 coverage binding: computed statuses, counts declared (not certified)."""
import json
import pathlib

import importlib.util

_spec = importlib.util.spec_from_file_location("effect_bindings", pathlib.Path(__file__).with_name("effect_bindings.py"))
eb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(eb)

SNAPSHOT = pathlib.Path(__file__).with_name("effect_bindings_snapshot.json")


def test_every_egress_module_has_exactly_one_status_and_evidence():
    res = eb.classify()
    assert res, "scan found no egress modules: wrong root?"
    for rel, v in res.items():
        assert v["status"] in ("GATED", "EXEMPT-BY-DESIGN", "UNGATED") and v["evidence"], rel


def test_gated_callers_have_gate_call_and_refusal_test():
    for rel, (needle, test) in eb.GATED_CALLERS.items():
        assert needle in (eb.APP / rel).read_text(encoding="utf-8"), rel
        assert (eb.ROOT / test).is_file(), test


def test_exempt_reasons_name_existing_prefixes():
    for pfx, reason in eb.EXEMPT_REASONS:
        assert reason and any(p.relative_to(eb.APP).as_posix().startswith(pfx) for p in eb.APP.rglob("*.py")), pfx


def test_snapshot_matches_computation_and_prints_declared_counts(capsys):
    res = eb.classify()
    got = {k: {"status": v["status"], "evidence": v["evidence"]} for k, v in sorted(res.items())}
    want = json.loads(SNAPSHOT.read_text())
    assert got == want, "binding changed: review the diff, then regenerate effect_bindings_snapshot.json"
    c = eb.counts(res)
    print(f"EFFECT_BINDINGS total={len(res)} GATED={c['GATED']} EXEMPT-BY-DESIGN={c['EXEMPT-BY-DESIGN']} UNGATED={c['UNGATED']} (declared by computation, not certified)")


def test_gated_status_is_computed_not_declared(monkeypatch):
    m06 = "modules/m06_social_media_manager/adapters.py"
    assert eb.classify()[m06]["status"] == "GATED"
    monkeypatch.setattr(eb, "GATED_CALLERS", {})
    assert eb.classify()[m06]["status"] == "UNGATED"


def test_missing_refusal_test_file_drops_gated(monkeypatch):
    m06 = "modules/m06_social_media_manager/adapters.py"
    callers = dict(eb.GATED_CALLERS)
    callers["modules/m06_social_media_manager/scheduler.py"] = ("dispatch_outbound", "tests/does_not_exist.py")
    monkeypatch.setattr(eb, "GATED_CALLERS", callers)
    assert eb.classify()[m06]["status"] == "UNGATED"
