"""Opt-in read-only outcome evidence from an already tenant-bound repository.

No service defaults, action execution, persistence tables or authority changes.
The caller must construct GCWRepository from authenticated tenant context. This
adapter does not authenticate callers or let a request select another tenant.

Evidence is caller/executor-reported action outcomes (the recorded succeeded flag
on stored episodes), not verified correctness of any current task. No mounted
service or HTTP integration exists for this packet; the gate is consumed in-process.
"""
from .episode_outcome_metacognition import gate_from_episodes
from .sql_repository import GCWRepository


def gate_from_repository(repository: GCWRepository, stakes_policy=None):
    if not isinstance(repository, GCWRepository):
        raise ValueError("a tenant-bound GCWRepository is required")
    gate, stats = gate_from_episodes(repository.list_episodes(), stakes_policy)
    return gate, {**stats, "repository_tenant_id": repository.tenant_id}
