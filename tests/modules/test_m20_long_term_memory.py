"""Chunk B tests: episodic memory, semantic memory, skill library."""
from datetime import datetime, timedelta, timezone

import pytest

from app.modules.m20_general_cognitive_worker.episodic_memory import EpisodicMemory
from app.modules.m20_general_cognitive_worker.schemas import (
    ActionRecord, EpisodeOutcome, SkillStatus,
)
from app.modules.m20_general_cognitive_worker.semantic_memory import SemanticMemory
from app.modules.m20_general_cognitive_worker.skill_library import SkillLibrary


def actions(*tools):
    return [ActionRecord(tool=t, succeeded=True) for t in tools]


def test_episode_logging_and_similarity_recall():
    mem = EpisodicMemory()
    mem.log_execution(task_id="t1", goal="write grant proposal for climate fund",
                      actions=actions("web_search", "draft_document"),
                      reflection="grant proposals need budget tables", tags=["grant"])
    mem.log_execution(task_id="t2", goal="cook pasta dinner",
                      actions=actions("recipe_search"), reflection="boil water")
    hits = mem.recall_similar("prepare a grant application with a budget", limit=2)
    assert hits and hits[0][0].task_id == "t1"
    assert hits[0][1] > 0.2
    assert mem.recall_similar("", limit=2) == []


def test_episodic_task_filter_and_successful_patterns():
    mem = EpisodicMemory()
    mem.log_execution(task_id="t1", goal="a", actions=actions("x", "y"))
    mem.log_execution(task_id="t1", goal="b", actions=actions("z"),
                      outcome=EpisodeOutcome.FAILED)
    assert len(mem.for_task("t1")) == 2
    patterns = mem.successful_patterns(min_actions=2)
    assert len(patterns) == 1 and patterns[0].goal == "a"


def test_semantic_store_query_and_graph():
    mem = SemanticMemory()
    f1 = mem.remember("Atlas module 3 writes grant proposals", kind="concept")
    f2 = mem.remember("Climate Foundation offers research grants", kind="fact")
    mem.remember("Best pizza is thin crust", kind="opinion")
    hits = mem.query("who gives out climate research grants")
    assert hits and hits[0][0].content == f2.content
    edge = mem.link(f1.id, "applies_to", f2.id)
    assert edge.relation == "applies_to"
    assert len(mem.neighbors(f1.id)) == 1
    with pytest.raises(KeyError):
        mem.link(f1.id, "rel", "nonexistent-node")


def test_knowledge_decay_and_refresh():
    mem = SemanticMemory()
    fact = mem.remember(" competitor pricing is $10/mo", decay_rate=2.0, confidence=1.0)
    past = datetime.now(timezone.utc) - timedelta(days=60)
    fact.last_confirmed_at = past
    fresh = mem.freshness(fact.id)
    assert fresh < 0.4
    due = mem.due_for_refresh(threshold=0.5)
    assert fact in due
    mem.confirm(fact.id)
    assert mem.due_for_refresh(threshold=0.5) == []
    stable = mem.remember("water boils at 100C at sea level", decay_rate=0.0)
    assert mem.freshness(stable.id) == 1.0


def test_skill_registration_versioning_and_match():
    lib = SkillLibrary()
    s1 = lib.compile("send-professional-email", "send a professional email",
                     actions("draft_email", "review_email", "send_email"))
    assert s1.version == 1 and s1.status == SkillStatus.ACTIVE
    s2 = lib.compile("send-professional-email", "send a professional email v2",
                     actions("draft_email", "send_email"))
    assert s2.version == 2
    matches = lib.match("please send a professional email to the professor")
    assert matches and matches[0].name == "send-professional-email"
    assert lib.match("") == []
    assert lib.retire("send-professional-email") is True
    assert lib.match("send a professional email") == []


def test_skill_learning_proposals_from_episodes():
    from app.modules.m20_general_cognitive_worker.episodic_memory import EpisodicMemory
    mem = EpisodicMemory()
    for i in range(3):
        mem.log_execution(task_id=f"t{i}", goal=f"research professor {i} then email",
                          actions=actions("web_search", "draft_email", "send_email"))
    lib = SkillLibrary()
    proposals = lib.propose_from_episodes(list(mem._episodes.values()), min_occurrences=2)
    assert len(proposals) == 1
    skill = proposals[0]
    assert skill.status == SkillStatus.PROPOSED
    assert skill.evidence["occurrences"] == 3
    assert [s.tool for s in skill.steps] == ["web_search", "draft_email", "send_email"]
    assert lib.propose_from_episodes(list(mem._episodes.values()), min_occurrences=2) == []
    lib.activate(skill.id)
    assert lib.find_by_name(skill.name) is not None
