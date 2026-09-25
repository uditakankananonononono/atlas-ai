"""Synthesize pytest suites for generated features.

Tests run in the sandbox BEFORE a feature may be proposed for activation.
Each suite checks the metadata contract, the kind-specific positive case,
empty input, wrong-type tolerance, and determinism.
"""
from __future__ import annotations

from .plans import FeaturePlan
from .safety import validate_source

_COMMON = '''
import json


def test_feature_metadata_contract():
    assert FEATURE["name"] == {name!r}
    assert FEATURE["kind"] == {kind!r}
    assert callable(run)


def test_empty_input():
    result = run([])
    assert isinstance(result, dict)


def test_wrong_type_tolerance():
    result = run([None, 42, {{"a": 1}}, "plain text"])
    assert isinstance(result, dict)


def test_determinism():
    sample = {sample!r}
    first = run(sample)
    second = run(sample)
    assert json.dumps(first, sort_keys=True, default=str) == json.dumps(second, sort_keys=True, default=str)

'''

_KIND_CASES = {
    "keyword_filter": '''

def test_keyword_filter_keeps_matches():
    result = run({sample!r})
    assert result["count"] >= 1
    assert all(any(k in json.dumps(i, default=str).lower() for k in {keywords!r})
               for i in result["items"])
''',
    "scoring_rule": '''

def test_scoring_rule_ranks_relevant_first():
    result = run({sample!r})
    assert result["scored"]
    assert result["scored"][0]["score"] >= result["scored"][-1]["score"]
    assert result["scored"][0]["selected"] is True
''',
    "text_transform": '''

def test_text_transform_changes_matching_strings():
    result = run({sample!r})
    assert result["changed"] >= 1
    assert len(result["items"]) == len({sample!r})
''',
    "aggregator": '''

def test_aggregator_groups_dict_items():
    result = run({sample!r})
    assert result["groups"]
    total = sum(v for v in result["groups"].values() if isinstance(v, int))
    assert total >= 1
''',
    "threshold_alert": '''

def test_threshold_alert_flags_crossing_items():
    result = run({sample!r})
    assert result["flagged"], "expected at least one flagged item"
    assert "skipped" in result
''',
    "field_extractor": '''

def test_field_extractor_pulls_named_fields():
    result = run({sample!r})
    assert result["matched_count"] >= 1
    assert any(r["extracted"] for r in result["records"])
''',
}


def synthesize_tests(plan: FeaturePlan, sample_items: list) -> str:
    if plan.kind not in _KIND_CASES:
        raise ValueError(f"no test template for kind {plan.kind!r}")
    header = "from feature import FEATURE, run\n" + _COMMON.format(
        name=plan.name, kind=plan.kind, sample=sample_items)
    case = _KIND_CASES[plan.kind].format(
        sample=sample_items,
        keywords=[str(k).lower() for k in plan.params.get("keywords", [])],
    )
    source = header + case
    validate_source(source, allowed_imports=frozenset({"json", "re", "feature"}))
    return source
