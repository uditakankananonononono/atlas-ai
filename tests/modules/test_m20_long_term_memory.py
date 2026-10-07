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


def test_no_unfitted_knowledge_freshness_or_refresh_prediction():
    mem = SemanticMemory()
    fact = mem.remember(" competitor pricing is $10/mo", decay_rate=2.0, confidence=1.0)
    past = datetime.now(timezone.utc) - timedelta(days=60)
    fact.last_confirmed_at = past
    mem.store(fact)
    fresh = mem.freshness(fact.id)
    assert fresh is None
    due = mem.due_for_refresh(threshold=0.5)
    assert due == []
    mem.confirm(fact.id)
    assert mem.due_for_refresh(threshold=0.5) == []
    stable = mem.remember("water boils at 100C at sea level", decay_rate=0.0)
    assert mem.freshness(stable.id) is None


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


def test_signature_proposals_exclude_failed_actions_outcomes_and_duplicates():
 from app.modules.m20_general_cognitive_worker.schemas import Episode,EpisodeOutcome
 lib=SkillLibrary()
 good=Episode(task_id='a',goal='fixture',actions=actions('read','summarize'),outcome=EpisodeOutcome.SUCCEEDED)
 failed=Episode(task_id='b',goal='fixture',actions=actions('read','summarize'),outcome=EpisodeOutcome.FAILED)
 bad_action=Episode(task_id='c',goal='fixture',actions=actions('read','summarize'),outcome=EpisodeOutcome.SUCCEEDED)
 bad_action.actions[-1].succeeded=False
 assert lib.propose_from_episodes([good,good,failed,bad_action],min_occurrences=2)==[]
 good2=good.model_copy(deep=True,update={'id':'distinct','task_id':'d'})
 proposal=lib.propose_from_episodes([good,good2,failed,bad_action],min_occurrences=2)[0]
 assert proposal.evidence['occurrences']==2
 assert set(proposal.evidence['episode_ids'])=={good.id,good2.id}
 assert proposal.evidence['generalizable_skill_verified'] is False
 good.actions[0].arguments['changed']=True
 assert 'changed' not in proposal.steps[0].arguments


def test_episode_snapshots_detached_from_input_and_all_readbacks():
 from app.modules.m20_general_cognitive_worker.episodic_memory import EpisodicMemory
 from app.modules.m20_general_cognitive_worker.schemas import Episode,EpisodeOutcome
 mem=EpisodicMemory();source=Episode(task_id='t',goal='fixture',actions=actions('a','b'),outcome=EpisodeOutcome.SUCCEEDED)
 stored=mem.record(source)
 source.goal='changed';stored.actions[0].arguments['tampered']=True
 for view in (mem.get(stored.id),mem.for_task('t')[0],mem.recall_similar('fixture')[0][0],mem.successful_patterns()[0]):
  view.outcome=EpisodeOutcome.FAILED;view.actions[0].arguments['tampered']=True
 original=mem.get(stored.id)
 assert original.goal=='fixture' and original.outcome==EpisodeOutcome.SUCCEEDED
 assert original.actions[0].arguments=={}
 bad=original.model_copy(deep=True,update={'id':'bad'});bad.actions[0].succeeded=False;mem.record(bad)
 assert [e.id for e in mem.successful_patterns()]==[stored.id]


def test_semantic_fact_and_graph_views_are_detached():
 mem=SemanticMemory();a=mem.remember('fixture a',provenance={'source':'supplied'});b=mem.remember('fixture b')
 a.content='caller';a.provenance['source']='changed'
 for view in (mem.get(a.id),mem.query('fixture a')[0][0]):
  view.content='readback';view.provenance['source']='changed'
 assert mem.get(a.id).content=='fixture a'
 assert mem.get(a.id).provenance=={'source':'supplied'}
 metadata={'label':'supplied'};edge=mem.link(a.id,'related',b.id,metadata=metadata)
 metadata['label']='caller';edge.metadata['label']='returned';mem.neighbors(a.id)[0].metadata['label']='view'
 assert mem.neighbors(a.id)[0].metadata=={'label':'supplied'}


class ToggleFailEmbedder:
    dimensions = 8
    fail = False
    def embed(self, text):
        if self.fail:
            raise RuntimeError("embedding unavailable")
        return [1.0] + [0.0] * 7


@pytest.mark.parametrize("kind", ["semantic", "episodic"])
def test_memory_embedding_failure_does_not_publish_content(kind):
    from app.modules.m20_general_cognitive_worker.schemas import SemanticFact, Episode
    embedder = ToggleFailEmbedder()
    memory = SemanticMemory(embedder) if kind == "semantic" else EpisodicMemory(embedder)
    old = SemanticFact(content="old") if kind == "semantic" else Episode(task_id="t", goal="old")
    publish = memory.store if kind == "semantic" else memory.record
    publish(old)
    before = memory.get(old.id)
    new = old.model_copy(deep=True)
    if kind == "semantic":
        new.content = "new"
    else:
        new.goal = "new"
        new.embedding_text = "new"
    embedder.fail = True
    with pytest.raises(RuntimeError):
        publish(new)
    assert memory.get(old.id) == before
    fresh = SemanticFact(content="fresh") if kind == "semantic" else Episode(task_id="fresh", goal="fresh")
    with pytest.raises(RuntimeError):
        publish(fresh)
    assert memory.get(fresh.id) is None


def test_cosine_large_finite_vectors_keep_exact_direction():
    from app.modules.m20_general_cognitive_worker.embeddings import cosine_similarity
    assert cosine_similarity([1e308, 1e308], [1e308, 1e308]) == pytest.approx(1)
    assert cosine_similarity([1e-300, 0], [1e-300, 0]) == pytest.approx(1)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), True])
def test_cosine_invalid_components_rejected(value):
    from app.modules.m20_general_cognitive_worker.embeddings import cosine_similarity
    with pytest.raises(ValueError):
        cosine_similarity([value, 1], [1, 0])


def test_cosine_scaled_independent_numpy_direction():
    import numpy as np
    from app.modules.m20_general_cognitive_worker.embeddings import cosine_similarity
    a = [3e200, -4e200, 2e200]
    b = [-2e-200, 5e-200, 1e-200]
    aa = np.array([3, -4, 2], dtype=float)
    bb = np.array([-2, 5, 1], dtype=float)
    expected = np.dot(aa, bb) / np.linalg.norm(aa) / np.linalg.norm(bb)
    assert cosine_similarity(a, b) == pytest.approx(expected)
    assert cosine_similarity([1e308, 0], [-1e-300, 0]) == pytest.approx(-1)


def test_skill_versions_do_not_reset_after_retirement():
    library = SkillLibrary()
    first = library.compile("fixture", "fixture", actions("a", "b"))
    library.retire("fixture")
    second = library.compile("fixture", "fixture", actions("a", "b"))
    assert second.version == first.version + 1


def test_skill_activation_has_one_active_same_name_revision():
    library = SkillLibrary()
    first = library.compile("fixture", "fixture", actions("a", "b"))
    second = library.compile("fixture", "fixture", actions("a", "b"))
    library.activate(first.id)
    active = library.list(status=SkillStatus.ACTIVE)
    assert [s.id for s in active] == [first.id]
