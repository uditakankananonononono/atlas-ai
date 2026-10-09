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
