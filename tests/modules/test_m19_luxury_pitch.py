import csv, io, pytest
from app.modules.m19_idea_incubator.luxury_ideation import generate_ideas
from app.modules.m19_idea_incubator.luxury_pitch import build_pitch_assets
from app.modules.m19_idea_incubator.luxury_outreach import LuxuryOutreachQueue
from tests.modules.test_m19_luxury_ideation import CAR

def first(): return generate_ideas(CAR)["ideas"][0]

def test_assets_cite_real_sources_and_carry_limits():
    a = build_pitch_assets(CAR, first(), {"label": "possible-prior-art", "caveat": "searched one index"}, {"built": ["ownership_care"], "all_tests_passed": True})
    md = a["files"]["brief.md"]
    assert "No affiliation" in md and "## Claim limits" in md and "possible-prior-art" in md and "passed" in md
    assert a["review_status"] == "pending" and a["external_action_started"] is False
    assert all(sid in md for sid in a["evidence_refs"])
    rows = list(csv.reader(io.StringIO(a["files"]["scorecard.csv"]))); assert rows[0] == ["metric", "value"] and any(r[0] == "total" for r in rows)

def test_failed_prototype_is_stated_not_hidden():
    a = build_pitch_assets(CAR, first(), None, {"built": ["x"], "all_tests_passed": False})
    assert "did NOT all pass" in a["files"]["brief.md"] and "unchecked" in a["files"]["brief.md"]

def test_html_is_escaped():
    i = first(); i["mechanism"] = "<script>alert(1)</script>"
    assert "<script>" not in build_pitch_assets(CAR, i)["files"]["one-pager.html"]

def test_unknown_source_or_no_evidence_rejected():
    i = first(); i["evidence"][0]["source_ids"] = ["nope"]
    with pytest.raises(ValueError, match="unknown sources"): build_pitch_assets(CAR, i)
    j = first(); j["evidence"] = []
    with pytest.raises(ValueError, match="without evidence"): build_pitch_assets(CAR, j)

def test_assets_alone_cannot_trigger_a_send():
    # assets are data; the only send path is the approval-gated queue, whose default adapter refuses
    from app.modules.m19_idea_incubator.luxury_outreach import refuse_sender, OutreachRefused
    with pytest.raises(OutreachRefused): refuse_sender({})
