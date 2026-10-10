"""Reduced-scale, per-idea decomposed analysis harness over the real M19 evidence ledger (ATLAS-U-1232, owner row 193 substitute).

What this does: counts the ledger's evidence rows as "variables" (one row = one strength/confidence/polarity observation), runs the
EXISTING `LedgerService.evidence_summary` for every idea (each idea is an independent block, so the analysis decomposes per-idea and can be
chunked or reordered without changing results), checks that chunked results equal the whole run, can seed a clearly labelled SYNTHETIC ledger
through the real ledger API for reduced-scale points, and measures wall time of the analysis step with an injected clock.
There is no matrix or optimisation solver here and no sparse-matrix code; "decomposed" means only per-idea blocks.
Measurements exist only when a caller runs `measure_scaling`; this module contains no recorded timings and does not extrapolate.
Seeded data is synthetic and says so in every point (`data_origin`). Analysis of a caller-supplied real ledger uses the same functions.

What it honestly cannot cover (verbatim): Literal 1M-variable claim

Unmet owner requirement: owner row 193 (1,000,000-variable analysis target) is NOT met. There is no real ledger data at that scale, and the
unit's gates exclude a numerical solver; this harness neither reaches 1,000,000 variables nor claims to. `target_met` is always False.
"""
from __future__ import annotations
import random,time
from datetime import datetime,timezone
from .schemas import *
GAP_VERBATIM="Literal 1M-variable claim"
TARGET_VARIABLES=1_000_000
SYNTHETIC_LABEL="synthetic-seeded-not-real-ledger-data"
UNMET_OWNER_GAP=("Owner row 193 (1,000,000-variable analysis target) is NOT met: no real ledger data exists at that scale and this unit has no numerical solver; "
                 "points are reduced-scale measurements of per-idea evidence summaries only.")
_OBSERVED_AT=datetime(2026,1,1,tzinfo=timezone.utc)
def _pos_int(v,name):
    if type(v) is not int or v<1:raise ValueError(f"{name} must be a positive integer")
    return v
def count_variables(service):
    """Number of evidence rows across every idea in the ledger."""
    return sum(len(service.repository.list_evidence(i.id)) for i in service.list_ideas())
def analyze_ideas(service,idea_ids):
    """Per-idea evidence summary (existing ledger logic) for the given ideas. Unknown ideas raise LookupError. Ideas are independent blocks."""
    return {i:service.evidence_summary(i).model_dump() for i in idea_ids}
def analyze_portfolio(service,chunk_size=None):
    """Analyze every idea in sorted-id order, optionally in chunks. Result does not depend on chunk_size."""
    if chunk_size is not None:_pos_int(chunk_size,"chunk_size")
    ids=sorted(i.id for i in service.list_ideas());step=chunk_size or max(1,len(ids));out={}
    for k in range(0,len(ids),step):out.update(analyze_ideas(service,ids[k:k+step]))
    n=sum(v["supporting_count"]+v["contradicting_count"]+v["neutral_count"] for v in out.values())
    return {"ideas":out,"variables_analyzed":n,"ideas_analyzed":len(out)}
def verify_decomposition(service,chunk_sizes=(1,2),analyzer=analyze_ideas):
    """Return mismatch descriptions between one whole run and chunked runs; an empty list means they agree."""
    ids=sorted(i.id for i in service.list_ideas());whole=analyzer(service,ids);bad=[]
    for k in chunk_sizes:
        _pos_int(k,"chunk size");merged={}
        for s in range(0,len(ids),k):merged.update(analyzer(service,ids[s:s+k]))
        if set(merged)!=set(whole):bad.append(f"chunk {k}: idea sets differ")
        for i in sorted(set(whole)&set(merged)):
            for f in sorted(set(whole[i])|set(merged[i])):
                if whole[i].get(f)!=merged[i].get(f):bad.append(f"chunk {k} idea {i} field {f}: whole={whole[i].get(f)!r} chunked={merged[i].get(f)!r}")
    return bad
def seed_synthetic(service,n_ideas,evidence_per_idea,seed=0):
    """Create n_ideas ideas with evidence_per_idea evidence rows each through the real ledger API. Values are pseudo-random (seeded) and SYNTHETIC."""
    _pos_int(n_ideas,"n_ideas");_pos_int(evidence_per_idea,"evidence_per_idea");rng=random.Random(seed);pols=(EvidencePolarity.SUPPORTS,EvidencePolarity.CONTRADICTS,EvidencePolarity.NEUTRAL);ids=[]
    for k in range(n_ideas):
        i=service.create_idea(IdeaCreate(title=f"synthetic-{k}",problem="synthetic",proposed_solution="synthetic")).id;ids.append(i)
        for _ in range(evidence_per_idea):
            service.add_evidence(i,EvidenceCreate(kind=EvidenceKind.OTHER,claim="synthetic",source="scaling_bench",polarity=rng.choice(pols),strength=round(rng.random(),4),confidence=round(rng.random(),4),observed_at=_OBSERVED_AT))
    return ids
def measure_scaling(make_service,variable_scales,evidence_per_idea=10,clock=time.perf_counter,seed=0):
    """For each scale: build a fresh ledger, seed synthetic evidence (not timed), then time only analyze_portfolio with `clock` (called exactly twice)."""
    _pos_int(evidence_per_idea,"evidence_per_idea")
    if not isinstance(variable_scales,(list,tuple)) or not variable_scales:raise ValueError("variable_scales must be a non-empty list")
    prev=0
    for n in variable_scales:
        _pos_int(n,"scale")
        if n<=prev:raise ValueError("scales must be strictly increasing")
        if n%evidence_per_idea:raise ValueError("each scale must be a multiple of evidence_per_idea")
        prev=n
    points=[]
    for n in variable_scales:
        service=make_service();seed_synthetic(service,n//evidence_per_idea,evidence_per_idea,seed=seed)
        t0=clock();res=analyze_portfolio(service);t1=clock();elapsed=t1-t0
        if elapsed<0:raise ValueError("clock went backwards")
        v=res["variables_analyzed"]
        points.append({"variables_analyzed":v,"ideas_analyzed":res["ideas_analyzed"],"elapsed_seconds":elapsed,"seconds_per_variable":elapsed/v,"data_origin":SYNTHETIC_LABEL})
    return points
def build_report(points):
    """Summarise measured points. Growth entries are plain ratios of consecutive measured points, not projections."""
    if not points:raise ValueError("no measurement points")
    growth=[]
    for a,b in zip(points,points[1:]):
        growth.append({"from_variables":a["variables_analyzed"],"to_variables":b["variables_analyzed"],
                       "variables_ratio":b["variables_analyzed"]/a["variables_analyzed"],
                       "elapsed_ratio":(b["elapsed_seconds"]/a["elapsed_seconds"]) if a["elapsed_seconds"] else None})
    return {"kind":"m19-reduced-scale-evidence-analysis","points":list(points),"growth":growth,"max_variables_measured":max(p["variables_analyzed"] for p in points),
            "target_variables":TARGET_VARIABLES,"target_met":False,"literal_1m_claimed":False,"gap_verbatim":GAP_VERBATIM,"unmet_owner_gap":UNMET_OWNER_GAP,
            "note":"measurements are whatever the caller's clock returned; nothing here was run by the author"}
