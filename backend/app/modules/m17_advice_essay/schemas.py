"""Typed contracts for Module 17.

The module accepts only user-owned or lawfully public material. It coaches the
user from their own experiences and never represents generated prose as a
submission-ready essay authored by the user.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class SourceKind(str, Enum):
    USER_SUBMITTED = "user_submitted"
    PUBLIC_API = "public_api"
    PUBLIC_WEB = "public_web"


class MediaKind(str, Enum):
    TEXT = "text"
    AUDIO_TRANSCRIPT = "audio_transcript"
    VIDEO_TRANSCRIPT = "video_transcript"


class AdviceSource(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    owner_id: UUID
    source_kind: SourceKind
    media_kind: MediaKind = MediaKind.TEXT
    platform: str = Field(min_length=1, max_length=80)
    canonical_url: str | None = Field(default=None, max_length=2048)
    creator: str | None = Field(default=None, max_length=200)
    content: str = Field(min_length=1, max_length=100_000)
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    permission_basis: str = Field(min_length=3, max_length=500)

    @model_validator(mode="after")
    def public_sources_need_a_url(self) -> "AdviceSource":
        if self.source_kind != SourceKind.USER_SUBMITTED and not self.canonical_url:
            raise ValueError("public sources require a canonical_url for provenance")
        return self


class AdviceTip(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    owner_id: UUID
    topic: str = Field(min_length=1, max_length=120)
    text: str = Field(min_length=1, max_length=2000)
    source_ids: list[UUID] = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    caveats: list[str] = Field(default_factory=list)


class IdentityMaterial(BaseModel):
    """A user-confirmed experience, value, trait, or writing sample."""

    id: UUID = Field(default_factory=uuid4)
    owner_id: UUID
    label: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=5000)
    user_confirmed: bool = False
    tags: list[str] = Field(default_factory=list, max_length=30)


class EssayBrief(BaseModel):
    owner_id: UUID
    prompt: str = Field(min_length=1, max_length=5000)
    word_limit: int = Field(ge=50, le=5000)
    material_ids: list[UUID] = Field(min_length=1)
    requested_concepts: int = Field(default=5, ge=1, le=10)


class EssayConcept(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    owner_id: UUID
    title: str = Field(min_length=1, max_length=200)
    metaphor: str = Field(min_length=1, max_length=500)
    outline: list[str] = Field(min_length=3, max_length=12)
    opening_scaffold: str = Field(min_length=1, max_length=1200)
    material_ids: list[UUID] = Field(min_length=1)
    advice_tip_ids: list[UUID] = Field(default_factory=list)
    coaching_notice: str = (
        "Coaching scaffold only. Verify every fact and rewrite in your own words "
        "before using it in an application."
    )


class CritiqueDimension(str, Enum):
    NARRATIVE_FLOW = "narrative_flow"
    GRAMMAR = "grammar"
    PROMPT_ALIGNMENT = "prompt_alignment"
    SPECIFICITY = "specificity"
    CLICHES = "cliches"
    VOICE_CONSISTENCY = "voice_consistency"


class CritiqueFinding(BaseModel):
    dimension: CritiqueDimension
    severity: str = Field(pattern="^(info|suggestion|important)$")
    message: str = Field(min_length=1, max_length=1200)
    start: int | None = Field(default=None, ge=0)
    end: int | None = Field(default=None, ge=0)
    suggestion: str | None = Field(default=None, max_length=1200)

    @model_validator(mode="after")
    def valid_span(self) -> "CritiqueFinding":
        if self.start is not None and self.end is not None and self.end < self.start:
            raise ValueError("end must be greater than or equal to start")
        return self


class EssayCritique(BaseModel):
    owner_id: UUID
    findings: list[CritiqueFinding]
    strengths: list[str]
    questions_for_writer: list[str]
    authorship_notice: str = (
        "Feedback is advisory. The writer remains responsible for the ideas, facts, "
        "wording, and final submission."
    )


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    owner_id: UUID
    action: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CommunicationSkill(str, Enum):
    PERSUASIVE_WRITING = "persuasive_writing"
    NEGOTIATION_TACTICS = "negotiation_tactics"
    CONFLICT_RESOLUTION = "conflict_resolution"
    MEDIATION = "mediation"
    ACTIVE_LISTENING = "active_listening"
    EMPATHETIC_RESPONSE = "empathetic_response"
    EMOTIONAL_INTELLIGENCE = "emotional_intelligence"
    SOCIAL_CALIBRATION = "social_calibration"
    CULTURAL_SENSITIVITY = "cultural_sensitivity"
    CROSS_CULTURAL_COMMUNICATION = "cross_cultural_communication"
    DIPLOMATIC_LANGUAGE = "diplomatic_language"
    ASSERTIVENESS = "assertiveness"
    BOUNDARY_SETTING = "boundary_setting"
    DIFFICULT_CONVERSATIONS = "difficult_conversations"
    FEEDBACK_DELIVERY = "feedback_delivery"
    FEEDBACK_RECEPTION = "feedback_reception"
    PUBLIC_SPEAKING = "public_speaking"
    PRESENTATION_DESIGN = "presentation_design"
    STORYTELLING = "storytelling"
    RAPPORT_BUILDING = "rapport_building"
    NETWORKING = "networking"
    MENTORSHIP = "mentorship"
    COACHING = "coaching"
    TEACHING = "teaching"
    EXPLAINING_COMPLEX_IDEAS = "explaining_complex_ideas"
    ANALOGIES = "analogies"
    METAPHORS = "metaphors"
    EXAMPLES = "examples"
    SCAFFOLDING = "scaffolding"
    QUESTIONING = "questioning"
    SOCRATIC_METHOD = "socratic_method"


class CommunicationCoachingRequest(BaseModel):
    owner_id: UUID
    skill: CommunicationSkill
    context: str = Field(min_length=1, max_length=10_000)
    goal: str = Field(min_length=1, max_length=1000)
    audience: str = Field(min_length=1, max_length=500)
    draft: str | None = Field(default=None, max_length=50_000)
    known_facts: list[str] = Field(default_factory=list, max_length=50)
    cultural_context: list[str] = Field(default_factory=list, max_length=30)
    constraints: list[str] = Field(default_factory=list, max_length=30)
    student_authored_work: bool = False


class CoachingObservation(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    detail: str = Field(min_length=1, max_length=1200)
    evidence: str | None = Field(default=None, max_length=1200)


class CommunicationCoachingResponse(BaseModel):
    owner_id: UUID
    skill: CommunicationSkill
    observations: list[CoachingObservation]
    questions: list[str]
    rehearsal_steps: list[str]
    draft_feedback: list[str]
    review_required: bool = True
    external_action_proposed: bool = False
    caveats: list[str] = Field(default_factory=list)
    authorship_notice: str | None = None
    evaluation: dict[str, Any] = Field(default_factory=dict)
    uncertainty: dict[str, Any] = Field(default_factory=dict)


class CollaborationSkill(str, Enum):
    FACILITATION = "facilitation"
    BRAINSTORMING = "brainstorming"
    CONSENSUS_BUILDING = "consensus_building"
    VOTING_DESIGN = "voting_design"
    DELIBERATION = "deliberation"
    DEBATE = "debate"
    RHETORIC = "rhetoric"
    LOGIC = "logic"
    FALLACY_DETECTION = "fallacy_detection"
    STEELMANNING = "steelmanning"
    CHARITABLE_INTERPRETATION = "charitable_interpretation"
    PRINCIPLE_OF_CHARITY = "principle_of_charity"
    STEEL_MANNING = "steel_manning"
    DEVILS_ADVOCACY = "devils_advocacy"
    RED_TEAMING = "red_teaming"
    WAR_GAMING = "war_gaming"
    TABLETOP_EXERCISES = "tabletop_exercises"
    SIMULATION = "simulation"
    ROLE_PLAYING = "role_playing"
    PERSPECTIVE_TAKING = "perspective_taking"
    THEORY_OF_MIND = "theory_of_mind"
    MENTALIZING = "mentalizing"
    EMPATHY = "empathy"
    COMPASSION = "compassion"
    ALTRUISM = "altruism"
    PROSOCIAL_BEHAVIOR = "prosocial_behavior"
    COOPERATION = "cooperation"
    COLLABORATION = "collaboration"
    TEAMWORK = "teamwork"
    TEAM_BUILDING = "team_building"


class CollaborationCoachingRequest(BaseModel):
    owner_id: UUID
    skill: CollaborationSkill
    context: str = Field(min_length=1, max_length=10_000)
    objective: str = Field(min_length=1, max_length=1000)
    participants: list[str] = Field(default_factory=list, max_length=100)
    proposal_or_argument: str | None = Field(default=None, max_length=50_000)
    known_facts: list[str] = Field(default_factory=list, max_length=100)
    constraints: list[str] = Field(default_factory=list, max_length=50)
    student_authored_work: bool = False


class CollaborationCoachingResponse(BaseModel):
    owner_id: UUID
    skill: CollaborationSkill
    agenda: list[str]
    questions: list[str]
    critique: list[str]
    safeguards: list[str]
    review_required: bool = True
    external_action_proposed: bool = False
    authorship_notice: str | None = None
    evaluation: dict[str, Any] = Field(default_factory=dict)
    uncertainty: dict[str, Any] = Field(default_factory=dict)


class TrustWellbeingSkill(str, Enum):
    TRUST_BUILDING = "trust_building"
    PSYCHOLOGICAL_SAFETY = "psychological_safety"
    INCLUSION = "inclusion"
    DIVERSITY = "diversity"
    EQUITY = "equity"
    JUSTICE = "justice"
    ETHICS = "ethics"
    INTEGRITY = "integrity"
    HONESTY = "honesty"
    TRANSPARENCY = "transparency"
    ACCOUNTABILITY = "accountability"
    RELIABILITY = "reliability"
    DEPENDABILITY = "dependability"
    CONSISTENCY = "consistency"
    PATIENCE = "patience"
    TOLERANCE = "tolerance"
    FORGIVENESS = "forgiveness"
    GRATITUDE = "gratitude"
    HUMILITY = "humility"
    CURIOSITY = "curiosity"
    OPEN_MINDEDNESS = "open_mindedness"
    INTELLECTUAL_HUMILITY = "intellectual_humility"
    WISDOM = "wisdom"
    PRUDENCE = "prudence"
    TEMPERANCE = "temperance"
    COURAGE = "courage"
    RESILIENCE = "resilience"
    GRIT = "grit"
    SELF_CONTROL = "self_control"
    DELAYED_GRATIFICATION = "delayed_gratification"
    IMPULSE_CONTROL = "impulse_control"
    EMOTIONAL_REGULATION = "emotional_regulation"
    STRESS_MANAGEMENT = "stress_management"
    COPING_STRATEGIES = "coping_strategies"
    MINDFULNESS = "mindfulness"
    MEDITATION = "meditation"
    RELAXATION = "relaxation"
    SLEEP_HYGIENE = "sleep_hygiene"
    EXERCISE = "exercise"


class TrustWellbeingCoachingRequest(BaseModel):
    owner_id: UUID
    skill: TrustWellbeingSkill
    context: str = Field(min_length=1, max_length=10_000)
    goal: str = Field(min_length=1, max_length=1000)
    preferences: list[str] = Field(default_factory=list, max_length=50)
    constraints: list[str] = Field(default_factory=list, max_length=50)
    reflection: str | None = Field(default=None, max_length=50_000)
    student_authored_work: bool = False


class TrustWellbeingCoachingResponse(BaseModel):
    owner_id: UUID
    skill: TrustWellbeingSkill
    reflection_questions: list[str]
    low_risk_steps: list[str]
    safeguards: list[str]
    escalation_boundary: str
    review_required: bool = True
    external_action_proposed: bool = False
    evaluation: dict[str, Any] = Field(default_factory=dict)
    uncertainty: dict[str, Any] = Field(default_factory=dict)
    authorship_notice: str | None = None
