"""G119: ordering gate computes completion, never trusts declared marks."""
from __future__ import annotations

import pytest

from app.modules.instinct_doc import ordering_gate_g119 as gate


REAL_MOD = '''"""Real module."""


def add(a, b):
    return a + b


def scale(xs, k):
    return [add(x, k) for x in xs]
'''
REAL_TEST = '''from mod import add


def test_add():
    assert add(2, 3) == 5
'''
STUB_MOD_PASS = '''def ship():
    pass
'''
STUB_MOD_NIE = '''def ship():
    raise NotImplementedError
'''
STUB_MOD_ELL = '''async def ship():
    ...
'''
FAIL_TEST = '''def test_nope():
    assert False
'''


def _repo(tmp_path, mod_src=REAL_MOD, test_src=REAL_TEST):
    (tmp_path / "mod.py").write_text(mod_src)
    (tmp_path / "test_mod.py").write_text(test_src)
    return {"as_of": "2026-10-12", "repo_root": str(tmp_path),
            "entries": [{"task_id": "t1", "module_path": "mod.py",
                         "test_path": "test_mod.py"}]}


def test_open_only_when_really_complete(tmp_path):
    out = gate.evaluate(_repo(tmp_path))
    assert out["verdict"] == "GATE_OPEN"
    r = out["results"][0]
    assert r["computed_complete"] and r["execution"]["executed"] and r["execution"]["passed"]
    assert r["module"]["real_functions"] == ["add", "scale"]
    assert r["tests"]["test_functions"] == ["test_add"]


@pytest.mark.parametrize("stub", [STUB_MOD_PASS, STUB_MOD_NIE, STUB_MOD_ELL])
def test_stub_modules_block(tmp_path, stub):
    out = gate.evaluate(_repo(tmp_path, mod_src=stub))
    assert out["verdict"] == "GATE_BLOCKED"
    assert any("stub" in f for f in out["results"][0]["failures"])


def test_failing_tests_block(tmp_path):
    out = gate.evaluate(_repo(tmp_path, test_src=FAIL_TEST))
    assert out["verdict"] == "GATE_BLOCKED"
    assert out["results"][0]["execution"]["executed"]
    assert "tests_failed" in out["results"][0]["failures"]


def test_missing_files_block(tmp_path):
    payload = _repo(tmp_path)
    (tmp_path / "test_mod.py").unlink()
    out = gate.evaluate(payload)
    assert out["verdict"] == "GATE_BLOCKED"
    assert "tests_missing" in out["results"][0]["failures"]


def test_run_tests_false_reports_not_executed(tmp_path):
    payload = _repo(tmp_path)
    payload["run_tests"] = False
    out = gate.evaluate(payload)
    assert out["verdict"] == "GATE_BLOCKED"  # not executed is not completion
    assert "tests_not_executed" in out["results"][0]["failures"]


def test_path_escape_and_bad_types_refused(tmp_path):
    payload = _repo(tmp_path)
    payload["entries"][0]["module_path"] = "../outside.py"
    with pytest.raises(ValueError, match="OGATE_REFUSED_BAD_PATH"):
        gate.evaluate(payload)
    with pytest.raises(ValueError, match="OGATE_REFUSED"):
        gate.evaluate({"as_of": "2026-10-12", "repo_root": str(tmp_path),
                       "entries": [{"task_id": "t1", "module_path": "mod.py",
                                    "test_path": "test_mod.py", "extra": 1}]})


def test_multi_entry_mixed_state(tmp_path):
    (tmp_path / "stub.py").write_text(STUB_MOD_PASS)
    (tmp_path / "test_stub.py").write_text("def test_ok():\n    assert True\n")
    payload = _repo(tmp_path)
    payload["entries"].append({"task_id": "t2", "module_path": "stub.py",
                               "test_path": "test_stub.py"})
    out = gate.evaluate(payload)
    assert out["verdict"] == "GATE_BLOCKED"
    assert out["tasks_computed_complete"] == 1 and out["tasks_total"] == 2
    assert out["results"][0]["computed_complete"]
    assert not out["results"][1]["computed_complete"]


def test_gate_against_this_repo_real_landed_groups():
    """The gate itself checks the G109-G118 lanes in the live repo."""
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[2]
    entries = [
        {"task_id": "g109", "module_path": "backend/app/market/predict.py",
         "test_path": "tests/market/test_predict_g109.py"},
        {"task_id": "g118", "module_path": "backend/app/modules/c30/masterplan_pdf.py",
         "test_path": "tests/modules/test_c30_masterplan_pdf_g118.py"},
    ]
    out = gate.evaluate({"as_of": "2026-10-12", "repo_root": str(root),
                         "entries": entries, "run_tests": False})
    assert {r["task_id"] for r in out["results"]} == {"g109", "g118"}
    for r in out["results"]:
        assert r["module"]["real_functions"], r
        assert r["tests"]["test_functions"], r
