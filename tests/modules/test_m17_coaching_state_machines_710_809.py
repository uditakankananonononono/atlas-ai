"""Distinctive per-row tests for the 100 coaching state machines, ledger rows 710-809."""
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.m17_advice_essay.coaching_state_machines_710_809 import (
    DISPATCH, METHODS, ROW_BY_METHOD, SPECS, assess_method, run_row,
)
from app.modules.m17_advice_essay.communication_coaching import CommunicationCoach
from app.modules.m17_advice_essay.in_memory_repository import InMemoryModule17Repository
from app.modules.m17_advice_essay.routes import build_router
from app.modules.m17_advice_essay.schemas import CommunicationCoachingRequest, CommunicationSkill
from app.modules.m17_advice_essay.service import AdviceEssayService

R = run_row

DEFAULTS = {
    "claims": [{"claim": "Daily practice improves recall", "evidence": "2023 spaced-repetition meta-analysis"}],
    "interests": [{"party": "owner", "interest": "fair rate"}, {"party": "client", "interest": "reliability"}],
    "walkaway": "I will keep my current contract instead of accepting below it.",
    "positions": ["Owner: ship Friday", "Client: ship Monday"],
    "shared_facts": ["The draft was due Friday", "It arrived Monday"],
    "parties": ["Asha", "Ravi"], "process_agreement": "Equal turns, no interruptions, either may pause.",
    "consent_confirmed": True,
    "heard_statement": "I felt ignored when my idea was skipped.",
    "stated_feeling": "frustrated",
    "own_state": "calm", "observable_cues": ["arms crossed", "short replies"],
    "setting": "small team retrospective", "audience_signals": ["reserved", "formal"],
    "stated_preferences": ["Prefers direct written feedback"],
    "message": "Let us touch base and find low-hanging fruit so we are on the same page.",
    "point": "The report arrived two days late",
    "need": "quiet focus time from 9 to 11", "request": "could we chat after 11",
    "limit": "no work messages after 8pm", "consequence": "I will mute the channel after 8pm",
    "topic": "school start times",
    "observed_behavior": "the last two reports arrived after the agreed date",
    "impact": "the review meeting had no data",
    "feedback_received": "Your summaries bury the main point.",
    "takeaway": "Practice beats talent", "duration_minutes": 10,
    "slides": [{"title": "Why", "claim": "Practice drives gains", "bullets": ["study 1", "study 2"]}],
    "true_event": "I failed the first driving test", "change": "I learned to prepare deliberately",
    "event_verified": True, "verified_facts": ["test score on record"],
    "shared_interest": "urban sketching", "genuine": True,
    "introduction": "I'm Udita; I'm reaching out because your watercolour series matches my study project.",
    "mutual_value": "They need student interviewees; I need mentor insight.",
    "mentee_goal": "publish a first short story",
    "coachee_goal": "speak up in class", "current_reality": "has not spoken this term",
    "options": ["ask one question weekly", "answer once weekly"], "commitment": "ask one question this week",
    "learning_objective": "explain recursion with one example",
    "concept": "recursion", "audience_knowledge": "knows loops and functions",
    "check_question": "Explain it back with a new example.",
    "comparison": "a set of nested boxes",
    "mappings": [{"concept_part": "base case", "comparison_part": "smallest box"}],
    "limits": ["Boxes have no self-reference."], "reviewed": True,
    "image": "a relay race", "implication": "Handoffs matter; it does not imply competition inside the team.",
    "example": "Khan Academy practice dashboards", "verified": True, "representative": True,
    "target_skill": "essay outlining", "current_level": "beginner",
    "fading_plan": "remove sentence starters by week 3", "mastery_evidence": "unaided outline scored proficient",
    "claim": "Later start times improve sleep", "evidence_discussed": True, "assumption_named": True,
    "purpose": "Choose the fall fundraiser", "decision_rule": "facilitator calls consensus",
    "roles": ["facilitator", "scribe"], "agenda_items": [{"item": "options", "minutes": 10}],
    "participants": ["Asha", "Ravi"], "speakers": ["Asha", "Ravi"],
    "prompt": "Ways to fund the art show",
    "ideas": ["paint mural", "bake sale", "raffle baskets", "sponsor letters", "online auction",
              "art auction", "ticket sales", "donation jar", "merch table"],
    "anonymous_channel": True, "idea_target": 8,
    "proposal": "Switch the newsletter to weekly",
    "consensus_check": True, "tie_policy": "facilitator casts the deciding vote",
    "minority_impact_assessment": "biweekly supporters lose frequency; revisit in a month",
    "rule": "majority",
    "question": "Should the club meet weekends?",
    "evidence": [{"claim": "attendance is low", "type": "fact"}, {"claim": "weekends feel restful", "type": "value"}],
    "tradeoffs": ["weekday fatigue vs weekend chores"],
    "sides": ["affirmative", "negative"], "turns": {"affirmative": 2, "negative": 2},
    "evidence_standard": "peer-reviewed or primary sources",
    "audience_needs": ["a clear next step"],
    "premises": ["Teens sleep less on early starts", "Sleep loss harms learning"],
    "conclusion": "Later starts help learning",
    "argument": "Studies show later starts help; of course you would say otherwise.",
    "opposing_view": "Uniforms reduce self-expression",
    "strongest_points": ["dress codes can burden low-income families"],
    "confirmed_with_holder": True, "updated_view": "keep the policy with a subsidy",
    "statement": "You never listen.",
    "interpretations": ["they feel unheard", "they are attacking me"],
    "ambiguous_statement": "Fine, do whatever.",
    "confirmed": True, "evidence_base": ["their three published op-eds"], "presented": True,
    "risks": ["vendor delays", "volunteer fatigue"], "timebox_minutes": 15, "learnings": "add a buffer week",
    "scope": ["staging.example.org"], "assets": ["user database"],
    "stop_conditions": ["any production alert"],
    "authorization": "signed authorization 2026-09-01 from the site owner",
    "remediation": [{"finding": "weak TLS", "owner": "ops"}],
    "scenario": "fictional supply-chain disruption exercise",
    "assumptions": ["the port closes for two weeks"],
    "moves": [{"actor": "blue", "action": "reroute freight", "deescalation_option": "pause orders"}],
    "uncertainties": ["demand volatility"],
    "objectives": ["test incident comms"],
    "injects": [{"time": 0, "event": "database down", "decision_required": "failover?"}],
    "safety_limits": ["no production changes"], "after_action_review": "Friday retro",
    "parameters": {"growth": {"min": 0.01, "max": 0.05}}, "validation_data": "2023-2025 actuals",
    "fictionalized": True, "debrief_done": True,
    "situation": "a teammate went quiet in meetings", "viewpoints": ["the teammate", "the manager"],
    "consulted": True,
    "observed_behavior_for_mind": None,
    "verification_plan": "ask Sam privately",
    "observation": "Priya answered with one word twice", "inferences": ["she is upset with me"],
    "stated_experience": "I felt anxious and tired before the results came out", "preference_asked": True,
    "stated_need": "someone to sit with me at lunch",
    "offers": [{"offer": "sit together Tuesday", "limit": "lunch only"}], "asked": True,
    "intended_help": "proofread their scholarship essay",
    "recipient_stated_need": "help with essay proofreading",
    "consent": True, "sustainable": True,
    "action": "organize a neighborhood cleanup", "beneficiaries": ["residents"],
    "decision_makers": "residents vote at the meeting",
    "shared_interest": "both want the event to succeed",
    "commitments": [{"party": "Asha", "commitment": "book the venue", "voluntary": True}],
    "repair_path": "name it at the weekly check-in", "check_in": "weekly",
    "joint_goal": "publish the zine", "contributions": [{"person": "Asha", "item": "cover art"}],
    "attribution": "masthead credit for everyone", "disagreement_process": "majority after discussion",
    "dependencies": [{"from": "editor", "to": "designer", "item": "final text", "handoff_plan": "shared folder by Wednesday"}],
    "help_channel": "ask in the team chat anytime",
    "team_context": "new five-person study group",
    "activities": [{"activity": "weekly problem swap", "voluntary": True}],
    "working_agreements": ["phones away during sessions"], "reflection": "monthly retro",
    "commitment": "I will send the outline by Friday 5pm", "feasible": True,
    "report_back_date": "Friday 6pm", "completed": True,
    "recent_response_to_dissent": "thanked and minuted the objection", "invitation": "round-robin concern check",
    "participation_channels": [{"channel": "in-person", "accessible": True}, {"channel": "async doc", "accessible": True}],
    "missing_groups": ["remote students"], "adjustments": ["add a video option"],
    "context": "club officer selection", "invited_perspectives": ["newer members"],
    "feedback": "anonymous pulse survey",
    "needs": [{"person_or_group": "wheelchair users", "barrier": "stairs only entrance"}],
    "criteria": ["published rubric v2"], "outcome_review": "term-end survey",
    "case_facts": ["the funds were spent on printing"], "process": "written evidence, then both sides speak",
    "rights_at_stake": ["the right to be heard"], "appeal_path": "faculty sponsor review",
    "stakeholders": ["classmates", "teacher"], "duties": ["accuracy", "consent for images"],
    "consent_considered": True, "publicity_test": True,
    "stated_values": ["honesty", "punctuality"], "planned_action": "submit the report on time",
    "alignment_check": True, "conflicts_of_interest": [{"conflict": "sibling judges the contest", "disclosed": True}],
    "known": ["venue capacity", "caterer confirmed"], "unknowns": ["final headcount"],
    "mistakes": ["I quoted the old date earlier"],
    "decision": "move the fair indoors", "reasons": ["rain forecast", "equipment safety"],
    "privacy_marks": {"vendor quote": "privacy of pricing"}, "explanation": "announce with reasons at assembly",
    "owned_part": "I sent the final draft late",
    "repair_actions": ["apologize", "request an extension"], "prevention": "draft due 48h early from now on",
    "promises": [{"promise": "review slides", "by_when": "Thursday", "effort_estimate": "30 min"}],
    "declined": ["the extra Saturday shift"],
    "expectations": ["post notes after each lecture"],
    "notify_if_late_by": "24 hours",
    "principle": "late work loses ten percent per day",
    "cases": [{"case": "Asha", "decision": "applied"}, {"case": "Ravi", "decision": "applied"}],
    "exception_criteria": "documented emergency only",
    "wait_context": "waiting on competition results",
    "controllable_actions": ["start the next project draft"], "chosen_action": "start the next project draft",
    "recheck_time": "Friday at noon",
    "difference": "a teammate observes different dietary rules", "harm_present": False,
    "needed_boundaries": ["no more private details shared"], "repair_needed": "an acknowledgment",
    "specific_act": "stayed late to help me fix the poster",
    "contributors": ["Asha designed the poster"],
    "correction_invited": True, "scoped_claim": "I coordinated logistics for the fundraiser",
    "current_belief": "online study groups do not work", "goal_is_exploration": True,
    "sources": ["interviews with two group members"],
    "view": "handwritten notes are best", "alternatives": ["typed notes with review"],
    "comparison": {"handwritten": "72%", "typed with review": "78%"}, "update": "try typed with review for a month",
    "belief": "I can finish the portfolio in a week", "confidence": 60, "evidence_strength": "medium",
    "pressures": ["midterm stress", "parent expectations"],
    "long_view_verdict": "keep the course with tutoring support",
    "downstream_effects": ["college credit", "schedule load"], "timing": "decide after midterms",
    "option": "launch the store now", "stakes": "high",
    "reversible_step": "a two-week pre-order page", "exit_criteria": "fewer than 20 pre-orders stops the launch",
    "desire": "late-night gaming", "goal": "consistent sleep for exams",
    "limit_aligned": True, "pause_plan": "the phone docks at 9:45",
    "feared_action": "present at the science fair", "values": ["growth", "sharing work"],
    "real_danger": False, "supports": ["practice with a friend first"],
    "smallest_step": "present to two classmates on Thursday",
    "setback": "lost the debate final", "recovery_time": "rest this weekend",
    "learning": "prepare rebuttals earlier", "restart_step": "outline one practice round Monday",
    "costs": ["skipped sleep twice", "missed family dinner weekly"],
    "still_worth_it": False, "adjustment": "cap practice at ten hours weekly",
    "impulse": "checking messages during study", "preferred_action": "finish the problem set",
    "cue": "the phone buzz", "friction_added": "phone charges in another room",
    "ease_added": "problem set open on the desk before starting",
    "future_benefit": "a strong portfolio earns the summer program spot", "wait_period": "12 weeks",
    "milestones": ["draft three pieces by week 4"], "review_interval": "every Sunday",
    "urge": "send an angry reply", "consequence_if_acted": "damages a friendship I value",
    "alternatives": ["walk around the block"], "support_contact": "my cousin",
    "own_feeling": "overwhelmed", "trigger": "three deadlines collided",
    "pause_taken": True, "chosen_response": "ask for one extension and plan the evening",
    "pressures_list": None,
    "triage": {"exam prep": "actionable", "club duties": "shareable"},
    "reduced": "delegated the poster design", "recovery_plan": "Saturday afternoon off",
    "challenge": "pre-exam nerves",
    "past_supports": [{"support": "evening walks", "safe": True}, {"support": "all-night cramming", "safe": False}],
    "chosen": "evening walks",
    "moment_context": "five minutes before the presentation", "judgment_free": True,
    "practice_preference": "breath", "minutes": 10,
    "environment": "shared bedroom", "preferences": ["quiet music", "stretching"],
    "current_routine": ["screens in bed until midnight", "caffeine late at 6pm"],
    "wind_down": "read a paper book for 20 minutes", "tonight_change": "charge the phone in the kitchen",
    "mobility_limits": ["mild knee pain"], "first_session": "20 minute easy swim",
}

# Per-method extras layered on top of DEFAULTS where names collide across rows.
OVERRIDES = {
    "difficult_conversations": {"setting": "private quiet office", "rehearsed": True, "goal": "our project",
                                "topic": "missed deadlines"},
    "social_calibration": {"feedback_channel": "ask directly after the meeting"},
    "cultural_sensitivity": {"confirmed_with_person": True},
    "cross_cultural_communication": {"plain_version": "Let us check in and pick the easiest tasks.",
                                     "confirmation_received": True},
    "diplomatic_language": {"fact": "The report arrived two days late",
                            "impact": "the review meeting had no data", "request": "send drafts by Wednesday"},
    "active_listening": {"accuracy_confirmed": True, "followup_asked": True},
    "empathetic_response": {"support_offered": True},
    "emotional_intelligence": {"verified": True},
    "boundary_setting": {"followthrough": "mute at 8pm without announcing"},
    "feedback_delivery": {"situation": "in the last two sprint reviews", "next_step": "send drafts by Wednesday"},
    "feedback_reception": {"summarized": True, "example_requested": True,
                           "decisions": {"adopt": "lead with the summary"}},
    "public_speaking": {"outline": ["hook", "p1", "p2", "p3", "close"], "rehearsals": 2},
    "storytelling": {"choice": "booked extra lessons", "consequence": "passed the retest"},
    "rapport_building": {"exit_respected": True},
    "networking": {"followup_preference": "email is fine"},
    "mentorship": {"experience_options": ["how I got my first story published"], "review": "monthly coffee"},
    "teaching": {"explanation": "a function that calls itself", "practice": "trace a factorial by hand",
                 "assessment": "write a countdown function"},
    "explaining_complex_ideas": {"explanation": "recursion splits problems into smaller copies"},
    "metaphors": {"audience_fit": True},
    "examples": {"label": ""},
    "scaffolding": {"current_level": "beginner"},
    "questioning": {"questions": ["What do you think about school start times?"], "no_answer_ok": True},
    "socratic_method": {"claim": "Later start times improve sleep", "evidence_discussed": True,
                        "assumption_named": True},
    "conflict_resolution": {"disputed_facts": ["whose delay it was"],
                            "repair_options": ["split the difference", "swap the next deadline"],
                            "agreement_draft": "Friday draft, Monday final"},
    "mediation": {"sessions": ["session 1"], "agreements": ["both pause when asked"]},
    "negotiation_tactics": {"concessions": [{"give": "faster delivery", "get": "a higher rate"}],
                            "agreement_test": "both confirmed capacity"},
    "persuasive_writing": {"counterarguments": ["practice can be poorly designed"]},
    "coaching": {"options": ["ask one question weekly", "answer once weekly"]},
    "theory_of_mind": {"observed_behavior": "Sam left the meeting when budgets came up"},
    "fallacy_detection": {"repairs": ["cite the district sleep study by name"]},
    "steelmanning": {},
    "principle_of_charity": {"interpretations": [{"reading": "genuine delegation", "coherent_with_evidence": True},
                                                 {"reading": "sarcasm", "coherent_with_evidence": False}]},
    "steel_manning": {"invented_claims": []},
    "devils_advocacy": {"risks": ["vendor delays", "volunteer fatigue"], "timebox_minutes": 15},
    "red_teaming": {"targets": ["staging.example.org"]},
    "war_gaming": {},
    "tabletop_exercises": {},
    "simulation": {},
    "role_playing": {"scenario": "fictional salary negotiation practice",
                     "roles": ["candidate", "recruiter"]},
    "voting_design": {"options": ["weekly", "biweekly"]},
    "debate": {},
    "rhetoric": {"evidence": ["district sleep study 2024"], "verified": True},
    "logic": {"evidence": ["Teens sleep less on early starts per district data"]},
    "deliberation": {},
    "brainstorming": {"ideas": ["paint mural", "bake sale", "raffle baskets", "sponsor letters", "online auction",
                                "art auction", "ticket sales", "donation jar", "merch table"],
                      "anonymous_channel": True, "idea_target": 8},
    "consensus_building": {"positions": [{"party": "Asha", "stance": "support"},
                                         {"party": "Ravi", "stance": "object", "objection": "volunteer burnout",
                                          "response": "rotate editors"}]},
    "facilitation": {"participants": ["Asha", "Ravi"], "agenda_items": [{"item": "options", "minutes": 10}]},
    "teamwork": {"dependencies": [{"from": "editor", "to": "designer", "item": "final text",
                                   "handoff_plan": "shared folder by Wednesday"}]},
    "collaboration": {},
    "cooperation": {},
    "prosocial_behavior": {"risks": [{"risk": "injury", "bearer": "volunteers"}],
                           "decision_makers": "residents vote at the meeting"},
    "altruism": {},
    "compassion": {},
    "empathy": {},
    "mentalizing": {"inferences": ["she is upset with me"]},
    "perspective_taking": {},
    "team_building": {},
    "trust_building": {},
    "psychological_safety": {},
    "inclusion": {},
    "diversity": {"declined_ok": True, "invited_perspectives": ["newer members"]},
    "equity": {"adjustments": {"stairs only entrance": "book the accessible room"}},
    "justice": {"rights_at_stake": ["the right to be heard"], "evidence_standard": "documents or two witnesses",
                "appeal_path": "faculty sponsor review"},
    "ethics": {},
    "integrity": {},
    "honesty": {"message": "The venue holds 200 people and the caterer confirmed."},
    "transparency": {},
    "accountability": {"impact": "the group missed the submission window"},
    "reliability": {},
    "dependability": {"dependencies": [{"item": "projector", "backup": "printed handouts"}],
                      "notify_if_late_by": "24 hours"},
    "consistency": {},
    "patience": {"controllable_actions": ["start the next project draft"], "chosen_action": "start the next project draft",
                 "recheck_time": "Friday at noon"},
    "tolerance": {},
    "forgiveness": {"situation": "a friend shared my private message"},
    "gratitude": {"impact": "we made the deadline"},
    "humility": {"claim": "I organized the fundraiser alone", "limits": ["I handled logistics only"],
                 "correction_invited": True, "scoped_claim": "I coordinated logistics for the fundraiser"},
    "curiosity": {},
    "open_mindedness": {},
    "intellectual_humility": {},
    "wisdom": {"decision": "drop the advanced course"},
    "prudence": {},
    "temperance": {"limit": "weeknights off by 10pm"},
    "courage": {},
    "resilience": {"supports": ["coach", "teammates"], "recovery_time": "rest this weekend",
                   "restart_step": "outline one practice round Monday"},
    "grit": {"goal": "win the national robotics title", "still_worth_it": False,
             "adjustment": "cap practice at ten hours weekly"},
    "self_control": {"cue": "the phone buzz", "friction_added": "phone charges in another room",
                     "ease_added": "problem set open on the desk before starting"},
    "delayed_gratification": {"milestones": ["draft three pieces by week 4"], "review_interval": "every Sunday"},
    "impulse_control": {},
    "emotional_regulation": {},
    "stress_management": {"pressures": ["exam prep", "club duties"],
                          "triage": {"exam prep": "actionable", "club duties": "shareable"}},
    "coping_strategies": {},
    "mindfulness": {},
    "meditation": {},
    "relaxation": {"chosen": "stretching", "adjustments": ["dim the lamp"]},
    "sleep_hygiene": {},
    "exercise": {"preferences": ["swimming", "cycling", "running"]},
}


def data(method: str) -> dict:
    spec = SPECS[ROW_BY_METHOD[method]]
    d = {k: spec_v for k in spec["required"] for spec_v in [DEFAULTS[k]]}
    for key, value in OVERRIDES.get(method, {}).items():
        d[key] = value
    # defaults that several rows share but are not required everywhere
    for key in ("consent_confirmed",):
        if SPECS[ROW_BY_METHOD[method]].get("consent"):
            d["consent_confirmed"] = True
    if SPECS[ROW_BY_METHOD[method]].get("authorization"):
        d["authorization"] = DEFAULTS["authorization"]
    return d


def test_exactly_100_contiguous_rows():
    assert len(METHODS) == 100 and len(set(METHODS)) == 100
    assert sorted(ROW_BY_METHOD.values()) == list(range(710, 810))
    assert set(DISPATCH) == set(ROW_BY_METHOD)


@pytest.mark.parametrize("method", METHODS)
def test_each_row_dispatches_to_substantive_output(method):
    out = R(method, data(method))
    assert out["row_id"] == ROW_BY_METHOD[method] and out["method"] == method
    assert out["named_function"] == f"row_{out['row_id']}_{method}"
    assert out["analysis"] and out["state_machine"]["states"]
    assert out["status"] in {"in_progress", "complete"}
    assert out["human_review_required"] is True and out["external_action_proposed"] is False
    assert out["boundary"] and out["uncertainty"]["level"] == "high"


@pytest.mark.parametrize("method", METHODS)
def test_each_row_rejects_missing_required_field(method):
    d = data(method)
    d.pop(SPECS[ROW_BY_METHOD[method]]["required"][0])
    with pytest.raises(ValueError, match="missing required"):
        R(method, d)


def test_unknown_method_rejected():
    with pytest.raises(ValueError, match="unsupported method"):
        R("mind_control", {})


def test_manipulative_intent_is_refused_not_coached():
    out = R("persuasive_writing", {"claims": [{"claim": "x", "evidence": "y"}],
                                   "goal": "Everyone knows you must agree with me."})
    assert out["status"] == "blocked"
    assert "false consensus" in out["boundary_violations"] or "coercive demand" in out["boundary_violations"]
    assert "honest_alternative" in out


def test_manipulative_draft_content_is_flagged_advisory_not_blocked():
    out = R("feedback_delivery", data("feedback_delivery") | {"draft": "You must fix this or else."})
    assert out["status"] != "blocked"
    assert out["analysis"]["manipulation_advisory"]


@pytest.mark.parametrize("method", ["mediation", "voting_design", "role_playing"])
def test_consent_gate_blocks_without_confirmed_consent(method):
    d = data(method)
    d["consent_confirmed"] = False
    out = R(method, d)
    assert out["status"] == "blocked" and "consent" in out["refusal"].lower()


def test_authorization_gate_blocks_red_teaming_without_documents():
    d = data("red_teaming")
    d["authorization"] = ""
    out = R("red_teaming", d)
    assert out["status"] == "blocked" and "authorization" in out["refusal"].lower()


def test_crisis_language_escalates_wellbeing_rows():
    out = R("stress_management", {"pressures": ["everything"], "context": "I feel like I might hurt myself"})
    assert out["status"] == "escalate" and out["escalation_required"] is True
    assert "emergency" in out["escalation_boundary"].lower()


def test_named_callable_is_importable_and_row_addressable():
    import app.modules.m17_advice_essay.coaching_state_machines_710_809 as mod
    fn = getattr(mod, "row_711_negotiation_tactics")
    out = fn(data("negotiation_tactics"))
    assert out["row_id"] == 711 and out["analysis"]["batna"]["specific"] is True


def test_route_mounted_owner_scoped_and_validated():
    owner = uuid4()
    service = AdviceEssayService(InMemoryModule17Repository())
    app = FastAPI()
    app.include_router(build_router(lambda: service, lambda: owner))
    client = TestClient(app)
    ok = client.post("/v1/modules/17/coaching/state-machine", json={
        "owner_id": str(owner), "method": "negotiation_tactics", "data": data("negotiation_tactics")})
    assert ok.status_code == 200
    assert ok.json()["analysis"]["batna"]["specific"] is True
    bad_method = client.post("/v1/modules/17/coaching/state-machine", json={
        "owner_id": str(owner), "method": "mind_control", "data": {}})
    assert bad_method.status_code == 422
    missing = client.post("/v1/modules/17/coaching/state-machine", json={
        "owner_id": str(owner), "method": "negotiation_tactics", "data": {}})
    assert missing.status_code == 422
    wrong_owner = client.post("/v1/modules/17/coaching/state-machine", json={
        "owner_id": str(uuid4()), "method": "negotiation_tactics", "data": data("negotiation_tactics")})
    assert wrong_owner.status_code == 403


def test_existing_coach_attaches_state_machine_to_response():
    result = CommunicationCoach().coach(CommunicationCoachingRequest(
        owner_id=uuid4(), skill=CommunicationSkill.NEGOTIATION_TACTICS,
        context="Rate discussion", goal="Reach a fair rate", audience="A client"))
    assert result.state_machine["row_id"] == 711
    assert result.state_machine["current_state"] == "inputs_supplied"
    assert any("interests" in blocker and "walkaway" in blocker for blocker in result.state_machine["blockers"])


# ---------------------------------------------------------------------------
# Distinctive per-row tests (one per ledger row)
# ---------------------------------------------------------------------------

def test_row_710_persuasive_writing_flags_unsupported_claim():
    out = R("persuasive_writing", {"claims": [{"claim": "Practice helps"}, {"claim": "Sleep matters", "evidence": "study"}]})
    assert out["analysis"]["unsupported_claims"] == ["Practice helps"]
    assert out["state_machine"]["current_state"] == "evidence_mapped"

def test_row_711_negotiation_flags_one_sided_concession():
    d = data("negotiation_tactics"); d["concessions"] = [{"give": "faster delivery"}]
    out = R("negotiation_tactics", d)
    assert len(out["analysis"]["unbalanced_concessions"]) == 1
    assert "Trade, never give" in out["analysis"]["fairness_rule"]

def test_row_712_conflict_separates_agreed_from_disputed():
    out = R("conflict_resolution", data("conflict_resolution"))
    assert out["analysis"]["agreed_facts"] == ["The draft was due Friday", "It arrived Monday"]
    assert out["analysis"]["disputed_facts"] == ["whose delay it was"]
    assert len(out["analysis"]["neutral_restatements"]) == 2

def test_row_713_mediation_builds_equal_turn_schedule():
    out = R("mediation", data("mediation"))
    turns = out["analysis"]["neutral_turn_schedule"]
    assert "Asha" in turns[0] and "Ravi" in turns[1]
    with pytest.raises(ValueError, match="at least two parties"):
        R("mediation", {"parties": ["Asha"], "process_agreement": "rules", "consent_confirmed": True})

def test_row_714_active_listening_paraphrases_then_checks():
    out = R("active_listening", data("active_listening"))
    assert "I felt ignored" in out["analysis"]["paraphrase"]
    assert "Did I get that right" in out["analysis"]["accuracy_check"]

def test_row_715_empathetic_response_rejects_inferred_feelings():
    d = data("empathetic_response"); d["inferred_feelings"] = ["secretly angry"]
    out = R("empathetic_response", d)
    assert out["analysis"]["rejected_inferences"][0]["inference"] == "secretly angry"
    assert "frustrated" in out["analysis"]["validation"]

def test_row_716_emotional_intelligence_holds_two_hypotheses_per_cue():
    out = R("emotional_intelligence", data("emotional_intelligence"))
    assert len(out["analysis"]["cue_hypotheses"][0]["readings"]) == 2
    assert out["analysis"]["cue_hypotheses"][0]["verification"] == "Ask; do not conclude."

def test_row_717_social_calibration_lowers_directness_for_reserved_audience():
    out = R("social_calibration", data("social_calibration"))
    assert out["analysis"]["recommended_directness"]["level"] == 2

def test_row_718_cultural_sensitivity_flags_group_generalization():
    d = data("cultural_sensitivity"); d["draft"] = "All teenagers are careless with deadlines."
    out = R("cultural_sensitivity", d)
    assert out["analysis"]["stereotype_flags"]
    assert out["state_machine"]["current_state"] == "assumptions_flagged"

def test_row_719_cross_cultural_finds_three_idioms():
    out = R("cross_cultural_communication", data("cross_cultural_communication"))
    assert set(out["analysis"]["idioms_found"]) == {"touch base", "low-hanging fruit", "on the same page"}

def test_row_720_diplomatic_language_flags_harsh_word():
    d = data("diplomatic_language"); d["draft"] = "This delay was stupid."
    out = R("diplomatic_language", d)
    assert out["analysis"]["harsh_words"] == ["stupid"]
    assert out["analysis"]["fact_impact_request"]["fact"] == "The report arrived two days late"

def test_row_721_assertiveness_builds_i_statement_and_flags_blame():
    d = data("assertiveness"); d["draft"] = "You never care about my time."
    out = R("assertiveness", d)
    assert out["analysis"]["i_statement"].startswith("I need quiet focus time")
    assert out["analysis"]["blame_patterns_in_draft"]

def test_row_722_boundary_setting_checks_proportionality_and_ownership():
    d = data("boundary_setting"); d["consequence"] = "I will never speak to you again"
    out = R("boundary_setting", d)
    assert out["analysis"]["consequence_owned_by_you"] is True
    assert out["analysis"]["proportionate"] is False

def test_row_723_difficult_conversation_scores_the_setting():
    d = data("difficult_conversations"); d["setting"] = "public open plan office"
    out = R("difficult_conversations", d)
    assert out["analysis"]["setting_check"]["private"] is False
    assert "missed deadlines" in out["analysis"]["opening_line"]

def test_row_724_feedback_delivery_rejects_generalized_behavior():
    d = data("feedback_delivery"); d["observed_behavior"] = "you always submit late"
    out = R("feedback_delivery", d)
    assert out["analysis"]["generalization_flags"] == ["always"]

def test_row_725_feedback_reception_summarizes_before_deciding():
    out = R("feedback_reception", data("feedback_reception"))
    assert "bury the main point" in out["analysis"]["summary_check"]
    assert "specific example" in out["analysis"]["clarifying_example_request"]

def test_row_726_public_speaking_budgets_words_from_duration():
    out = R("public_speaking", data("public_speaking"))
    assert out["analysis"]["total_word_budget"] == 1300
    assert [p["part"] for p in out["analysis"]["structure"]] == ["hook", "point_1", "point_2", "point_3", "close"]

def test_row_727_presentation_design_flags_claimless_slide():
    d = data("presentation_design"); d["slides"] = [{"title": "Intro", "bullets": ["a", "b"]}]
    out = R("presentation_design", d)
    assert out["analysis"]["slides_missing_claim"] == ["Intro"]

def test_row_728_storytelling_rejects_invented_details():
    d = data("storytelling"); d["invented_details"] = ["a dramatic thunderstorm that did not happen"]
    out = R("storytelling", d)
    assert out["analysis"]["invented_details_rejected"]
    assert out["analysis"]["arc"]["change"] == "I learned to prepare deliberately"

def test_row_729_rapport_requires_genuine_interest():
    d = data("rapport_building"); d["genuine"] = False
    out = R("rapport_building", d)
    assert out["state_machine"]["current_state"] == "interest_genuine"
    assert len(out["analysis"]["open_questions"]) == 3

def test_row_730_networking_requires_transparent_intro():
    d = data("networking"); d["introduction"] = "Hi there."
    out = R("networking", d)
    assert out["analysis"]["transparent"] is False
    assert "no worries" in out["analysis"]["no_pressure_question"]

def test_row_731_mentorship_blocks_directive_control():
    d = data("mentorship"); d["directive_given"] = True
    out = R("mentorship", d)
    assert out["state_machine"]["current_state"] == "decision_left_to_mentee"

def test_row_732_coaching_runs_grow_and_requires_two_options():
    d = data("coaching"); d["options"] = ["only one option"]
    out = R("coaching", d)
    assert out["analysis"]["grow_model"]["goal"] == "speak up in class"
    assert out["state_machine"]["current_state"] == "options_generated"

def test_row_733_teaching_requires_measurable_objective():
    d = data("teaching"); d["learning_objective"] = "understand recursion"
    out = R("teaching", d)
    assert out["analysis"]["objective_measurable"] is False

def test_row_734_explaining_flags_jargon_in_explanation():
    d = data("explaining_complex_ideas"); d["explanation"] = "recursion enables problem decomposition"
    out = R("explaining_complex_ideas", d)
    assert "decomposition" in out["analysis"]["jargon_flags"]
    assert out["analysis"]["layers"][0]["layer"] == 1

def test_row_735_analogies_demand_a_stated_limit():
    d = data("analogies")
    out = R("analogies", d)
    assert "stops resembling" in out["analysis"]["limit_statement"]
    d["limits"] = "Boxes do not call themselves."
    out2 = R("analogies", d)
    assert out2["analysis"]["limit_statement"] == "Boxes do not call themselves."

def test_row_736_metaphors_screen_charged_imagery():
    d = data("metaphors"); d["image"] = "a war on distractions"
    out = R("metaphors", d)
    assert "war" in out["analysis"]["violent_imagery_flags"]

def test_row_737_examples_block_unverified_unlabeled_and_leaky_examples():
    d = data("examples"); d.update(verified=False, label="", example="Email me at real.person@example.com for the data")
    out = R("examples", d)
    assert out["analysis"]["factuality"]["acceptable"] is False
    assert out["analysis"]["privacy_leaks"]

def test_row_738_scaffolding_requires_a_known_level():
    d = data("scaffolding"); d["current_level"] = "expert"
    out = R("scaffolding", d)
    assert out["state_machine"]["current_state"] == "level_assessed"
    d["current_level"] = "beginner"
    assert R("scaffolding", d)["analysis"]["ladder"][0]["support"] == "full worked model first"

def test_row_739_questioning_flags_leading_questions():
    d = data("questioning"); d["questions"] = ["Don't you think start times are too early?"]
    out = R("questioning", d)
    assert out["analysis"]["leading_flags"] == ["Don't you think start times are too early?"]

def test_row_740_socratic_method_refuses_scripted_answers():
    d = data("socratic_method"); d["expected_answers"] = ["the assumption is wrong"]
    out = R("socratic_method", d)
    assert "trap" in out["analysis"]["trap_risk"]["warning"].lower()
    assert out["state_machine"]["current_state"] == "no_traps"

def test_row_741_facilitation_flags_untimed_items_and_unheard_voices():
    d = data("facilitation"); d["agenda_items"] = [{"item": "open floor"}]; d["speakers"] = ["Asha"]
    out = R("facilitation", d)
    assert out["analysis"]["untimed_items"] == ["open floor"]
    assert out["analysis"]["unheard_participants"] == ["Ravi"]

def test_row_742_brainstorming_separates_generation_from_evaluation():
    d = data("brainstorming"); d["evaluation_started"] = True
    out = R("brainstorming", d)
    assert out["state_machine"]["current_state"] == "generation_unjudged"
    assert out["analysis"]["idea_count"] == 9

def test_row_743_consensus_never_treats_silence_as_agreement():
    d = data("consensus_building")
    d["positions"] = [{"party": "Asha", "stance": "support"}, {"party": "Ravi", "stance": "object", "objection": "burnout"}]
    out = R("consensus_building", d)
    assert out["analysis"]["unresolved_objections"] == ["burnout"]
    assert "Silence is not consent" in out["analysis"]["silence_warning"]

def test_row_744_voting_design_rejects_unrecognized_rule():
    d = data("voting_design"); d["rule"] = "coin flip"
    out = R("voting_design", d)
    assert out["analysis"]["rule_recognized"] is False
    assert out["state_machine"]["current_state"] == "rule_transparent"

def test_row_745_deliberation_separates_facts_from_values():
    d = data("deliberation"); d["evidence"] = [{"claim": "weekends are sacred"}]
    out = R("deliberation", d)
    assert len(out["analysis"]["untyped_items"]) == 1

def test_row_746_debate_assigns_burden_and_checks_equal_turns():
    d = data("debate"); d["turns"] = {"affirmative": 3, "negative": 2}
    out = R("debate", d)
    assert out["analysis"]["burden_of_proof"] == "affirmative"
    assert out["analysis"]["turns_equal"] is False

def test_row_747_rhetoric_blocks_pathos_without_logos():
    d = data("rhetoric"); d.pop("evidence"); d["emotional_appeal"] = "think of the children"
    out = R("rhetoric", d)
    assert "manipulation" in out["analysis"]["proportionality"]

def test_row_748_logic_finds_gap_terms_and_unsupported_premises():
    out = R("logic", data("logic"))
    assert "later" in out["analysis"]["gap_terms"]
    assert "Sleep loss harms learning" in out["analysis"]["unsupported_premises"]

def test_row_749_fallacy_detection_labels_tentatively_and_repairs():
    out = R("fallacy_detection", {"argument": "If we allow late work, next thing nobody ever submits anything."})
    labels = [f["tentative_label"] for f in out["analysis"]["findings"]]
    assert "slippery slope" in labels
    assert all("tentative" in f["confidence"] for f in out["analysis"]["findings"])

def test_row_750_steelermanning_requires_strongest_points_before_confirmation():
    out = R("steelmanning", {"opposing_view": "Uniforms reduce expression"})
    assert out["state_machine"]["current_state"] == "strongest_form_built"
    assert "recognize" in out["analysis"]["confirmation_question"]

def test_row_751_charitable_interpretation_generates_benign_readings():
    out = R("charitable_interpretation", {"statement": "That presentation was interesting."})
    assert out["analysis"]["benign_readings"]
    assert "hypothesis" in out["analysis"]["uncertainty_retained"]

def test_row_752_principle_of_charity_prefers_the_coherent_reading():
    out = R("principle_of_charity", data("principle_of_charity"))
    assert out["analysis"]["most_charitable_coherent_reading"]["reading"] == "genuine delegation"

def test_row_753_steel_manning_rejects_invented_beliefs():
    d = data("steel_manning"); d["invented_claims"] = ["they secretly want control"]
    out = R("steel_manning", d)
    assert out["analysis"]["invented_beliefs_rejected"] == ["they secretly want control"]
    assert out["analysis"]["best_version"]["attached_evidence"]

def test_row_754_devils_advocacy_is_declared_and_timeboxed():
    out = R("devils_advocacy", data("devils_advocacy"))
    assert out["analysis"]["assigned_challenge_role"] is True
    assert out["analysis"]["failure_modes"] == ["vendor delays", "volunteer fatigue"]

def test_row_755_red_teaming_confines_targets_to_authorized_scope():
    d = data("red_teaming"); d["targets"] = ["staging.example.org", "prod.example.org"]
    out = R("red_teaming", d)
    assert out["analysis"]["out_of_scope_targets"] == ["prod.example.org"]
    assert out["state_machine"]["current_state"] == "scope_bounded"

def test_row_756_war_gaming_requires_deescalation_paths():
    d = data("war_gaming"); d["moves"] = [{"actor": "red", "action": "blockade"}]
    out = R("war_gaming", d)
    assert out["analysis"]["moves_without_deescalation"] == 1

def test_row_757_tabletop_exercises_sequence_injects_by_time():
    d = data("tabletop_exercises"); d["injects"] = [{"event": "no timestamp"}]
    out = R("tabletop_exercises", d)
    assert len(out["analysis"]["unstructured_injects"]) == 1

def test_row_758_simulation_flags_single_point_parameters():
    d = data("simulation"); d["parameters"] = {"growth": {"min": 0.01, "max": 0.05}, "churn": 0.03}
    out = R("simulation", d)
    assert out["analysis"]["parameters_without_sensitivity_range"] == ["churn"]

def test_row_759_role_playing_requires_fictionalized_details():
    d = data("role_playing"); d["fictionalized"] = False
    out = R("role_playing", d)
    assert out["state_machine"]["current_state"] == "details_fictionalized"
    assert "without explanation or penalty" in out["analysis"]["opt_out"]

def test_row_760_perspective_taking_generates_hypotheses_per_viewpoint():
    out = R("perspective_taking", data("perspective_taking"))
    assert set(out["analysis"]["hypotheses_by_viewpoint"]) == {"the teammate", "the manager"}
    assert len(out["analysis"]["hypotheses_by_viewpoint"]["the manager"]) == 2

def test_row_761_theory_of_mind_keeps_every_hypothesis_tentative():
    out = R("theory_of_mind", data("theory_of_mind"))
    assert out["analysis"]["belief_hypotheses"]
    assert all(h["confidence"] == "tentative" for h in out["analysis"]["belief_hypotheses"])
    assert all(len(h["alternatives"]) == 3 for h in out["analysis"]["belief_hypotheses"])

def test_row_762_mentalizing_turns_inferences_into_questions():
    out = R("mentalizing", data("mentalizing"))
    assert out["analysis"]["inferred"] == ["she is upset with me"]
    assert out["analysis"]["ask_instead"]

def test_row_763_empathy_mirrors_only_stated_emotion_words():
    out = R("empathy", data("empathy"))
    assert set(out["analysis"]["mirrored_emotion_words"]) == {"anxious", "tired"}
    assert "anxious" in out["analysis"]["reflection"]

def test_row_764_compassion_bounds_every_offer():
    d = data("compassion"); d["offers"] = [{"offer": "anything you need, anytime"}]
    out = R("compassion", d)
    assert len(out["analysis"]["unbounded_offers"]) == 1

def test_row_765_altruism_checks_help_matches_stated_need():
    d = data("altruism"); d["intended_help"] = "organize their garage"
    out = R("altruism", d)
    assert "ask the recipient" in out["analysis"]["match_verdict"]

def test_row_766_prosocial_behavior_assigns_risk_and_decision_rights():
    out = R("prosocial_behavior", data("prosocial_behavior"))
    assert out["analysis"]["who_bears_risk"] == [{"risk": "injury", "bearer": "volunteers"}]
    assert out["analysis"]["who_decides"] == "residents vote at the meeting"

def test_row_767_cooperation_rejects_involuntary_commitments():
    d = data("cooperation"); d["commitments"] = [{"party": "Asha", "commitment": "work weekends", "voluntary": False}]
    out = R("cooperation", d)
    assert out["analysis"]["involuntary_commitments"]

def test_row_768_collaboration_requires_attribution_before_work():
    d = data("collaboration"); d["contributions"] = [{"item": "orphan task"}]
    out = R("collaboration", d)
    assert out["analysis"]["unattributed_contributions"] == [{"item": "orphan task"}]

def test_row_769_teamwork_flags_unplanned_handoffs():
    d = data("teamwork"); d["dependencies"] = [{"from": "a", "to": "b", "item": "design"}]
    out = R("teamwork", d)
    assert len(out["analysis"]["handoff_risks"]) == 1

def test_row_770_team_building_rejects_compulsory_fun():
    d = data("team_building"); d["activities"] = [{"activity": "mandatory karaoke", "voluntary": False}]
    out = R("team_building", d)
    assert out["analysis"]["non_voluntary_activities"]

def test_row_771_trust_building_requires_specific_commitments():
    d = data("trust_building"); d["commitment"] = "do better soon"
    out = R("trust_building", d)
    assert out["analysis"]["specific_and_timebound"] is False
    assert out["state_machine"]["current_state"] == "commitment_specific"

def test_row_772_psychological_safety_detects_retaliation_and_repairs():
    d = data("psychological_safety"); d["recent_response_to_dissent"] = "the intern was mocked in the channel"
    out = R("psychological_safety", d)
    assert out["analysis"]["retaliation_signals"] == ["mocked"]
    assert "repair" in out["analysis"]["repair_note"].lower()

def test_row_773_inclusion_flags_inaccessible_channels():
    d = data("inclusion"); d["participation_channels"] = [{"channel": "stairs-only venue", "accessible": False}]
    out = R("inclusion", d)
    assert len(out["analysis"]["accessibility_gaps"]) == 1

def test_row_774_diversity_rejects_tokenizing_invitations():
    d = data("diversity"); d["asked_to_represent_group"] = True
    out = R("diversity", d)
    assert out["analysis"]["tokenizing_flag"] is True
    assert out["state_machine"]["current_state"] == "invitations_without_tokenizing"

def test_row_775_equity_matches_support_to_every_barrier():
    d = data("equity"); d["adjustments"] = {}
    out = R("equity", d)
    assert len(out["analysis"]["barriers_without_adjustment"]) == 1

def test_row_776_justice_requires_an_appeal_path():
    d = data("justice"); d["appeal_path"] = ""
    out = R("justice", d)
    assert out["state_machine"]["current_state"] == "appeal_available"

def test_row_777_ethics_frames_harms_benefits_per_stakeholder():
    out = R("ethics", data("ethics"))
    assert set(out["analysis"]["harms_benefits_frame"]) == {"classmates", "teacher"}
    assert "everyone affected knew" in out["analysis"]["publicity_test"]

def test_row_778_integrity_demands_disclosed_conflicts():
    d = data("integrity"); d["conflicts_of_interest"] = [{"conflict": "sibling judges", "disclosed": False}]
    out = R("integrity", d)
    assert out["analysis"]["undisclosed_conflicts"]

def test_row_779_honesty_flags_manufactured_certainty():
    d = data("honesty"); d["message"] = "It is guaranteed to work, no doubt."
    out = R("honesty", d)
    assert set(out["analysis"]["overclaim_flags"]) == {"guaranteed", "no doubt"}

def test_row_780_transparency_requires_valid_basis_for_withholding():
    d = data("transparency"); d["privacy_marks"] = {"vendor quote": "competitive advantage"}
    out = R("transparency", d)
    assert out["analysis"]["private_without_valid_basis"] == ["vendor quote"]

def test_row_781_accountability_rejects_deflection():
    d = data("accountability"); d["owned_part"] = "I was late but they rushed me"
    out = R("accountability", d)
    assert out["analysis"]["deflection_flag"] is True

def test_row_782_reliability_rejects_underspecified_promises():
    d = data("reliability"); d["promises"] = [{"promise": "handle it"}]
    out = R("reliability", d)
    assert len(out["analysis"]["under_specified_promises"]) == 1

def test_row_783_dependability_requires_backups_and_triggers():
    d = data("dependability"); d["dependencies"] = [{"item": "projector"}]
    out = R("dependability", d)
    assert len(out["analysis"]["dependencies_without_backup"]) == 1
    assert out["analysis"]["notify_trigger"] == "24 hours"

def test_row_784_consistency_requires_reasons_for_deviation():
    d = data("consistency"); d["cases"] = [{"case": "Asha", "decision": "applied"}, {"case": "Ravi", "decision": "waived"}]
    out = R("consistency", d)
    assert len(out["analysis"]["deviations_without_reason"]) == 1

def test_row_785_patience_is_active_not_ruminating():
    out = R("patience", data("patience"))
    assert out["analysis"]["controllable_actions"] == ["start the next project draft"]
    assert "does not change it" in out["analysis"]["rumination_guard"]

def test_row_786_tolerance_sets_boundaries_where_harm_exists():
    d = data("tolerance"); d["harm_present"] = True
    out = R("tolerance", d)
    assert out["state_machine"]["current_state"] == "boundary_set_where_needed"
    assert "never requires absorbing damage" in out["analysis"]["rule"]

def test_row_787_forgiveness_is_optional_and_separate_from_access():
    out = R("forgiveness", data("forgiveness"))
    assert "never an obligation" in out["analysis"]["forgiveness_is_optional"]
    assert "independent decisions" in out["analysis"]["rule"]

def test_row_788_gratitude_names_act_and_impact_without_debt():
    out = R("gratitude", data("gratitude"))
    assert "stayed late" in out["analysis"]["acknowledgment_draft"]
    assert "we made the deadline" in out["analysis"]["acknowledgment_draft"]
    assert "no debt" in out["analysis"]["no_obligation"]

def test_row_789_humility_requires_named_limits_and_credit():
    out = R("humility", data("humility"))
    assert out["analysis"]["contributors_credited"] == ["Asha designed the poster"]
    assert out["analysis"]["limits"] == ["I handled logistics only"]

def test_row_790_curiosity_generates_non_defensive_questions():
    out = R("curiosity", data("curiosity"))
    assert len(out["analysis"]["open_questions"]) == 3
    assert "school start times" in out["analysis"]["open_questions"][0]

def test_row_791_open_mindedness_applies_one_standard_to_all_views():
    d = data("open_mindedness"); d["evidence_standard"] = ""
    out = R("open_mindedness", d)
    assert out["state_machine"]["current_state"] == "same_standard_applied"

def test_row_792_intellectual_humility_flags_miscalibration():
    d = data("intellectual_humility"); d.update(confidence=95, evidence_strength="low")
    out = R("intellectual_humility", d)
    assert out["analysis"]["miscalibration_flag"] is True

def test_row_793_wisdom_judges_beyond_the_loudest_moment():
    out = R("wisdom", data("wisdom"))
    assert out["analysis"]["current_pressures"] == ["midterm stress", "parent expectations"]
    assert "after the immediate pressure passes" in out["analysis"]["long_view_test"]

def test_row_794_prudence_warns_on_high_stakes_irreversibility():
    d = data("prudence"); d["reversible_step"] = ""
    out = R("prudence", d)
    assert out["analysis"]["high_stakes_warning"] is True

def test_row_795_temperance_sets_a_limit_that_serves_the_goal():
    out = R("temperance", data("temperance"))
    assert out["analysis"]["chosen_limit"] == "weeknights off by 10pm"
    assert "punish the desire" in out["analysis"]["alignment_question"]

def test_row_796_courage_treats_real_danger_as_safety_not_character():
    d = data("courage"); d["real_danger"] = True
    out = R("courage", d)
    assert "not a test of character" in out["analysis"]["safety_first"]

def test_row_797_resilience_requires_recovery_before_restart():
    out = R("resilience", data("resilience"))
    assert out["analysis"]["recovery_time"] == "rest this weekend"
    assert out["analysis"]["restart_step"] == "outline one practice round Monday"

def test_row_798_grit_reassesses_when_the_cost_is_health():
    out = R("grit", data("grit"))
    assert out["analysis"]["costs_touching_health_or_relationships"]
    assert out["analysis"]["still_worth_it"] is False

def test_row_799_self_control_redesigns_environment_not_willpower():
    out = R("self_control", data("self_control"))
    assert "not fight impulse with willpower" in out["analysis"]["rule"]
    assert out["analysis"]["friction_added"] == "phone charges in another room"

def test_row_800_delayed_gratification_requires_concrete_benefit_and_milestones():
    d = data("delayed_gratification"); d["future_benefit"] = "good"
    out = R("delayed_gratification", d)
    assert out["analysis"]["concrete"] is False
    assert out["analysis"]["milestones"] == ["draft three pieces by week 4"]

def test_row_801_impulse_control_needs_a_pause_plan():
    d = data("impulse_control"); d["alternatives"] = []
    out = R("impulse_control", d)
    assert out["state_machine"]["current_state"] == "pause_ready"
    assert "ten minutes" in out["analysis"]["rule"]

def test_row_802_emotional_regulation_names_slows_then_chooses():
    d = data("emotional_regulation"); d["pause_taken"] = False
    out = R("emotional_regulation", d)
    assert out["state_machine"]["current_state"] == "response_slowed"
    assert "not denying the feeling" in out["analysis"]["suppression_note"]

def test_row_803_stress_management_triages_every_pressure():
    d = data("stress_management"); d["pressures"] = ["exam prep", "club duties", "family ask"]
    out = R("stress_management", d)
    assert out["analysis"]["untriaged"] == ["family ask"]
    assert out["analysis"]["triage"]["shareable"] == ["club duties"]

def test_row_804_coping_excludes_options_that_create_bigger_harms():
    out = R("coping_strategies", data("coping_strategies"))
    assert out["analysis"]["safe_options"] == [{"support": "evening walks", "safe": True}]
    assert out["analysis"]["excluded_harmful_options"] == [{"support": "all-night cramming", "safe": False}]

def test_row_805_mindfulness_is_voluntary_and_unscored():
    out = R("mindfulness", data("mindfulness"))
    assert "notice five things" in out["analysis"]["exercise"]
    assert "Skip or stop anytime" in out["analysis"]["voluntary"]

def test_row_806_meditation_bounds_duration_and_honors_none():
    d = data("meditation"); d["minutes"] = 120
    out = R("meditation", d)
    assert out["analysis"]["minutes_bounded"] == 30
    d2 = data("meditation"); d2["practice_preference"] = "tantrum"
    out2 = R("meditation", d2)
    assert out2["state_machine"]["current_state"] == "preference_respected"
    with pytest.raises(ValueError, match="minutes must be an integer"):
        R("meditation", {"practice_preference": "breath", "minutes": "lots"})

def test_row_807_relaxation_stops_on_discomfort():
    out = R("relaxation", data("relaxation"))
    assert out["analysis"]["chosen_option"] == "stretching"
    assert "Stop anything that feels uncomfortable" in out["analysis"]["stop_rule"]

def test_row_808_sleep_hygiene_maps_disruptors_to_alternatives():
    out = R("sleep_hygiene", data("sleep_hygiene"))
    assert set(out["analysis"]["disruptors_found"]) == {"screens in bed", "caffeine late"}
    assert "licensed clinician" in out["analysis"]["professional_boundary"]

def test_row_809_exercise_excludes_impact_against_limits():
    out = R("exercise", data("exercise"))
    assert out["analysis"]["suitable_options"] == ["swimming", "cycling"]
    assert out["analysis"]["excluded_for_limits"] == ["running"]
    assert "clinician" in out["analysis"]["medical_clearance_note"]
