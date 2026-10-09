import asyncio
import pytest
from app.modules.m19_idea_incubator.luxury_venture import VentureBrief
from app.modules.m19_idea_incubator.luxury_ideation import generate_ideas
from app.modules.m19_idea_incubator.luxury_priorart import check_idea, check_ideas

def mk(name, sector, stmts, caps):
    n = len(stmts)
    return VentureBrief.model_validate({
        "brand_or_segment": name, "sector": sector, "customer_job": "Help customers get more value from the brand experience.",
        "constraints": ["consent"],
        "sources": [{"source_id": f"s{i}", "url": "https://example.com/" + str(i), "title": "t" + str(i), "observed_at": "2026-10-01", "finding": f"Finding text number {i} about the brand."} for i in range(max(2, n))],
        "signals": [{"signal_id": f"g{i}", "statement": s, "source_ids": [f"s{i}"], "importance": imp} for i, (s, imp) in enumerate(stmts)],
        "capabilities": [{"capability_id": cid, "description": d, "readiness": r} for cid, d, r in caps]})

CAR = mk("Auto Marque", "automotive", [("Owners report long waits for service and restoration of classic models.", .9), ("Limited edition allocation sparks collector complaints about the waitlist.", .8)],
         [("svc", "service scheduling data", .8)])
HOTEL = mk("Grand Stay", "hotel", [("Guests want personal preferences honoured on return visits.", .9), ("Staff shortages hurt service and reviews.", .7)],
           [("crm", "guest crm and preferences data", .6)])

def test_different_brands_get_different_ideas_from_their_evidence():
    a = generate_ideas(CAR); b = generate_ideas(HOTEL)
    ka = {i["idea_id"] for i in a["ideas"]}; kb = {i["idea_id"] for i in b["ideas"]}
    assert "ownership_care" in ka and "scarcity_access" in ka and ka != kb
    assert "personalization" in kb and "operations_quality" in kb
    assert "ownership_care" not in kb
    assert all(i["evidence"] and all(e["quote"] for e in i["evidence"]) for i in a["ideas"] + b["ideas"])

def test_scores_move_with_importance_and_readiness():
    base = generate_ideas(CAR)["ideas"][0]["scores"]["total"]
    low = mk("Auto Marque", "automotive", [("Owners report long waits for service and restoration of classic models.", .1), ("Limited edition allocation sparks collector complaints about the waitlist.", .1)], [("svc", "service scheduling data", .1)])
    assert generate_ideas(low)["ideas"][0]["scores"]["total"] < base

def test_no_matching_evidence_yields_no_ideas_and_reports_gap():
    z = mk("Zed Co", "other", [("Quarterly planet alignment was unusual.", .9), ("Weather patterns varied widely.", .5)], [("x", "anything", .5)])
    out = generate_ideas(z)
    assert out["ideas"] == [] and set(out["unmatched_signals"]) == {"g0", "g1"}

def test_combined_levers_present_and_max_ideas_respected():
    out = generate_ideas(CAR, max_ideas=2)
    assert len(out["ideas"]) == 2
    assert any("+" in i["idea_id"] for i in generate_ideas(CAR)["ideas"])
    with pytest.raises(ValueError): generate_ideas(CAR, 0)

def run(c): return asyncio.run(c)

def test_priorart_done_before_when_hit_overlaps():
    idea = generate_ideas(CAR)["ideas"][0]
    async def f(q): return [{"title": "Vehicle service restoration", "snippet": " ".join(idea["evidence"][0]["matched_terms"]) + " " + idea["mechanism"], "url": "https://x"}]
    r = run(check_idea(idea, "automotive", f))
    assert r["label"] == "done-before" and r["hits"][0]["url"] == "https://x"

def test_priorart_none_found_is_hedged_and_failure_is_unchecked():
    idea = generate_ideas(CAR)["ideas"][0]
    async def empty(q): return []
    async def boom(q): raise RuntimeError("down")
    async def ontopic(q): return [{"title": "Car buyers survey", "snippet": "vehicle owners and drivers discuss paint colours", "url": "https://z"}]
    r = run(check_idea(idea, "automotive", ontopic))
    assert r["label"] == "no-prior-art-found" and "not proof" in r["caveat"]
    assert run(check_idea(idea, "automotive", empty))["label"] == "inconclusive"
    assert run(check_idea(idea, "automotive", boom))["label"] == "unchecked"

def test_priorart_unrelated_hits_do_not_count():
    idea = generate_ideas(CAR)["ideas"][0]
    async def junk(q): return [{"title": "Medieval pottery", "snippet": "clay glaze kiln", "url": "https://y"}]
    assert run(check_idea(idea, "automotive", junk))["label"] == "inconclusive"
    assert len(run(check_ideas(generate_ideas(CAR)["ideas"], "automotive", junk))) == len(generate_ideas(CAR)["ideas"])


def test_one_stray_sector_word_in_snippet_is_not_on_topic():
    idea = [i for i in generate_ideas(CAR)["ideas"] if i["idea_id"] == "operations_quality"][0]
    async def stray(q): return [{"title": "Maldives Police Service", "snippet": "staff reviews complaints analytics quality, once led by a driver", "url": "https://p"}]
    r = run(check_idea(idea, "automotive", stray))
    assert r["label"] == "inconclusive"
    async def real(q): return [{"title": "Automotive dealer staffing analytics", "snippet": "service quality reviews and complaints analytics for car dealers", "url": "https://d"}]
    assert run(check_idea(idea, "automotive", real))["label"] in ("possible-prior-art", "done-before")


def test_studio_no_longer_serves_fixed_templates():
    from app.modules.m19_idea_incubator.luxury_venture import build_luxury_venture
    a = build_luxury_venture(CAR); b = build_luxury_venture(HOTEL)
    ia = {c["concept_id"] for c in a["concepts"]}; ib = {c["concept_id"] for c in b["concepts"]}
    assert ia != ib and not ({"guest_or_owner_intelligence", "operations_quality", "provenance_storytelling"} & ia & ib - {"operations_quality"})
    assert all(c["evidence"] for c in a["concepts"] + b["concepts"])

def test_studio_refuses_when_no_lever_matches_evidence():
    from app.modules.m19_idea_incubator.luxury_venture import build_luxury_venture
    z = mk("Zed Co", "other", [("Quarterly planet alignment was unusual.", .9), ("Weather patterns varied widely.", .5)], [("x", "anything", .5)])
    with pytest.raises(ValueError, match="no idea lever matched"): build_luxury_venture(z)

def test_priorart_label_changes_differentiation_score():
    from app.modules.m19_idea_incubator.luxury_venture import build_luxury_venture
    cid = build_luxury_venture(CAR)["concepts"][0]["concept_id"]
    base = build_luxury_venture(CAR)["concepts"]
    hit = build_luxury_venture(CAR, priorart={cid: "done-before"})["concepts"]
    d = lambda cs: {c["concept_id"]: c["scores"]["differentiation"] for c in cs}
    assert d(hit)[cid] < d(base)[cid]


def test_anchor_score_requires_concept_group_for_every_lever():
    from app.modules.m19_idea_incubator.luxury_priorart import anchor_score
    assert anchor_score(["ownership_care"], "Dealer launches preventive service care program for owners") == 1.0
    assert anchor_score(["ownership_care"], "vehicle owners discuss paint colours") < 0.5
    assert anchor_score(["ownership_care", "scarcity_access"], "owner maintenance program") < 0.5   # second lever's concept missing
    assert anchor_score(["ownership_care", "scarcity_access"], "owner maintenance program with a transparent waitlist for buyers") == 1.0
    assert anchor_score(["unknown_lever"], "anything") == 0.0


def test_generic_words_do_not_satisfy_concept_anchors():
    from app.modules.m19_idea_incubator.luxury_priorart import anchor_score
    assert anchor_score(["operations_quality"], "Internal Revenue Service reviews analytics for customers") < 0.5
    assert anchor_score(["ownership_care"], "American Motors Corporation was an owner of many service stations") < 0.5
    assert anchor_score(["operations_quality"], "Hotel uses guest feedback sentiment to adjust staffing level") == 1.0


def test_keyword_stuffing_is_capped():
    from app.modules.m19_idea_incubator.luxury_ideation import generate_ideas
    stuffed = mk("Auto Marque", "automotive", [("limited waitlist allocation exclusive edition collector queue demand sold", .2), ("Owners report long waits for restoration.", .9)], [("svc", "service scheduling data", .8)])
    ideas = {i["idea_id"]: i for i in generate_ideas(stuffed)["ideas"]}
    assert ideas["scarcity_access"]["scores"]["evidence_strength"] <= 0.2 * 3 + 1e-9

def test_evidence_exposes_the_source_passage_that_matched():
    ev = generate_ideas(CAR)["ideas"][0]["evidence"]
    assert all("source_passages" in e for e in ev)


def test_check_ideas_survives_a_malformed_idea():
    good = generate_ideas(CAR)["ideas"][0]
    async def f(q): return []
    out = run(check_ideas([good, {"idea_id": "bad"}], "automotive", f))
    assert len(out) == 2 and out[1]["label"] == "unchecked"


def test_source_passage_content_matches_the_source_finding():
    d = CAR.model_dump()
    d["sources"][0]["finding"] = "Owners wait months for restoration and service appointments at the dealer."
    brief = VentureBrief.model_validate(d)
    passages = [p for i in generate_ideas(brief)["ideas"] for e in i["evidence"] for p in e["source_passages"]]
    assert passages
    assert all(p["finding"] == d["sources"][0]["finding"] and p["source_id"] == "s0" for p in passages)


def test_check_ideas_converts_an_idea_that_raises_into_unchecked():
    good = generate_ideas(CAR)["ideas"][0]
    out = run(check_ideas([{"idea_id": "bad"}, good], "automotive", lambda q: asyncio.sleep(0, result=[])))
    assert out[0]["label"] == "unchecked" and out[0]["error"] and out[1]["idea_id"] == good["idea_id"]


def test_combined_fetch_survives_one_failing_index(monkeypatch):
    from app.modules.m19_idea_incubator import luxury_priorart as lp
    async def boom(q): raise RuntimeError("down")
    async def ok(q): return [{"title": "t", "snippet": "s", "url": "u"}]
    monkeypatch.setattr(lp, "wikipedia_fetch", boom); monkeypatch.setattr(lp, "news_fetch", ok)
    assert run(lp.combined_fetch("x")) == [{"title": "t", "snippet": "s", "url": "u"}]
