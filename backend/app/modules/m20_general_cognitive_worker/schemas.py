"""Shared schemas for Module 20: the General Cognitive Worker (GCW).

The GCW is Atlas's universal intellectual agent (spec section 4). These
models are the typed vocabulary every subcomponent speaks: cognitive events
from the sensory layer, working-memory chunks, long-term memory records,
HTN plans, tool specifications, task contexts, safety artefacts, and the
transparent reasoning trace. Pydantic v2, no I/O at import time.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid4())


MODULE_ID = 20
MODULE_SLUG = "m20_general_cognitive_worker"


class Modality(str, Enum):
    TEXT = "text"
    AUDIO = "audio"
    IMAGE = "image"
    CSV = "csv"
    PDF = "pdf"
    EMAIL = "email"


class ChunkType(str, Enum):
    FACT = "fact"
    GOAL = "goal"
    HYPOTHESIS = "hypothesis"
    QUESTION = "question"


class Risk(str, Enum):
    READ = "read"
    REVERSIBLE = "reversible"
    EXTERNAL = "external"
    IRREVERSIBLE = "irreversible"


class TaskState(str, Enum):
    PENDING = "pending"
    PLANNING = "planning"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    WAITING_USER = "waiting_user"
    RUMINATING = "ruminating"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class EpisodeOutcome(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ABANDONED = "abandoned"


class SkillStatus(str, Enum):
    PROPOSED = "proposed"
    ACTIVE = "active"
    RETIRED = "retired"


class MethodSource(str, Enum):
    LIBRARY = "library"
    LEARNED = "learned"


class CognitiveEvent(BaseModel):
    """One normalized unit of perception (spec 4.2.1)."""

    model_config = ConfigDict(frozen=False)

    id: str = Field(default_factory=new_id)
    modality: Modality
    text: str
    source: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    external_id: str | None = None
    content_hash: str = ""
    confidence: float = 1.0
    observed_at: datetime = Field(default_factory=utcnow)


class MemoryChunk(BaseModel):
    """One working-memory chunk (spec 4.2.2): fact, goal, hypothesis, question."""

    id: str = Field(default_factory=new_id)
    type: ChunkType
    content: str
    confidence: float = 1.0
    source: str = ""
    salience: float = 0.5
    attention_score: float = 0.0
    created_at: datetime = Field(default_factory=utcnow)
    context_id: str | None = None


class ActionRecord(BaseModel):
    """One executed action inside an episode or plan step."""

    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    result_summary: str = ""
    succeeded: bool = True
    started_at: datetime = Field(default_factory=utcnow)
    finished_at: datetime | None = None


class Episode(BaseModel):
    """Episodic memory record (spec 4.2.3): one task execution, logged."""

    id: str = Field(default_factory=new_id)
    task_id: str
    goal: str
    start_state: str = ""
    actions: list[ActionRecord] = Field(default_factory=list)
    outcome: EpisodeOutcome = EpisodeOutcome.SUCCEEDED
    reflection: str = ""
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow)
    embedding_text: str = ""


class SemanticFact(BaseModel):
    """Semantic memory record: a fact, concept, or document summary."""

    id: str = Field(default_factory=new_id)
    content: str
    kind: str = "fact"
    provenance: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 1.0
    decay_rate: float = 0.0
    created_at: datetime = Field(default_factory=utcnow)
    last_confirmed_at: datetime = Field(default_factory=utcnow)


class KnowledgeEdge(BaseModel):
    """Knowledge-graph edge linking two memory nodes (spec 4.2.3)."""

    id: str = Field(default_factory=new_id)
    from_id: str
    relation: str
    to_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class PlanNode(BaseModel):
    """One node in an HTN decomposition DAG."""

    id: str = Field(default_factory=new_id)
    title: str
    kind: str = "task"
    tool: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)
    risk: Risk = Risk.READ
    state: TaskState = TaskState.PENDING
    max_attempts: int = 3
    attempts: int = 0
    approval_id: str | None = None
    result_summary: str = ""


class HTNMethod(BaseModel):
    """A reusable decomposition method (spec 4.2.4)."""

    id: str = Field(default_factory=new_id)
    name: str
    goal_pattern: str
    subtasks: list[PlanNode] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    source: MethodSource = MethodSource.LIBRARY
    times_used: int = 0
    success_rate: float = 0.0


class Skill(BaseModel):
    """Procedural memory record (spec 4.2.3): a compiled action sequence."""

    id: str = Field(default_factory=new_id)
    name: str
    goal_pattern: str
    steps: list[ActionRecord] = Field(default_factory=list)
    version: int = 1
    status: SkillStatus = SkillStatus.PROPOSED
    evidence: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utcnow)


class ToolSpec(BaseModel):
    """Tool registry entry (spec 4.2.5)."""

    name: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    preconditions: list[str] = Field(default_factory=list)
    risk: Risk = Risk.READ
    capabilities: list[str] = Field(default_factory=list)
    timeout_seconds: int = 60
    max_retries: int = 2


class TaskContext(BaseModel):
    """One concurrent project context (spec 4.2.6)."""

    id: str = Field(default_factory=new_id)
    goal: str
    state: TaskState = TaskState.PENDING
    importance: int = 3
    deadline: datetime | None = None
    plan: list[PlanNode] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    wm_partition: str = ""
    standup_notes: list[str] = Field(default_factory=list)


class EmotionalState(BaseModel):
    """Internal emotional-state vector (spec 4.2.8). Biases tone only."""

    valence: float = 0.0
    arousal: float = 0.0
    confidence: float = 0.5
    overridden: bool = False
    override_tone: str | None = None


class Uncertainty(BaseModel):
    """Explicit uncertainty expression (spec 4.2.8)."""

    confidence: float
    rationale: str = ""
    targeted_questions: list[str] = Field(default_factory=list)
    high_stakes: bool = False


class TraceEntry(BaseModel):
    """Transparent reasoning-stream entry: inspectable by the user."""

    id: str = Field(default_factory=new_id)
    task_id: str | None = None
    phase: str
    detail: str
    policy_basis: str = ""
    created_at: datetime = Field(default_factory=utcnow)


class Retrospective(BaseModel):
    """Post-task self-critique (spec 4.2.7), embedded for later retrieval."""

    id: str = Field(default_factory=new_id)
    task_id: str
    went_well: list[str] = Field(default_factory=list)
    went_poorly: list[str] = Field(default_factory=list)
    lessons: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow)


class Scratchpad(BaseModel):
    """Structured-reasoning scratchpad (spec 4.2.7). Resumable."""

    id: str = Field(default_factory=new_id)
    task_id: str
    chain_of_thought: list[str] = Field(default_factory=list)
    hypotheses: list[str] = Field(default_factory=list)
    decision_matrix: list[dict[str, Any]] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=utcnow)


class ApprovalGateRequest(BaseModel):
    """Approval request handed to Module 0 through the gate protocol."""

    id: str = Field(default_factory=new_id)
    module_id: int = MODULE_ID
    task_id: str | None = None
    action_type: str
    summary: str
    payload: dict[str, Any] = Field(default_factory=dict)
    risk: Risk = Risk.EXTERNAL
    expires_at: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow)


class ApprovalGateDecision(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    PENDING = "pending"


class Budget(BaseModel):
    """Per-run resource budget (spec 5: cost management)."""

    seconds: float = 300.0
    tokens: int = 100_000
    money_usd: float = 0.0

class GoalIn(BaseModel):
    goal: str = Field(min_length=3, max_length=8000)
    constraints: dict[str, Any] = Field(default_factory=dict)
    budget: dict[str, float] = Field(default_factory=lambda: {"seconds": 900, "tokens": 100000, "money": 0})
