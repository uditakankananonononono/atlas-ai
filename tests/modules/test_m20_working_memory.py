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
