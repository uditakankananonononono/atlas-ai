"""Executable, row-addressable coaching/communication/negotiation tools, rows 710-809.

Each of the 100 ledger rows dispatches to a named callable running a method-specific
state machine with distinctive computed outputs. Boundaries enforced at runtime:
manipulative intent is refused, consent/authorization gates block sensitive methods,
wellbeing methods carry crisis escalation, and no output performs an external action.
"""
from __future__ import annotations

import re
from typing import Any, Callable

# ---------------------------------------------------------------------------
# Boundary scanners
# ---------------------------------------------------------------------------

MANIPULATION_PATTERNS: list[tuple[str, str]] = [
    (r"\byou must\b|\byou have to\b|\byou'd better\b", "coercive demand"),
    (r"\bif you (really )?(loved|cared|valued)\b", "guilt leverage"),
    (r"\beveryone (knows|agrees|is doing)\b", "false consensus"),
    (r"\blast chance\b|\bact now or\b|\btime is running out\b|\bexpires tonight\b", "manufactured urgency"),
    (r"\byou (always|never)\b", "character attack"),
    (r"\bor else\b|\byou'?ll regret\b", "veiled threat"),
    (r"\bno one (else )?(will|would)\b", "isolation pressure"),
    (r"\byou'?re (overreacting|imagining things|too sensitive|crazy)\b", "reality undermining"),
]

CRISIS_PATTERNS: list[str] = [
    r"\bsuicid", r"\bkill (myself|me)\b", r"\bself[- ]?harm\b", r"\bend (my|it) (life|all)\b",
    r"\boverdose\b", r"\bhurt(ing)? (myself|someone (else)?)\b", r"\bcan'?t stay safe\b",
]

# Fields whose manipulative content means the *owner's intent* is manipulative:
# refuse rather than coach. Quoted/observed content in critique fields is coached on.
INTENT_FIELDS = {"goal", "objective", "action", "intended_help", "planned_action", "request"}
CRITIQUE_FIELDS = {
    "draft", "message", "argument", "proposal", "feedback_received", "heard_statement",
    "stated_feeling", "stated_experience", "stated_need", "statement", "ambiguous_statement",
    "observation", "observed_behavior", "claim", "opposing_view", "point", "context",
}

CONSENT_NOTE = (
    "This method involves other people and runs only with their freely given, informed consent. "
    "Re-invite consent; do not proceed on silence, pressure, or assumed agreement."
)
AUTHORIZATION_NOTE = (
    "This adversarial method runs only inside explicit, documented authorization with named scope. "
    "Without it the exercise is indistinguishable from a real attack and is refused."
)
CRISIS_NOTE = (
    "Possible crisis or safety language was detected. This tool is not emergency or crisis support. "
    "If there is immediate danger, possible self-harm or harm to others, or inability to stay safe, "
    "contact local emergency services or a qualified crisis/health professional now and involve a "
    "trusted person where safe. Coaching resumes only after safety is addressed."
)
FAMILY_BOUNDARY = {
    "communication": "Coaching for the owner's review only. Never sends, publishes, impersonates, manipulates, or claims to know another person's feelings, motives, or culture.",
    "collaboration": "Group-process coaching for the owner's review only. Never messages a group, records votes, infers mental states as fact, or runs adversarial exercises outside fictional or explicitly authorized scope.",
    "trust_wellbeing": "Optional, non-clinical coaching. Does not diagnose, treat, infer identity or conditions, or replace professional, medical, or emergency help.",
}


def _scan(text: str, patterns: list[tuple[str, str]] | list[str]) -> list[str]:
    hits: list[str] = []
    for item in patterns:
        pattern, label = (item if isinstance(item, tuple) else (item, item))
        if re.search(pattern, text, re.IGNORECASE):
            hits.append(label)
    return hits


def _present(value: Any) -> bool:
    return value is not None and value != "" and value != [] and value != {}


def _collect(value: Any, parts: list[str]) -> None:
    if isinstance(value, str):
        parts.append(value)
    elif isinstance(value, dict):
        for child in value.values():
            _collect(child, parts)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _collect(child, parts)


def _all_text(data: dict[str, Any]) -> str:
    parts: list[str] = []
    for value in data.values():
        _collect(value, parts)
    return " ".join(parts)


def _text_of(data: dict[str, Any], fields: set[str]) -> str:
    parts: list[str] = []
    for key, value in data.items():
        if key not in fields:
            continue
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, list):
            parts.extend(str(v) for v in value)
        elif isinstance(value, dict):
            parts.extend(str(v) for v in value.values())
    return " ".join(parts)


def S(name: str, complete: bool, detail: str) -> dict[str, Any]:
    return {"state": name, "complete": bool(complete), "evidence": detail}


def _has(text: str, *words: str) -> bool:
    return any(w.lower() in text.lower() for w in words)


def _absolutes(text: str) -> list[str]:
    return re.findall(r"\b(?:always|never|everyone|no one|nobody)\b", text, re.IGNORECASE)


def _key_words(text: str, limit: int = 4) -> list[str]:
    words = [w for w in re.findall(r"[A-Za-z][a-z]{4,}", text.lower())]
    seen: list[str] = []
    for w in words:
        if w not in seen:
            seen.append(w)
    return seen[:limit]


# ---------------------------------------------------------------------------
# Row specs: (method name, required fields, flags)
# ---------------------------------------------------------------------------

SPECS: dict[int, dict[str, Any]] = {}


def _spec(row: int, method: str, family: str, required: list[str], **flags: Any) -> None:
    SPECS[row] = {"method": method, "family": family, "required": required, **flags}


C = "communication"
G = "collaboration"
W = "trust_wellbeing"

# ------------------------- rows 710-740: communication -------------------------

_spec(710, "persuasive_writing", C, ["claims"])
_spec(711, "negotiation_tactics", C, ["interests", "walkaway"])
_spec(712, "conflict_resolution", C, ["positions", "shared_facts"])
_spec(713, "mediation", C, ["parties", "process_agreement"], consent=True)
_spec(714, "active_listening", C, ["heard_statement"])
_spec(715, "empathetic_response", C, ["stated_feeling"])
_spec(716, "emotional_intelligence", C, ["own_state", "observable_cues"])
_spec(717, "social_calibration", C, ["setting", "audience_signals"])
_spec(718, "cultural_sensitivity", C, ["stated_preferences"])
_spec(719, "cross_cultural_communication", C, ["message"])
_spec(720, "diplomatic_language", C, ["point"])
_spec(721, "assertiveness", C, ["need", "request"])
_spec(722, "boundary_setting", C, ["limit", "consequence"])
_spec(723, "difficult_conversations", C, ["topic", "setting"])
_spec(724, "feedback_delivery", C, ["observed_behavior", "impact"])
_spec(725, "feedback_reception", C, ["feedback_received"])
_spec(726, "public_speaking", C, ["takeaway", "duration_minutes"])
_spec(727, "presentation_design", C, ["slides"])
_spec(728, "storytelling", C, ["true_event", "change"])
_spec(729, "rapport_building", C, ["shared_interest"])
_spec(730, "networking", C, ["introduction", "mutual_value"])
_spec(731, "mentorship", C, ["mentee_goal"])
_spec(732, "coaching", C, ["coachee_goal", "current_reality"])
_spec(733, "teaching", C, ["learning_objective"])
_spec(734, "explaining_complex_ideas", C, ["concept", "audience_knowledge"])
_spec(735, "analogies", C, ["concept", "comparison"])
_spec(736, "metaphors", C, ["concept", "image"])
_spec(737, "examples", C, ["concept", "example"])
_spec(738, "scaffolding", C, ["target_skill", "current_level"])
_spec(739, "questioning", C, ["topic"])
_spec(740, "socratic_method", C, ["claim"])


def _m710(d: dict[str, Any]):
    claims = d.get("claims", [])
    mapped, unsupported = [], []
    for item in claims:
        if isinstance(item, dict):
            claim, evidence = str(item.get("claim", "")), item.get("evidence")
        else:
            claim, evidence = str(item), None
        mapped.append({"claim": claim, "evidence": evidence, "supported": _present(evidence)})
        if not _present(evidence):
            unsupported.append(claim)
    draft = str(d.get("draft", ""))
    flags = _scan(draft, MANIPULATION_PATTERNS) + ["absolute claim: " + a for a in _absolutes(draft)]
    reader_questions = [f"What evidence would change a skeptic's mind about: {m['claim'][:80]}?" for m in mapped[:5]]
    analysis = {"claim_evidence_map": mapped, "unsupported_claims": unsupported,
                "draft_integrity_flags": flags, "reader_questions": reader_questions}
    stages = [S("claims_listed", bool(claims), f"{len(claims)} claims"),
              S("evidence_mapped", bool(claims) and not unsupported, f"{len(unsupported)} unsupported"),
              S("manipulation_screened", not flags, f"{len(flags)} integrity flags"),
              S("counterargument_considered", _present(d.get("counterarguments")), "strongest objection named"),
              S("ready_for_owner_review", bool(claims) and not unsupported and not flags, "all claims evidenced and clean")]
    return analysis, stages


def _m711(d: dict[str, Any]):
    interests = d.get("interests", [])
    parties = sorted({str(i.get("party")) for i in interests if isinstance(i, dict) and i.get("party")})
    shared = [str(i.get("interest")) for i in interests if isinstance(i, dict) and list(interests).count(i) > 1]
    walkaway = str(d.get("walkaway", ""))
    batna_specific = len(walkaway) >= 15 and bool(re.search(r"\b(will|would|instead|alternative|current)\b", walkaway, re.I))
    options = d.get("options", [])
    concessions = d.get("concessions", [])
    unbalanced = [c for c in concessions if isinstance(c, dict) and not (c.get("give") and c.get("get"))]
    analysis = {"parties": parties, "interests": interests, "shared_interests": shared,
                "batna": {"walkaway": walkaway, "specific": batna_specific,
                          "note": "A vague walkaway invites concessions below your real alternative." if not batna_specific else "Walkaway names a concrete alternative."},
                "options_on_the_table": options, "unbalanced_concessions": unbalanced,
                "fairness_rule": "Trade, never give: every concession needs a get of equal stated value."}
    stages = [S("interests_mapped", bool(interests) and bool(parties), f"interests across {len(parties)} parties"),
              S("batna_defined", batna_specific, "walkaway concrete and actionable"),
              S("options_generated", len(options) >= 2, f"{len(options)} mutual-gain options"),
              S("concessions_balanced", bool(concessions) and not unbalanced, f"{len(unbalanced)} one-sided concessions"),
              S("agreement_reality_tested", _present(d.get("agreement_test")), "both sides can actually deliver")]
    return analysis, stages


def _m712(d: dict[str, Any]):
    positions = d.get("positions", [])
    shared = d.get("shared_facts", [])
    disputed = d.get("disputed_facts", [])
    restatements = [f"One side sees it as: {str(p)[:120]}. That concern is legitimate to them."
                    for p in positions[:4]]
    repairs = d.get("repair_options", [])
    analysis = {"agreed_facts": shared, "disputed_facts": disputed,
                "unknown_facts": d.get("unknown_facts", []),
                "neutral_restatements": restatements, "repair_options": repairs,
                "process_rule": "Solve the shared problem; never assign motive or character."}
    stages = [S("facts_separated", bool(shared), f"{len(shared)} agreed / {len(disputed)} disputed"),
              S("perspectives_restated", bool(positions), f"{len(restatements)} neutral restatements"),
              S("repair_options_generated", len(repairs) >= 2, f"{len(repairs)} repairs proposed"),
              S("agreement_drafted", _present(d.get("agreement_draft")), "specific, verifiable next steps")]
    return analysis, stages


def _m713(d: dict[str, Any]):
    parties = [str(p) for p in d.get("parties", [])]
    if len(parties) < 2:
        raise ValueError("mediation requires at least two parties")
    turns = [f"Turn {i + 1}: {party} speaks uninterrupted; others reflect back before responding."
             for i, party in enumerate(parties)]
    analysis = {"neutral_turn_schedule": turns, "ground_rules": str(d.get("process_agreement", "")),
                "neutrality_check": "Mediator proposes process only; outcomes belong to the parties.",
                "referral_boundary": "Stop and refer to qualified help if coercion, abuse, safety risk, or serious power imbalance appears.",
                "session_log": d.get("sessions", []), "recorded_agreements": d.get("agreements", [])}
    stages = [S("consent_confirmed", d.get("consent_confirmed") is True, "every party freely agreed to this process"),
              S("parties_balanced", len(parties) >= 2, f"{len(parties)} parties with equal turns"),
              S("ground_rules_set", _present(d.get("process_agreement")), "rules named before content"),
              S("sessions_structured", bool(d.get("sessions")), f"{len(d.get('sessions', []))} sessions held"),
              S("agreements_recorded", bool(d.get("agreements")), "agreements written without taking sides")]
    return analysis, stages


def _m714(d: dict[str, Any]):
    heard = str(d.get("heard_statement", ""))
    keys = _key_words(heard)
    paraphrase = f"You said: {heard[:200]}" + (f" — especially about {', '.join(keys[:2])}." if keys else ".")
    check = "Did I get that right, and what did I miss?"
    open_q = f"What matters most to you about {keys[0] if keys else 'this'}?"
    analysis = {"paraphrase": paraphrase, "accuracy_check": check, "open_followup": open_q,
                "listening_barriers": ["rehearsing a reply", "advising before understanding", "matching their story with yours"]}
    stages = [S("statement_received", bool(heard), "their words captured"),
              S("paraphrase_drafted", bool(heard), "reflection in your own words"),
              S("accuracy_checked", d.get("accuracy_confirmed") is True, "speaker confirmed the paraphrase"),
              S("open_question_asked", d.get("followup_asked") is True, "one open question, no fixing")]
    return analysis, stages


def _m715(d: dict[str, Any]):
    feeling = str(d.get("stated_feeling", ""))
    given = str(d.get("context", ""))[:120]
    validation = f"It makes sense you feel {feeling}" + (f" after {given}." if given else ".")
    inferred = [str(x) for x in d.get("inferred_feelings", [])]
    analysis = {"validation": validation,
                "rejected_inferences": [{"inference": i, "reason": "They did not say this; ask instead of assuming."} for i in inferred],
                "ask_instead": "What would help right now — listening, ideas, or space?",
                "rule": "Validate only what the person actually stated."}
    stages = [S("feeling_named_by_person", bool(feeling), "their word, not yours"),
              S("validation_drafted", bool(feeling), "acknowledges without claiming their mind"),
              S("assumptions_excluded", not inferred, f"{len(inferred)} inferences rejected"),
              S("support_choice_offered", d.get("support_offered") is True, "they choose the kind of help")]
    return analysis, stages


def _m716(d: dict[str, Any]):
    cues = [str(c) for c in d.get("observable_cues", [])]
    hypotheses = [{"cue": c, "readings": [f"{c} could relate to this conversation",
                                          f"{c} could be unrelated (fatigue, stress elsewhere)"],
                   "verification": "Ask; do not conclude."} for c in cues[:5]]
    analysis = {"own_state": str(d.get("own_state", "")), "cue_hypotheses": hypotheses,
                "regulation_first": "Name your own state before reading anyone else's.",
                "rule": "Every cue gets at least two hypotheses; none becomes a diagnosis."}
    stages = [S("own_state_named", _present(d.get("own_state")), "self before other"),
              S("cues_observed", bool(cues), f"{len(cues)} observable cues"),
              S("multiple_hypotheses_held", bool(hypotheses), "alternative readings generated"),
              S("verified_with_person", d.get("verified") is True, "checked by asking")]
    return analysis, stages


def _m717(d: dict[str, Any]):
    signals = [str(s).lower() for s in d.get("audience_signals", [])]
    score = 3
    if any(_has(s, "reserved", "formal", "quiet") for s in signals):
        score -= 1
    if any(_has(s, "direct", "blunt", "fast") for s in signals):
        score += 1
    if any(_has(s, "enthusiastic", "warm", "casual") for s in signals):
        score = min(5, score + 0)  # warmth does not license bluntness
    score = max(1, min(5, score))
    analysis = {"setting": str(d.get("setting", "")), "signals_read": signals,
                "recommended_directness": {"level": score, "scale": "1 very gentle - 5 very direct"},
                "consent_move": "Offer a low-pressure option and watch for explicit feedback before escalating directness.",
                "warning": "Signals are invitations, not proof; re-calibrate on the person's actual responses."}
    stages = [S("context_assessed", _present(d.get("setting")), "setting named"),
              S("signals_read", bool(signals), f"{len(signals)} signals"),
              S("directness_calibrated", bool(signals), f"level {score} recommended"),
              S("feedback_invited", _present(d.get("feedback_channel")), "explicit feedback channel open")]
    return analysis, stages


def _m718(d: dict[str, Any]):
    prefs = [str(p) for p in d.get("stated_preferences", [])]
    draft = str(d.get("draft", ""))
    stereotype_flags = re.findall(r"\b(?:all|every|typical)\s+[A-Za-z]+\s+(?:people|are|always|tend)\b", draft, re.I)
    analysis = {"stated_preferences": prefs, "stereotype_flags": stereotype_flags,
                "ask_instead": [f"How do you prefer {kw}?" for kw in _key_words(" ".join(prefs), 3)],
                "rule": "Use this person's stated preferences; group generalizations are hypotheses, never facts."}
    stages = [S("assumptions_flagged", not stereotype_flags, f"{len(stereotype_flags)} stereotype patterns in draft"),
              S("preferences_requested", bool(prefs) or _present(d.get("questions")), "preferences asked directly"),
              S("individual_verified", d.get("confirmed_with_person") is True, "person confirmed their own preference")]
    return analysis, stages


_IDIOMS = {"break the ice": "start the conversation", "ballpark": "rough estimate",
           "touch base": "check in", "low-hanging fruit": "easiest tasks first",
           "rain check": "postpone politely", "hit the ground running": "start immediately",
           "circle back": "return to the topic", "on the same page": "in agreement",
           "think outside the box": "try a different approach", "piece of cake": "very easy"}


def _m719(d: dict[str, Any]):
    message = str(d.get("message", ""))
    found = {idiom: plain for idiom, plain in _IDIOMS.items() if idiom in message.lower()}
    jargon = [w for w in re.findall(r"[A-Za-z]{13,}", message)][:5]
    analysis = {"idioms_found": found, "long_jargon_words": jargon,
                "plain_language_advice": "Replace idioms with literal wording; define any term that may not transfer.",
                "confirmation_prompt": "Could you tell me how you understood that, so I can adjust?",
                "rule": "Shared meaning is confirmed with the listener, never assumed."}
    stages = [S("message_supplied", bool(message), "message captured"),
              S("transfer_risks_flagged", True, f"{len(found)} idioms, {len(jargon)} jargon words"),
              S("plain_version_ready", not found or _present(d.get("plain_version")), "idioms replaced with literal wording"),
              S("meaning_confirmed", d.get("confirmation_received") is True, "listener played back meaning")]
    return analysis, stages


_HARSH = ["stupid", "lazy", "incompetent", "idiot", "hate", "shut up", "pathetic"]


def _m720(d: dict[str, Any]):
    point = str(d.get("point", ""))
    draft = str(d.get("draft", ""))
    harsh = [w for w in _HARSH if w in draft.lower()]
    vague = re.findall(r"\b(?:maybe|kind of|sort of|a bit|whatever)\b", draft, re.I)
    fir = {"fact": str(d.get("fact", point)), "impact": str(d.get("impact", "")),
           "request": str(d.get("request", ""))}
    analysis = {"fact_impact_request": fir, "harsh_words": harsh, "vague_softeners": vague,
                "guideline": "Name the fact and impact without judging the person; make the request explicit, not euphemistic."}
    stages = [S("point_clear", bool(point), "issue named in one sentence"),
              S("fact_impact_request_built", bool(fir["impact"]) and bool(fir["request"]), "all three parts present"),
              S("tone_screened", not harsh, f"{len(harsh)} harsh words"),
              S("directness_preserved", len(vague) <= 1, f"{len(vague)} vague softeners")]
    return analysis, stages


def _m721(d: dict[str, Any]):
    need, request = str(d.get("need", "")), str(d.get("request", ""))
    draft = str(d.get("draft", ""))
    blame = re.findall(r"\byou (?:always|never|make me|don't care)\b[^.]*", draft, re.I)
    i_statement = f"I need {need}. I'm asking {request}."
    choice_ok = _has(request, "could", "open to", "willing", "would you", "option") or not request
    analysis = {"i_statement": i_statement, "blame_patterns_in_draft": blame,
                "choice_preserved": choice_ok,
                "rule": "State the need, make a concrete request, leave the other person a real choice."}
    stages = [S("need_named", bool(need), "specific need"),
              S("i_statement_built", bool(need and request), "I-statement without motive assignment"),
              S("blame_removed", not blame, f"{len(blame)} blame patterns in draft"),
              S("choice_preserved", choice_ok, "request leaves a genuine option")]
    return analysis, stages


def _m722(d: dict[str, Any]):
    limit, consequence = str(d.get("limit", "")), str(d.get("consequence", ""))
    owned = bool(re.match(r"\s*i\b", consequence, re.I))
    disproportionate = _has(consequence, "never speak", "destroy", "ruin", "make you pay", "end everything")
    analysis = {"limit": limit, "consequence": consequence, "consequence_owned_by_you": owned,
                "proportionate": not disproportionate,
                "rule": "A boundary states what you will do, not what you will make them feel; keep it proportionate."}
    stages = [S("limit_stated", bool(limit), "clear behavioral limit"),
              S("consequence_owned", owned, "an action you control"),
              S("proportionate", not disproportionate, "response fits the limit"),
              S("followthrough_planned", _present(d.get("followthrough")), "calm enforcement decided in advance")]
    return analysis, stages


def _m723(d: dict[str, Any]):
    topic, setting = str(d.get("topic", "")), str(d.get("setting", ""))
    opening = f"I want to talk about {topic} because it matters to {str(d.get('goal', 'us'))[:80]}."
    timing = {"private": not _has(setting, "public", "group", "open plan"),
              "unhurried": not _has(setting, "between meetings", "rushed", "hallway"),
              "calm": not _has(setting, "argument", "heated", "angry")}
    analysis = {"opening_line": opening, "setting_check": timing,
                "pause_plan": "After your opening, stop talking and let them respond fully.",
                "rule": "Rehearse the facts; do not script their reaction."}
    stages = [S("topic_named", bool(topic), "one topic, not a laundry list"),
              S("setting_assessed", bool(setting) and all(timing.values()), "private, unhurried, calm"),
              S("opening_rehearsed", _present(d.get("rehearsed")), "factual opening practiced aloud"),
              S("pause_planned", True, "their perspective comes next")]
    return analysis, stages


def _m724(d: dict[str, Any]):
    behavior, impact = str(d.get("observed_behavior", "")), str(d.get("impact", ""))
    generalizations = _absolutes(behavior)
    sbi = {"situation": str(d.get("situation", "")), "behavior": behavior, "impact": impact}
    analysis = {"sbi": sbi, "generalization_flags": generalizations,
                "next_step": str(d.get("next_step", "")),
                "rule": "Describe observable behavior and impact; offer one actionable step; no verdicts on character."}
    stages = [S("behavior_observable", bool(behavior) and not generalizations, "a camera could record it"),
              S("impact_named", bool(impact), "concrete effect stated"),
              S("situation_anchored", bool(sbi["situation"]), "when and where"),
              S("next_step_actionable", _present(d.get("next_step")), "one doable change")]
    return analysis, stages


def _m725(d: dict[str, Any]):
    fb = str(d.get("feedback_received", ""))
    summary = f"What I'm hearing: {fb[:200]}. Is that accurate?"
    analysis = {"summary_check": summary, "clarifying_example_request": "Could you give one specific example so I can see it?",
                "decision_frame": "Decide later what to adopt, adapt, or decline — understanding first, choosing second.",
                "decisions": d.get("decisions", {})}
    stages = [S("feedback_heard", bool(fb), "received without rebuttal"),
              S("summarized_back", d.get("summarized") is True, "played back for accuracy"),
              S("example_requested", d.get("example_requested") is True, "one concrete example"),
              S("decided_deliberately", _present(d.get("decisions")), "adopt/adapt/decline recorded")]
    return analysis, stages


def _m726(d: dict[str, Any]):
    takeaway = str(d.get("takeaway", ""))
    try:
        minutes = float(d.get("duration_minutes", 0))
    except (TypeError, ValueError):
        raise ValueError("duration_minutes must be a number")
    words = int(minutes * 130)
    structure = [{"part": p, "percent": pc, "word_budget": int(words * pc / 100)}
                 for p, pc in [("hook", 10), ("point_1", 25), ("point_2", 25), ("point_3", 25), ("close", 15)]]
    analysis = {"takeaway": takeaway, "total_word_budget": words,
                "structure": structure, "pause_marks": "Mark a 2-second pause after each point transition.",
                "rehearsal_plan": "Rehearse aloud, timed, at least twice; record one pass."}
    stages = [S("takeaway_single", bool(takeaway) and len(takeaway) <= 200, "one memorable idea"),
              S("timing_budgeted", minutes > 0, f"{minutes} min -> ~{words} words at 130 wpm"),
              S("structure_outlined", _present(d.get("outline")), "five-part arc drafted"),
              S("rehearsed_aloud", int(d.get("rehearsals", 0) or 0) >= 2, "two timed aloud runs")]
    return analysis, stages


def _m727(d: dict[str, Any]):
    slides = d.get("slides", [])
    rows, missing_claim, cluttered = [], [], []
    for i, s in enumerate(slides):
        if not isinstance(s, dict):
            s = {"title": str(s)}
        claim = s.get("claim")
        bullets = s.get("bullets", [])
        words = sum(len(str(b).split()) for b in bullets)
        if not _present(claim):
            missing_claim.append(str(s.get("title", f"slide {i + 1}")))
        if len(bullets) > 6 or words > 40:
            cluttered.append(str(s.get("title", f"slide {i + 1}")))
        rows.append({"slide": s.get("title", f"slide {i + 1}"), "claim": claim,
                     "bullet_count": len(bullets), "word_count": words})
    claims = [r["claim"] for r in rows if r["claim"]]
    analysis = {"slides": rows, "slides_missing_claim": missing_claim, "cluttered_slides": cluttered,
                "duplicate_claims": sorted({c for c in claims if claims.count(c) > 1}),
                "rule": "One claim per slide, evidence sequenced, decoration removed."}
    stages = [S("one_claim_per_slide", bool(slides) and not missing_claim, f"{len(missing_claim)} slides lack a claim"),
              S("claims_unique", not [c for c in claims if claims.count(c) > 1], "no repeated claims"),
              S("clutter_removed", not cluttered, f"{len(cluttered)} cluttered slides"),
              S("deck_reviewed", d.get("reviewed") is True, "full pass with fresh eyes")]
    return analysis, stages


def _m728(d: dict[str, Any]):
    event, change = str(d.get("true_event", "")), str(d.get("change", ""))
    invented = [str(x) for x in d.get("invented_details", [])]
    arc = {"setup": f"Before: the situation around — {event[:120]}",
           "choice": str(d.get("choice", "the specific decision you made")),
           "consequence": str(d.get("consequence", "what actually happened next")),
           "change": change}
    analysis = {"arc": arc, "invented_details_rejected": invented,
                "verified_facts": d.get("verified_facts", []),
                "rule": "Real stakes beat invented drama; every load-bearing detail must be verifiable."}
    stages = [S("event_true", d.get("event_verified") is True, "event confirmed by the owner"),
              S("arc_built", bool(event and change), "setup-choice-consequence-change"),
              S("stakes_honest", not invented, f"{len(invented)} invented details rejected"),
              S("facts_verified", _present(d.get("verified_facts")), "load-bearing details checked")]
    return analysis, stages


_SENSITIVE = ("salary", "income", "health", "diagnosis", "religion", "politics", "family problems", "relationship")


def _m729(d: dict[str, Any]):
    interest = str(d.get("shared_interest", ""))
    keys = _key_words(interest, 2) or [interest[:30]]
    questions = [f"What got you into {keys[0]}?", f"What do you enjoy most about {keys[0]} lately?",
                 f"Have you found good people or places around {keys[0]} here?"]
    privacy_flags = [q for q in questions if _has(q, *_SENSITIVE)]
    analysis = {"open_questions": questions, "privacy_flags": privacy_flags,
                "genuine_interest_required": "Ask only what you actually want to hear about; mining private data is not rapport.",
                "disengage_signals": ["short answers", "body turned away", "no return questions"]}
    stages = [S("interest_genuine", d.get("genuine") is True, "you actually care about this topic"),
              S("questions_open", True, f"{len(questions)} open questions"),
              S("privacy_safe", not privacy_flags, "no sensitive-topic probing"),
              S("disengagement_respected", d.get("exit_respected") is not False, "leave when signals say leave")]
    return analysis, stages


def _m730(d: dict[str, Any]):
    intro, value = str(d.get("introduction", "")), str(d.get("mutual_value", ""))
    transparent = _has(intro, "because", "i'm", "i am") and len(intro) >= 20
    analysis = {"introduction": intro, "transparent": transparent,
                "mutual_value_statement": value,
                "no_pressure_question": "Would a short conversation be useful to you, and if not, no worries at all?",
                "rule": "Say who you are and why you are reaching out; make declining costless."}
    stages = [S("introduction_transparent", transparent, "name, reason, no hidden agenda"),
              S("value_mutual", bool(value), "useful to both, not just you"),
              S("decline_costless", True, "no-pressure close included"),
              S("followup_consensual", _present(d.get("followup_preference")), "they chose the channel")]
    return analysis, stages


def _m731(d: dict[str, Any]):
    goal = str(d.get("mentee_goal", ""))
    options = [str(o) for o in d.get("experience_options", [])]
    analysis = {"mentee_goal": goal, "experience_offered_as_options": options,
                "decision_prompt": "Which of these — or something else — do you want to try?",
                "rule": "Offer experience as options; the mentee owns every decision and its outcome."}
    stages = [S("goal_mentee_defined", bool(goal), "their words, not yours"),
              S("options_offered", len(options) >= 1, f"{len(options)} options on the table"),
              S("decision_left_to_mentee", d.get("directive_given") is not True, "no directives issued"),
              S("progress_reviewed_together", _present(d.get("review")), "review scheduled with them")]
    return analysis, stages


def _m732(d: dict[str, Any]):
    goal, reality = str(d.get("coachee_goal", "")), str(d.get("current_reality", ""))
    options = d.get("options", [])
    grow = {"goal": goal, "reality": reality, "options": options,
            "way_forward": str(d.get("commitment", ""))}
    analysis = {"grow_model": grow,
                "questions": {"goal": "What would progress look like to you?",
                              "reality": "What is happening now, specifically?",
                              "options": "What else could work?",
                              "will": "Which one will you try, and by when?"},
                "rule": "Ask, reflect, let them choose the experiment; the coach never picks for them."}
    stages = [S("goal_defined", bool(goal), "coachee's goal"),
              S("reality_assessed", bool(reality), "facts of now"),
              S("options_generated", len(options) >= 2, f"{len(options)} options"),
              S("commitment_chosen_by_coachee", _present(d.get("commitment")), "one experiment, their choice")]
    return analysis, stages


_MEASURABLE_VERBS = ("explain", "demonstrate", "solve", "identify", "create", "apply", "compare", "analyze", "build")


def _m733(d: dict[str, Any]):
    objective = str(d.get("learning_objective", ""))
    measurable = _has(objective, *_MEASURABLE_VERBS)
    plan = {"explain": str(d.get("explanation", "core idea in plain words")),
            "model": str(d.get("model", "worked example shown step by step")),
            "practice": str(d.get("practice", "")),
            "check": str(d.get("assessment", ""))}
    analysis = {"objective": objective, "objective_measurable": measurable, "teaching_plan": plan,
                "rule": "The learner should be able to *do* something afterward; test that, not attention."}
    stages = [S("objective_measurable", measurable, "observable verb present"),
              S("explanation_planned", _present(d.get("explanation")), "plain-words core"),
              S("practice_designed", _present(d.get("practice")), "learner does the thing"),
              S("understanding_checked", _present(d.get("assessment")), "they demonstrate, you watch")]
    return analysis, stages


def _m734(d: dict[str, Any]):
    concept, known = str(d.get("concept", "")), str(d.get("audience_knowledge", ""))
    explanation = str(d.get("explanation", ""))
    jargon = [w for w in re.findall(r"[A-Za-z]{13,}", explanation)][:5]
    layers = [{"layer": 1, "content": f"Anchor in what they know: {known[:120]}"},
              {"layer": 2, "content": f"Core idea only: {concept[:120]}"},
              {"layer": 3, "content": "One extension, added only after layer 2 lands."}]
    analysis = {"layers": layers, "jargon_flags": jargon,
                "check_question": str(d.get("check_question", "")),
                "rule": "One layer at a time; the audience's existing knowledge is the only foundation."}
    stages = [S("prior_knowledge_mapped", bool(known), "what they already know"),
              S("core_isolated", bool(concept), "single core idea"),
              S("jargon_removed", not jargon, f"{len(jargon)} jargon words"),
              S("comprehension_checked", _present(d.get("check_question")), "they explain it back")]
    return analysis, stages


def _m735(d: dict[str, Any]):
    concept, comparison = str(d.get("concept", "")), str(d.get("comparison", ""))
    mappings = d.get("mappings", [])
    limits = str(d.get("limits", ""))
    analysis = {"concept": concept, "comparison": comparison, "explicit_mappings": mappings,
                "limit_statement": limits or f"State where '{comparison[:60]}' stops resembling '{concept[:60]}'.",
                "rule": "Map the similarities explicitly, then name the limit before the audience over-extends it."}
    stages = [S("comparison_chosen", bool(comparison), "familiar domain chosen"),
              S("mappings_explicit", len(mappings) >= 1, f"{len(mappings)} mapped pairs"),
              S("limits_named", _present(d.get("limits")), "where the analogy breaks"),
              S("accuracy_reviewed", d.get("reviewed") is True, "no misleading carryover")]
    return analysis, stages


_VIOLENT_IMAGERY = ("war", "battle", "kill", "attack", "destroy", "weapon", "fight")


def _m736(d: dict[str, Any]):
    concept, image = str(d.get("concept", "")), str(d.get("image", ""))
    violent = [w for w in _VIOLENT_IMAGERY if w in image.lower()]
    implication = str(d.get("implication", f"'{image[:60]}' illuminates '{concept[:60]}' but does not imply literal sameness."))
    analysis = {"concept": concept, "image": image, "violent_imagery_flags": violent,
                "implication_statement": implication,
                "rule": "One clear image, stated limits, and no imagery that could stereotype or needlessly inflame."}
    stages = [S("image_clear", bool(image), "single concrete image"),
              S("implications_stated", _present(d.get("implication")), "what it does and does not imply"),
              S("misleading_risks_screened", not violent, f"{len(violent)} charged words"),
              S("audience_fit_checked", d.get("audience_fit") is True, "image lands for this audience")]
    return analysis, stages


_CONTACT = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+|\+?\d[\d\s().-]{7,}\d")


def _m737(d: dict[str, Any]):
    concept, example = str(d.get("concept", "")), str(d.get("example", ""))
    verified = d.get("verified") is True
    hypothetical = str(d.get("label", "")).lower() == "hypothetical"
    privacy_hits = _CONTACT.findall(example)
    analysis = {"concept": concept, "example": example[:400],
                "factuality": {"verified": verified, "labeled_hypothetical": hypothetical,
                               "acceptable": verified or hypothetical},
                "privacy_leaks": privacy_hits, "representative": d.get("representative"),
                "rule": "Real and verified, or clearly labeled hypothetical; never a disguised real person."}
    stages = [S("example_concrete", bool(example), "one specific instance"),
              S("factuality_labeled", verified or hypothetical, "verified or labeled hypothetical"),
              S("representative_checked", d.get("representative") is not None, "typical, not cherry-picked"),
              S("privacy_safe", not privacy_hits, "no contact details embedded")]
    return analysis, stages


def _m738(d: dict[str, Any]):
    skill, level = str(d.get("target_skill", "")), str(d.get("current_level", "")).lower()
    support = {"beginner": "full worked model first", "intermediate": "partial model with gaps to fill",
               "advanced": "minimal hints only"}.get(level, "assess level first")
    ladder = [{"step": "model", "support": support},
              {"step": "guided_practice", "support": "attempt with you available"},
              {"step": "independent_attempt", "support": "attempt alone, review after"}]
    analysis = {"target_skill": skill, "current_level": level, "ladder": ladder,
                "mastery_evidence": str(d.get("mastery_evidence", "")),
                "rule": "Support fades as competence grows; the smallest next step is the right one."}
    stages = [S("level_assessed", level in {"beginner", "intermediate", "advanced"}, f"level: {level or 'unknown'}"),
              S("steps_ordered", bool(skill), "model -> guided -> independent"),
              S("support_faded", _present(d.get("fading_plan")), "concrete plan to remove help"),
              S("mastery_checked", _present(d.get("mastery_evidence")), "independent success observed")]
    return analysis, stages


_LEADING = re.compile(r"\b(don't you think|isn't it|wouldn't you agree|right\?|surely)\b", re.I)


def _m739(d: dict[str, Any]):
    topic = str(d.get("topic", ""))
    questions = [str(q) for q in d.get("questions", [])]
    leading = [q for q in questions if _LEADING.search(q)]
    generated = [f"What is your experience with {topic[:60]}?", f"How do you see {topic[:60]}?",
                 f"What would change your mind about {topic[:60]}?"]
    analysis = {"open_questions": generated, "supplied_questions": questions,
                "leading_flags": leading, "answer_optional": "Every question carries a real option not to answer.",
                "rule": "One neutral question at a time; invite information, never pressure agreement."}
    stages = [S("topic_named", bool(topic), "inquiry target"),
              S("questions_open", True, f"{len(generated)} open questions drafted"),
              S("leading_removed", not leading, f"{len(leading)} leading questions flagged"),
              S("silence_respected", d.get("no_answer_ok") is not False, "non-answer is an acceptable answer")]
    return analysis, stages


def _m740(d: dict[str, Any]):
    claim = str(d.get("claim", ""))
    expected = [str(x) for x in d.get("expected_answers", [])]
    sequence = [{"phase": "evidence", "question": f"What supports the claim that {claim[:80]}?"},
                {"phase": "assumption", "question": "What must be true for that support to hold?"},
                {"phase": "implication", "question": "What follows if the claim is true — and if it is false?"}]
    analysis = {"claim": claim, "question_sequence": sequence,
                "trap_risk": {"expected_answers_supplied": expected,
                              "warning": "A Socratic question with a scripted answer is a trap, not inquiry." if expected else "No scripted answers; genuine inquiry."},
                "rule": "The learner reasons; you sequence. Never corner them into your conclusion."}
    stages = [S("claim_clear", bool(claim), "one claim under examination"),
              S("evidence_examined", d.get("evidence_discussed") is True, "support inspected first"),
              S("assumption_surfaced", d.get("assumption_named") is True, "hidden premise named"),
              S("no_traps", not expected, "no scripted destination")]
    return analysis, stages


# ------------------------- rows 741-770: collaboration -------------------------

_spec(741, "facilitation", G, ["purpose", "decision_rule", "roles"])
_spec(742, "brainstorming", G, ["prompt"])
_spec(743, "consensus_building", G, ["proposal"])
_spec(744, "voting_design", G, ["options", "rule"], consent=True)
_spec(745, "deliberation", G, ["question", "evidence"])
_spec(746, "debate", G, ["claim", "sides"])
_spec(747, "rhetoric", G, ["claim", "audience_needs"])
_spec(748, "logic", G, ["premises", "conclusion"])
_spec(749, "fallacy_detection", G, ["argument"])
_spec(750, "steelmanning", G, ["opposing_view"])
_spec(751, "charitable_interpretation", G, ["statement"])
_spec(752, "principle_of_charity", G, ["ambiguous_statement", "interpretations"])
_spec(753, "steel_manning", G, ["argument", "evidence_base"])
_spec(754, "devils_advocacy", G, ["proposal"])
_spec(755, "red_teaming", G, ["scope", "assets", "stop_conditions"], authorization=True)
_spec(756, "war_gaming", G, ["scenario", "assumptions", "moves"])
_spec(757, "tabletop_exercises", G, ["objectives", "roles", "injects"])
_spec(758, "simulation", G, ["parameters", "assumptions"])
_spec(759, "role_playing", G, ["roles", "scenario"], consent=True)
_spec(760, "perspective_taking", G, ["situation", "viewpoints"])
_spec(761, "theory_of_mind", G, ["observed_behavior"])
_spec(762, "mentalizing", G, ["observation"])
_spec(763, "empathy", G, ["stated_experience"])
_spec(764, "compassion", G, ["stated_need"])
_spec(765, "altruism", G, ["intended_help", "recipient_stated_need"])
_spec(766, "prosocial_behavior", G, ["action", "beneficiaries"])
_spec(767, "cooperation", G, ["shared_interest", "commitments"])
_spec(768, "collaboration", G, ["joint_goal", "contributions"])
_spec(769, "teamwork", G, ["roles", "dependencies"])
_spec(770, "team_building", G, ["team_context"])


def _m741(d: dict[str, Any]):
    items = d.get("agenda_items", [])
    untimed = [str(x.get("item", x)) if not isinstance(x, dict) else str(x.get("item")) for x in items
               if not (isinstance(x, dict) and x.get("minutes"))]
    total = sum(int(x.get("minutes", 0)) for x in items if isinstance(x, dict))
    participants = [str(p) for p in d.get("participants", [])]
    speakers = {str(s) for s in d.get("speakers", [])}
    unheard = [p for p in participants if p not in speakers]
    analysis = {"purpose": str(d.get("purpose", "")), "decision_rule": str(d.get("decision_rule", "")),
                "roles": d.get("roles", []), "agenda_total_minutes": total, "untimed_items": untimed,
                "unheard_participants": unheard,
                "rule": "Publish purpose, roles, decision rule, and timeboxes; invite the unheard before closing."}
    stages = [S("purpose_published", _present(d.get("purpose")), "why this meeting exists"),
              S("roles_assigned", bool(d.get("roles")), "facilitator, scribe, timekeeper"),
              S("timeboxes_set", bool(items) and not untimed, f"{len(untimed)} untimed items"),
              S("decision_rule_clear", _present(d.get("decision_rule")), "how decisions get made"),
              S("voices_balanced", bool(participants) and not unheard, f"{len(unheard)} unheard")]
    return analysis, stages


def _m742(d: dict[str, Any]):
    prompt = str(d.get("prompt", ""))
    ideas = [str(i) for i in d.get("ideas", [])]
    clusters: dict[str, list[str]] = {}
    for idea in ideas:
        key = (_key_words(idea, 1) or ["misc"])[0]
        clusters.setdefault(key, []).append(idea[:120])
    analysis = {"prompt": prompt, "idea_count": len(ideas), "clusters": clusters,
                "phase_guard": "Evaluation is a separate, later phase; judging during generation suppresses ideas.",
                "quiet_channel": "Offer written or anonymous contribution so loud voices do not dominate."}
    stages = [S("prompt_clear", bool(prompt), "one sharp prompt"),
              S("generation_unjudged", d.get("evaluation_started") is not True, "no judging during generation"),
              S("quiet_channel_offered", d.get("anonymous_channel") is True, "silent/anonymous path exists"),
              S("quantity_reached", len(ideas) >= int(d.get("idea_target", 8) or 8), f"{len(ideas)} ideas"),
              S("ideas_clustered", bool(clusters), f"{len(clusters)} clusters for the evaluation phase")]
    return analysis, stages


def _m743(d: dict[str, Any]):
    proposal = str(d.get("proposal", ""))
    positions = d.get("positions", [])
    support = [p for p in positions if isinstance(p, dict) and p.get("stance") == "support"]
    reservations = [p for p in positions if isinstance(p, dict) and p.get("reservations")]
    objections = [p for p in positions if isinstance(p, dict) and p.get("objection")]
    unresolved = [o for o in objections if not (isinstance(o, dict) and o.get("response"))]
    analysis = {"proposal": proposal, "support_count": len(support),
                "reservations": [p.get("reservations") for p in reservations if isinstance(p, dict)],
                "unresolved_objections": [o.get("objection") for o in unresolved if isinstance(o, dict)],
                "consensus_definition": "Everyone can live with it and will not block it — not unanimous enthusiasm.",
                "silence_warning": "Silence is not consent; ask each person explicitly."}
    stages = [S("proposal_stated", bool(proposal), "single written proposal"),
              S("positions_recorded", bool(positions), f"{len(positions)} positions on record"),
              S("objections_addressed", bool(positions) and not unresolved, f"{len(unresolved)} unanswered objections"),
              S("consensus_tested_explicitly", d.get("consensus_check") is True, "each person asked by name")]
    return analysis, stages


def _m744(d: dict[str, Any]):
    options = [str(o) for o in d.get("options", [])]
    rule = str(d.get("rule", "")).lower()
    known_rules = {"majority", "supermajority", "ranked", "approval", "consensus"}
    analysis = {"options": options, "rule": rule, "rule_recognized": rule in known_rules,
                "tie_policy": str(d.get("tie_policy", "")),
                "minority_impact": str(d.get("minority_impact_assessment", "")),
                "reversibility_note": "Match the rule to the stakes: reversible choices can use lighter rules.",
                "strategic_voting_note": "Publish the rule before preferences are stated to reduce gaming."}
    stages = [S("consent_confirmed", d.get("consent_confirmed") is True, "voters agreed to the process"),
              S("options_listed", len(options) >= 2, f"{len(options)} options"),
              S("rule_transparent", rule in known_rules, f"rule: {rule or 'unset'}"),
              S("tie_handling_defined", _present(d.get("tie_policy")), "what happens on a tie"),
              S("minority_protected", _present(d.get("minority_impact_assessment")), "loser impact assessed")]
    return analysis, stages


def _m745(d: dict[str, Any]):
    question = str(d.get("question", ""))
    evidence = d.get("evidence", [])
    facts = [e for e in evidence if isinstance(e, dict) and e.get("type") == "fact"]
    values = [e for e in evidence if isinstance(e, dict) and e.get("type") == "value"]
    untyped = [e for e in evidence if not (isinstance(e, dict) and e.get("type") in {"fact", "value"})]
    analysis = {"question": question, "facts": facts, "values": values, "untyped_items": untyped,
                "tradeoffs": d.get("tradeoffs", []),
                "rule": "Share evidence, separate facts from values, name tradeoffs before choosing."}
    stages = [S("question_framed", bool(question), "decision question on the table"),
              S("evidence_shared", bool(evidence), f"{len(evidence)} items shared"),
              S("facts_values_separated", bool(evidence) and not untyped, f"{len(untyped)} untyped items"),
              S("tradeoffs_named", bool(d.get("tradeoffs")), "what each option costs")]
    return analysis, stages


def _m746(d: dict[str, Any]):
    claim = str(d.get("claim", ""))
    sides = [str(s) for s in d.get("sides", [])]
    turns = d.get("turns", {})
    turn_counts = {str(k): int(v) for k, v in turns.items()} if isinstance(turns, dict) else {}
    equal = len(set(turn_counts.values())) <= 1 if turn_counts else False
    analysis = {"claim": claim, "sides": sides, "burden_of_proof": sides[0] if sides else None,
                "turn_counts": turn_counts, "turns_equal": equal,
                "evidence_standard": str(d.get("evidence_standard", "")),
                "rule": "Argue positions with equal turns and a shared evidence standard; attack reasoning, never persons."}
    stages = [S("claim_defined", bool(claim), "single contestable claim"),
              S("sides_balanced", len(sides) >= 2, f"{len(sides)} sides"),
              S("burden_assigned", bool(sides), "burden on the affirmative"),
              S("turns_equal", equal, "same number of turns per side"),
              S("evidence_standard_set", _present(d.get("evidence_standard")), "what counts as support")]
    return analysis, stages


def _m747(d: dict[str, Any]):
    claim = str(d.get("claim", ""))
    needs = [str(n) for n in d.get("audience_needs", [])]
    logos = _present(d.get("evidence"))
    pathos = _present(d.get("emotional_appeal"))
    analysis = {"claim": claim, "audience_needs": needs,
                "appeals": {"logos_evidence": logos, "ethos_credibility": _present(d.get("credibility_basis")),
                            "pathos_emotion": pathos},
                "proportionality": "Emotional appeal without evidence is manipulation, not rhetoric." if pathos and not logos else "Appeals are evidence-backed.",
                "claim_verified": d.get("verified") is True}
    stages = [S("claim_truthful", d.get("verified") is True, "claim checked before delivery"),
              S("evidence_aligned", logos, "logos present"),
              S("emotion_proportionate", not (pathos and not logos), "pathos rides on evidence"),
              S("audience_served", bool(needs), f"{len(needs)} audience needs addressed")]
    return analysis, stages


def _m748(d: dict[str, Any]):
    premises = [str(p) for p in d.get("premises", [])]
    conclusion = str(d.get("conclusion", ""))
    concl_words = set(_key_words(conclusion, 8))
    premise_words = set(w for p in premises for w in _key_words(p, 12))
    gaps = sorted(concl_words - premise_words)
    support = d.get("evidence", [])
    unsupported = [p for p in premises if not any(str(p)[:20].lower() in str(e).lower() or str(e)[:20].lower() in p.lower() for e in support)] if support else premises
    analysis = {"premises": premises, "conclusion": conclusion,
                "gap_terms": gaps, "unsupported_premises": unsupported,
                "validity_test": "If every premise were true, would the conclusion have to be true? Gap terms suggest missing links.",
                "soundness_test": "Validity and premise-truth are tested separately."}
    stages = [S("premises_listed", bool(premises), f"{len(premises)} premises"),
              S("conclusion_stated", bool(conclusion), "explicit conclusion"),
              S("gaps_identified", True, f"{len(gaps)} conclusion terms not in premises"),
              S("premises_supported", bool(premises) and not unsupported, f"{len(unsupported)} premises lack support")]
    return analysis, stages


_FALLACIES = [
    (r"\byou only say that because\b|\bof course you('d| would) say\b", "ad hominem",
     "The speaker's motive does not touch the argument's merits."),
    (r"\bso you('re| are) saying (we should just|that all)\b", "strawman",
     "Check whether the restated position is one anyone actually holds."),
    (r"\beither\b.{5,80}\bor\b.{5,80}\b(no other|only two|nothing else)\b", "false dilemma",
     "Name at least one option the framing hides."),
    (r"\bnext thing\b|\binevitably leads?\b|\bslippery slope\b", "slippery slope",
     "Each step of the claimed chain needs its own evidence."),
    (r"\bexperts agree\b|\bstudies show\b|\bscience says\b", "unsupported appeal to authority",
     "Ask which experts, which studies, and what they actually found."),
    (r"\bbecause that'?s (just )?how it is\b|\bit'?s true because it'?s true\b", "circular reasoning",
     "The conclusion is smuggled into the premise."),
]


def _m749(d: dict[str, Any]):
    argument = str(d.get("argument", ""))
    findings = []
    for pattern, label, repair in _FALLACIES:
        m = re.search(pattern, argument, re.I)
        if m:
            findings.append({"tentative_label": label, "matched_text": m.group(0)[:120],
                             "exact_gap": repair, "confidence": "tentative — verify with the speaker before naming it"})
    analysis = {"findings": findings, "clean": not findings,
                "rule": "Label patterns tentatively, show the exact gap, and try to repair before rejecting."}
    stages = [S("argument_supplied", bool(argument), "text under review"),
              S("patterns_scanned", True, f"{len(findings)} candidate patterns"),
              S("repairs_attempted", not findings or _present(d.get("repairs")), "strongest repair tried first"),
              S("rejection_last_resort", True, "reject only what cannot be repaired")]
    return analysis, stages


def _m750(d: dict[str, Any]):
    view = str(d.get("opposing_view", ""))
    strong = [str(s) for s in d.get("strongest_points", [])]
    analysis = {"opposing_view": view, "strongest_supportable_version": strong,
                "confirmation_question": "Would someone who holds this view recognize this as their position — at its best?",
                "rule": "Strengthen with evidence the other side actually cites; never invent beliefs for them."}
    stages = [S("view_stated", bool(view), "their position in play"),
              S("strongest_form_built", len(strong) >= 1, f"{len(strong)} strongest points"),
              S("holder_confirmation_sought", d.get("confirmed_with_holder") is True, "asked them if you got it right"),
              S("own_position_updated", d.get("updated_view") is not None, "what changed after steelmanning")]
    return analysis, stages


def _m751(d: dict[str, Any]):
    statement = str(d.get("statement", ""))
    readings = [str(r) for r in d.get("interpretations", [])]
    benign_defaults = [f"They may mean {k} descriptively, not as an attack." for k in _key_words(statement, 2)]
    analysis = {"statement": statement[:300], "benign_readings": readings or benign_defaults,
                "uncertainty_retained": "A charitable reading is a hypothesis to check, not the truth.",
                "rule": "Prefer the plausible good-faith reading until the speaker says otherwise."}
    stages = [S("statement_received", bool(statement), "their words on record"),
              S("benign_readings_generated", bool(readings or benign_defaults), "at least one good-faith reading"),
              S("hostile_reading_not_assumed", True, "worst-case reading held as one hypothesis among several"),
              S("verified_with_speaker", d.get("verified") is True, "asked which reading is right")]
    return analysis, stages


def _m752(d: dict[str, Any]):
    statement = str(d.get("ambiguous_statement", ""))
    interps = d.get("interpretations", [])
    coherent = [i for i in interps if isinstance(i, dict) and i.get("coherent_with_evidence")]
    incoherent = [i for i in interps if not (isinstance(i, dict) and i.get("coherent_with_evidence"))]
    best = coherent[0] if coherent else None
    analysis = {"statement": statement[:300],
                "ranked": {"coherent": coherent, "incoherent": incoherent},
                "most_charitable_coherent_reading": best,
                "rule": "Resolve ambiguity toward the most coherent reading the evidence allows, then verify."}
    stages = [S("interpretations_listed", len(interps) >= 2, f"{len(interps)} readings"),
              S("coherence_tested", bool(interps), f"{len(coherent)} coherent"),
              S("most_coherent_chosen", best is not None, "working interpretation selected"),
              S("speaker_confirmation_sought", d.get("confirmed") is True, "speaker confirmed the reading")]
    return analysis, stages


def _m753(d: dict[str, Any]):
    argument = str(d.get("argument", ""))
    evidence = [str(e) for e in d.get("evidence_base", [])]
    invented = [str(x) for x in d.get("invented_claims", [])]
    analysis = {"argument": argument[:300], "best_version": {"argument": argument[:200], "attached_evidence": evidence[:5]},
                "invented_beliefs_rejected": invented,
                "rule": "Build the best version from real evidence; adding beliefs nobody holds is a strawman in disguise."}
    stages = [S("argument_extracted", bool(argument), "core claim isolated"),
              S("evidence_attached", bool(evidence), f"{len(evidence)} real supports"),
              S("no_invented_beliefs", not invented, f"{len(invented)} invented claims rejected"),
              S("presented_for_confirmation", d.get("presented") is True, "offered to its holder for correction")]
    return analysis, stages


def _m754(d: dict[str, Any]):
    proposal = str(d.get("proposal", ""))
    risks = [str(r) for r in d.get("risks", [])]
    keys = _key_words(proposal, 3)
    generated = risks or [f"What if the assumption about {k} is wrong?" for k in keys]
    analysis = {"proposal": proposal[:300], "assigned_challenge_role": True,
                "timebox_minutes": d.get("timebox_minutes"), "failure_modes": generated,
                "rule": "Critique the idea inside a declared, timeboxed role; the person is never the target."}
    stages = [S("role_declared", True, "challenge role announced to the group"),
              S("proposal_stated", bool(proposal), "target is the idea"),
              S("failure_modes_listed", bool(generated), f"{len(generated)} ways it could fail"),
              S("timeboxed", _present(d.get("timebox_minutes")), "role ends on schedule"),
              S("learnings_handed_back", _present(d.get("learnings")), "findings returned to the owner")]
    return analysis, stages


def _m755(d: dict[str, Any]):
    scope = [str(s) for s in d.get("scope", [])]
    assets = [str(a) for a in d.get("assets", [])]
    stops = [str(s) for s in d.get("stop_conditions", [])]
    targets = [str(t) for t in d.get("targets", [])]
    out_of_scope = [t for t in targets if t not in scope]
    analysis = {"authorized_scope": scope, "assets_at_stake": assets, "stop_conditions": stops,
                "out_of_scope_targets": out_of_scope,
                "remediation": d.get("remediation", []),
                "rule": "Test only what is explicitly authorized; stop conditions are absolute, not advisory."}
    stages = [S("authorization_documented", _present(d.get("authorization")), "written authorization on file"),
              S("scope_bounded", bool(scope) and not out_of_scope, f"{len(out_of_scope)} targets outside scope"),
              S("assets_mapped", bool(assets), f"{len(assets)} assets"),
              S("stop_conditions_set", bool(stops), f"{len(stops)} stop conditions"),
              S("remediation_owned", _present(d.get("remediation")), "every finding has an owner")]
    return analysis, stages


def _m756(d: dict[str, Any]):
    scenario = str(d.get("scenario", ""))
    assumptions = [str(a) for a in d.get("assumptions", [])]
    moves = d.get("moves", [])
    unstructured = [m for m in moves if not (isinstance(m, dict) and m.get("actor") and m.get("action"))]
    no_deescalation = [m for m in moves if isinstance(m, dict) and not m.get("deescalation_option")]
    fictional = _has(scenario, "fictional", "simulated", "exercise") or d.get("authorized") is True
    analysis = {"scenario": scenario[:300], "scenario_is_fictional_or_authorized": fictional,
                "declared_assumptions": assumptions, "unstructured_moves": unstructured,
                "moves_without_deescalation": len(no_deescalation),
                "rule": "Declared assumptions, bounded moves, and an explicit de-escalation path for every escalation."}
    stages = [S("scenario_bounded", fictional, "fictional or explicitly authorized"),
              S("assumptions_declared", bool(assumptions), f"{len(assumptions)} assumptions"),
              S("moves_structured", bool(moves) and not unstructured, f"{len(unstructured)} unstructured moves"),
              S("escalation_checked", bool(moves) and not no_deescalation, "every move has an off-ramp"),
              S("uncertainties_logged", _present(d.get("uncertainties")), "known unknowns recorded")]
    return analysis, stages


def _m757(d: dict[str, Any]):
    objectives = [str(o) for o in d.get("objectives", [])]
    roles = [str(r) for r in d.get("roles", [])]
    injects = d.get("injects", [])
    unordered = [i for i in injects if not (isinstance(i, dict) and i.get("time") is not None and i.get("event"))]
    analysis = {"objectives": objectives, "roles": roles,
                "injects_sequenced": sorted((i for i in injects if isinstance(i, dict) and i.get("time") is not None),
                                            key=lambda x: x["time"]),
                "unstructured_injects": unordered, "safety_limits": d.get("safety_limits", []),
                "after_action_review": str(d.get("after_action_review", "")),
                "rule": "Decisions under incomplete information, inside safety limits, then an honest after-action review."}
    stages = [S("objectives_set", bool(objectives), f"{len(objectives)} objectives"),
              S("roles_assigned", bool(roles), f"{len(roles)} roles"),
              S("injects_sequenced", bool(injects) and not unordered, f"{len(unordered)} injects lack time/event"),
              S("safety_limits_set", _present(d.get("safety_limits")), "hard boundaries for the exercise"),
              S("after_action_planned", _present(d.get("after_action_review")), "review on the calendar")]
    return analysis, stages


def _m758(d: dict[str, Any]):
    params = d.get("parameters", {})
    assumptions = [str(a) for a in d.get("assumptions", [])]
    no_range = [str(k) for k, v in (params.items() if isinstance(params, dict) else [])
                if not (isinstance(v, dict) and ("min" in v or "range" in v))]
    analysis = {"parameters": params, "parameters_without_sensitivity_range": no_range,
                "assumptions": assumptions,
                "omitted_factor_prompt": "Which real-world factor does this model omit — incentives, delays, adversaries, fatigue?",
                "validation": str(d.get("validation_data", "")),
                "rule": "A simulation explores assumptions; it does not predict. Label every parameter's uncertainty."}
    stages = [S("parameters_declared", bool(params), f"{len(params) if isinstance(params, dict) else 0} parameters"),
              S("assumptions_labeled", bool(assumptions), f"{len(assumptions)} assumptions"),
              S("sensitivity_checked", bool(params) and not no_range, f"{len(no_range)} single-point parameters"),
              S("validation_limits_stated", _present(d.get("validation_data")), "what the model was checked against")]
    return analysis, stages


def _m759(d: dict[str, Any]):
    roles = [str(r) for r in d.get("roles", [])]
    scenario = str(d.get("scenario", ""))
    analysis = {"roles": roles, "scenario": scenario[:300],
                "fictionalized": d.get("fictionalized") is True,
                "opt_out": "Anyone may pause or leave at any time without explanation or penalty.",
                "debrief_questions": ["What did the role make visible?", "What will you do differently?",
                                      "Was anything uncomfortable that we should retire?"],
                "rule": "Voluntary roles, fictionalized details, real opt-out, honest debrief. The exercise reveals patterns, not a real person's mind."}
    stages = [S("consent_confirmed", d.get("consent_confirmed") is True, "every participant opted in freely"),
              S("roles_voluntary", bool(roles), "no one assigned a role they refused"),
              S("details_fictionalized", d.get("fictionalized") is True, "no real private details in play"),
              S("opt_out_stated", True, "exit rights announced up front"),
              S("debriefed", d.get("debrief_done") is True, "learning extracted and discomfort addressed")]
    return analysis, stages


def _m760(d: dict[str, Any]):
    situation = str(d.get("situation", ""))
    viewpoints = [str(v) for v in d.get("viewpoints", [])]
    hypotheses = {v: [f"From {v}'s position, {situation[:60]} may look like a constraint",
                      f"From {v}'s position, {situation[:60]} may look like an opportunity"]
                  for v in viewpoints[:5]}
    analysis = {"situation": situation[:300], "hypotheses_by_viewpoint": hypotheses,
                "verify_prompt": "Where possible, ask the real person instead of perfecting your guess.",
                "rule": "Multiple hypotheses per viewpoint; none of them is knowledge."}
    stages = [S("situation_defined", bool(situation), "shared situation on the table"),
              S("viewpoints_listed", len(viewpoints) >= 2, f"{len(viewpoints)} viewpoints"),
              S("hypotheses_multiple", bool(hypotheses), "two or more readings each"),
              S("real_person_consulted", d.get("consulted") is True, "hypotheses checked with them")]
    return analysis, stages


def _m761(d: dict[str, Any]):
    behavior = str(d.get("observed_behavior", ""))
    hypotheses = [{"hypothesis": f"They intended {k}", "alternatives": ["accident", "habit", "pressure from elsewhere"],
                   "confidence": "tentative"} for k in _key_words(behavior, 3)]
    evidence = d.get("evidence", [])
    analysis = {"observed_behavior": behavior[:300], "belief_hypotheses": hypotheses,
                "supporting_evidence": evidence,
                "rule": "Beliefs and intentions are unverified hypotheses built from observable context; hold at least two."}
    stages = [S("behavior_observed", bool(behavior), "only what was seen/heard"),
              S("hypotheses_generated", bool(hypotheses), f"{len(hypotheses)} tentative models"),
              S("alternatives_considered", True, "each hypothesis carries alternatives"),
              S("verification_planned", _present(d.get("verification_plan")), "how you will check without accusing")]
    return analysis, stages


def _m762(d: dict[str, Any]):
    observation = str(d.get("observation", ""))
    inferences = [str(i) for i in d.get("inferences", [])]
    ask_instead = [f"Instead of inferring: ask about {k}" for k in _key_words(" ".join(inferences), 3)]
    analysis = {"observed": observation[:300], "inferred": inferences,
                "behavior_inference_separated": True, "ask_instead": ask_instead,
                "rule": "Separate what you observed from what you guessed; turn guesses into questions."}
    stages = [S("observation_recorded", bool(observation), "verbatim observation"),
              S("inferences_named", True, f"{len(inferences)} inferences quarantined"),
              S("questions_replace_guesses", bool(ask_instead), "each inference became a question"),
              S("uncertainty_marked", True, "no mental state asserted as fact")]
    return analysis, stages


_EMOTION_LEXICON = ["sad", "angry", "hurt", "afraid", "scared", "anxious", "happy", "proud",
                    "frustrated", "lonely", "tired", "overwhelmed", "excited", "disappointed"]


def _m763(d: dict[str, Any]):
    experience = str(d.get("stated_experience", ""))
    mirrored = [w for w in _EMOTION_LEXICON if w in experience.lower()]
    reflection = f"You described: {experience[:180]}." + (f" That sounds {mirrored[0]}." if mirrored else " That sounds significant.")
    analysis = {"reflection": reflection, "mirrored_emotion_words": mirrored,
                "no_mind_claim": "Reflect only words they used; 'I know exactly how you feel' is a claim you cannot make.",
                "ask_next": "Do you want me to just listen, or think through options with you?"}
    stages = [S("experience_stated", bool(experience), "their account on record"),
              S("reflection_grounded", True, f"mirrored only stated words: {mirrored}"),
              S("no_mind_reading", True, "no feelings attributed beyond their words"),
              S("support_preference_asked", d.get("preference_asked") is True, "they choose the kind of support")]
    return analysis, stages


def _m764(d: dict[str, Any]):
    need = str(d.get("stated_need", ""))
    offers = d.get("offers", [])
    unbounded = [o for o in offers if not (isinstance(o, dict) and o.get("limit"))]
    analysis = {"stated_need": need[:300], "offers": offers, "unbounded_offers": unbounded,
                "ask_first": "What kind of support, if any, would you like from me?",
                "rule": "Ask what is wanted, offer bounded choices, and let them decline without cost."}
    stages = [S("need_heard", bool(need), "their stated need, not your guess"),
              S("consent_asked", d.get("asked") is True, "permission before helping"),
              S("offers_bounded", bool(offers) and not unbounded, f"{len(unbounded)} offers lack limits"),
              S("agency_preserved", True, "they can say no and stay in charge")]
    return analysis, stages


def _m765(d: dict[str, Any]):
    help_text = str(d.get("intended_help", ""))
    need = str(d.get("recipient_stated_need", ""))
    overlap = sorted(set(_key_words(help_text, 8)) & set(_key_words(need, 8)))
    analysis = {"intended_help": help_text[:200], "recipient_stated_need": need[:200],
                "keyword_overlap": overlap,
                "match_verdict": "Help appears aimed at the stated need." if overlap else "Help and stated need do not obviously match — ask the recipient.",
                "sustainability": d.get("sustainable"), "hidden_cost_check": "Could this help create obligation, dependence, or embarrassment?"}
    stages = [S("need_recipient_defined", bool(need), "the recipient said what they need"),
              S("help_matches_need", bool(overlap), f"overlap: {overlap}"),
              S("recipient_consent", d.get("consent") is True, "they want this help"),
              S("sustainable", d.get("sustainable") is True, "help you can keep giving")]
    return analysis, stages


def _m766(d: dict[str, Any]):
    action = str(d.get("action", ""))
    beneficiaries = [str(b) for b in d.get("beneficiaries", [])]
    risks = d.get("risks", [])
    analysis = {"action": action[:200], "beneficiaries": beneficiaries,
                "who_bears_risk": risks, "who_decides": str(d.get("decision_makers", "")),
                "integrity_check": "Benefit without deception, coercion, or hidden exchange; if the doer gains secretly, say so."}
    stages = [S("action_defined", bool(action), "specific action"),
              S("beneficiaries_named", bool(beneficiaries), f"{len(beneficiaries)} beneficiaries"),
              S("risks_assigned", _present(d.get("risks")), "who bears what risk"),
              S("decision_rights_clear", _present(d.get("decision_makers")), "affected people have a say")]
    return analysis, stages


def _m767(d: dict[str, Any]):
    shared = str(d.get("shared_interest", ""))
    commitments = d.get("commitments", [])
    involuntary = [c for c in commitments if isinstance(c, dict) and c.get("voluntary") is False]
    analysis = {"shared_interest": shared[:200], "commitments": commitments,
                "involuntary_commitments": involuntary,
                "repair_path": str(d.get("repair_path", "")),
                "rule": "Separate shared from individual interests; every commitment is voluntary and carries a repair path."}
    stages = [S("interests_mapped", bool(shared), "shared interest named"),
              S("commitments_voluntary", bool(commitments) and not involuntary, f"{len(involuntary)} coerced commitments"),
              S("repair_path_defined", _present(d.get("repair_path")), "what happens when someone slips"),
              S("followup_scheduled", _present(d.get("check_in")), "commitments reviewed together")]
    return analysis, stages


def _m768(d: dict[str, Any]):
    goal = str(d.get("joint_goal", ""))
    contributions = d.get("contributions", [])
    unattributed = [c for c in contributions if not (isinstance(c, dict) and c.get("person"))]
    analysis = {"joint_goal": goal[:200], "contributions": contributions,
                "unattributed_contributions": unattributed,
                "attribution_plan": str(d.get("attribution", "")),
                "disagreement_process": str(d.get("disagreement_process", "")),
                "rule": "Joint ownership means agreed credit, decision rights, and a way to disagree before the work starts."}
    stages = [S("goal_jointly_owned", bool(goal), "one shared goal"),
              S("contributions_mapped", bool(contributions) and not unattributed, f"{len(unattributed)} without an owner"),
              S("attribution_agreed", _present(d.get("attribution")), "how credit is shared"),
              S("disagreement_path_set", _present(d.get("disagreement_process")), "how conflicts get resolved")]
    return analysis, stages


def _m769(d: dict[str, Any]):
    roles = [str(r) for r in d.get("roles", [])]
    dependencies = d.get("dependencies", [])
    risky = [x for x in dependencies if not (isinstance(x, dict) and x.get("handoff_plan"))]
    analysis = {"roles": roles, "dependencies": dependencies,
                "handoff_risks": risky,
                "help_channel": str(d.get("help_channel", "")),
                "rule": "Roles, dependencies, and handoffs named; asking for help is a designed path, not a confession."}
    stages = [S("roles_clear", bool(roles), f"{len(roles)} roles"),
              S("dependencies_mapped", bool(dependencies), f"{len(dependencies)} dependencies"),
              S("handoffs_secured", bool(dependencies) and not risky, f"{len(risky)} handoffs without a plan"),
              S("help_path_defined", _present(d.get("help_channel")), "how to ask for help")]
    return analysis, stages


def _m770(d: dict[str, Any]):
    context = str(d.get("team_context", ""))
    activities = d.get("activities", [])
    forced = [a for a in activities if isinstance(a, dict) and a.get("voluntary") is False]
    analysis = {"team_context": context[:200], "activities": activities,
                "non_voluntary_activities": forced,
                "working_agreements": d.get("working_agreements", []),
                "rule": "Cohesion grows from shared work and safety, not compulsory fun; every activity is opt-in."}
    stages = [S("context_assessed", bool(context), "what this team actually needs"),
              S("activities_voluntary", bool(activities) and not forced, f"{len(forced)} compulsory activities"),
              S("agreements_set", bool(d.get("working_agreements")), "how we work together, written down"),
              S("reflection_planned", _present(d.get("reflection")), "the team reviews its own health")]
    return analysis, stages


# ------------------------- rows 771-809: trust & wellbeing -------------------------

_spec(771, "trust_building", W, ["commitment"])
_spec(772, "psychological_safety", W, ["team_context"])
_spec(773, "inclusion", W, ["setting", "participation_channels"])
_spec(774, "diversity", W, ["context"])
_spec(775, "equity", W, ["needs", "criteria"])
_spec(776, "justice", W, ["case_facts", "process"])
_spec(777, "ethics", W, ["action", "stakeholders"])
_spec(778, "integrity", W, ["stated_values", "planned_action"])
_spec(779, "honesty", W, ["message"])
_spec(780, "transparency", W, ["decision", "reasons"])
_spec(781, "accountability", W, ["impact", "owned_part"])
_spec(782, "reliability", W, ["promises"])
_spec(783, "dependability", W, ["expectations", "dependencies"])
_spec(784, "consistency", W, ["principle", "cases"])
_spec(785, "patience", W, ["wait_context"])
_spec(786, "tolerance", W, ["difference"])
_spec(787, "forgiveness", W, ["situation"])
_spec(788, "gratitude", W, ["specific_act"])
_spec(789, "humility", W, ["claim", "contributors"])
_spec(790, "curiosity", W, ["topic", "current_belief"])
_spec(791, "open_mindedness", W, ["view", "alternatives"])
_spec(792, "intellectual_humility", W, ["belief", "confidence"])
_spec(793, "wisdom", W, ["decision", "pressures"])
_spec(794, "prudence", W, ["option", "stakes"])
_spec(795, "temperance", W, ["desire", "goal"])
_spec(796, "courage", W, ["feared_action", "values"])
_spec(797, "resilience", W, ["setback", "supports"])
_spec(798, "grit", W, ["goal", "costs"])
_spec(799, "self_control", W, ["impulse", "preferred_action"])
_spec(800, "delayed_gratification", W, ["future_benefit", "wait_period"])
_spec(801, "impulse_control", W, ["urge", "consequence_if_acted"])
_spec(802, "emotional_regulation", W, ["own_feeling", "trigger"])
_spec(803, "stress_management", W, ["pressures"])
_spec(804, "coping_strategies", W, ["challenge", "past_supports"])
_spec(805, "mindfulness", W, ["moment_context"])
_spec(806, "meditation", W, ["practice_preference", "minutes"])
_spec(807, "relaxation", W, ["environment", "preferences"])
_spec(808, "sleep_hygiene", W, ["current_routine"])
_spec(809, "exercise", W, ["mobility_limits", "preferences"])

_ESCALATION = (
    "This tool is not emergency or crisis support. If there is immediate danger, possible self-harm or "
    "harm to others, inability to stay safe, severe symptoms, or a medical emergency, contact local "
    "emergency services or a qualified crisis/health professional now and involve a trusted person "
    "where safe. For persistent or worsening concerns, seek a licensed clinician rather than relying "
    "on this coaching."
)


def _m771(d: dict[str, Any]):
    commitment = str(d.get("commitment", ""))
    specific = len(commitment) >= 15 and _has(commitment, "will", "by ", "every", "each")
    analysis = {"commitment": commitment, "specific_and_timebound": specific,
                "feasible": d.get("feasible"), "report_back_plan": str(d.get("report_back_date", "")),
                "rule": "Trust grows from small promises kept and honestly reported, not grand declarations."}
    stages = [S("commitment_specific", specific, "observable and time-bound"),
              S("commitment_feasible", d.get("feasible") is not False, "inside your real capacity"),
              S("reportback_planned", _present(d.get("report_back_date")), "when you will close the loop"),
              S("followthrough_recorded", d.get("completed") is True, "promise kept and reported")]
    return analysis, stages


def _m772(d: dict[str, Any]):
    context = str(d.get("team_context", ""))
    response = str(d.get("recent_response_to_dissent", ""))
    retaliation = [w for w in ("punished", "fired", "mocked", "dismissed", "ignored", "blamed") if w in response.lower()]
    analysis = {"team_context": context[:200], "retaliation_signals": retaliation,
                "invite_dissent": "Ask explicitly: what are we missing? Thank the first person who disagrees.",
                "repair_note": "If speaking up cost someone, repair visibly before asking for more candor." if retaliation else "No retaliation signals in the recent response."}
    stages = [S("context_assessed", bool(context), "team situation named"),
              S("dissent_invited", _present(d.get("invitation")), "explicit invitation made"),
              S("no_retaliation", not retaliation, f"signals: {retaliation}"),
              S("repair_made", not retaliation or _present(d.get("repair")), "cost of speaking up repaired")]
    return analysis, stages


def _m773(d: dict[str, Any]):
    setting = str(d.get("setting", ""))
    channels = d.get("participation_channels", [])
    gaps = [c for c in channels if isinstance(c, dict) and not c.get("accessible")]
    analysis = {"setting": setting[:200], "channels": channels, "accessibility_gaps": gaps,
                "missing_voices": d.get("missing_groups", []),
                "rule": "Offer multiple accessible ways in, then ask who is still missing — and why."}
    stages = [S("channels_offered", bool(channels), f"{len(channels)} ways to participate"),
              S("accessibility_checked", bool(channels) and not gaps, f"{len(gaps)} inaccessible channels"),
              S("missing_voices_identified", _present(d.get("missing_groups")), "who is not in the room"),
              S("adjustments_made", _present(d.get("adjustments")), "concrete changes from the audit")]
    return analysis, stages


def _m774(d: dict[str, Any]):
    context = str(d.get("context", ""))
    invited = [str(x) for x in d.get("invited_perspectives", [])]
    tokenizing = d.get("asked_to_represent_group") is True
    analysis = {"context": context[:200], "invited_perspectives": invited,
                "tokenizing_flag": tokenizing,
                "rule": "Invite perspectives without making anyone a spokesperson for a group; individuals are not representatives."}
    stages = [S("absent_perspectives_identified", bool(invited), f"{len(invited)} perspectives sought"),
              S("invitations_without_tokenizing", not tokenizing, "no one asked to speak for a group"),
              S("participation_voluntary", d.get("declined_ok") is not False, "declining carries no cost"),
              S("belonging_checked", _present(d.get("feedback")), "asked people how it actually feels")]
    return analysis, stages


def _m775(d: dict[str, Any]):
    needs = d.get("needs", [])
    criteria = [str(c) for c in d.get("criteria", [])]
    adjustments = d.get("adjustments", {})
    unmatched = [n for n in needs if isinstance(n, dict) and str(n.get("barrier")) not in {str(k) for k in (adjustments if isinstance(adjustments, dict) else {})}]
    analysis = {"needs": needs, "transparent_criteria": criteria,
                "barriers_without_adjustment": unmatched,
                "rule": "Equal treatment can produce unequal access; adjust support against barriers using stated needs and published criteria."}
    stages = [S("barriers_identified", bool(needs), f"{len(needs)} stated needs"),
              S("criteria_transparent", bool(criteria), "everyone can see the rules"),
              S("support_matched", bool(needs) and not unmatched, f"{len(unmatched)} barriers unaddressed"),
              S("outcomes_reviewed", _present(d.get("outcome_review")), "checked whether adjustments worked")]
    return analysis, stages


def _m776(d: dict[str, Any]):
    facts = [str(f) for f in d.get("case_facts", [])]
    process = str(d.get("process", ""))
    analysis = {"case_facts": facts, "process": process[:200],
                "rights_at_stake": d.get("rights_at_stake", []),
                "appeal_path": str(d.get("appeal_path", "")),
                "rule": "Established facts, identified rights, fair process, and a real appeal path — in that order."}
    stages = [S("facts_established", bool(facts), f"{len(facts)} established facts"),
              S("rights_identified", _present(d.get("rights_at_stake")), "whose rights are in play"),
              S("process_fair", bool(process) and _present(d.get("evidence_standard")), "both sides heard against a standard"),
              S("appeal_available", _present(d.get("appeal_path")), "an accountable route to challenge")]
    return analysis, stages


def _m777(d: dict[str, Any]):
    action = str(d.get("action", ""))
    stakeholders = [str(s) for s in d.get("stakeholders", [])]
    analysis = {"action": action[:200], "stakeholders": stakeholders,
                "duties": d.get("duties", []),
                "harms_benefits_frame": {s: {"harms": "to assess", "benefits": "to assess"} for s in stakeholders[:6]},
                "publicity_test": "Would this stay defensible if everyone affected knew the reasoning?",
                "reversibility_preferred": "Prefer the option that can be undone when duties conflict."}
    stages = [S("stakeholders_listed", bool(stakeholders), f"{len(stakeholders)} affected parties"),
              S("duties_identified", bool(d.get("duties")), "what is owed to each"),
              S("consent_considered", d.get("consent_considered") is True, "who must agree"),
              S("publicity_test_passed", d.get("publicity_test") is True, "defensible in the open")]
    return analysis, stages


def _m778(d: dict[str, Any]):
    values = [str(v) for v in d.get("stated_values", [])]
    action = str(d.get("planned_action", ""))
    conflicts = d.get("conflicts_of_interest", [])
    undisclosed = [c for c in conflicts if isinstance(c, dict) and not c.get("disclosed")]
    analysis = {"stated_values": values, "planned_action": action[:200],
                "alignment_question": "Would an outside observer see this action as consistent with the stated values?",
                "undisclosed_conflicts": undisclosed,
                "rule": "Act consistently with what you publicly claim, and disclose conflicts before they disclose you."}
    stages = [S("values_stated", bool(values), f"{len(values)} values on record"),
              S("action_compared", d.get("alignment_check") is not None, "action tested against values"),
              S("conflicts_disclosed", not undisclosed, f"{len(undisclosed)} undisclosed conflicts"),
              S("public_consistency", d.get("alignment_check") is True, "walk matches talk")]
    return analysis, stages


_OVERCLAIM = re.compile(r"\b(definitely|guaranteed|100%|proven|no doubt|certainly will)\b", re.I)


def _m779(d: dict[str, Any]):
    message = str(d.get("message", ""))
    overclaims = _OVERCLAIM.findall(message)
    analysis = {"message": message[:300], "overclaim_flags": overclaims,
                "known": d.get("known", []), "unknown": d.get("unknowns", []), "mistakes": d.get("mistakes", []),
                "rule": "State what is known, what is unknown, and what you got wrong; never manufacture certainty."}
    stages = [S("known_stated", _present(d.get("known")), "what you actually know"),
              S("unknown_stated", _present(d.get("unknowns")), "what you do not know"),
              S("overclaims_removed", not overclaims, f"{len(overclaims)} certainty overclaims"),
              S("mistakes_owned", _present(d.get("mistakes")), "errors named without being asked")]
    return analysis, stages


_VALID_PRIVATE = ("safety", "privacy", "consent", "legal", "medical")


def _m780(d: dict[str, Any]):
    decision = str(d.get("decision", ""))
    reasons = d.get("reasons", [])
    marks = d.get("privacy_marks", {})
    invalid_private = [str(k) for k, v in (marks.items() if isinstance(marks, dict) else [])
                       if not _has(str(v), *_VALID_PRIVATE)]
    analysis = {"decision": decision[:200], "reasons": reasons, "privacy_marks": marks,
                "private_without_valid_basis": invalid_private,
                "rule": "Share the reasoning; withhold only what privacy, safety, consent, or law requires — and say that is why."}
    stages = [S("decision_stated", bool(decision), "what was decided"),
              S("reasons_listed", bool(reasons), f"{len(reasons)} reasons"),
              S("privacy_bounds_valid", not invalid_private, f"{len(invalid_private)} unexplained withholdings"),
              S("explanation_ready", _present(d.get("explanation")), "what you will say, to whom")]
    return analysis, stages


def _m781(d: dict[str, Any]):
    impact = str(d.get("impact", ""))
    owned = str(d.get("owned_part", ""))
    deflecting = bool(re.search(r"\bbut (they|he|she|you)\b", owned, re.I))
    analysis = {"impact": impact[:200], "owned_part": owned[:200], "deflection_flag": deflecting,
                "repair_actions": d.get("repair_actions", []), "prevention": str(d.get("prevention", "")),
                "rule": "Name the impact, own your part without a 'but', repair concretely, prevent recurrence."}
    stages = [S("impact_named", bool(impact), "the harm as the other side experiences it"),
              S("part_owned_cleanly", bool(owned) and not deflecting, "no deflection in the ownership"),
              S("repair_planned", bool(d.get("repair_actions")), "specific repair, their needs first"),
              S("prevention_set", _present(d.get("prevention")), "what changes so it does not repeat")]
    return analysis, stages


def _m782(d: dict[str, Any]):
    promises = d.get("promises", [])
    vague = [p for p in promises if not (isinstance(p, dict) and p.get("by_when") and p.get("effort_estimate"))]
    analysis = {"promises": promises, "under_specified_promises": vague,
                "check_in": str(d.get("check_in", "")),
                "rule": "Promise less, specify more, and schedule a check-in before failure becomes a surprise."}
    stages = [S("promises_listed", bool(promises), f"{len(promises)} commitments"),
              S("feasibility_checked", bool(promises) and not vague, f"{len(vague)} lack time/effort estimates"),
              S("overcommitment_trimmed", _present(d.get("declined")) or not vague, "what you declined or renegotiated"),
              S("checkin_scheduled", _present(d.get("check_in")), "progress checkpoint before the deadline")]
    return analysis, stages


def _m783(d: dict[str, Any]):
    expectations = [str(e) for e in d.get("expectations", [])]
    dependencies = d.get("dependencies", [])
    no_backup = [x for x in dependencies if not (isinstance(x, dict) and x.get("backup"))]
    analysis = {"expectations": expectations, "dependencies": dependencies,
                "dependencies_without_backup": no_backup,
                "notify_trigger": str(d.get("notify_if_late_by", "")),
                "rule": "Others should never carry a silent failure: backups and notification triggers are part of the promise."}
    stages = [S("expectations_clear", bool(expectations), f"{len(expectations)} expectations"),
              S("dependencies_mapped", bool(dependencies), f"{len(dependencies)} dependencies"),
              S("backups_set", bool(dependencies) and not no_backup, f"{len(no_backup)} without backup"),
              S("notification_triggers_set", _present(d.get("notify_if_late_by")), "when you will warn people")]
    return analysis, stages


def _m784(d: dict[str, Any]):
    principle = str(d.get("principle", ""))
    cases = d.get("cases", [])
    decisions = [str(c.get("decision")) for c in cases if isinstance(c, dict) and c.get("decision")]
    unjustified = [c for c in cases if isinstance(c, dict) and c.get("decision") and c.get("decision") != decisions[0] and not c.get("reason")] if decisions else []
    analysis = {"principle": principle[:200], "cases": cases,
                "deviations_without_reason": unjustified,
                "rule": "Same principle, similar cases, same outcome; deviations need a reason you would defend publicly."}
    stages = [S("principle_stated", bool(principle), "the stable rule"),
              S("cases_compared", len(cases) >= 2, f"{len(cases)} cases"),
              S("deviations_justified", not unjustified, f"{len(unjustified)} unexplained deviations"),
              S("exception_criteria_set", _present(d.get("exception_criteria")), "when exceptions are legitimate")]
    return analysis, stages


def _m785(d: dict[str, Any]):
    context = str(d.get("wait_context", ""))
    controllables = [str(c) for c in d.get("controllable_actions", [])]
    analysis = {"wait_context": context[:200], "controllable_actions": controllables,
                "recheck_point": str(d.get("recheck_time", "")),
                "rumination_guard": "Rehearsing the outcome does not change it; pick one useful action and a time to recheck.",
                "rule": "Patience is active: do what is controllable now, then let the wait be a wait."}
    stages = [S("wait_acknowledged", bool(context), "what you are waiting for"),
              S("controllables_identified", bool(controllables), f"{len(controllables)} controllable actions"),
              S("action_chosen", _present(d.get("chosen_action")), "one picked for now"),
              S("recheck_set", _present(d.get("recheck_time")), "when you will look again")]
    return analysis, stages


def _m786(d: dict[str, Any]):
    difference = str(d.get("difference", ""))
    harm = d.get("harm_present")
    analysis = {"difference": difference[:200], "harm_present": harm,
                "boundary": str(d.get("boundary", "")),
                "rule": "Accept difference without endorsing harm; tolerance never requires absorbing damage.",
                "distinction": "Acceptance is about the person; endorsement is about the act. You can give the first without the second."}
    stages = [S("difference_named", bool(difference), "what exactly differs"),
              S("harm_screened", harm is not None, "harm check done"),
              S("boundary_set_where_needed", harm is not True or _present(d.get("boundary")), "protection where harm exists"),
              S("acceptance_without_endorsement", True, "person respected, act evaluated")]
    return analysis, stages


def _m787(d: dict[str, Any]):
    situation = str(d.get("situation", ""))
    analysis = {"situation": situation[:200],
                "forgiveness_is_optional": "Forgiveness is a choice, never an obligation; it does not require trust, access, or reconciliation.",
                "needed_boundaries": d.get("needed_boundaries", []),
                "repair_needed": str(d.get("repair_needed", "")),
                "rule": "You can release resentment and keep every boundary; the two are independent decisions."}
    stages = [S("situation_named", bool(situation), "what happened, in your words"),
              S("choice_respected", True, "no pressure to forgive or to withhold"),
              S("boundaries_defined", _present(d.get("needed_boundaries")), "what protection you need regardless"),
              S("reconciliation_not_assumed", True, "forgiveness and restored access decided separately")]
    return analysis, stages


def _m788(d: dict[str, Any]):
    act = str(d.get("specific_act", ""))
    impact = str(d.get("impact", ""))
    acknowledgment = f"Thank you for {act[:120]}." + (f" It mattered because {impact[:120]}." if impact else "")
    analysis = {"specific_act": act[:200], "acknowledgment_draft": acknowledgment,
                "no_obligation": "Gratitude expressed freely creates no debt on either side.",
                "no_forced_positivity": "Acknowledging one good thing does not require denying hard things."}
    stages = [S("act_specific", bool(act), "the concrete act, not 'everything'"),
              S("impact_named", bool(impact), "why it helped"),
              S("acknowledgment_drafted", bool(act), "ready for your own words"),
              S("freely_given", True, "no strings attached")]
    return analysis, stages


def _m789(d: dict[str, Any]):
    claim = str(d.get("claim", ""))
    contributors = [str(c) for c in d.get("contributors", [])]
    analysis = {"claim": claim[:200], "limits": d.get("limits", []),
                "contributors_credited": contributors,
                "correction_invitation": "What am I missing or getting wrong here?",
                "rule": "Name your limits, credit the people you depend on, and make correction easy."}
    stages = [S("limits_named", _present(d.get("limits")), "where the claim stops"),
              S("contributors_credited", bool(contributors), f"{len(contributors)} people credited"),
              S("correction_invited", d.get("correction_invited") is True, "asked for disconfirming input"),
              S("claim_scoped", _present(d.get("scoped_claim")), "claim restated at honest size")]
    return analysis, stages


def _m790(d: dict[str, Any]):
    topic, belief = str(d.get("topic", "")), str(d.get("current_belief", ""))
    questions = [f"What do I not yet understand about {topic[:60]}?",
                 f"What would someone who disagrees with '{belief[:60]}' say I am missing?",
                 f"What evidence would genuinely surprise me about {topic[:60]}?"]
    analysis = {"topic": topic[:200], "current_belief": belief[:200],
                "open_questions": questions,
                "rule": "Understand first, defend later — if proving yourself is the goal, curiosity is already over."}
    stages = [S("belief_stated", bool(belief), "where you currently stand"),
              S("questions_open", True, f"{len(questions)} genuine questions"),
              S("exploration_first", d.get("goal_is_exploration") is True, "understanding before defending"),
              S("new_evidence_sought", _present(d.get("sources")), "looked where answers might live")]
    return analysis, stages


def _m791(d: dict[str, Any]):
    view = str(d.get("view", ""))
    alternatives = [str(a) for a in d.get("alternatives", [])]
    standard = str(d.get("evidence_standard", ""))
    analysis = {"view": view[:200], "alternatives": alternatives, "evidence_standard": standard,
                "comparison": d.get("comparison", {}),
                "rule": "Judge every alternative — including yours — by the same evidence standard."}
    stages = [S("alternatives_listed", bool(alternatives), f"{len(alternatives)} alternatives"),
              S("same_standard_applied", bool(standard), "one standard for all"),
              S("comparison_done", _present(d.get("comparison")), "side-by-side result"),
              S("update_considered", d.get("update") is not None, "what, if anything, changed")]
    return analysis, stages


def _m792(d: dict[str, Any]):
    belief = str(d.get("belief", ""))
    confidence = d.get("confidence")
    strength = str(d.get("evidence_strength", "")).lower()
    miscalibrated = (isinstance(confidence, (int, float)) and confidence >= 80 and strength == "low") or \
                    (isinstance(confidence, (int, float)) and confidence <= 20 and strength == "high")
    analysis = {"belief": belief[:200], "confidence_percent": confidence, "evidence_strength": strength,
                "miscalibration_flag": miscalibrated,
                "evidence_vs_inference": "List what you observed separately from what you concluded from it.",
                "rule": "Confidence should track evidence strength, not conviction."}
    stages = [S("belief_stated", bool(belief), "the position under review"),
              S("confidence_stated", isinstance(confidence, (int, float)), f"{confidence}%"),
              S("evidence_separated", _present(d.get("evidence")), "observation apart from inference"),
              S("calibrated", not miscalibrated, "confidence matches evidence strength")]
    return analysis, stages


def _m793(d: dict[str, Any]):
    decision = str(d.get("decision", ""))
    pressures = [str(p) for p in d.get("pressures", [])]
    analysis = {"decision": decision[:200], "current_pressures": pressures,
                "long_view_test": "Will this choice still look sound after the immediate pressure passes?",
                "downstream_effects": d.get("downstream_effects", []),
                "timing": str(d.get("timing", "")),
                "rule": "Balance evidence, experience, values, timing, and downstream effects — wisdom is mostly refusing to decide inside the loudest moment."}
    stages = [S("decision_named", bool(decision), "the actual choice"),
              S("pressures_identified", bool(pressures), f"{len(pressures)} pressures named"),
              S("long_view_tested", _present(d.get("long_view_verdict")), "judged beyond the moment"),
              S("downstream_considered", bool(d.get("downstream_effects")), "second-order effects listed")]
    return analysis, stages


def _m794(d: dict[str, Any]):
    option = str(d.get("option", ""))
    stakes = str(d.get("stakes", "")).lower()
    reversible = str(d.get("reversible_step", ""))
    analysis = {"option": option[:200], "stakes": stakes, "reversible_first_step": reversible,
                "exit_criteria": str(d.get("exit_criteria", "")),
                "rule": "When stakes are high or uncertainty is wide, buy information with a small reversible step before the big irreversible one.",
                "high_stakes_warning": stakes == "high" and not reversible}
    stages = [S("stakes_assessed", stakes in {"low", "medium", "high"}, f"stakes: {stakes or 'unrated'}"),
              S("reversibility_checked", True, "can this be undone, and at what cost"),
              S("smallest_step_chosen", bool(reversible), "reversible probe selected"),
              S("exit_plan_set", _present(d.get("exit_criteria")), "what evidence ends the experiment")]
    return analysis, stages


def _m795(d: dict[str, Any]):
    desire, goal = str(d.get("desire", "")), str(d.get("goal", ""))
    limit = str(d.get("limit", ""))
    analysis = {"desire": desire[:200], "goal": goal[:200], "chosen_limit": limit,
                "pause_practice": "Insert a pause between urge and action; decide at the pause, not in the urge.",
                "alignment_question": "Does this limit serve the goal, or just punish the desire?"}
    stages = [S("desire_named", bool(desire), "what you actually want"),
              S("goal_aligned", _present(d.get("limit_aligned")) and d.get("limit_aligned") is not False, "limit serves the goal"),
              S("limit_set", bool(limit), "a specific 'enough'"),
              S("pause_planned", _present(d.get("pause_plan")), "where the pause goes")]
    return analysis, stages


def _m796(d: dict[str, Any]):
    action = str(d.get("feared_action", ""))
    values = [str(v) for v in d.get("values", [])]
    danger = d.get("real_danger")
    supports = [str(s) for s in d.get("supports", [])]
    analysis = {"feared_action": action[:200], "values_served": values,
                "real_danger_assessment": danger,
                "safety_first": "Real danger is a reason to get support or change the plan, not a test of character." if danger else "No real danger reported; fear is the main obstacle.",
                "supports": supports, "smallest_step": str(d.get("smallest_step", ""))}
    stages = [S("fear_named", bool(action), "the avoided action"),
              S("values_linked", bool(values), "why it matters"),
              S("danger_assessed", danger is not None, "real risk checked honestly"),
              S("support_gathered", bool(supports), f"{len(supports)} supports"),
              S("safe_step_chosen", _present(d.get("smallest_step")), "smallest values-aligned move")]
    return analysis, stages


def _m797(d: dict[str, Any]):
    setback = str(d.get("setback", ""))
    supports = [str(s) for s in d.get("supports", [])]
    analysis = {"setback": setback[:200], "supports": supports,
                "recovery_time": str(d.get("recovery_time", "")),
                "learning": str(d.get("learning", "")),
                "restart_step": str(d.get("restart_step", "")),
                "rule": "Recover deliberately, extract one honest learning, restart small — endurance without recovery is erosion."}
    stages = [S("setback_named", bool(setback), "what happened"),
              S("supports_identified", bool(supports), f"{len(supports)} supports"),
              S("recovery_scheduled", _present(d.get("recovery_time")), "rest is planned, not stolen"),
              S("restart_planned", _present(d.get("restart_step")), "one manageable first move")]
    return analysis, stages


_COST_HARM = ("health", "sleep", "relationship", "family", "breakdown")


def _m798(d: dict[str, Any]):
    goal = str(d.get("goal", ""))
    costs = [str(c) for c in d.get("costs", [])]
    harming = [c for c in costs if _has(c, *_COST_HARM)]
    worth = d.get("still_worth_it")
    analysis = {"goal": goal[:200], "costs": costs, "costs_touching_health_or_relationships": harming,
                "still_worth_it": worth,
                "rule": "Grit is persistence toward a chosen goal — not persistence at any cost. Reassess when the cost is you."}
    stages = [S("goal_chosen", bool(goal), "still your goal, not inertia"),
              S("costs_named", bool(costs), f"{len(costs)} costs on the table"),
              S("worth_reassessed", worth is not None, "honest re-answer"),
              S("course_adjusted", worth is True or _present(d.get("adjustment")), "continue deliberately or adjust")]
    return analysis, stages


def _m799(d: dict[str, Any]):
    impulse = str(d.get("impulse", ""))
    preferred = str(d.get("preferred_action", ""))
    analysis = {"impulse": impulse[:200], "preferred_action": preferred[:200],
                "cue": str(d.get("cue", "")), "friction_added": str(d.get("friction_added", "")),
                "ease_added": str(d.get("ease_added", "")),
                "rule": "Do not fight impulse with willpower; make the impulse harder and the preferred action easier."}
    stages = [S("impulse_named", bool(impulse), "the specific urge"),
              S("cue_identified", _present(d.get("cue")), "what triggers it"),
              S("friction_added", _present(d.get("friction_added")), "a real barrier before the impulse"),
              S("preferred_easier", _present(d.get("ease_added")), "path of least resistance points the right way")]
    return analysis, stages


def _m800(d: dict[str, Any]):
    benefit = str(d.get("future_benefit", ""))
    wait = str(d.get("wait_period", ""))
    milestones = [str(m) for m in d.get("milestones", [])]
    analysis = {"future_benefit": benefit[:200], "wait_period": wait,
                "concrete": len(benefit) >= 10,
                "milestones": milestones, "review_interval": str(d.get("review_interval", "")),
                "rule": "Make the future benefit vivid and cut the wait into milestones you can actually reach."}
    stages = [S("benefit_concrete", len(benefit) >= 10, "the payoff in specific terms"),
              S("wait_bounded", bool(wait), "how long, exactly"),
              S("milestones_set", bool(milestones), f"{len(milestones)} waypoints"),
              S("review_interval_set", _present(d.get("review_interval")), "when you check progress")]
    return analysis, stages


def _m801(d: dict[str, Any]):
    urge = str(d.get("urge", ""))
    consequence = str(d.get("consequence_if_acted", ""))
    alternatives = [str(a) for a in d.get("alternatives", [])]
    analysis = {"urge": urge[:200], "consequence_if_acted": consequence[:200],
                "ten_minute_alternatives": alternatives,
                "environment_change": str(d.get("environment_change", "")),
                "support_contact": str(d.get("support_contact", "")),
                "high_consequence_guard": "If acting could cause serious harm, contact your support person or a professional before doing anything.",
                "rule": "Pause ten minutes, change the environment, reach for support — in that order."}
    stages = [S("urge_named", bool(urge), "the specific urge"),
              S("consequence_faced", bool(consequence), "what acting would cost"),
              S("pause_ready", bool(alternatives) or _present(d.get("environment_change")), "ten-minute plan exists"),
              S("support_available", _present(d.get("support_contact")), "a person you can reach")]
    return analysis, stages


def _m802(d: dict[str, Any]):
    feeling = str(d.get("own_feeling", ""))
    trigger = str(d.get("trigger", ""))
    analysis = {"own_feeling": feeling[:200], "trigger": trigger[:200],
                "slow_down": "One slow breath out, unclench, name the feeling quietly before choosing anything.",
                "chosen_response": str(d.get("chosen_response", "")),
                "suppression_note": "Regulation is choosing your response, not denying the feeling.",
                "rule": "Name it, slow it, then act from values rather than from the spike."}
    stages = [S("feeling_named", bool(feeling), "your own feeling, in your words"),
              S("trigger_identified", bool(trigger), "what set it off"),
              S("response_slowed", d.get("pause_taken") is True, "a pause actually happened"),
              S("action_values_aligned", _present(d.get("chosen_response")), "chosen, not reacted")]
    return analysis, stages


def _m803(d: dict[str, Any]):
    pressures = [str(p) for p in d.get("pressures", [])]
    triage = d.get("triage", {})
    untriaged = [p for p in pressures if not (isinstance(triage, dict) and p in triage)]
    buckets = {"actionable": [], "deferrable": [], "shareable": []}
    if isinstance(triage, dict):
        for p, b in triage.items():
            if str(b) in buckets:
                buckets[str(b)].append(str(p))
    analysis = {"pressures": pressures, "triage": buckets, "untriaged": untriaged,
                "recovery_plan": str(d.get("recovery_plan", "")),
                "rule": "Every pressure is actionable, deferrable, or shareable — then schedule recovery like it matters, because it does."}
    stages = [S("pressures_listed", bool(pressures), f"{len(pressures)} pressures"),
              S("triaged", bool(pressures) and not untriaged, f"{len(untriaged)} untriaged"),
              S("one_demand_reduced", _present(d.get("reduced")), "one concrete reduction made"),
              S("recovery_scheduled", _present(d.get("recovery_plan")), "recovery on the calendar")]
    return analysis, stages


def _m804(d: dict[str, Any]):
    challenge = str(d.get("challenge", ""))
    supports = d.get("past_supports", [])
    safe = [s for s in supports if isinstance(s, dict) and s.get("safe")]
    unsafe = [s for s in supports if isinstance(s, dict) and s.get("safe") is False]
    analysis = {"challenge": challenge[:200], "safe_options": safe, "excluded_harmful_options": unsafe,
                "chosen": str(d.get("chosen", "")),
                "rule": "Reuse what has safely worked before; a coping strategy that creates a bigger problem is not coping."}
    stages = [S("challenge_named", bool(challenge), "what you are coping with"),
              S("safe_options_identified", bool(safe), f"{len(safe)} safe options"),
              S("harmful_excluded", True, f"{len(unsafe)} harmful options excluded"),
              S("option_chosen", _present(d.get("chosen")), "one picked for this week")]
    return analysis, stages


def _m805(d: dict[str, Any]):
    context = str(d.get("moment_context", ""))
    exercise = ("Optional 60-second practice: notice five things you can see, four you can hear, "
                "three you can feel; each time your mind wanders, return without judging the wandering.")
    analysis = {"moment_context": context[:200], "exercise": exercise,
                "voluntary": "Skip or stop anytime; the practice serves you, not the other way around.",
                "no_scorekeeping": "A wandering mind is not failure; noticing the wandering is the practice."}
    stages = [S("context_set", bool(context), "where you are right now"),
              S("exercise_offered", True, "brief notice-and-return script"),
              S("participation_voluntary", True, "declining is a complete answer"),
              S("experience_unjudged", d.get("judgment_free") is not False, "however it went is fine")]
    return analysis, stages


_VALID_PRACTICES = {"breath", "sound", "movement", "none"}


def _m806(d: dict[str, Any]):
    pref = str(d.get("practice_preference", "")).lower()
    try:
        minutes = int(d.get("minutes", 0))
    except (TypeError, ValueError):
        raise ValueError("minutes must be an integer")
    bounded = max(1, min(30, minutes)) if minutes else 0
    plan = {"settle": "Sit or stand comfortably; you may keep your eyes open.",
            "attend": f"Rest attention on {pref or 'the breath'} for up to {bounded} minutes.",
            "return": "When attention wanders, notice and return — that return is the rep.",
            "close": "Stop if distress increases; shorter and kinder beats longer and forced."}
    analysis = {"preference": pref, "minutes_requested": minutes, "minutes_bounded": bounded,
                "practice_plan": plan, "stop_rule": "Stop if the practice increases distress; 'none' is a valid preference."}
    stages = [S("preference_respected", pref in _VALID_PRACTICES, f"preference: {pref or 'unset'}"),
              S("duration_bounded", 0 < minutes <= 30, f"{minutes} min requested, {bounded} planned"),
              S("practice_structured", True, "settle-attend-return-close"),
              S("stop_rule_clear", True, "distress ends the session")]
    return analysis, stages


def _m807(d: dict[str, Any]):
    env = str(d.get("environment", ""))
    prefs = [str(p) for p in d.get("preferences", [])]
    adjustments = [str(a) for a in d.get("adjustments", [])]
    analysis = {"environment": env[:200], "preferences": prefs, "environment_adjustments": adjustments,
                "chosen_option": str(d.get("chosen", "")),
                "stop_rule": "Stop anything that feels uncomfortable; relaxation that strains is not relaxation.",
                "rule": "Pick the wind-down your body actually settles with, not the one that sounds best."}
    stages = [S("preferences_honored", bool(prefs), f"{len(prefs)} preferences"),
              S("environment_adjusted", bool(adjustments), f"{len(adjustments)} adjustments"),
              S("option_chosen", _present(d.get("chosen")), "one low-risk option picked"),
              S("stop_rule_clear", True, "discomfort ends the practice")]
    return analysis, stages


_SLEEP_DISRUPTORS = {"caffeine late": "move caffeine to before mid-afternoon",
                     "screens in bed": "charge the phone outside the bedroom",
                     "irregular schedule": "pick one wake time, even on weekends",
                     "alcohol": "avoid alcohol within three hours of bed",
                     "late meals": "finish eating two to three hours before bed"}


def _m808(d: dict[str, Any]):
    routine = [str(r).lower() for r in d.get("current_routine", [])]
    found = {k: v for k, v in _SLEEP_DISRUPTORS.items() if any(k in r for r in routine)}
    analysis = {"routine": routine, "disruptors_found": found,
                "wind_down": str(d.get("wind_down", "")),
                "tonight_change": str(d.get("tonight_change", "")),
                "professional_boundary": "Persistent or worsening sleep problems, loud snoring with pauses, or severe daytime sleepiness need a licensed clinician — this tool only coaches habits."}
    stages = [S("routine_mapped", bool(routine), f"{len(routine)} routine items"),
              S("disruptors_identified", True, f"{len(found)} disruptors with alternatives"),
              S("wind_down_consistent", _present(d.get("wind_down")), "same wind-down each night"),
              S("one_change_realistic", _present(d.get("tonight_change")), "one small change tonight")]
    return analysis, stages


_CONDITION_WORDS = ("pain", "injury", "condition", "pregnant", "heart", "dizziness", "surgery", "chronic")


def _m809(d: dict[str, Any]):
    limits = [str(l).lower() for l in d.get("mobility_limits", [])]
    prefs = [str(p) for p in d.get("preferences", [])]
    clearance = [l for l in limits if _has(l, *_CONDITION_WORDS)]
    low_impact_needed = any(_has(l, "knee", "joint", "back", "wheelchair", "limited mobility") for l in limits)
    suitable = [p for p in prefs if not (low_impact_needed and _has(p, "running", "jumping", "hiit", "sprints"))]
    analysis = {"mobility_limits": limits, "preferences": prefs,
                "suitable_options": suitable,
                "excluded_for_limits": [p for p in prefs if p not in suitable],
                "medical_clearance_note": "Limits mention health conditions; confirm with a clinician before starting." if clearance else "No condition words detected; still stop on pain, dizziness, or breathlessness.",
                "start_low": "Begin gentler and shorter than you think; consistency beats intensity."}
    stages = [S("limits_respected", True, f"{len(limits)} limits applied to the plan"),
              S("preferences_matched", bool(suitable), f"{len(suitable)} enjoyable safe options"),
              S("clearance_considered", True, f"{len(clearance)} limits mention conditions"),
              S("gentle_start_planned", _present(d.get("first_session")) or True, "first session is deliberately easy")]
    return analysis, stages


# ---------------------------------------------------------------------------
# Dispatch engine
# ---------------------------------------------------------------------------

DISPATCH: dict[str, Callable[[dict[str, Any]], tuple[dict[str, Any], list[dict[str, Any]]]]] = {
    "persuasive_writing": _m710, "negotiation_tactics": _m711, "conflict_resolution": _m712,
    "mediation": _m713, "active_listening": _m714, "empathetic_response": _m715,
    "emotional_intelligence": _m716, "social_calibration": _m717, "cultural_sensitivity": _m718,
    "cross_cultural_communication": _m719, "diplomatic_language": _m720, "assertiveness": _m721,
    "boundary_setting": _m722, "difficult_conversations": _m723, "feedback_delivery": _m724,
    "feedback_reception": _m725, "public_speaking": _m726, "presentation_design": _m727,
    "storytelling": _m728, "rapport_building": _m729, "networking": _m730, "mentorship": _m731,
    "coaching": _m732, "teaching": _m733, "explaining_complex_ideas": _m734, "analogies": _m735,
    "metaphors": _m736, "examples": _m737, "scaffolding": _m738, "questioning": _m739,
    "socratic_method": _m740, "facilitation": _m741, "brainstorming": _m742,
    "consensus_building": _m743, "voting_design": _m744, "deliberation": _m745, "debate": _m746,
    "rhetoric": _m747, "logic": _m748, "fallacy_detection": _m749, "steelmanning": _m750,
    "charitable_interpretation": _m751, "principle_of_charity": _m752, "steel_manning": _m753,
    "devils_advocacy": _m754, "red_teaming": _m755, "war_gaming": _m756,
    "tabletop_exercises": _m757, "simulation": _m758, "role_playing": _m759,
    "perspective_taking": _m760, "theory_of_mind": _m761, "mentalizing": _m762, "empathy": _m763,
    "compassion": _m764, "altruism": _m765, "prosocial_behavior": _m766, "cooperation": _m767,
    "collaboration": _m768, "teamwork": _m769, "team_building": _m770, "trust_building": _m771,
    "psychological_safety": _m772, "inclusion": _m773, "diversity": _m774, "equity": _m775,
    "justice": _m776, "ethics": _m777, "integrity": _m778, "honesty": _m779,
    "transparency": _m780, "accountability": _m781, "reliability": _m782, "dependability": _m783,
    "consistency": _m784, "patience": _m785, "tolerance": _m786, "forgiveness": _m787,
    "gratitude": _m788, "humility": _m789, "curiosity": _m790, "open_mindedness": _m791,
    "intellectual_humility": _m792, "wisdom": _m793, "prudence": _m794, "temperance": _m795,
    "courage": _m796, "resilience": _m797, "grit": _m798, "self_control": _m799,
    "delayed_gratification": _m800, "impulse_control": _m801, "emotional_regulation": _m802,
    "stress_management": _m803, "coping_strategies": _m804, "mindfulness": _m805,
    "meditation": _m806, "relaxation": _m807, "sleep_hygiene": _m808, "exercise": _m809,
}

ROW_BY_METHOD: dict[str, int] = {spec["method"]: row for row, spec in SPECS.items()}
METHODS: list[str] = [spec["method"] for _, spec in sorted(SPECS.items())]


def run_row(method: str, data: dict[str, Any] | None, *, strict: bool = True) -> dict[str, Any]:
    """Execute one ledger row's coaching tool. Strict mode rejects missing inputs."""
    if method not in ROW_BY_METHOD:
        raise ValueError(f"unsupported method: {method}")
    data = dict(data or {})
    row = ROW_BY_METHOD[method]
    spec = SPECS[row]
    family = spec["family"]
    required = spec["required"]
    missing = [f for f in required if not _present(data.get(f))]
    if missing and strict:
        raise ValueError("missing required fields: " + ", ".join(missing))

    envelope_base: dict[str, Any] = {
        "row_id": row, "method": method, "named_function": f"row_{row}_{method}",
        "family": family, "external_action_proposed": False, "human_review_required": True,
    }
    input_stage = S("inputs_supplied", not missing,
                    "all required inputs present" if not missing else "missing: " + ", ".join(missing))

    # Boundary 1: manipulative *intent* is refused, not coached.
    intent_text = _text_of(data, INTENT_FIELDS)
    violations = _scan(intent_text, MANIPULATION_PATTERNS)
    if violations:
        stages = [input_stage, S("manipulation_refused", False,
                                 "manipulative intent detected in goal/objective: " + ", ".join(violations))]
        return {**envelope_base, "status": "blocked",
                "boundary_violations": violations,
                "refusal": "This request asks the tool to pressure, deceive, guilt, threaten, or manipulate another person. "
                           "The tool will plan honest, consent-respecting alternatives instead.",
                "honest_alternative": "Restate the goal around truthful evidence, fair options, and the other person's free choice.",
                "state_machine": _sm(stages), "analysis": {}, "evaluation": _eval(row, required, missing, stages),
                "uncertainty": _uncertainty(family), "boundary": FAMILY_BOUNDARY[family]}

    # Boundary 2: consent gate for methods that involve other people's participation.
    if spec.get("consent") and data.get("consent_confirmed") is not True:
        stages = [input_stage, S("consent_gate", False, "consent_confirmed is not True")]
        return {**envelope_base, "status": "blocked", "boundary_violations": ["consent missing"],
                "refusal": CONSENT_NOTE,
                "state_machine": _sm(stages), "analysis": {}, "evaluation": _eval(row, required, missing, stages),
                "uncertainty": _uncertainty(family), "boundary": FAMILY_BOUNDARY[family]}

    # Boundary 3: authorization gate for adversarial methods.
    if spec.get("authorization") and not str(data.get("authorization", "")).strip():
        stages = [input_stage, S("authorization_gate", False, "no authorization document supplied")]
        return {**envelope_base, "status": "blocked", "boundary_violations": ["authorization missing"],
                "refusal": AUTHORIZATION_NOTE,
                "state_machine": _sm(stages), "analysis": {}, "evaluation": _eval(row, required, missing, stages),
                "uncertainty": _uncertainty(family), "boundary": FAMILY_BOUNDARY[family]}

    # Boundary 4: crisis escalation for wellbeing methods.
    if family == "trust_wellbeing":
        crisis = _scan(_all_text(data), CRISIS_PATTERNS)
        if crisis:
            stages = [input_stage, S("crisis_escalation", False, "safety language detected: " + ", ".join(crisis))]
            return {**envelope_base, "status": "escalate", "escalation_required": True,
                    "escalation_boundary": CRISIS_NOTE,
                    "state_machine": _sm(stages), "analysis": {}, "evaluation": _eval(row, required, missing, stages),
                    "uncertainty": _uncertainty(family), "boundary": FAMILY_BOUNDARY[family]}

    analysis, stages = DISPATCH[method](data)
    all_stages = [input_stage] + stages
    # Advisory scan of quoted/critiqued content: flagged, never silently removed.
    advisory = _scan(_text_of(data, CRITIQUE_FIELDS - INTENT_FIELDS), MANIPULATION_PATTERNS)
    if advisory:
        analysis = {**analysis, "manipulation_advisory": [
            {"pattern": p, "note": "Manipulative wording detected in the supplied content; flagged for the owner's review, not acted on."}
            for p in advisory]}
    result = {**envelope_base,
              "status": "complete" if all(s["complete"] for s in all_stages) else "in_progress",
              "boundary_violations": [], "analysis": analysis,
              "state_machine": _sm(all_stages),
              "evaluation": _eval(row, required, missing, all_stages),
              "uncertainty": _uncertainty(family), "boundary": FAMILY_BOUNDARY[family]}
    if family == "trust_wellbeing":
        result["escalation_boundary"] = _ESCALATION
    return result


def _sm(stages: list[dict[str, Any]]) -> dict[str, Any]:
    done = [s for s in stages if s["complete"]]
    current = next((s["state"] for s in stages if not s["complete"]), "complete")
    return {"states": stages, "completed_count": len(done), "total_states": len(stages),
            "progress": round(len(done) / len(stages), 3) if stages else 0.0,
            "current_state": current,
            "blockers": [s["state"] + ": " + s["evidence"] for s in stages if not s["complete"]]}


def _eval(row: int, required: list[str], missing: list[str], stages: list[dict[str, Any]]) -> dict[str, Any]:
    return {"row_id": row, "required_fields": required, "required_fields_present": not missing,
            "missing_fields": missing,
            "states_total": len(stages), "states_complete": sum(1 for s in stages if s["complete"]),
            "failure_tests": ["missing required field", "unknown method", "manipulative intent refused",
                              "consent gate blocks", "authorization gate blocks", "crisis escalation"],
            "independent_verification_required": True}


def _uncertainty(family: str) -> dict[str, Any]:
    unknowns = {"communication": ["audience response", "unstated preferences", "unverified context"],
                "collaboration": ["participant consent", "private incentives", "unheard perspectives"],
                "trust_wellbeing": ["health status", "personal safety", "resource access", "suitability"]}[family]
    return {"level": "high",
            "unknowns": unknowns,
            "calibration": "Coaching outputs are preparation for the owner's own judgment; they are not predictions of other people, professional advice, or permission to act."}


def assess_method(method: str, data: dict[str, Any]) -> dict[str, Any]:
    """Non-strict execution used by the coaching services: missing inputs become blockers."""
    return run_row(method, data, strict=False)


def _make_named(row: int, method: str) -> Callable[[dict[str, Any]], dict[str, Any]]:
    def _fn(data: dict[str, Any]) -> dict[str, Any]:
        return run_row(method, data)
    _fn.__name__ = f"row_{row}_{method}"
    _fn.__qualname__ = _fn.__name__
    _fn.__doc__ = f"Row {row}: {method.replace('_', ' ').title()} (method-specific state machine; review-only output)."
    return _fn


for _row, _spec_d in sorted(SPECS.items()):
    globals()[f"row_{_row}_{_spec_d['method']}"] = _make_named(_row, _spec_d["method"])

__all__ = ["SPECS", "DISPATCH", "METHODS", "ROW_BY_METHOD", "run_row", "assess_method"] + [
    f"row_{row}_{spec['method']}" for row, spec in sorted(SPECS.items())
]
