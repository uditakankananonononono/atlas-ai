"""Explicit as-of filtered ranking for Module 19 (ATLAS-M19-HISTORICAL-RANKING-01).

This module is additive. It does not change ranking.py; it filters what the ranking sees and reuses
`rank_portfolio` unchanged for scoring.

What it does (and does not do)
  * `as_of` is required and must be timezone-aware. There is no wall-clock default, so output is deterministic.
  * Rows are KNOWN at as_of when their own timestamps are <= as_of:
      ideas        created_at <= as_of
      evidence     observed_at <= as_of AND created_at <= as_of   (future-observed or later-recorded rows are excluded)
      tests        tested_at <= as_of
      experiments  created_at <= as_of, and updated_at <= as_of (see below)
  * Every excluded row is listed in `diagnostics` with its id, kind, reason and the timestamp that caused it.
  * NO HISTORICAL RECONSTRUCTION IS CLAIMED. The repository keeps only current state. Idea stage, experiment
    status/deadline, and the test/evidence field values are the CURRENT values. An experiment with
    updated_at > as_of may have had a different status or deadline at as_of; that state is not recoverable,
    so by default (`stale_experiment_policy="exclude"`) it is dropped and diagnosed. "current" keeps it
    scored on its current state and flags it in `caveats`. Stage filtering (active vs terminal) uses the current
    stage and is reported as a caveat.
  * Provenance carries a sha256 over canonical JSON of the inputs (as_of, half-life, policies, included and
    excluded ids with reasons and the actual filtered scoring inputs). Same repository content and arguments give the same digest.
"""
from __future__ import annotations
import hashlib,json
from datetime import datetime,timezone
from pydantic import BaseModel
from .ranking import PortfolioRanking,rank_portfolio
STALE_POLICIES=("exclude","current")
RECONSTRUCTION_NOTE=("as-of FILTER over current repository state; not a historical reconstruction: stage, experiment status/deadline "
                     "and field values are current, only row timestamps are compared to as_of")
class ExcludedRow(BaseModel):
    kind:str;row_id:str;idea_id:str;reason:str;timestamp:datetime
class HistoricalProvenance(BaseModel):
    as_of:datetime;half_life_days:float;include_terminal:bool;stale_experiment_policy:str
    included:dict[str,list[str]];excluded_count:int;digest:str;reconstruction_claimed:bool=False;note:str=RECONSTRUCTION_NOTE
class HistoricalRanking(BaseModel):
    ranking:PortfolioRanking;diagnostics:list[ExcludedRow];caveats:list[str];provenance:HistoricalProvenance
def _aware(d):return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
class AsOfRepositoryView:
    """Read-only view exposing the repository methods rank_portfolio uses, filtered to rows known at as_of."""
    def __init__(self,repository,as_of,stale_experiment_policy="exclude"):
        if as_of is None or not isinstance(as_of,datetime):raise ValueError("as_of must be a datetime")
        if as_of.tzinfo is None:raise ValueError("as_of must be timezone-aware")
        if stale_experiment_policy not in STALE_POLICIES:raise ValueError(f"stale_experiment_policy must be one of {STALE_POLICIES}")
        self._r=repository;self.as_of=as_of;self.policy=stale_experiment_policy
        self.excluded:dict[tuple,ExcludedRow]={};self.included={"ideas":set(),"evidence":set(),"tests":set(),"experiments":set()}
        self.stale_kept:set[str]=set();self.scoring_inputs={"ideas":[],"evidence":[],"tests":[],"experiments":[]}
    def _ex(self,kind,row,idea_id,reason,ts):
        self.excluded[(kind,row.id)]=ExcludedRow(kind=kind,row_id=row.id,idea_id=idea_id,reason=reason,timestamp=ts)
    def list_ideas(self):
        out=[]
        for i in self._r.list_ideas():
            if _aware(i.created_at)>self.as_of:self._ex("idea",i,i.id,"idea_created_after_as_of",i.created_at)
            else:out.append(i);self.included["ideas"].add(i.id);self.scoring_inputs["ideas"].append(i.model_dump(mode="json"))
        return out
    def list_evidence(self,idea_id):
        out=[]
        for e in self._r.list_evidence(idea_id):
            if _aware(e.observed_at)>self.as_of:self._ex("evidence",e,idea_id,"evidence_observed_after_as_of",e.observed_at)
            elif _aware(e.created_at)>self.as_of:self._ex("evidence",e,idea_id,"evidence_recorded_after_as_of",e.created_at)
            else:out.append(e);self.included["evidence"].add(e.id);self.scoring_inputs["evidence"].append(e.model_dump(mode="json"))
        return out
    def list_tests(self,idea_id):
        out=[]
        for t in self._r.list_tests(idea_id):
            if _aware(t.tested_at)>self.as_of:self._ex("test",t,idea_id,"test_after_as_of",t.tested_at)
            else:out.append(t);self.included["tests"].add(t.id);self.scoring_inputs["tests"].append(t.model_dump(mode="json"))
        return out
    def list_experiments(self,idea_id):
        out=[]
        for x in self._r.list_experiments(idea_id):
            if _aware(x.created_at)>self.as_of:self._ex("experiment",x,idea_id,"experiment_created_after_as_of",x.created_at);continue
            if _aware(x.updated_at)>self.as_of:
                if self.policy=="exclude":self._ex("experiment",x,idea_id,"experiment_state_changed_after_as_of_unrecoverable",x.updated_at);continue
                self.stale_kept.add(x.id)
            out.append(x);self.included["experiments"].add(x.id);self.scoring_inputs["experiments"].append(x.model_dump(mode="json"))
        return out
def _digest(payload):return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest()
def rank_portfolio_as_of(repository,as_of,half_life_days=90.0,include_terminal=False,limit=None,stale_experiment_policy="exclude"):
    """Rank using only rows whose own timestamps are <= as_of. Raises ValueError on naive/missing as_of or bad arguments."""
    if type(include_terminal) is not bool:raise ValueError("include_terminal must be bool")
    if limit is not None and (type(limit) is not int or limit<1):raise ValueError("limit must be positive integer")
    view=AsOfRepositoryView(repository,as_of,stale_experiment_policy)
    ranking=rank_portfolio(view,as_of=as_of,half_life_days=half_life_days,include_terminal=include_terminal,limit=limit)
    diags=sorted(view.excluded.values(),key=lambda d:(d.kind,d.row_id))
    caveats=["as-of filter only: current idea stage, experiment status/deadline and row field values are used; no historical reconstruction"]
    if not include_terminal:caveats.append("active/terminal stage filter uses the CURRENT idea stage")
    if view.stale_kept:caveats.append("experiments scored on current state although updated after as_of: "+", ".join(sorted(view.stale_kept)))
    if any(d.kind=="experiment" and d.reason.startswith("experiment_state_changed") for d in diags):
        caveats.append("experiments changed after as_of were dropped: their state at as_of is not recoverable")
    inc={k:sorted(v) for k,v in view.included.items()}
    ranked_ids=[r.idea_id for r in ranking.ranked]
    digest=_digest({"as_of":as_of.astimezone(timezone.utc).isoformat(),"half_life_days":half_life_days,"include_terminal":include_terminal,"policy":stale_experiment_policy,
                    "limit":limit,"scoring_inputs":{k:sorted(v,key=lambda r:r["id"]) for k,v in view.scoring_inputs.items()},"included":inc,"excluded":[[d.kind,d.row_id,d.reason] for d in diags],"ranked":ranked_ids})
    prov=HistoricalProvenance(as_of=as_of,half_life_days=half_life_days,include_terminal=include_terminal,stale_experiment_policy=stale_experiment_policy,
                              included=inc,excluded_count=len(diags),digest=digest)
    return HistoricalRanking(ranking=ranking,diagnostics=diags,caveats=caveats,provenance=prov)
