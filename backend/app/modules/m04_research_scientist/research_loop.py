"""Question-then-research loop (M04 rows 223/239), REAL collection, HEURISTIC planning.

What is real: every step runs a live arXiv and/or PubMed query through the throttled
collectors and records the papers actually returned.
What is heuristic: the next query is built by deterministic term expansion (frequent terms
in retrieved abstracts that are not already in the query). There is no language model, so
this does not "think like a human", form hypotheses, or judge relevance. It is a
transparent retrieval loop. Stops at max_steps, when a step adds no new papers, or when
the expansion has no new terms.
"""
from __future__ import annotations

import re
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field

from .schemas import PaperInput

STOP = {"about", "after", "also", "among", "based", "before", "between", "both", "could", "data",
        "from", "have", "into", "more", "paper", "results", "show", "study", "than", "that",
        "their", "these", "this", "using", "were", "which", "with", "within", "what", "does",
        "when", "where", "how", "why", "the", "and", "for", "are", "can", "new", "propose",
        "method", "approach", "model", "models", "present", "work", "however", "while",
        "but", "not", "only", "such", "they", "them", "has", "had", "its", "our", "out", "all", "any",
        "each", "other", "some", "most", "many", "several", "often", "thus", "then", "there", "been",
        "being", "will", "would", "may", "might", "via", "over", "under", "across", "through", "being",
        "well", "high", "different", "existing", "recent", "both", "two", "one", "first", "novel",
        "performance", "demonstrate", "demonstrates", "proposed", "framework", "task", "tasks"}


def _stem(w: str) -> str:
    return w[:-1] if len(w) > 4 and w.endswith("s") else w
Collector = Callable[[str, int], list[PaperInput]]


def key_terms(text: str) -> list[str]:
    seen, out = set(), []
    for w in re.findall(r"[a-z][a-z0-9\-]{2,}", text.lower()):
        if w not in STOP and w not in seen:
            seen.add(w); out.append(w)
    return out


@dataclass
class Step:
    index: int
    source: str
    query: str
    fetched: int
    new_paper_ids: list[str]
    added_terms: list[str]


@dataclass
class LoopResult:
    question: str
    steps: list[Step] = field(default_factory=list)
    papers: dict[str, PaperInput] = field(default_factory=dict)
    stop_reason: str = ""
    status: str = "complete"  # complete | partial (stopped early with a trail) | failed (nothing collected)
    error: str | None = None  # fixed category only, never upstream text


def run_loop(question: str, collectors: dict[str, Collector], *, max_steps: int = 3,
             per_step: int = 10, deadline_s: float = 60.0,
             clock: Callable[[], float] = time.monotonic) -> LoopResult:
    """deadline_s is checked BEFORE each collector call. A call already started can still run
    up to the collector's own 30 s HTTP timeout (plus throttle waits), so worst-case runtime is
    about deadline_s + 30 s + 3 s, not deadline_s."""
    if not 1 <= max_steps <= 3 or not 1 <= per_step <= 20:
        raise ValueError("max_steps 1-3 and per_step 1-20")
    base = key_terms(question)[:6]
    if len(base) < 1:
        raise ValueError("question has no usable terms")
    if not 1 <= deadline_s <= 120:
        raise ValueError("deadline_s 1-120")
    res = LoopResult(question=question)
    started = clock()
    extra: list[str] = []
    for i in range(1, max_steps + 1):
        query = " ".join(base + extra)[:280]
        new_total = 0
        for source, collect in collectors.items():
            if clock() - started > deadline_s:
                res.stop_reason = "deadline"; res.status = "partial" if res.papers else "failed"; return res
            try:
                got = collect(query, per_step)
            except Exception as exc:  # noqa: BLE001 - recorded by type only; a partial trail is kept honestly
                res.stop_reason = "collector_error"
                res.error = type(exc).__name__
                res.status = "partial" if res.papers else "failed"
                return res
            new = [p.paper_id for p in got if p.paper_id not in res.papers]
            for p in got:
                res.papers.setdefault(p.paper_id, p)
            new_total += len(new)
            res.steps.append(Step(i, source, query, len(got), new, list(extra)))
        if new_total == 0:
            res.stop_reason = "no_new_papers"; return res
        df = Counter(t for p in res.papers.values() for t in set(key_terms(f"{p.title} {p.abstract}")))
        used = {_stem(t) for t in set(base) | set(extra)}
        cand = [t for t, c in df.most_common() if c >= 2 and _stem(t) not in used]
        if not cand:
            res.stop_reason = "no_new_terms"; return res
        extra = (extra + cand[:1])[-2:]
    res.stop_reason = "max_steps"
    return res
