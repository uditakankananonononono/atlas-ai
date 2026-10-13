from __future__ import annotations

import pytest
from app.modules.m21_claire.application_portfolio import ApplicationPortfolioStore, build_application_packet
from app.modules.m21_claire.venture_studio import generate_venture_hypotheses, build_content_calendar


def test_application_profiles_and_records_are_tenant_scoped(tmp_path):
    store = ApplicationPortfolioStore(tmp_path / "apps.sqlite3")
    store.save_profile("tenant-a", {"country": "India", "facts": [{"claim": "built a project", "source": "portfolio.pdf"}]})
    item = store.add_listing("tenant-a", {"title": "STEM Competition", "official_url": "https://example.org/apply"})
    assert store.get_profile("tenant-b") is None
    assert store.list_applications("tenant-b") == []
    assert store.get_application("tenant-a", item["id"])["status"] == "discovered"
    with pytest.raises(KeyError):
        store.get_application("tenant-b", item["id"])


def test_application_listing_deduplicates_per_tenant_and_rejects_non_https(tmp_path):
    store = ApplicationPortfolioStore(tmp_path / "apps.sqlite3")
    listing = {"title": "Competition", "official_url": "https://example.org/competition"}
    first = store.add_listing("a", listing)
    second = store.add_listing("a", listing)
    other_tenant = store.add_listing("b", listing)
    assert first["created"] is True and second["duplicate"] is True
    assert other_tenant["created"] is True
    with pytest.raises(ValueError):
        store.add_listing("a", {"title": "bad", "official_url": "http://example.org"})


def test_application_packet_does_not_invent_facts_or_claim_verification():
    profile = {"country": "India", "facts": [{"claim": "Built a biology tool", "source": "portfolio.pdf"}], "documents": {}}
    listing = {"title": "Research Program", "official_url": "https://example.org/program",
               "required_profile_fields": ["country", "grade"], "required_documents": ["transcript"],
               "essay_prompts": ["Why this program?"], "eligibility": {"country": ["India", "United States"]}}
    packet = build_application_packet(profile, listing)
    assert packet["readiness"] == "incomplete_or_needs_verification"
    assert packet["missing_profile_fields"] == ["grade"]
    assert packet["available_claims"][0]["verification_status"] == "user_supplied_unverified"
    assert packet["external_submission_performed"] is False
    assert packet["essay_scaffolds"][0]["status"] == "outline_needed"


def test_application_status_requires_review_before_approval_and_receipt_before_submitted(tmp_path):
    store = ApplicationPortfolioStore(tmp_path / "apps.sqlite3")
    store.save_profile("a", {"country": "India", "documents": {"transcript": "transcript.pdf"}})
    item = store.add_listing("a", {"title": "Program", "official_url": "https://example.org/apply", "required_profile_fields": ["country"], "required_documents": ["transcript"], "application_components": ["form"]})
    with pytest.raises(ValueError, match="invalid status transition"):
        store.update_status("a", item["id"], "user_approved_to_submit")
    store.prepare("a", item["id"])
    store.update_status("a", item["id"], "user_approved_to_submit")
    with pytest.raises(ValueError, match="confirm a real submission"):
        store.update_status("a", item["id"], "submitted_confirmed")
    result = store.update_status("a", item["id"], "submitted_confirmed", submission_receipt_url="https://example.org/receipt")
    assert result["submission_performed_by_system"] is False


def test_venture_hypotheses_keep_sources_and_are_explicitly_unvalidated():
    signals = [
        {"title": "Student research discovery tools", "summary": "students need better research discovery workflows", "link": "https://example.org/1", "source_domain": "example.org"},
        {"title": "Research discovery workflow", "summary": "workflow tools for research students", "link": "https://example.net/2", "source_domain": "example.net"},
    ]
    out = generate_venture_hypotheses(signals, {"sectors": ["education"], "audiences": ["high school researchers"]}, limit=5)
    assert out["count"] > 0
    assert all(i["status"] == "unvalidated_hypothesis" for i in out["items"])
    assert all(i["evidence"] and i["validation_plan"] for i in out["items"])
    assert "does not scan all internet content" in " ".join(out["limits"])


def test_content_calendar_does_not_publish():
    out = build_content_calendar([{"title": "Public paper", "link": "https://example.org/paper"}], audience="students")
    assert out["count"] == 1
    assert out["publish_action"] == "not_performed"


def test_multitimescale_cognitive_loops_emit_separate_proposals_and_never_execute(tmp_path):
    from app.modules.m21_claire.cognitive_loops import CognitiveLoopCoordinator
    coordinator = CognitiveLoopCoordinator(tmp_path / "loops.sqlite3")
    out = coordinator.run_cycle(
        "tenant",
        signals=[
            {"id": "s1", "title": "Novel student learning systems", "summary": "learning systems for students", "link": "https://example.org/a"},
            {"id": "s2", "title": "Student learning systems benchmark", "summary": "benchmark student learning", "link": "https://example.net/b"},
        ],
        outcomes=[{"id": "o1", "domain": "biology", "task_type": "classification", "passed": False}],
        goals=[{"title": "Finish research plan", "impact": .9, "urgency": .8, "cost": .2}],
    )
    loops = {p["loop_name"] for p in out["proposals"]}
    assert {"fast", "deliberative", "learning", "strategic"}.issubset(loops)
    assert out["execution"].startswith("proposal-only")
    assert coordinator.list_proposals("other") == []
    assert coordinator.list_proposals("tenant")


def test_multitimescale_review_accepts_for_planning_only(tmp_path):
    from app.modules.m21_claire.cognitive_loops import CognitiveLoopCoordinator
    coordinator = CognitiveLoopCoordinator(tmp_path / "loops.sqlite3")
    out = coordinator.run_cycle("tenant", goals=[{"title": "One goal"}])
    proposal_id = out["proposals"][0]["id"]
    reviewed = coordinator.review_proposal("tenant", proposal_id, accepted=True, note="reviewed")
    assert reviewed["review_status"] == "accepted_for_planning"
    assert reviewed["execution"].startswith("none")
    with pytest.raises(KeyError):
        coordinator.review_proposal("tenant", proposal_id, accepted=True)


def test_venture_hypotheses_deterministic_across_hash_seeds():
    import json, os, subprocess, sys, pathlib
    code = (
        "import json;from app.modules.m21_claire.venture_studio import generate_venture_hypotheses as g;"
        "s=[{'title':t,'link':'https://example.org/%d'%i,'summary':m} for i,(t,m) in enumerate(["
        "('Alpha beta gamma','delta epsilon zeta'),('Beta gamma eta','theta iota kappa'),('Gamma lambda mu','nu xi omicron'),"
        "('Pi rho sigma','tau upsilon phi'),('Chi psi omega','alpha lambda pi')])];"
        "print(json.dumps([i['id']+i['signal_pattern'] for i in g(s,{'sectors':['health']},limit=12)['items']]))")
    root = pathlib.Path(__file__).resolve().parents[3] / "backend"
    outs = []
    for seed in ("1", "2", "12345"):
        env = {**os.environ, "PYTHONHASHSEED": seed, "PYTHONPATH": str(root)}
        outs.append(subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, check=True).stdout)
    assert outs[0] == outs[1] == outs[2] and json.loads(outs[0])
