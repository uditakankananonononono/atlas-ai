import hashlib
from pathlib import Path

import pytest

from app.self_improve.registry import FeatureRegistry, RegistryError

CODE = '''FEATURE = {"name": "demo", "kind": "keyword_filter", "version": 1}

def run(items, params=None):
    return {"items": [i for i in items if "x" in str(i)], "count": 0}
'''
CODE_V2 = CODE.replace('"count": 0', '"count": len([i for i in items if "x" in str(i)])')
TESTS = "def test_ok():\n    assert True\n"


def propose(registry, code=CODE):
    return registry.save_proposal("k" + hashlib.sha256(code.encode()).hexdigest()[:8],
                                  name="demo", kind="keyword_filter", code=code,
                                  test_code=TESTS, gap_signature="sig")


def test_activate_and_dispatch(tmp_path):
    reg = FeatureRegistry("m1", tmp_path)
    propose(reg)
    entry = reg.activate("k" + hashlib.sha256(CODE.encode()).hexdigest()[:8], approval_id="a1")
    assert entry["version"] == 1
    out = reg.dispatch("demo", ["x1", "y2", "x3"])
    assert out["items"] == ["x1", "x3"]


def test_tampered_feature_refuses_to_run(tmp_path):
    reg = FeatureRegistry("m1", tmp_path)
    key = propose(reg) and "k" + hashlib.sha256(CODE.encode()).hexdigest()[:8]
    entry = reg.activate(key, approval_id="a1")
    Path(entry["file"]).write_text(CODE + "\n# hand edit\n", encoding="utf-8")
    with pytest.raises(RegistryError, match="integrity"):
        reg.dispatch("demo", ["x"])


def test_changed_candidate_refuses_activation(tmp_path):
    reg = FeatureRegistry("m1", tmp_path)
    key = "k" + hashlib.sha256(CODE.encode()).hexdigest()[:8]
    proposal = propose(reg)
    Path(proposal["code_file"]).write_text(CODE_V2, encoding="utf-8")
    with pytest.raises(RegistryError, match="changed since proposal"):
        reg.activate(key, approval_id="a1")


def test_rollback_to_previous_version(tmp_path):
    reg = FeatureRegistry("m1", tmp_path)
    k1 = "k" + hashlib.sha256(CODE.encode()).hexdigest()[:8]
    propose(reg, CODE)
    reg.activate(k1, approval_id="a1")
    k2 = "k" + hashlib.sha256(CODE_V2.encode()).hexdigest()[:8]
    propose(reg, CODE_V2)
    reg.activate(k2, approval_id="a2")
    assert reg._load()["features"]["demo"]["active_version"] == 2
    outcome = reg.rollback("demo", approval_id="a3")
    assert outcome == {"name": "demo", "rolled_back_from": 2, "active_version": 1}
    assert reg.dispatch("demo", ["x"])["items"] == ["x"]


def test_path_containment(tmp_path):
    reg = FeatureRegistry("m1", tmp_path)
    with pytest.raises(RegistryError):
        reg._contained(tmp_path.parent / "evil.py")


def test_persistence_across_instances(tmp_path):
    reg = FeatureRegistry("m1", tmp_path)
    key = "k" + hashlib.sha256(CODE.encode()).hexdigest()[:8]
    propose(reg)
    reg.activate(key, approval_id="a1")
    fresh = FeatureRegistry("m1", tmp_path)
    assert fresh.dispatch("demo", ["xa", "b"])["items"] == ["xa"]
    assert fresh.covers_gap("sig")
