"""Chunk A tests: working memory + attention."""
import pytest

from app.modules.m20_general_cognitive_worker.schemas import ChunkType, MemoryChunk
from app.modules.m20_general_cognitive_worker.working_memory import (
    HeuristicAttentionController, WorkingMemory,
)


def make_chunk(content, type=ChunkType.FACT, salience=0.5, confidence=1.0):
    return MemoryChunk(type=type, content=content, salience=salience, confidence=confidence)


def test_capacity_enforced_weakest_evicted():
    wm = WorkingMemory(capacity=3)
    goal = "climate grant research"
    wm.put(make_chunk("climate grant deadline is Friday", salience=0.9), active_goal=goal)
    wm.put(make_chunk("climate data on emissions", salience=0.8), active_goal=goal)
    wm.put(make_chunk("pizza toppings list", salience=0.0, confidence=0.1), active_goal=goal)
    wm.put(make_chunk("climate policy updates", salience=0.7), active_goal=goal)
    assert len(wm) == 3
    contents = [c.content for c in wm.focused()]
    assert "pizza toppings list" not in contents


def test_attention_scores_relevant_higher():
    attn = HeuristicAttentionController()
    goal = "write the market analysis report"
    relevant = make_chunk("market analysis shows growth", type=ChunkType.FACT)
    irrelevant = make_chunk("unrelated cooking note", type=ChunkType.FACT)
    assert attn.score(relevant, goal) > attn.score(irrelevant, goal)


def test_partitions_isolated_and_clearable():
    wm = WorkingMemory(capacity=50)
    wm.put(make_chunk("context A note"), partition="ctx-a")
    wm.put(make_chunk("context B note"), partition="ctx-b")
    assert len(wm.focused(partition="ctx-a")) == 1
    cleared = wm.clear_partition("ctx-a")
    assert cleared == 1
    assert len(wm.focused(partition="ctx-a")) == 0
    assert len(wm.focused(partition="ctx-b")) == 1


def test_partition_capacity_is_per_context():
    wm = WorkingMemory(capacity=2)
    for i in range(4):
        wm.put(make_chunk(f"a{i}"), partition="ctx-a")
    for i in range(3):
        wm.put(make_chunk(f"b{i}"), partition="ctx-b")
    assert len(wm.focused(partition="ctx-a")) == 2
    assert len(wm.focused(partition="ctx-b")) == 2


def test_context_render_and_refresh():
    wm = WorkingMemory(capacity=10)
    goal = "prepare pitch deck"
    wm.put(make_chunk("pitch deck needs 10 slides", ChunkType.GOAL, salience=0.9), active_goal=goal, partition="p")
    wm.put(make_chunk("random noise", salience=0.1, confidence=0.1), active_goal=goal, partition="p")
    wm.refresh_attention(goal, partition="p")
    rendered = wm.context(partition="p")
    assert "[goal | conf=1.00] pitch deck needs 10 slides" in rendered
    focused = wm.focused(partition="p")
    assert focused[0].content.startswith("pitch deck")


def test_remove_and_get():
    wm = WorkingMemory()
    chunk = wm.put(make_chunk("x"))
    assert wm.get(chunk.id) is not None
    assert wm.remove(chunk.id) is True
    assert wm.remove(chunk.id) is False
    with pytest.raises(ValueError):
        WorkingMemory(capacity=0)


def test_reused_chunk_id_cannot_leak_other_partition_content():
 wm=WorkingMemory();a=make_chunk('a private');wm.put(a,partition='a')
 b=a.model_copy(deep=True,update={'content':'b private'})
 with pytest.raises(ValueError,match='different partition'):wm.put(b,partition='b')
 assert 'b private' not in wm.context(partition='a') and wm.focused(partition='b')==[]
 a.content='caller mutation'
 assert wm.get(a.id).content=='a private'
 returned=wm.get(a.id);returned.content='readback mutation'
 assert wm.get(a.id).content=='a private'
 wm.focused(partition='a')[0].context_id='b'
 assert wm.get(a.id).context_id=='a'


def test_default_partition_capacity_does_not_evict_other_tasks():
 wm=WorkingMemory(capacity=1)
 wm.put(make_chunk('a'),partition='a');wm.put(make_chunk('b'),partition='b')
 wm.put(make_chunk('default1'));wm.put(make_chunk('default2'))
 assert len(wm.focused(partition='a'))==len(wm.focused(partition='b'))==1
 assert len(wm.focused(partition=''))==1
 assert len(wm)==3


@pytest.mark.parametrize('score', [float('nan'), float('inf'), -0.1, 1.1, True, '0.5'])
def test_attention_invalid_scores_reject_without_publication(score):
    class SuppliedAttention:
        def score(self, chunk, active_goal):
            return score
    wm = WorkingMemory(attention=SuppliedAttention())
    with pytest.raises(ValueError):
        wm.put(make_chunk('fixture'))
    assert len(wm) == 0


def test_capacity_scoring_failure_leaves_original_partition_unchanged():
    class FailingAttention:
        fail = False
        def score(self, chunk, active_goal):
            if self.fail and chunk.content == 'original':
                raise RuntimeError('fixture scoring failure')
            return 0.5
    attention = FailingAttention()
    wm = WorkingMemory(capacity=1, attention=attention)
    original = wm.put(make_chunk('original'), partition='p')
    attention.fail = True
    with pytest.raises(RuntimeError, match='fixture scoring failure'):
        wm.put(make_chunk('new'), partition='p')
    assert wm.focused(partition='p') == [original]


def test_refresh_scoring_failure_does_not_publish_partial_scores():
    class FailingAttention:
        fail = False
        def score(self, chunk, active_goal):
            if self.fail and chunk.content == 'second':
                raise RuntimeError('fixture refresh failure')
            return 0.9 if self.fail else 0.5
    attention = FailingAttention()
    wm = WorkingMemory(attention=attention)
    wm.put(make_chunk('first')); wm.put(make_chunk('second'))
    before = wm.focused()
    attention.fail = True
    with pytest.raises(RuntimeError):
        wm.refresh_attention('fixture')
    assert wm.focused() == before


def test_attention_callback_cannot_edit_published_chunk_content():
    class MutatingAttention:
        def score(self, chunk, active_goal):
            chunk.content = 'callback edit'
            return 0.5
    wm = WorkingMemory(attention=MutatingAttention())
    stored = wm.put(make_chunk('original'))
    assert stored.content == 'original'
    wm.refresh_attention('fixture')
    assert wm.get(stored.id).content == 'original'
