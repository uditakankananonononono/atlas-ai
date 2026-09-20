"""FastAPI routes for the GCW (spec 4.3 dashboard surface).

Mounted by the integrator at /api/modules/20. The service instance is
injected with bind_service() (or FastAPI dependency override in tests).
All externally visible effects still flow through Module 0 inside the
service - these endpoints only expose control and inspection.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .safety import ApprovalGateDecision
from .schemas import Risk, ToolSpec

router = APIRouter(prefix="/api/modules/20", tags=["m20_general_cognitive_worker"])

_service = None


def bind_service(service) -> None:
    global _service
    _service = service


def get_service():
    if _service is None:
        raise HTTPException(status_code=503, detail="GCW service not bound yet")
    return _service


class GoalRequest(BaseModel):
    goal: str = Field(min_length=1)
    importance: int = Field(default=3, ge=1, le=5)
    deadline: datetime | None = None
    run_immediately: bool = True


class TextIngestRequest(BaseModel):
    text: str = Field(min_length=1)
    source: str = "api"
    external_id: str | None = None
    context_id: str | None = None


class EmailIngestRequest(BaseModel):
    subject: str
    body: str
    sender: str
    external_id: str | None = None
    context_id: str | None = None


class ResumeRequest(BaseModel):
    node_id: str
    approved: bool


class RememberRequest(BaseModel):
    content: str = Field(min_length=1)
    kind: str = "fact"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    decay_rate: float = Field(default=0.0, ge=0.0)


class RetrospectiveRequest(BaseModel):
    went_well: list[str] = []
    went_poorly: list[str] = []
    lessons: list[str] = []


@router.post("/goals", status_code=201)
def submit_goal(request: GoalRequest) -> dict[str, Any]:
    service = get_service()
    context = service.submit_goal(
        request.goal, importance=request.importance,
        deadline=request.deadline, run_immediately=request.run_immediately,
    )
    return {"task_id": context.id, "state": context.state.value,
            "steps": len(context.plan)}


@router.get("/tasks")
def list_tasks() -> list[dict[str, Any]]:
    service = get_service()
    return [
        {"id": c.id, "goal": c.goal, "state": c.state.value,
         "importance": c.importance, "deadline": c.deadline,
         "steps_total": len(c.plan),
         "steps_done": sum(1 for n in c.plan if n.state.value == "succeeded")}
        for c in service.scheduler._contexts.values()
    ]


@router.get("/tasks/{task_id}")
def get_task(task_id: str) -> dict[str, Any]:
    service = get_service()
    context = service.scheduler.get(task_id)
    if context is None:
        raise HTTPException(status_code=404, detail="task not found")
    return {
        "id": context.id, "goal": context.goal, "state": context.state.value,
        "plan": [n.model_dump(mode="json") for n in context.plan],
        "working_memory": service.working_memory.context(partition=context.id),
    }


@router.post("/tasks/{task_id}/resume")
def resume_task(task_id: str, request: ResumeRequest) -> dict[str, Any]:
    service = get_service()
    context = service.resume(task_id, request.node_id, approved=request.approved)
    if context is None:
        raise HTTPException(status_code=404, detail="task not found")
    return {"task_id": context.id, "state": context.state.value}


@router.post("/tasks/{task_id}/ruminate")
def ruminate_task(task_id: str) -> dict[str, Any]:
    service = get_service()
    result = service.ruminate(task_id)
    if result is None:
        raise HTTPException(status_code=404, detail="task not found")
    return result


@router.post("/tasks/{task_id}/retrospective")
def close_task(task_id: str, request: RetrospectiveRequest) -> dict[str, str]:
    service = get_service()
    if service.scheduler.get(task_id) is None:
        raise HTTPException(status_code=404, detail="task not found")
    service.close_task(
        task_id, went_well=request.went_well,
        went_poorly=request.went_poorly, lessons=request.lessons,
    )
    return {"status": "closed"}


@router.post("/ingest/text", status_code=201)
def ingest_text(request: TextIngestRequest) -> dict[str, Any]:
    service = get_service()
    event = service.sensory.ingest_text(
        request.text, source=request.source, external_id=request.external_id,
    )
    if event is None:
        return {"ingested": False, "reason": "duplicate"}
    service.ingest(event, context_id=request.context_id)
    return {"ingested": True, "event_id": event.id}


@router.post("/ingest/email", status_code=201)
def ingest_email(request: EmailIngestRequest) -> dict[str, Any]:
    service = get_service()
    event = service.sensory.ingest_email(
        subject=request.subject, body=request.body, sender=request.sender,
        external_id=request.external_id,
    )
    if event is None:
        return {"ingested": False, "reason": "duplicate"}
    service.ingest(event, context_id=request.context_id)
    return {"ingested": True, "event_id": event.id}


@router.post("/memory/facts", status_code=201)
def remember_fact(request: RememberRequest) -> dict[str, str]:
    service = get_service()
    fact = service.semantic.remember(
        request.content, kind=request.kind,
        confidence=request.confidence, decay_rate=request.decay_rate,
    )
    return {"fact_id": fact.id}


@router.get("/memory/facts")
def query_facts(query: str = "", limit: int = 5) -> list[dict[str, Any]]:
    service = get_service()
    if not query:
        raise HTTPException(status_code=400, detail="query required")
    return [
        {"content": f.content, "kind": f.kind, "confidence": f.confidence, "score": s}
        for f, s in service.semantic.query(query, limit=limit)
    ]


@router.get("/memory/episodes")
def recall_episodes(query: str = "", limit: int = 5) -> list[dict[str, Any]]:
    service = get_service()
    if not query:
        raise HTTPException(status_code=400, detail="query required")
    return [
        {"goal": e.goal, "outcome": e.outcome.value, "reflection": e.reflection, "score": s}
        for e, s in service.episodic.recall_similar(query, limit=limit)
    ]


@router.get("/skills")
def list_skills() -> list[dict[str, Any]]:
    service = get_service()
    return [
        {"id": s.id, "name": s.name, "version": s.version, "status": s.status.value}
        for s in service.skills.list()
    ]


@router.get("/tools")
def list_tools() -> list[dict[str, Any]]:
    return get_service().tools.describe()


@router.get("/standup")
def standup() -> dict[str, str]:
    return {"standup": get_service().standup()}


@router.get("/traces")
def traces(task_id: str | None = None) -> list[dict[str, Any]]:
    return [t.model_dump(mode="json") for t in get_service().traces(task_id=task_id)]


@router.get("/health")
def health() -> dict[str, Any]:
    return get_service().supervise()
