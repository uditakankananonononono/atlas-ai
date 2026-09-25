import pytest

from app.self_improve.codegen import synthesize_code
from app.self_improve.plans import CAPABILITY_KINDS, FeaturePlan
from app.self_improve.safety import SafetyViolation, validate_source


def make_plan(kind, params=None, sig="gap sig"):
    return FeaturePlan(module_slug="m1", name=f"auto_{kind}", kind=kind,
                       description="d", gap_signature=sig, params=params or {})


def test_all_kinds_render_valid_code():
    for kind in CAPABILITY_KINDS:
        src = synthesize_code(make_plan(kind))
        assert "def run(items, params=None)" in src
        assert "FEATURE" in src
        validate_source(src)


def test_generated_code_executes():
    src = synthesize_code(make_plan("keyword_filter", {"keywords": ["alpha"]}))
    ns = {}
    exec(compile(src, "<t>", "exec"), ns)
    out = ns["run"](["alpha beta", "gamma"], None)
    assert out["items"] == ["alpha beta"]


def test_hostile_params_cannot_inject():
    plan = make_plan("keyword_filter", {
        "keywords": ['x");\nimport os\nos.system("id")\n#'],
        "mode": 'keep"""'}
    )
    src = synthesize_code(plan)
    validate_source(src)
    assert "import os" not in [l.strip() for l in src.splitlines()]


def test_scanner_blocks_forbidden_constructs():
    with pytest.raises(SafetyViolation):
        validate_source("import os\n")
    with pytest.raises(SafetyViolation):
        validate_source("exec('1+1')\n")
    with pytest.raises(SafetyViolation):
        validate_source("x = (1).__class__.__bases__\n")
    with pytest.raises(SafetyViolation):
        validate_source("async def f():\n    pass\n")
    with pytest.raises(SafetyViolation):
        validate_source("def f(:\n")


def test_scanner_allows_clean_code():
    validate_source("import re, json\ndef run(items, params=None):\n    return {'n': len(items)}\n")
