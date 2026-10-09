"""Evidence-decayed portfolio ranking with next-action guidance for Module 19.

Formula (every term is computed from ledger rows, nothing is a fixed score):
  decayed(x)      = strength * confidence * 0.5 ** (age_days / half_life_days)
  support/contra  = 1 - prod(1 - decayed(x))            over evidence of that polarity (noisy-OR, same as the ledger)
  net             = support - contra                     in [-1, 1]
  feasibility     = latest weighted_score/100 * weighted_confidence, None if no test
  experiments     = (succeeded - failed) / finished_count (cancelled ignored), None if none finished
  overdue         = open experiments whose deadline < as_of
  priority        = 100 * clamp(0.4*feas + 0.4*(net+1)/2 + 0.2*(exp+1)/2 - min(0.3, 0.1*overdue), 0, 1)
The weights are chosen constants, not learned or validated: a transparent heuristic.
Missing signals, exactly as computed: no feasibility test scores 0 for the feasibility term (conservative:
absence is not credit); no evidence gives net = 0 and no finished experiment gives experiment signal = 0, which
after the (x+1)/2 shift contribute their midpoint 0.5 (neutral). Every missing signal is listed in
`missing_signals` and `signal_coverage` = present signals / 3, so thin-evidence ideas never look verified.
as_of is only the decay anchor, not a historical snapshot: it does not rewind the ledger, so rows created after
as_of are still counted, and evidence observed after as_of gets age 0 (no boost beyond full weight).
half_life_days must be a finite number > 0 (NaN/Inf raise ValueError).
"""
from __future__ import annotations
from datetime import datetime,timezone
from math import isfinite,prod
from pydantic import BaseModel
from .schemas import *
ACTIVE_STAGES={IdeaStage.CAPTURED,IdeaStage.DISCOVERY,IdeaStage.VALIDATION,IdeaStage.EXPERIMENTING}
TERMINAL_EXP={ExperimentStatus.SUCCEEDED,ExperimentStatus.FAILED,ExperimentStatus.INCONCLUSIVE,ExperimentStatus.CANCELLED}
class RankedIdea(BaseModel):
    rank:int;idea_id:str;title:str;stage:IdeaStage;priority:float;signal_coverage:float;missing_signals:list[str]
    support:float;contradiction:float;net_evidence:float;feasibility:float|None;experiment_signal:float|None;overdue_experiments:int
    next_action:str;reasons:list[str]
class PortfolioRanking(BaseModel):
    as_of:datetime;half_life_days:float;method:str;ranked:list[RankedIdea];excluded_count:int
def _aware(d):return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
def _noisy_or(values):return 1-prod(1-v for v in values) if values else 0.0
def score_idea(idea,evidence,tests,experiments,as_of,half_life_days):
    sup=[];con=[]
    for e in evidence:
        age=max(0.0,(as_of-_aware(e.observed_at)).total_seconds()/86400);d=e.strength*e.confidence*0.5**(age/half_life_days)
        if e.polarity==EvidencePolarity.SUPPORTS:sup.append(d)
        elif e.polarity==EvidencePolarity.CONTRADICTS:con.append(d)
    support=_noisy_or(sup);contra=_noisy_or(con);net=support-contra
    latest=max(tests,key=lambda t:_aware(t.tested_at)) if tests else None
    feas=round(latest.weighted_score/100*latest.weighted_confidence,4) if latest else None
    done=[x for x in experiments if x.status in TERMINAL_EXP and x.status!=ExperimentStatus.CANCELLED]
    exp=round((sum(x.status==ExperimentStatus.SUCCEEDED for x in done)-sum(x.status==ExperimentStatus.FAILED for x in done))/len(done),4) if done else None
    overdue=sum(1 for x in experiments if x.status not in TERMINAL_EXP and x.deadline is not None and _aware(x.deadline)<as_of)
    missing=[n for n,v in (("evidence",evidence or None),("feasibility",latest),("experiments",exp)) if v is None]
    p=0.4*(feas or 0.0)+0.4*(net+1)/2+0.2*((exp if exp is not None else 0.0)+1)/2-min(0.3,0.1*overdue)
    return dict(priority=round(100*min(1.0,max(0.0,p)),2),support=round(support,4),contradiction=round(contra,4),net=round(net,4),feas=feas,exp=exp,overdue=overdue,missing=missing,coverage=round((3-len(missing))/3,4),latest=latest)
def next_action(idea,s,evidence,experiments):
    if not evidence:return "add evidence: no evidence is recorded"
    if s["latest"] is None:return "run a feasibility test: none recorded"
    if s["overdue"]:return f"resolve {s['overdue']} overdue experiment(s)"
    if s["latest"].outcome==FeasibilityOutcome.FAIL:return "address feasibility blockers or park the idea"
    if s["net"]<=0:return "gather supporting evidence: net evidence is not positive"
    if not experiments:return "design an experiment: none exist"
    if any(x.status not in TERMINAL_EXP for x in experiments):return "finish open experiments"
    return "ready for a stage decision"
def rank_portfolio(repository,as_of=None,half_life_days=90.0,include_terminal=False,limit=None):
    if not isinstance(half_life_days,(int,float)) or isinstance(half_life_days,bool) or not isfinite(half_life_days) or half_life_days<=0:raise ValueError("half_life_days must be a finite number greater than 0")
    as_of=_aware(as_of) if as_of else datetime.now(timezone.utc);rows=[];excluded=0
    for idea in repository.list_ideas():
        if not include_terminal and idea.stage not in ACTIVE_STAGES:excluded+=1;continue
        ev=repository.list_evidence(idea.id);te=repository.list_tests(idea.id);ex=repository.list_experiments(idea.id)
        s=score_idea(idea,ev,te,ex,as_of,half_life_days);reasons=[f"net evidence {s['net']} (support {s['support']}, contradiction {s['contradiction']}, half-life {half_life_days:g}d)"]
        reasons.append(f"feasibility {s['feas']}" if s["feas"] is not None else "no feasibility test (scored 0, not neutral)")
        if s["missing"]:reasons.append("missing signals: "+", ".join(s["missing"]))
        rows.append((s["priority"],s["coverage"],idea.created_at,idea,s,ev,ex,reasons))
    rows.sort(key=lambda r:(-r[0],-r[1],_aware(r[2]),r[3].id))
    ranked=[RankedIdea(rank=i+1,idea_id=r[3].id,title=r[3].title,stage=r[3].stage,priority=r[0],signal_coverage=r[1],missing_signals=r[4]["missing"],support=r[4]["support"],contradiction=r[4]["contradiction"],net_evidence=r[4]["net"],feasibility=r[4]["feas"],experiment_signal=r[4]["exp"],overdue_experiments=r[4]["overdue"],next_action=next_action(r[3],r[4],r[5],r[6]),reasons=r[7]) for i,r in enumerate(rows)]
    if limit is not None:ranked=ranked[:limit]
    return PortfolioRanking(as_of=as_of,half_life_days=half_life_days,method="evidence-decayed noisy-OR; see ranking.py docstring",ranked=ranked,excluded_count=excluded)
