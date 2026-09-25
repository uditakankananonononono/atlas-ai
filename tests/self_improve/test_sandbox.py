from app.self_improve.codegen import synthesize_code
from app.self_improve.plans import Candidate, FeaturePlan
from app.self_improve.sandbox import SandboxRunner
from app.self_improve.testsynth import synthesize_tests


_DEFAULT_PARAMS = {
    "keyword_filter": {"keywords": ["grant"], "mode": "keep"},
    "scoring_rule": {"weights": {"grant": 1.0}, "threshold": 1.0},
    "text_transform": {"pattern": r"\s+", "replacement": " "},
    "aggregator": {"group_by": "category", "op": "count", "value_field": "value"},
    "threshold_alert": {"field": "value", "threshold": 0.0, "direction": "above"},
    "field_extractor": {"fields": {"email": r"[\w.+-]+@[\w-]+\.[\w.]+"}},
}


def candidate(kind="keyword_filter", params=None):
    plan = FeaturePlan(module_slug="m1", name=f"auto_{kind}", kind=kind,
                       description="d", gap_signature="g",
                       params=params or _DEFAULT_PARAMS[kind])
    code = synthesize_code(plan)
    from app.self_improve.engine import _KIND_SAMPLES
    tests = synthesize_tests(plan, list(_KIND_SAMPLES[kind]))
    return Candidate(plan=plan, code=code, test_code=tests)


def test_sandbox_passes_good_candidate():
    result = SandboxRunner(timeout_seconds=60).run(candidate())
    assert result.passed, result.stdout + result.stderr
    assert result.exit_code == 0


def test_sandbox_all_kinds():
    for kind in ("scoring_rule", "text_transform", "aggregator",
                 "threshold_alert", "field_extractor"):
        result = SandboxRunner(timeout_seconds=60).run(candidate(kind))
        assert result.passed, f"{kind}: {result.stdout}{result.stderr}"


def test_sandbox_catches_failing_feature():
    c = candidate()
    bad = Candidate(plan=c.plan, code=c.code,
                    test_code=c.test_code + "\n\ndef test_forced_failure():\n    assert False\n")
    result = SandboxRunner(timeout_seconds=60).run(bad)
    assert not result.passed
    assert result.exit_code != 0
