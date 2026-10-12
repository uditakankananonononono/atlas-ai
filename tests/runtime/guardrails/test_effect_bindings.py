"""Row 137/142 coverage binding: statuses/counts computed under declared policy tables (not certified)."""
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
    print(f"EFFECT_BINDINGS total={len(res)} GATED={c['GATED']} EXEMPT-BY-DESIGN={c['EXEMPT-BY-DESIGN']} UNGATED={c['UNGATED']} (computed under declared policy tables, not certified)")


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


def test_generic_m01_transport_is_not_read_exempt():
    res = eb.classify()
    assert res["modules/m01_opportunity_discovery/http.py"]["status"] == "UNGATED"
    assert "POST" in res["modules/m01_opportunity_discovery/http.py"]["evidence"]


def test_m18_response_body_is_not_a_request_write():
    import ast
    rel = "modules/m18_side_hustle_scraper/lane_http.py"
    tree = ast.parse((eb.APP / rel).read_text())
    requests = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute) and n.func.attr == "Request"]
    assert requests and all(not any(k.arg in ("data", "method") for k in n.keywords) for n in requests)
    assert eb.classify()[rel]["status"] == "EXEMPT-BY-DESIGN"


def test_dead_gate_import_cannot_make_egress_gated(monkeypatch):
    import ast
    rel = "fixture/dead.py"
    source = "import httpx\nfrom app.runtime.guardrails.enforcer import GuardrailEnforcer\nhttpx.post('https://offline.invalid')\n"
    monkeypatch.setattr(eb, "_files", lambda: [(rel, source, ast.parse(source))])
    assert eb.classify()[rel]["status"] == "UNGATED"


def test_no_package_publish_call_cannot_vacuously_gate(monkeypatch):
    import ast
    rel = "modules/m06_social_media_manager/adapters.py"
    source = "import httpx\nasync def publish(request): pass\n"
    monkeypatch.setattr(eb, "_files", lambda: [(rel, source, ast.parse(source))])
    assert eb.classify()[rel]["status"] == "UNGATED"


def _assert_clicky_rationale_matches_source(source, note):
    """Narrow structural binding of the reviewed gap, not a runtime gate certificate."""
    import ast
    tree = ast.parse(source)
    functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    fetch, execute = functions["_fetch"], functions["execute_stats_request"]
    requests = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and isinstance(n.func.value, ast.Name) and n.func.value.id == "_urlreq"
                and n.func.attr == "Request"]
    assert len(requests) == 1 and requests[0] in list(ast.walk(fetch))
    keywords = {k.arg: k.value for k in requests[0].keywords}
    assert "data" not in keywords and ast.literal_eval(keywords["method"]) == "GET"
    base_guard = next(n for n in execute.body if isinstance(n, ast.If)
                      and ast.unparse(n.test) == "base_url is None")
    guard = base_guard.body[0]
    expected = ast.parse('live_approved is not True or os.environ.get(LIVE_ENV_FLAG) != "1"', mode="eval").body
    assert isinstance(guard, ast.If) and ast.dump(guard.test) == ast.dump(expected)
    assert isinstance(guard.body[0], ast.Raise)
    assert ast.unparse(guard.body[0].exc) == "ValueError('APPLY_REFUSED_NOT_APPROVED')"
    flag = next(n for n in tree.body if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "LIVE_ENV_FLAG" for t in n.targets))
    assert ast.literal_eval(flag.value) == "ATLAS_CLICKY_LIVE_OWNER_APPROVED"
    assert "live_approved=True AND ATLAS_CLICKY_LIVE_OWNER_APPROVED=1" in note
    assert "default-off guard, not M00 authority" in note
    assert "ThreadPoolExecutor.submit" in note and "no network write" in note
    assert "one GET" in note and "baselined, not gated" in note


def test_reviewed_ungated_rationale_is_code_bound():
    baseline = set(pathlib.Path(__file__).with_name("egress_ungated_baseline.txt").read_text().split())
    snapshot = json.loads(SNAPSHOT.read_text())
    res = eb.classify()
    for rel, note in eb.REVIEWED_UNGATED.items():
        assert rel in baseline and rel in snapshot and rel in res
        assert snapshot[rel]["status"] == res[rel]["status"] == "UNGATED"
        assert note in res[rel]["evidence"] and note in snapshot[rel]["evidence"]
        if rel == "modules/c31/clicky.py":
            _assert_clicky_rationale_matches_source((eb.APP / rel).read_text(), note)
        else:
            raise AssertionError("new reviewed gap requires its own code-bound rationale test")


def test_clicky_guard_and_method_removal_are_detected_without_regenerating_snapshot():
    rel = "modules/c31/clicky.py"
    source, note = (eb.APP / rel).read_text(), eb.REVIEWED_UNGATED[rel]
    _assert_clicky_rationale_matches_source(source, note)
    import pytest
    for old, new in (('if live_approved is not True or os.environ.get(LIVE_ENV_FLAG) != "1":', 'if False:'),
                     ('method="GET")', 'method="POST")')):
        assert old in source
        with pytest.raises(AssertionError):
            _assert_clicky_rationale_matches_source(source.replace(old, new, 1), note)


def test_clicky_rationale_wording_cannot_overclaim_owner_authority():
    import pytest
    rel = "modules/c31/clicky.py"
    source, note = (eb.APP / rel).read_text(), eb.REVIEWED_UNGATED[rel]
    with pytest.raises(AssertionError):
        _assert_clicky_rationale_matches_source(source, note.replace("default-off guard, not M00 authority",
                                                                   "M00 authority verified"))
