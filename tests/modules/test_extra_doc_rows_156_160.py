"""Extra doc rows 156-160 (m19 research features 125-129): covering pins.
Existing coverage at ce19b328: tests/modules/test_m19_research_110_134.py pins
artifact envelopes (source_bound, inputs echo, claims) for 125-129 and the
129 scenario_only claims override with its not-predicted caveat. New kills
here: the per-feature required-input refusals (repository, checksums,
target_audience, venue_policies, documented_features). The 129 claims asserts
below duplicate existing coverage and are regression guards only; the caveat
assert likewise. v4 (whole, tests-only, supersedes v3): after executed peer evidence that
head/tail pair pins survive middle-element REQ-tuple swaps on all five rows,
each row now pins anchored whole-message equality for every adjacent-pair
omission keys[i:i+2] (20 assertions across the five rows). Exchange argument:
a permutation preserving the relative order of every adjacent pair preserves
the chain order by transitivity, so any non-identity permutation reverses at
least one adjacent pair and fails here. v4 also pins None/[]/{} as missing and
0/False as VALID (not missing; e.g. row 160 publication_year=0) for every
required key of each row. Kills REQ-tuple reversal, middle-swap, rotation and
sentinel-extension (0/False) mutants. GREEN on ce19b328. Builder
self-report."""
from datetime import datetime, timezone

import pytest

from app.modules.m19_idea_incubator.business_models import Provenance
from app.modules.m19_idea_incubator.research_models import ResearchAnalysisRequest, ResearchFeature
from app.modules.m19_idea_incubator.research_service import ResearchAnalysisService

PROV = [Provenance(source_id="pin-1", source_type="experiment",
                   observed_at=datetime(2026, 1, 1, tzinfo=timezone.utc))]


def _req(feature, inputs, **kw):
    kw.setdefault("provenance", PROV)
    return ResearchAnalysisRequest(feature=ResearchFeature(feature), inputs=inputs,
                                   confidence=kw.pop("confidence", 0.9), **kw)


def test_row156_open_science_requires_repository():
    # GREEN on ce19b328; broken by M156 ("repository" removed from REQ[125]).
    out = ResearchAnalysisService().analyze("idea-1", _req(125, {
        "data_plan": "d", "code_plan": "c", "materials_plan": "m", "license": "CC-BY",
        "repository": "OSF", "privacy_constraints": "de-identified"}))
    assert out.method == "open-science checklist"
    assert out.analysis["source_bound"] is True
    with pytest.raises(ValueError, match="missing required inputs: repository"):
        ResearchAnalysisService().analyze("idea-1", _req(125, {
            "data_plan": "d", "code_plan": "c", "materials_plan": "m",
            "license": "CC-BY", "privacy_constraints": "de-identified"}))


def test_row157_reproducibility_requires_checksums():
    # GREEN on ce19b328; broken by M157 ("checksums" removed from REQ[126]).
    out = ResearchAnalysisService().analyze("idea-1", _req(126, {
        "artifacts": ["a"], "environment": "lockfile", "steps": ["s1"],
        "expected_outputs": ["o1"], "checksums": {"a": "sha256:..."}}))
    assert out.method == "reproducibility audit"
    with pytest.raises(ValueError, match="missing required inputs: checksums"):
        ResearchAnalysisService().analyze("idea-1", _req(126, {
            "artifacts": ["a"], "environment": "lockfile", "steps": ["s1"],
            "expected_outputs": ["o1"]}))


def test_row158_peer_review_requires_target_audience():
    # GREEN on ce19b328; broken by M158 ("target_audience" removed from REQ[127]).
    out = ResearchAnalysisService().analyze("idea-1", _req(127, {
        "manuscript_sections": ["intro"], "claims": ["c1"], "methods": "m",
        "limitations": ["l1"], "target_audience": "field reviewers"}))
    assert out.method == "pre-submission peer-review rubric"
    with pytest.raises(ValueError, match="missing required inputs: target_audience"):
        ResearchAnalysisService().analyze("idea-1", _req(127, {
            "manuscript_sections": ["intro"], "claims": ["c1"], "methods": "m",
            "limitations": ["l1"]}))


def test_row159_journal_match_requires_venue_policies():
    # GREEN on ce19b328; broken by M159 ("venue_policies" removed from REQ[128]).
    out = ResearchAnalysisService().analyze("idea-1", _req(128, {
        "manuscript_scope": "s", "methods": "m", "audience": "a",
        "candidate_venues": ["v1"], "venue_policies": {"v1": "open data required"}}))
    assert out.method == "journal scope-and-policy match"
    with pytest.raises(ValueError, match="missing required inputs: venue_policies"):
        ResearchAnalysisService().analyze("idea-1", _req(128, {
            "manuscript_scope": "s", "methods": "m", "audience": "a",
            "candidate_venues": ["v1"]}))


def test_row160_citation_estimate_is_scenario_only():
    # M160 (f==129 scenario_only override dropped) is ALSO killed by existing
    # test_row_129_no_impact_prediction; the new kill here is the
    # documented_features required-input refusal.
    out = ResearchAnalysisService().analyze("idea-1", _req(129, {
        "historical_comparables": ["c1"], "field": "f", "publication_year": 2026,
        "documented_features": ["df1"]}))
    assert out.method == "citation-scenario estimate"
    assert out.claims["impact_prediction"] == "scenario_only"
    assert out.claims["invented_studies"] is False
    assert any("not predicted" in s for s in out.uncertainty.limitations)
    with pytest.raises(ValueError, match="missing required inputs: documented_features"):
        ResearchAnalysisService().analyze("idea-1", _req(129, {
            "historical_comparables": ["c1"], "field": "f", "publication_year": 2026}))

REQ_156_160 = {
    125: ("data_plan", "code_plan", "materials_plan", "license", "repository",
          "privacy_constraints"),
    126: ("artifacts", "environment", "steps", "expected_outputs", "checksums"),
    127: ("manuscript_sections", "claims", "methods", "limitations",
          "target_audience"),
    128: ("manuscript_scope", "methods", "audience", "candidate_venues",
          "venue_policies"),
    129: ("historical_comparables", "field", "publication_year",
          "documented_features"),
}

VALID_156_160 = {
    125: {"data_plan": "d", "code_plan": "c", "materials_plan": "m",
          "license": "CC-BY", "repository": "OSF",
          "privacy_constraints": "de-identified"},
    126: {"artifacts": ["a"], "environment": "lockfile", "steps": ["s1"],
          "expected_outputs": ["o1"], "checksums": {"a": "sha256:..."}},
    127: {"manuscript_sections": ["intro"], "claims": ["c1"], "methods": "m",
          "limitations": ["l1"], "target_audience": "field reviewers"},
    128: {"manuscript_scope": "s", "methods": "m", "audience": "a",
          "candidate_venues": ["v1"],
          "venue_policies": {"v1": "open data required"}},
    129: {"historical_comparables": ["c1"], "field": "f",
          "publication_year": 2026, "documented_features": ["df1"]},
}


@pytest.mark.parametrize("feature", [125, 126, 127, 128, 129])
def test_rows156_160_adjacent_pair_omissions_pin_total_order(feature):
    # Kills any REQ-tuple permutation (reversal, middle swap, rotation).
    # Exchange argument: if a permutation preserved the relative order of every
    # adjacent pair (keys[i], keys[i+1]), the chain order would be preserved by
    # transitivity and the permutation would be the identity; hence any
    # non-identity permutation reverses at least one adjacent pair, and that
    # pair's omission produces the keys in the wrong order here. Anchored
    # whole-message match, one assertion per adjacent pair (20 total).
    keys = REQ_156_160[feature]
    valid = VALID_156_160[feature]
    for i in range(len(keys) - 1):
        pair = keys[i:i + 2]
        inputs = {k: v for k, v in valid.items() if k not in pair}
        with pytest.raises(ValueError, match="^missing required inputs: " + ", ".join(pair) + "$"):
            ResearchAnalysisService().analyze("idea-1", _req(feature, inputs))


@pytest.mark.parametrize("feature", [125, 126, 127, 128, 129])
def test_rows156_160_none_empty_list_empty_dict_count_as_missing(feature):
    # Kills the empty-clause-drop mutant (`or x[k] in (None,[],{})` removed):
    # every required key must be treated as missing when set to None, [], {}.
    for key in REQ_156_160[feature]:
        for bad in (None, [], {}):
            inputs = dict(VALID_156_160[feature])
            inputs[key] = bad
            with pytest.raises(ValueError, match="^missing required inputs: " + key + "$"):
                ResearchAnalysisService().analyze("idea-1", _req(feature, inputs))


@pytest.mark.parametrize("feature", [125, 126, 127, 128, 129])
def test_rows156_160_zero_and_false_are_valid_values(feature):
    # Pins the sentinel boundary: only None, [], {} count as missing. 0 and
    # False are legitimate values (row 160: publication_year=0) and must NOT be
    # refused. Kills mutants extending the sentinel tuple with 0 or False.
    for key in REQ_156_160[feature]:
        for val in (0, False):
            inputs = dict(VALID_156_160[feature])
            inputs[key] = val
            out = ResearchAnalysisService().analyze("idea-1", _req(feature, inputs))
            got = out.analysis["sections"][key]
            assert got == val and type(got) is type(val)
