"""Rows 771-809: non-clinical trust, values, and wellbeing coaching."""

from __future__ import annotations

from .coaching_state_machines_710_809 import assess_method
from .schemas import TrustWellbeingCoachingRequest, TrustWellbeingCoachingResponse, TrustWellbeingSkill

ROW_BY_SKILL: dict[TrustWellbeingSkill, int] = {skill: row for row, skill in enumerate(TrustWellbeingSkill, start=771)}

_GUIDANCE: dict[TrustWellbeingSkill, tuple[str, str]] = {
 TrustWellbeingSkill.TRUST_BUILDING:("Make one specific, realistic commitment and report back honestly.","What observable action would earn confidence over time?"),
 TrustWellbeingSkill.PSYCHOLOGICAL_SAFETY:("Invite dissent, respond without retaliation, and repair when speaking up carries a cost.","What would make it safer to raise a concern?"),
 TrustWellbeingSkill.INCLUSION:("Offer accessible ways to participate and ask who is missing.","Whose access or voice has not been considered?"),
 TrustWellbeingSkill.DIVERSITY:("Value individual differences without inferring identity or treating anyone as representative.","What perspective is absent, and how can it be invited without tokenizing?"),
 TrustWellbeingSkill.EQUITY:("Compare barriers and adjust support using stated needs and transparent criteria.","Does equal treatment create unequal access here?"),
 TrustWellbeingSkill.JUSTICE:("Identify rights, harms, process, evidence, and an accountable appeal path.","Who is affected and what fair process is owed?"),
 TrustWellbeingSkill.ETHICS:("List stakeholders, duties, harms, benefits, consent, and reversible alternatives.","What action remains defensible if everyone affected knows about it?"),
 TrustWellbeingSkill.INTEGRITY:("Align the next action with stated values and disclose conflicts.","Would your action match what you publicly claim?"),
 TrustWellbeingSkill.HONESTY:("State what is known, unknown, and mistaken without fabricating certainty.","What truth is difficult but necessary to say?"),
 TrustWellbeingSkill.TRANSPARENCY:("Share relevant reasons and limits while protecting privacy and safety.","What can be explained, and what must remain private for a valid reason?"),
 TrustWellbeingSkill.ACCOUNTABILITY:("Name the impact, own the part you controlled, repair, and prevent recurrence.","What specific repair can you make?"),
 TrustWellbeingSkill.RELIABILITY:("Reduce promises to what is feasible and create a check-in before failure.","What can you reliably commit to?"),
 TrustWellbeingSkill.DEPENDABILITY:("Clarify expectations, dependencies, backup, and notification triggers.","What backup prevents others from carrying a silent failure?"),
 TrustWellbeingSkill.CONSISTENCY:("Use a small repeatable rule while allowing reasoned exceptions.","What principle should stay stable across similar cases?"),
 TrustWellbeingSkill.PATIENCE:("Choose a useful action during the wait and set a reasonable recheck point.","What is controllable while you wait?"),
 TrustWellbeingSkill.TOLERANCE:("Respect difference while keeping boundaries against harm.","Can you accept the difference without endorsing harm?"),
 TrustWellbeingSkill.FORGIVENESS:("Treat forgiveness as optional and separate it from trust, access, or reconciliation.","What boundary or repair would you need, whether or not you forgive?"),
 TrustWellbeingSkill.GRATITUDE:("Notice a specific contribution without forcing positivity or creating obligation.","What specific act helped, and how can you acknowledge it freely?"),
 TrustWellbeingSkill.HUMILITY:("Name limits, invite correction, and credit contributors.","Where might you be wrong or dependent on others?"),
 TrustWellbeingSkill.CURIOSITY:("Ask a genuine open question before defending a conclusion.","What would you want to understand if proving yourself were not the goal?"),
 TrustWellbeingSkill.OPEN_MINDEDNESS:("Compare alternatives using the same evidence standard.","What evidence would make another view more plausible?"),
 TrustWellbeingSkill.INTELLECTUAL_HUMILITY:("Calibrate confidence and separate evidence from inference.","How certain are you, and why?"),
 TrustWellbeingSkill.WISDOM:("Balance evidence, experience, values, timing, and downstream effects.","What choice will still look sound after the immediate pressure passes?"),
 TrustWellbeingSkill.PRUDENCE:("Prefer a reversible next step when uncertainty or stakes are high.","What is the smallest safe experiment?"),
 TrustWellbeingSkill.TEMPERANCE:("Add a pause and choose a limit consistent with your goal.","What amount or boundary would be enough?"),
 TrustWellbeingSkill.COURAGE:("Take a values-aligned step without ignoring real danger or support needs.","What safe, supported action moves toward what matters?"),
 TrustWellbeingSkill.RESILIENCE:("Identify support, recovery time, learning, and one manageable restart.","What resource helps you recover rather than merely endure?"),
 TrustWellbeingSkill.GRIT:("Reconnect effort to a chosen goal and reassess when persistence becomes harmful.","Is this goal still worth the cost?"),
 TrustWellbeingSkill.SELF_CONTROL:("Add friction before the impulse and make the preferred action easier.","What cue and pause can interrupt the pattern?"),
 TrustWellbeingSkill.DELAYED_GRATIFICATION:("Make the future benefit concrete and choose a short review interval.","What smaller milestone makes waiting workable?"),
 TrustWellbeingSkill.IMPULSE_CONTROL:("Pause, change environment, and contact support before high-consequence action.","What can you do for ten minutes instead?"),
 TrustWellbeingSkill.EMOTIONAL_REGULATION:("Name your own feeling if known, slow the response, and choose a low-stakes next action.","What do you notice in your body and what response fits your values?"),
 TrustWellbeingSkill.STRESS_MANAGEMENT:("Reduce one demand, add one support, and schedule recovery.","Which pressure is actionable, deferrable, or shareable?"),
 TrustWellbeingSkill.COPING_STRATEGIES:("Choose a safe coping option that fits your preference and does not create a larger harm.","Which support has helped safely before?"),
 TrustWellbeingSkill.MINDFULNESS:("Try a brief optional notice-and-return exercise without judging the experience.","What can you notice right now without trying to change it?"),
 TrustWellbeingSkill.MEDITATION:("If comfortable, try a short attention practice and stop if it increases distress.","Would breath, sound, movement, or no practice feel safest?"),
 TrustWellbeingSkill.RELAXATION:("Try a brief low-risk wind-down chosen by you; stop if uncomfortable.","Which environment or activity helps your body settle?"),
 TrustWellbeingSkill.SLEEP_HYGIENE:("Use a consistent wind-down and reduce avoidable disruption; persistent problems need professional advice.","What small change to timing or environment is realistic tonight?"),
 TrustWellbeingSkill.EXERCISE:("Choose accessible, enjoyable movement within known limits; medical clearance may be needed.","What gentle movement feels safe and sustainable for you?"),
}

_WELLBEING = set(list(TrustWellbeingSkill)[26:])

class TrustWellbeingCoach:
    def coach(self, request: TrustWellbeingCoachingRequest) -> TrustWellbeingCoachingResponse:
        step, question = _GUIDANCE[request.skill]
        safeguards = [
            "This is optional, non-clinical coaching; it does not diagnose, treat, or make medical claims.",
            "No identity, emotion, condition, motive, capacity, or risk level is inferred from the request.",
            "Owner review is required and no message, disclosure, commitment, or external action is made.",
        ]
        if request.skill in _WELLBEING:
            safeguards.append("Stop any practice that feels unsafe or worsens distress; adapt for disability, health conditions, and professional advice.")
        if request.skill in {TrustWellbeingSkill.FORGIVENESS, TrustWellbeingSkill.TOLERANCE}:
            safeguards.append("Forgiveness, reconciliation, tolerating harm, and restoring access are not required.")
        escalation = (
            "This tool is not emergency or crisis support. If there is immediate danger, possible self-harm or harm to others, "
            "inability to stay safe, severe symptoms, or a medical emergency, contact local emergency services or a qualified "
            "crisis/health professional now and involve a trusted person where safe. For persistent or worsening sleep, stress, "
            "mood, impulse, exercise, or health concerns, seek a licensed clinician rather than relying on this coaching."
        )
        sm = assess_method(request.skill.value, {
            "context": request.context, "goal": request.goal,
            "preferences": request.preferences, "constraints": request.constraints,
            "reflection": request.reflection or "",
        })
        state_machine = {"row_id": sm["row_id"], "status": sm["status"],
                         "current_state": sm["state_machine"]["current_state"],
                         "progress": sm["state_machine"]["progress"],
                         "blockers": sm["state_machine"]["blockers"],
                         "states": sm["state_machine"]["states"]}
        if sm["status"] == "escalate":
            escalation = sm["escalation_boundary"]
        notice = None
        if request.student_authored_work:
            notice = "Student-authored boundary: use reflection questions to develop your own work; no submission-ready text is generated."
        return TrustWellbeingCoachingResponse(
            owner_id=request.owner_id, skill=request.skill,
            reflection_questions=[question, "What constraint, support, or uncertainty should shape the next step?"],
            low_risk_steps=[step, "Choose one small step, review its effect, and stop or change course if it is not helpful."],
            safeguards=safeguards, escalation_boundary=escalation,
            review_required=True, external_action_proposed=False, authorship_notice=notice,
            state_machine=state_machine,
            evaluation={"row_id": ROW_BY_SKILL[request.skill], "preference_coverage": min(1.0, len(request.preferences) / 3), "constraint_count": len(request.constraints), "reflection_supplied": request.reflection is not None, "safety_checks": ["agency", "non-diagnosis", "accessibility", "escalation"]},
            uncertainty={"level": "high", "unknowns": ["health status", "personal safety", "resource access", "suitability"], "calibration": "Wellbeing guidance is general and must not replace qualified care."},
        )
