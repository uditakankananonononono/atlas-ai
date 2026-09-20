"""Rows 741-770: ethical group-process, reasoning, and collaboration coaching."""

from __future__ import annotations

import re

from .schemas import CollaborationCoachingRequest, CollaborationCoachingResponse, CollaborationSkill


ROW_BY_SKILL: dict[CollaborationSkill, int] = {skill: row for row, skill in enumerate(CollaborationSkill, start=741)}

_GUIDANCE: dict[CollaborationSkill, tuple[str, str]] = {
    CollaborationSkill.FACILITATION: ("Publish purpose, roles, decision rule, and timeboxes.", "Who has not had a fair chance to contribute?"),
    CollaborationSkill.BRAINSTORMING: ("Separate idea generation from evaluation; allow quiet/anonymous contribution.", "What different category of idea have we not tried?"),
    CollaborationSkill.CONSENSUS_BUILDING: ("Define consensus and record support, reservations, and unresolved objections.", "What change would make this safe enough to try?"),
    CollaborationSkill.VOTING_DESIGN: ("Choose a transparent rule and test it for ties, strategic voting, and minority impact.", "What decision rule fits the stakes and reversibility?"),
    CollaborationSkill.DELIBERATION: ("Share evidence, surface tradeoffs, and distinguish facts from values.", "Which evidence would change your view?"),
    CollaborationSkill.DEBATE: ("Define the claim, burden of proof, equal turns, and evidence standard.", "What is the strongest evidence for and against the claim?"),
    CollaborationSkill.RHETORIC: ("Align truthful claims, relevant evidence, and audience needs without coercion.", "Is the emotional appeal proportionate and factually grounded?"),
    CollaborationSkill.LOGIC: ("List premises and conclusion, then test validity and premise support separately.", "Does the conclusion follow if every premise is true?"),
    CollaborationSkill.FALLACY_DETECTION: ("Name the reasoning pattern tentatively and explain the exact gap.", "Can the argument be repaired before it is rejected?"),
    CollaborationSkill.STEELMANNING: ("Restate the strongest supportable opposing case and ask its holder to confirm it.", "Would the other side recognize this as their argument?"),
    CollaborationSkill.CHARITABLE_INTERPRETATION: ("Prefer a plausible good-faith reading while retaining uncertainty.", "What benign interpretation fits the same words?"),
    CollaborationSkill.PRINCIPLE_OF_CHARITY: ("Resolve ambiguity toward coherence, then verify with the speaker.", "Which interpretation makes the argument most coherent?"),
    CollaborationSkill.STEEL_MANNING: ("Build the best evidence-backed version, without inventing beliefs for its holder.", "What premise would make this version strongest?"),
    CollaborationSkill.DEVILS_ADVOCACY: ("Timebox an explicitly assigned challenge role; critique the idea, not a person.", "What would make this proposal fail?"),
    CollaborationSkill.RED_TEAMING: ("Define authorized scope, assets, harms, stop conditions, and remediation ownership.", "Which failure can we test safely without affecting outsiders?"),
    CollaborationSkill.WAR_GAMING: ("Use fictional or authorized scenarios, declared assumptions, and bounded moves.", "What uncertainty or escalation risk is missing?"),
    CollaborationSkill.TABLETOP_EXERCISES: ("Set objectives, injects, roles, safety limits, and an after-action review.", "What decision must each role make with incomplete information?"),
    CollaborationSkill.SIMULATION: ("Label assumptions, parameters, uncertainty, and validation limits.", "Which real-world factor does the model omit?"),
    CollaborationSkill.ROLE_PLAYING: ("Use voluntary roles, fictionalized details, opt-out, and a debrief.", "What did the role exercise reveal without claiming it reveals a real person's mind?"),
    CollaborationSkill.PERSPECTIVE_TAKING: ("Generate multiple hypotheses and ask the real person where possible.", "What might this look like from another position?"),
    CollaborationSkill.THEORY_OF_MIND: ("Treat beliefs and intentions as unverified hypotheses based on observable context.", "What evidence supports this hypothesis, and what alternatives fit?"),
    CollaborationSkill.MENTALIZING: ("Separate observed behavior from guessed thoughts or feelings.", "What could you ask instead of inferring their mental state?"),
    CollaborationSkill.EMPATHY: ("Reflect the experience they stated; do not claim to feel or know what they feel.", "What did the person actually say matters to them?"),
    CollaborationSkill.COMPASSION: ("Ask what support is wanted and offer bounded choices.", "What help would be useful without taking away agency?"),
    CollaborationSkill.ALTRUISM: ("Check consent, impact, sustainability, and the recipient's stated needs.", "Could this help impose an unwanted cost or obligation?"),
    CollaborationSkill.PROSOCIAL_BEHAVIOR: ("Choose actions that benefit people without deception, coercion, or hidden exchange.", "Who benefits, who bears risk, and who decides?"),
    CollaborationSkill.COOPERATION: ("Define shared and separate interests, commitments, and a repair path.", "What can each party commit to voluntarily?"),
    CollaborationSkill.COLLABORATION: ("Define joint ownership, contribution channels, decisions, and attribution.", "How will credit and disagreement be handled?"),
    CollaborationSkill.TEAMWORK: ("Clarify roles, dependencies, handoffs, and ways to ask for help.", "Where could a handoff fail?"),
    CollaborationSkill.TEAM_BUILDING: ("Build cohesion through shared work, psychological safety, and voluntary reflection.", "What working agreement would make participation safer?"),
}


class CollaborationCoach:
    def coach(self, request: CollaborationCoachingRequest) -> CollaborationCoachingResponse:
        step, question = _GUIDANCE[request.skill]
        safeguards = [
            "Owner review is required; no group message, vote, invitation, or exercise is executed.",
            "Do not infer private beliefs, feelings, motives, or cultural traits; ask and preserve uncertainty.",
            "Participation must be voluntary, with a clear way to pause or opt out.",
        ]
        if request.skill in {CollaborationSkill.RED_TEAMING, CollaborationSkill.WAR_GAMING, CollaborationSkill.TABLETOP_EXERCISES, CollaborationSkill.SIMULATION}:
            safeguards.append("Use only fictional or explicitly authorized systems and data; stop before real-world effects.")
        if request.skill in {CollaborationSkill.RHETORIC, CollaborationSkill.DEBATE}:
            safeguards.append("Do not use deception, humiliation, false urgency, or targeted exploitation of vulnerabilities.")
        if request.skill in {CollaborationSkill.THEORY_OF_MIND, CollaborationSkill.MENTALIZING, CollaborationSkill.PERSPECTIVE_TAKING, CollaborationSkill.EMPATHY}:
            safeguards.append("Any mental-state model is a tentative hypothesis, never a diagnosis or fact claim.")
        notice = None
        if request.student_authored_work:
            notice = "Student-authored boundary: use the questions and critique to revise your own work; no submission-ready argument is generated."
        return CollaborationCoachingResponse(
            owner_id=request.owner_id,
            skill=request.skill,
            agenda=[f"State the objective: {request.objective}", step, "Record decisions, dissent, owners, and open questions."],
            questions=[question, "What assumption, evidence, or affected voice is missing?"],
            critique=self._critique(request.proposal_or_argument),
            safeguards=safeguards,
            review_required=True,
            external_action_proposed=False,
            authorship_notice=notice,
        )

    @staticmethod
    def _critique(text: str | None) -> list[str]:
        if not text:
            return ["No proposal or argument supplied; prepare one for evidence-based critique."]
        feedback: list[str] = []
        if re.search(r"\b(obviously|everyone knows|must agree|only an idiot)\b", text, re.I):
            feedback.append("Remove coercive or dismissive rhetoric and address evidence and tradeoffs.")
        if re.search(r"\b(always|never|everyone|nobody)\b", text, re.I):
            feedback.append("Test absolute claims and narrow them to supported scope.")
        if not re.search(r"\b(because|therefore|evidence|data|example)\b", text, re.I):
            feedback.append("Make premises and supporting evidence explicit before drawing a conclusion.")
        return feedback or ["Test the strongest counterargument and identify what evidence would change the conclusion."]
