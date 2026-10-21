from typing import Any
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,Field
from .cognitive_1960_2009 import ROWS,run,capability_scope,supplied_scope
router=APIRouter(prefix="/cognitive-1960-2009",tags=["cognitive-1960-2009"])
class Request(BaseModel):method:str=Field(min_length=1);data:dict[str,Any]=Field(default_factory=dict);seed:int=Field(0,ge=0)
@router.get("/methods")
def methods():
 rows=[{"method":m,"feature_row":r,**capability_scope(m),**supplied_scope(m)} for m,r in ROWS.items()]
 for row in rows:
  if row['method']=='genetic_algorithms':
   row['actual_implementation']={'route':'/api/v1/api/modules/20/genetic-algorithms/solve','algorithm':'binary_genetic_algorithm','objective':'maximize_weighted_bit_sum','acceptance':'independent audit pending; legacy reference result unchanged'}
 return rows
@router.post("/analyze")
def analyze(request:Request):
 try:return run(request.method,request.data,request.seed)
 except (ValueError,TypeError,KeyError) as exc:raise HTTPException(422,str(exc)) from exc


class GoTThought(BaseModel):
    text: str = Field(min_length=1)
    score: float = Field(ge=0, le=1)


class GoTRequest(BaseModel):
    seed: str = Field(min_length=1)
    thoughts: list[GoTThought] = Field(min_length=1, max_length=500)
    branching: int = Field(3, ge=1, le=8)
    max_depth: int = Field(3, ge=1, le=8)
    beam_width: int = Field(2, ge=1, le=16)
    max_nodes: int = Field(100, ge=1, le=10000)


@router.post("/graph-of-thought/search")
def graph_of_thought_search(request: GoTRequest):
    """Row 1960 practitioner-depth Graph-of-Thought search over caller-supplied
    scored thoughts. No bundled language model: every thought and score is
    supplied in the request; the route executes the search controller itself."""
    from .graph_of_thought_1960 import run_graph_of_thought
    # seed normalization is owned by the core (seed.strip()); the scorer
    # identifies the root by node.kind, never by comparing seed text.
    pool = [(t.text, t.score) for t in request.thoughts]
    scores = {}
    for text, score in pool:
        if text in scores and scores[text] != score:
            raise HTTPException(422, "conflicting scores for duplicate thought text")
        scores[text] = score
    texts = [t.text for t in request.thoughts]

    def proposer(path_texts, k, kind):
        if kind != "expansion":
            return [" + ".join(path_texts)] if kind == "aggregation" else []
        used = set(path_texts)
        return [t for t in texts if t not in used][:k]

    def scorer(node, path):
        if node.kind == "root":
            return min(scores.values())  # the seed is the problem statement, never a candidate answer
        if node.kind == "aggregation":
            # structured parent scoring: path[:-1] carries the parent texts in
            # beam order from the controller; no parsing of the joined text, so
            # a pool entry equal to the joined string cannot bypass the cap.
            parents = path[:-1]
            if not parents or any(t not in scores for t in parents):
                raise ValueError("aggregation parents must be supplied scored thoughts")
            return min(scores[t] for t in parents)
        if node.text in scores:
            return scores[node.text]
        raise ValueError("no supplied score for thought")

    try:
        result = run_graph_of_thought(request.seed, proposer, scorer,
                                      branching=request.branching, max_depth=request.max_depth,
                                      beam_width=request.beam_width, max_nodes=request.max_nodes,
                                      refine_budget=0)
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(422, str(exc)) from exc
    result["verification_boundary"] = ("Search controller executed on caller-supplied thoughts and "
                                       "scores; no bundled language model, no external calls.")
    return result
