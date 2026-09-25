import pytest

from app.self_improve.detector import CapabilityGap
from app.self_improve.planner import FeaturePlanner, NullRefiner


def gap(signature, detail=""):
    return CapabilityGap(module_slug="m1", signature=signature, occurrences=3,
                         kinds=("capability_miss",), exemplars=(), detail=detail,
                         first_seen=0.0, last_seen=1.0, severity=0.5)


def test_kind_rules():
    planner = FeaturePlanner()
    assert planner.plan(gap("cannot extract invoice dates")).kind == "field_extractor"
    assert planner.plan(gap("please rank applicants")).kind == "scoring_rule"
    assert planner.plan(gap("alert me when spend exceeds limit")).kind == "threshold_alert"
    assert planner.plan(gap("group results by category")).kind == "aggregator"
    assert planner.plan(gap("normalize whitespace in titles")).kind == "text_transform"
    assert planner.plan(gap("filter only biology grants")).kind == "keyword_filter"
    assert planner.plan(gap("something else entirely")).kind == "keyword_filter"


def test_plan_params_and_names():
    plan = FeaturePlanner().plan(gap("filter only biology grants"))
    assert plan.name.startswith("auto_")
    assert "biology" in plan.params["keywords"] or "filter" in plan.params["keywords"]
    assert plan.gap_signature == "filter only biology grants"


def test_refiner_cannot_escape_whitelist():
    class EvilRefiner:
        def refine(self, plan, g):
            from app.self_improve.plans import FeaturePlan
            return FeaturePlan(module_slug=plan.module_slug, name=plan.name,
                               kind="arbitrary_code", description="x",
                               gap_signature=plan.gap_signature)
    with pytest.raises(ValueError):
        FeaturePlanner(refiner=EvilRefiner()).plan(gap("filter grants"))


def test_null_refiner_is_identity():
    planner = FeaturePlanner(refiner=NullRefiner())
    plan = planner.plan(gap("rank things"))
    assert plan.kind == "scoring_rule"
