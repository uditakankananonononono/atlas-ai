"""Row 1960 Graph-of-Thought: executable search controller over thought graphs.

This is the algorithmic core of the named capability (graph-of-thoughts
reasoning): thoughts are nodes, typed operations build the graph (expansion,
aggregation, refinement), a supplied scorer ranks thoughts, and beam
keep-best plus depth/node caps bound the search. The language-model boundary
is explicit: proposal and scoring functions are injected pure callables; this
module never claims a bundled LLM and performs no external calls.
Deterministic for deterministic injected functions (insertion-ordered ids,
stable tie-breaks).

Precise bounds: max_depth caps EXPANSION depth only. Aggregation, when
enabled, adds exactly one node one layer beyond the deepest beam node.
Refinement adds one layer per budget step beyond the node it refines.
max_nodes caps total nodes across all kinds.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Iterable
import math

KINDS = ("root", "expansion", "aggregation", "refinement")


@dataclass
class ThoughtNode:
    id: int
    text: str
    parents: tuple[int, ...]
    depth: int
    kind: str
    score: float | None = None


def _int(value, name, lo, hi):
    if isinstance(value, bool) or not isinstance(value, int) or not lo <= value <= hi:
        raise ValueError(f"{name} must be an integer in [{lo},{hi}]")
    return value


def _score(scorer, node: ThoughtNode, path_texts) -> float:
    value = scorer(node, list(path_texts))
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("scorer must return a finite number in [0,1]")
    try:
        result = float(value)  # huge ints raise OverflowError on conversion
    except (OverflowError, ValueError):
        raise ValueError("scorer must return a finite number in [0,1]") from None
    if not math.isfinite(result) or not 0 <= result <= 1:
        raise ValueError("scorer must return a finite number in [0,1]")
    return result


def _propose(proposer, node_texts, k, kind):
    proposals = proposer(list(node_texts), k, kind)
    if not isinstance(proposals, list) or len(proposals) > k:
        raise ValueError(f"proposer must return at most {k} proposals")
    for proposal in proposals:
        if not isinstance(proposal, str) or not proposal.strip():
            raise ValueError("proposals must be non-empty strings")
    # duplicate proposals within one operation carry no extra information
    return list(dict.fromkeys(proposals))


def run_graph_of_thought(
    seed: str,
    proposer: Callable[[list[str], int, str], list[str]],
    scorer: Callable[[ThoughtNode, list[str]], float],
    *,
    branching: int = 3,
    max_depth: int = 3,
    beam_width: int = 2,
    max_nodes: int = 100,
    aggregate_final: bool = True,
    refine_budget: int = 0,
) -> dict:
    """Execute a bounded graph-of-thoughts search and return the full graph.

    proposer(path_texts, k, kind) -> up to k candidate thought strings; kind is
    "expansion", "aggregation" or "refinement". scorer(node, path_texts) ->
    finite number in [0,1]; node carries id/text/parents/depth/kind, so callers
    score by structure (e.g. node.kind), never by parsing joined text.
    The returned dict contains the FULL graph: every node (id, text, parents,
    depth, kind, score) and every typed edge, plus counts and the op trace.
    Best selection: highest score wins; ties prefer the most-developed (latest)
    thought. The root CAN win when no developed thought outscores it (or none
    exists); best_kind == "root" then means "no better answer found".
    """
    if not isinstance(seed, str) or not seed.strip():
        raise ValueError("seed must be a non-empty string")
    branching = _int(branching, "branching", 1, 8)
    max_depth = _int(max_depth, "max_depth", 1, 8)
    beam_width = _int(beam_width, "beam_width", 1, 16)
    max_nodes = _int(max_nodes, "max_nodes", 1, 10000)
    refine_budget = _int(refine_budget, "refine_budget", 0, 8)
    if not callable(proposer) or not callable(scorer):
        raise ValueError("proposer and scorer callables are required")

    nodes: list[ThoughtNode] = [ThoughtNode(0, seed.strip(), (), 0, "root")]
    nodes[0].score = _score(scorer, nodes[0], [nodes[0].text])
    edges: list[tuple[int, int, str]] = []
    trace: list[str] = []

    def path_texts(node: ThoughtNode) -> Iterable[str]:
        chain, cur = [], node
        while True:
            chain.append(cur.text)
            if not cur.parents:
                return reversed(chain)
            cur = nodes[cur.parents[0]]

    beam = [nodes[0]]
    for depth in range(1, max_depth + 1):
        candidates: list[ThoughtNode] = []
        for parent in beam:
            for text in _propose(proposer, list(path_texts(parent)), branching, "expansion"):
                if len(nodes) >= max_nodes:
                    break
                node = ThoughtNode(len(nodes), text, (parent.id,), depth, "expansion")
                node.score = _score(scorer, node, list(path_texts(node)))
                nodes.append(node)
                edges.append((parent.id, node.id, "expansion"))
                candidates.append(node)
                trace.append(f"expand:{parent.id}->#{node.id}@{depth}")
        if not candidates:
            break
        # keep-best: highest score first; ties broken by lowest id for determinism
        candidates.sort(key=lambda n: (-n.score, n.id))
        beam = candidates[:beam_width]
    # aggregation: merge the final beam into one multi-parent thought, exactly
    # one layer beyond the deepest beam node (may exceed max_depth by one)
    if aggregate_final and len(beam) > 1 and len(nodes) < max_nodes:
        texts = [n.text for n in beam]
        merged = _propose(proposer, texts, 1, "aggregation")
        if merged:
            depth = max(n.depth for n in beam) + 1
            node = ThoughtNode(len(nodes), merged[0], tuple(n.id for n in beam), depth, "aggregation")
            node.score = _score(scorer, node, texts + [node.text])
            nodes.append(node)
            for parent in beam:
                edges.append((parent.id, node.id, "aggregation"))
            trace.append(f"aggregate:{tuple(n.id for n in beam)}->#{node.id}")
            beam = [node]
    # refinement: improve the single best thought while budget remains
    while refine_budget > 0 and len(beam) == 1 and len(nodes) < max_nodes:
        best = beam[0]
        improved = _propose(proposer, [best.text], 1, "refinement")
        if not improved or improved[0] == best.text:
            break
        node = ThoughtNode(len(nodes), improved[0], (best.id,), best.depth + 1, "refinement")
        node.score = _score(scorer, node, [best.text, node.text])
        nodes.append(node)
        edges.append((best.id, node.id, "refinement"))
        trace.append(f"refine:{best.id}->#{node.id}")
        beam = [node]
        refine_budget -= 1
        if node.score <= best.score:
            break  # no improvement; further refinement is wasted budget

    # highest score wins; ties prefer the most-developed (latest) thought.
    # The root is a legitimate winner: it means no developed thought outscored
    # the seed (or none was produced), surfaced as best_kind == "root".
    best = max(nodes, key=lambda n: (n.score, n.id))
    if best.kind == "aggregation":
        # an aggregate has several parents; report the strongest parent chain
        strongest = max((nodes[p] for p in best.parents), key=lambda n: (n.score, n.id))
        best_path = list(path_texts(strongest)) + [best.text]
    else:
        best_path = list(path_texts(best))
    return {
        "best_path": best_path,
        "best_score": best.score,
        "best_kind": best.kind,
        "nodes": [{"id": n.id, "text": n.text, "parents": list(n.parents),
                   "depth": n.depth, "kind": n.kind, "score": n.score} for n in nodes],
        "edges": [{"from": a, "to": b, "kind": k} for a, b, k in edges],
        "graph": {"node_count": len(nodes), "edge_count": len(edges),
                  "kinds": {k: sum(1 for n in nodes if n.kind == k) for k in KINDS}},
        "trace": trace,
        "limits": ["Graph-of-thought search controller only; proposal and scoring "
                   "functions are injected, no bundled language model, no external calls."],
    }
