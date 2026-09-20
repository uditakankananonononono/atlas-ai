"""Application service for ethical advice compilation and essay coaching."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Sequence
from typing import Protocol
from uuid import UUID

from .communication_coaching import CommunicationCoach
from .schemas import (
    AdviceSource,
    CommunicationCoachingRequest,
    CommunicationCoachingResponse,
    AdviceTip,
    CritiqueDimension,
    CritiqueFinding,
    EssayBrief,
    EssayConcept,
    EssayCritique,
    IdentityMaterial,
    SourceKind,
)


class Module17Repository(Protocol):
    def add_source(self, source: AdviceSource) -> AdviceSource: ...
    def list_sources(self, owner_id: UUID) -> list[AdviceSource]: ...
    def add_material(self, material: IdentityMaterial) -> IdentityMaterial: ...
    def list_materials(self, owner_id: UUID, ids: Sequence[UUID]) -> list[IdentityMaterial]: ...
    def add_tip(self, tip: AdviceTip) -> AdviceTip: ...
    def list_tips(self, owner_id: UUID) -> list[AdviceTip]: ...
    def add_concept(self, concept: EssayConcept) -> EssayConcept: ...


class Coach(Protocol):
    def concepts(
        self,
        brief: EssayBrief,
        materials: Sequence[IdentityMaterial],
        tips: Sequence[AdviceTip],
    ) -> list[EssayConcept]: ...

    def critique(self, owner_id: UUID, prompt: str, draft: str) -> EssayCritique: ...


class DeterministicCoach:
    """Offline baseline used when no approved model adapter is configured.

    It deliberately emits scaffolds and questions rather than submission-ready essays.
    """

    _cliches = (
        "since I was a child",
        "changed my life",
        "think outside the box",
        "journey of self-discovery",
        "make the world a better place",
    )

    def concepts(
        self,
        brief: EssayBrief,
        materials: Sequence[IdentityMaterial],
        tips: Sequence[AdviceTip],
    ) -> list[EssayConcept]:
        if not materials:
            raise ValueError("at least one confirmed identity material is required")
        concepts: list[EssayConcept] = []
        for index in range(brief.requested_concepts):
            material = materials[index % len(materials)]
            tip_ids = [tip.id for tip in tips[:3]]
            concepts.append(
                EssayConcept(
                    owner_id=brief.owner_id,
                    title=f"Lens {index + 1}: {material.label}",
                    metaphor=f"Use {material.label.lower()} as a lens, only if it feels true to you.",
                    outline=[
                        f"Open on one concrete moment from: {material.description[:160]}",
                        "Name the tension or question you faced without inflating the stakes.",
                        "Show one choice and its consequence using verifiable detail.",
                        "Reflect on what changed and connect it directly to the prompt.",
                    ],
                    opening_scaffold=(
                        "Writer prompt: place yourself in a specific scene from this experience. "
                        "What could you see, hear, or do, and what decision had to be made?"
                    ),
                    material_ids=[material.id],
                    advice_tip_ids=tip_ids,
                )
            )
        return concepts

    def critique(self, owner_id: UUID, prompt: str, draft: str) -> EssayCritique:
        findings: list[CritiqueFinding] = []
        lower = draft.lower()
        for phrase in self._cliches:
            start = lower.find(phrase)
            if start >= 0:
                findings.append(
                    CritiqueFinding(
                        dimension=CritiqueDimension.CLICHES,
                        severity="suggestion",
                        message=f"The phrase '{phrase}' is common and may hide your specific experience.",
                        start=start,
                        end=start + len(phrase),
                        suggestion="Replace it with a concrete action, observation, or choice only you could describe.",
                    )
                )
        sentences = [part.strip() for part in re.split(r"[.!?]+", draft) if part.strip()]
        if sentences and max(map(len, sentences)) > 280:
            findings.append(
                CritiqueFinding(
                    dimension=CritiqueDimension.NARRATIVE_FLOW,
                    severity="suggestion",
                    message="One sentence is very long and may blur the sequence of events.",
                    suggestion="Split the sentence where the action or time changes.",
                )
            )
        prompt_terms = {word for word in re.findall(r"[a-z]{5,}", prompt.lower())}
        if prompt_terms and not prompt_terms.intersection(lower.split()):
            findings.append(
                CritiqueFinding(
                    dimension=CritiqueDimension.PROMPT_ALIGNMENT,
                    severity="important",
                    message="The draft does not yet make its connection to the prompt explicit.",
                    suggestion="Add a reflection that answers the prompt in your own words.",
                )
            )
        return EssayCritique(
            owner_id=owner_id,
            findings=findings,
            strengths=["The draft gives the writer material that can be revised with specific detail."],
            questions_for_writer=[
                "Which moment in this draft could only have happened to you?",
                "What fact or interpretation should be checked before submission?",
            ],
        )


class AdviceEssayService:
    def __init__(self, repository: Module17Repository, coach: Coach | None = None) -> None:
        self.repository = repository
        self.coach = coach or DeterministicCoach()
        self.communication_coach = CommunicationCoach()

    def coach_communication(self, request: CommunicationCoachingRequest) -> CommunicationCoachingResponse:
        return self.communication_coach.coach(request)

    def ingest_source(self, source: AdviceSource) -> AdviceSource:
        if source.source_kind not in {SourceKind.USER_SUBMITTED, SourceKind.PUBLIC_API, SourceKind.PUBLIC_WEB}:
            raise ValueError("unsupported source kind")
        permission = source.permission_basis.lower()
        prohibited = ("bypass", "stolen credential", "paywall", "fake account", "rotating proxy")
        if any(marker in permission for marker in prohibited):
            raise ValueError("source permission basis describes prohibited collection")
        return self.repository.add_source(source)

    def compile_advice(self, owner_id: UUID) -> list[AdviceTip]:
        sources = self.repository.list_sources(owner_id)
        grouped: dict[str, list[AdviceSource]] = defaultdict(list)
        for source in sources:
            topic = self._topic(source.content)
            grouped[topic].append(source)
        tips: list[AdviceTip] = []
        for topic, items in sorted(grouped.items()):
            sentence = self._first_sentence(items[0].content)
            tip = AdviceTip(
                owner_id=owner_id,
                topic=topic,
                text=sentence,
                source_ids=[item.id for item in items],
                confidence=min(0.95, 0.45 + 0.1 * len(items)),
                caveats=[] if len(items) > 1 else ["Single-source advice; verify before relying on it."],
            )
            tips.append(self.repository.add_tip(tip))
        return tips

    def add_identity_material(self, material: IdentityMaterial) -> IdentityMaterial:
        if not material.user_confirmed:
            raise ValueError("identity material must be confirmed by the user")
        return self.repository.add_material(material)

    def create_concepts(self, brief: EssayBrief) -> list[EssayConcept]:
        materials = self.repository.list_materials(brief.owner_id, brief.material_ids)
        if len(materials) != len(set(brief.material_ids)):
            raise ValueError("all requested materials must exist, belong to the owner, and be confirmed")
        tips = self.repository.list_tips(brief.owner_id)
        concepts = self.coach.concepts(brief, materials, tips)
        return [self.repository.add_concept(concept) for concept in concepts]

    def critique(self, owner_id: UUID, prompt: str, draft: str) -> EssayCritique:
        if not prompt.strip() or not draft.strip():
            raise ValueError("prompt and draft are required")
        return self.coach.critique(owner_id, prompt, draft)

    @staticmethod
    def _topic(content: str) -> str:
        words = [word.lower() for word in re.findall(r"[A-Za-z][A-Za-z'-]{3,}", content)]
        stop = {"that", "this", "with", "from", "your", "have", "into", "when", "essay"}
        return next((word for word in words if word not in stop), "general")[:120]

    @staticmethod
    def _first_sentence(content: str) -> str:
        sentence = re.split(r"(?<=[.!?])\s+", content.strip(), maxsplit=1)[0]
        return sentence[:2000]
