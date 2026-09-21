"""Rows 710-740: ethical communication coaching and critique.

Outputs prepare the owner to communicate. They never send, publish, impersonate,
manipulate, diagnose emotions, or treat cultural generalizations as facts.
"""

from __future__ import annotations

import re

from .coaching_state_machines_710_809 import assess_method
from .schemas import (
    CoachingObservation,
    CommunicationCoachingRequest,
    CommunicationCoachingResponse,
    CommunicationSkill,
)


ROW_BY_SKILL: dict[CommunicationSkill, int] = {
    skill: row for row, skill in enumerate(CommunicationSkill, start=710)
}


_SKILL_GUIDANCE: dict[CommunicationSkill, tuple[str, str, str]] = {
    CommunicationSkill.PERSUASIVE_WRITING: ("Claim and evidence", "What evidence would change a reasonable reader's mind?", "Separate claims, evidence, and uncertainty."),
    CommunicationSkill.NEGOTIATION_TACTICS: ("Interests and options", "What does each side need, and what can remain flexible?", "List fair options and your walk-away boundary."),
    CommunicationSkill.CONFLICT_RESOLUTION: ("Shared problem", "Which facts are agreed, disputed, or still unknown?", "Restate both perspectives before proposing repair."),
    CommunicationSkill.MEDIATION: ("Neutral process", "Has each person freely agreed to this mediation process?", "Set equal turns and record agreements without taking sides."),
    CommunicationSkill.ACTIVE_LISTENING: ("Understanding check", "What would you reflect back before responding?", "Paraphrase, check accuracy, then ask one open question."),
    CommunicationSkill.EMPATHETIC_RESPONSE: ("Acknowledge without assuming", "What feeling did the person name, rather than what do you infer?", "Validate the stated experience without claiming to know their mind."),
    CommunicationSkill.EMOTIONAL_INTELLIGENCE: ("Emotion as hypothesis", "What observable cue supports your interpretation, and what else could it mean?", "Name your own state; ask rather than diagnose another's."),
    CommunicationSkill.SOCIAL_CALIBRATION: ("Context and consent", "What level of directness has this audience invited?", "Offer a low-pressure option and watch for explicit feedback."),
    CommunicationSkill.CULTURAL_SENSITIVITY: ("Individual over stereotype", "What preference can you ask this person directly?", "Flag assumptions and use the person's stated preferences."),
    CommunicationSkill.CROSS_CULTURAL_COMMUNICATION: ("Shared meaning", "Which terms, norms, or idioms may not transfer?", "Use plain language and ask the listener to confirm meaning."),
    CommunicationSkill.DIPLOMATIC_LANGUAGE: ("Respectful directness", "Can the issue be named without judging the person?", "State the fact, impact, and request without euphemistic deception."),
    CommunicationSkill.ASSERTIVENESS: ("Clear need", "What do you need, and what choice remains with the other person?", "Use a specific I-statement and a concrete request."),
    CommunicationSkill.BOUNDARY_SETTING: ("Limit and consequence", "What will you do if the limit is crossed?", "State the limit and a proportionate action you control."),
    CommunicationSkill.DIFFICULT_CONVERSATIONS: ("Facts, impact, request", "What is the safest time and setting for this conversation?", "Rehearse a factual opening and pause for their perspective."),
    CommunicationSkill.FEEDBACK_DELIVERY: ("Behavior and impact", "What observable behavior can you cite?", "Describe behavior, impact, and one actionable next step."),
    CommunicationSkill.FEEDBACK_RECEPTION: ("Understand before deciding", "What example would clarify the feedback?", "Summarize what you heard, ask for an example, then choose what to use."),
    CommunicationSkill.PUBLIC_SPEAKING: ("Audience takeaway", "What single idea should the audience remember?", "Rehearse aloud, time it, and mark intentional pauses."),
    CommunicationSkill.PRESENTATION_DESIGN: ("One point per slide", "What claim does each slide support?", "Build a claim-evidence sequence and remove decorative clutter."),
    CommunicationSkill.STORYTELLING: ("Truthful change", "What specific choice or consequence creates the arc?", "Use verified detail; do not invent stakes or experiences."),
    CommunicationSkill.RAPPORT_BUILDING: ("Genuine curiosity", "What can you ask without mining private information?", "Find a real shared interest and respect signals to disengage."),
    CommunicationSkill.NETWORKING: ("Mutual relevance", "Why might a conversation be useful to both people?", "Prepare a transparent introduction and a no-pressure question."),
    CommunicationSkill.MENTORSHIP: ("Mentee ownership", "What outcome does the mentee want?", "Offer experience as an option and leave the decision with them."),
    CommunicationSkill.COACHING: ("Goal and next experiment", "What would progress look like to the person being coached?", "Ask, reflect, and let them choose one next experiment."),
    CommunicationSkill.TEACHING: ("Learning objective", "What should the learner be able to do afterward?", "Explain, model, invite practice, then check understanding."),
    CommunicationSkill.EXPLAINING_COMPLEX_IDEAS: ("Core model", "What prerequisite does the audience already know?", "Start with the core idea, then add one layer at a time."),
    CommunicationSkill.ANALOGIES: ("Mapped comparison", "Where does the comparison stop being accurate?", "Map similarities explicitly and name the analogy's limit."),
    CommunicationSkill.METAPHORS: ("Illuminating image", "Could this image mislead or stereotype?", "Use one clear image and state what it does not imply."),
    CommunicationSkill.EXAMPLES: ("Concrete instance", "Is the example factual, representative, and privacy-safe?", "Give one real or clearly labeled hypothetical example."),
    CommunicationSkill.SCAFFOLDING: ("Progressive support", "What is the smallest next step the learner can attempt?", "Move from model to guided practice to independent attempt."),
    CommunicationSkill.QUESTIONING: ("Open, non-leading inquiry", "Does the question invite information rather than pressure agreement?", "Ask one neutral question and allow a real option not to answer."),
    CommunicationSkill.SOCRATIC_METHOD: ("Reasoning through questions", "Which assumption should the learner examine first?", "Ask a sequence from evidence to assumption to implication; do not trap them."),
}


class CommunicationCoach:
    def coach(self, request: CommunicationCoachingRequest) -> CommunicationCoachingResponse:
        label, question, rehearsal = _SKILL_GUIDANCE[request.skill]
        caveats = [
            "This is coaching for the owner's review, not a sent message or external action.",
            "Claims about another person's feelings, motives, or culture remain hypotheses until they confirm them.",
        ]
        if request.skill in {CommunicationSkill.PERSUASIVE_WRITING, CommunicationSkill.NEGOTIATION_TACTICS}:
            caveats.append("Use truthful evidence and fair choices; do not exploit fear, private vulnerabilities, or false urgency.")
        if request.skill in {CommunicationSkill.MEDIATION, CommunicationSkill.CONFLICT_RESOLUTION}:
            caveats.append("Do not mediate where safety, coercion, abuse, or a serious power imbalance calls for qualified help.")
        observations = [
            CoachingObservation(label=label, detail=rehearsal, evidence=self._evidence(request)),
            CoachingObservation(label="Audience and goal", detail=f"Prepare for {request.audience}: {request.goal}"),
        ]
        feedback = self._critique(request)
        sm = assess_method(request.skill.value, {
            "context": request.context, "goal": request.goal, "audience": request.audience,
            "draft": request.draft or "", "known_facts": request.known_facts,
            "cultural_context": request.cultural_context, "constraints": request.constraints,
        })
        state_machine = {"row_id": sm["row_id"], "status": sm["status"],
                         "current_state": sm["state_machine"]["current_state"],
                         "progress": sm["state_machine"]["progress"],
                         "blockers": sm["state_machine"]["blockers"],
                         "states": sm["state_machine"]["states"]}
        if sm["status"] == "blocked":
            caveats = caveats + ["State machine blocked: " + sm.get("refusal", "boundary gate")]
        authorship_notice = None
        if request.student_authored_work:
            authorship_notice = (
                "Student-authored work boundary: use these questions and comments to revise your own words. "
                "No submission-ready response or invented experience is provided."
            )
            caveats.append("The student must verify every fact and remain the author of the final work.")
        return CommunicationCoachingResponse(
            owner_id=request.owner_id,
            skill=request.skill,
            observations=observations,
            questions=[question, "What fact, preference, or assumption should you verify before acting?"],
            rehearsal_steps=[rehearsal, "Review the result for truth, tone, consent, privacy, and unintended pressure."],
            draft_feedback=feedback,
            review_required=True,
            external_action_proposed=False,
            caveats=caveats,
            authorship_notice=authorship_notice,
            state_machine=state_machine,
            evaluation={
                "row_id": ROW_BY_SKILL[request.skill],
                "evidence_coverage": min(1.0, len(request.known_facts) / 3),
                "draft_supplied": request.draft is not None,
                "checks": ["truth", "tone", "consent", "privacy", "pressure"],
                "issues_found": len(feedback),
            },
            uncertainty={
                "level": "high" if not request.known_facts else "medium",
                "unknowns": ["audience response", "unstated preferences", "unverified context"],
                "calibration": "Treat interpretations as hypotheses and verify with the audience.",
            },
        )

    @staticmethod
    def _evidence(request: CommunicationCoachingRequest) -> str | None:
        if request.known_facts:
            return "Known facts supplied by owner: " + "; ".join(request.known_facts[:3])
        return "No supporting facts were supplied; verify factual claims."

    @staticmethod
    def _critique(request: CommunicationCoachingRequest) -> list[str]:
        if not request.draft:
            return ["No draft supplied. Rehearse an outline, then bring back your own draft for critique."]
        feedback: list[str] = []
        draft = request.draft
        if re.search(r"\b(always|never|everyone|no one)\b", draft, re.IGNORECASE):
            feedback.append("Check absolute wording against the evidence and narrow it where needed.")
        if re.search(r"\b(obviously|clearly you|you must|you have to)\b", draft, re.IGNORECASE):
            feedback.append("This wording may pressure or dismiss the audience; state evidence and preserve choice.")
        if "I" not in draft and request.skill in {CommunicationSkill.ASSERTIVENESS, CommunicationSkill.BOUNDARY_SETTING}:
            feedback.append("Try an I-statement that names your need or limit without assigning motive.")
        if not feedback:
            feedback.append("Check each claim for evidence, then ask whether the tone leaves room for response.")
        return feedback
