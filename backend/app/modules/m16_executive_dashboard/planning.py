"""Durable planning and measurement domain logic (features rows 388-399).

Pure functions over typed entities: prioritization scoring, roadmap
sequencing, sprint/backlog math, velocity, burndown, kanban WIP rules,
retrospective rollups, experiment design validation and fixed-horizon
frequentist statistics (two-proportion z-test, chi-square via a Numerical
Recipes incomplete-gamma; no scipy dependency).

Every computed claim carries its inputs and assumptions; nothing here
touches the network or the framework.
"""
from __future__ import annotations
import math
from datetime import datetime,timedelta
from .schemas import (BurndownPoint,ExperimentOut,PrioritizedItem,RetrospectiveOut,SignificanceReport,SprintOut,VariantResult,VelocityPoint,WorkItemOut)
# --- rows 388: feature prioritization ---
PRIORITIZATION_METHODS=("rice","ice","wsjf")
def _inputs(item:WorkItemOut)->dict[str,float|None]:
    return {"reach":item.reach,"impact":item.impact,"confidence":item.confidence,"effort":item.effort,"value":item.value,"estimate":item.estimate}
def score_item(item:WorkItemOut,method:str)->PrioritizedItem:
    inputs=_inputs(item);formula="";score=None;missing=[]
    def need(*names):
        for n in names:
            v=inputs[n]
            if v is None:missing.append(n)
    if method=="rice":
        need("reach","impact","confidence","effort")
        formula="reach * impact * confidence / effort"
        if not missing and inputs["effort"] and inputs["effort"]>0:
            score=inputs["reach"]*inputs["impact"]*inputs["confidence"]/inputs["effort"]
        elif not missing:missing.append("effort>0")
    elif method=="ice":
        need("impact","confidence","effort")
        formula="impact * confidence * (1/effort)  [ease assumed as inverse effort]"
        if not missing and inputs["effort"] and inputs["effort"]>0:
            score=inputs["impact"]*inputs["confidence"]/inputs["effort"]
        elif not missing:missing.append("effort>0")
    elif method=="wsjf":
        need("value","estimate")
        formula="value (cost of delay) / estimate (job size)"
        if not missing and inputs["estimate"] and inputs["estimate"]>0:
            score=inputs["value"]/inputs["estimate"]
        elif not missing:missing.append("estimate>0")
    else:raise ValueError(f"unknown prioritization method {method}")
    return PrioritizedItem(item=item,method=method,score=score,inputs={k:v for k,v in inputs.items()},formula=formula,missing_inputs=missing)
def prioritize(items:list[WorkItemOut],method:str)->list[PrioritizedItem]:
    scored=[score_item(i,method) for i in items]
    return sorted(scored,key=lambda p:(p.score is None,-(p.score or 0),p.item.rank,p.item.id))
# --- rows 389: roadmap sequencing ---
def roadmap_view(items:list[WorkItemOut])->dict[str,list[WorkItemOut]]:
    """Group planned items by ISO week of planned_start; unplanned items land in 'unplanned'."""
    lanes:dict[str,list[WorkItemOut]]={}
    for i in sorted(items,key=lambda x:(x.planned_start is None,x.planned_start or x.created_at,x.rank)):
        key=f"{i.planned_start.isocalendar().year}-W{i.planned_start.isocalendar().week:02d}" if i.planned_start else "unplanned"
        lanes.setdefault(key,[]).append(i)
    return lanes
# --- rows 390/391: sprint + backlog ---
def committed_points(items:list[WorkItemOut])->float:
    return sum(i.estimate or 0 for i in items)
def stale_backlog(items:list[WorkItemOut],now:datetime,stale_after_days:int=30)->list[WorkItemOut]:
    return [i for i in items if i.status=="backlog" and (now-i.updated_at).days>=stale_after_days]
# --- rows 392: velocity ---
def velocity(sprints:list[SprintOut],items_by_sprint:dict[str,list[WorkItemOut]])->tuple[list[VelocityPoint],float|None]:
    points=[]
    for s in sorted((s for s in sprints if s.status=="closed"),key=lambda x:x.end):
        done=sum(i.estimate or 0 for i in items_by_sprint.get(s.id,[]) if i.status=="done")
        committed=sum(i.estimate or 0 for i in items_by_sprint.get(s.id,[]))
        points.append(VelocityPoint(sprint_id=s.id,sprint_name=s.name,committed_points=committed,completed_points=done))
    avg=sum(p.completed_points for p in points)/len(points) if points else None
    return points,avg
# --- rows 393: burndown ---
def burndown(sprint:SprintOut,items:list[WorkItemOut],now:datetime)->tuple[list[BurndownPoint],list[str]]:
    total=committed_points(items);start=sprint.start.date();end=min(now.date(),sprint.end.date())
    days=max(1,(sprint.end.date()-sprint.start.date()).days)
    added=[i for i in items if i.created_at.date()>sprint.start.date()]
    series=[];assumptions=["Ideal line is linear from committed points at sprint start to zero at sprint end.","Completion is credited on the item's completed_at day; items without estimates count as 0 points."]
    if added:assumptions.append(f"{len(added)} item(s) were added after sprint start; scope increases appear as upward steps in actual remaining.")
    d=start
    while d<=end:
        remaining=total
        for i in items:
            if i.status=="done" and i.completed_at and i.completed_at.date()<=d:remaining-=(i.estimate or 0)
        ideal=total*(1-(d-start).days/days) if total else 0
        series.append(BurndownPoint(day=datetime(d.year,d.month,d.day),ideal_remaining=round(max(0,ideal),2),actual_remaining=remaining,total_committed=total))
        d+=timedelta(days=1)
    return series,assumptions
# --- rows 394: kanban ---
KANBAN_COLUMNS=("backlog","ready","in_progress","review","done")
DEFAULT_WIP_LIMITS={"backlog":None,"ready":None,"in_progress":3,"review":2,"done":None}
class WipLimitExceeded(Exception):pass
def move_item(item:WorkItemOut,column:str,board_items:list[WorkItemOut],wip_limits:dict[str,int|None]|None=None)->WorkItemOut:
    if column not in KANBAN_COLUMNS:raise ValueError(f"unknown kanban column {column}")
    limits=wip_limits or DEFAULT_WIP_LIMITS
    limit=limits.get(column)
    if limit is not None and column!=item.status:
        occupying=sum(1 for i in board_items if i.status==column and i.id!=item.id)
        if occupying>=limit:raise WipLimitExceeded(f"column {column} is at its WIP limit of {limit}")
    return item
# --- rows 395/396: ceremonies + retrospectives ---
def retro_rollup(retros:list[RetrospectiveOut])->dict[str,object]:
    total_actions=sum(len(r.action_items) for r in retros)
    done=sum(1 for r in retros for a in r.action_items if a.get("status")=="done")
    open_items=[{"sprint_id":r.sprint_id,**a} for r in retros for a in r.action_items if a.get("status")!="done"]
    return {"retrospectives":len(retros),"action_items_total":total_actions,"action_items_done":done,"action_items_open":open_items,"completion_rate":(done/total_actions if total_actions else None)}
# --- rows 397/398/399: experiments + statistics ---
def validate_experiment(kind:str,variants:list[dict])->list[str]:
    errors=[]
    if kind not in("ab","multivariate"):errors.append(f"unknown experiment kind {kind}")
    if len(variants)<2:errors.append("at least two variants are required")
    total=sum(float(v.get("allocation",0)) for v in variants)
    if abs(total-1.0)>1e-6:errors.append(f"allocations must sum to 1.0 (got {total:g})")
    keys=[v.get("key") for v in variants]
    if len(set(keys))!=len(keys):errors.append("variant keys must be unique")
    if kind=="multivariate":
        for v in variants:
            if not v.get("factors"):errors.append(f"variant {v.get('key')} is missing factor assignments")
    return errors
def _phi(z:float)->float:return 0.5*(1+math.erf(z/math.sqrt(2)))
def _gammp(a:float,x:float)->float:
    """Regularized lower incomplete gamma P(a,x); Numerical Recipes series/continued fraction."""
    if x<=0:return 0.0
    if x<a+1:
        term=1.0/a;total=term
        for _ in range(1000):
            a+=1;term*=x/a;total+=term
            if abs(term)<abs(total)*1e-14:break
        return total*math.exp(-x+a*math.log(x)-math.lgamma(a))
    b=x+1-a;c=1e30;d=1/b;h=d
    for i in range(1,1000):
        an=-i*(i-a);b+=2;d=an*d+b
        if abs(d)<1e-30:d=1e-30
        c=b+an/c
        if abs(c)<1e-30:c=1e-30
        d=1/d;delta=d*c;h*=delta
        if abs(delta-1)<1e-14:break
    return 1-math.exp(-x+a*math.log(x)-math.lgamma(a))*h
def chi_square_sf(stat:float,df:int)->float:
    return 1-_gammp(df/2,stat/2)
def z_test(control:dict,treatment:dict,alpha:float=0.05,min_trials:int=30)->SignificanceReport:
    """Fixed-horizon two-proportion z-test. Inputs are raw per-variant counts."""
    n0,n1=control["trials"],treatment["trials"];x0,x1=control["successes"],treatment["successes"]
    assumptions=["Fixed-horizon test: the sample size was not peeked at or chosen from running results.","Observations are independent and identically distributed within each variant.","Normal approximation to the binomial (two-proportion z-test)."]
    if min(n0,n1)<min_trials:
        return SignificanceReport(test="two_proportion_z",p_value=None,significant=False,alpha=alpha,uplift=None,confidence_interval=None,inputs={"control":control,"treatment":treatment},assumptions=assumptions+[f"Insufficient sample: each variant needs at least {min_trials} trials."])
    p0,p1=x0/n0,x1/n1;pooled=(x0+x1)/(n0+n1)
    se=math.sqrt(pooled*(1-pooled)*(1/n0+1/n1))
    if se==0:
        return SignificanceReport(test="two_proportion_z",p_value=None,significant=False,alpha=alpha,uplift=p1-p0,confidence_interval=None,inputs={"control":control,"treatment":treatment},assumptions=assumptions+["Zero variance across both variants; no detectable difference."])
    z=(p1-p0)/se;p=2*(1-_phi(abs(z)))
    se_diff=math.sqrt(p0*(1-p0)/n0+p1*(1-p1)/n1);half=1.96*se_diff
    return SignificanceReport(test="two_proportion_z",p_value=p,significant=p<alpha,alpha=alpha,uplift=p1-p0,confidence_interval=(p1-p0-half,p1-p0+half),inputs={"control":control,"treatment":treatment},assumptions=assumptions)
def multivariate_test(variants:list[dict],alpha:float=0.05,min_trials:int=30)->SignificanceReport:
    """Chi-square homogeneity test across variant success rates (df = k-1)."""
    assumptions=["Fixed-horizon test; samples not peeked.","Independent observations per variant.","Chi-square approximation with k-1 degrees of freedom."]
    if any(v["trials"]<min_trials for v in variants):
        return SignificanceReport(test="chi_square",p_value=None,significant=False,alpha=alpha,uplift=None,confidence_interval=None,inputs={"variants":variants},assumptions=assumptions+[f"Insufficient sample: every variant needs at least {min_trials} trials."])
    total_s=sum(v["successes"] for v in variants);total_n=sum(v["trials"] for v in variants)
    p=total_s/total_n;stat=0.0
    for v in variants:
        expected=v["trials"]*p
        if expected>0:stat+=(v["successes"]-expected)**2/expected+((v["trials"]-v["successes"])-(v["trials"]-expected))**2/max(v["trials"]-expected,1e-12)
    df=len(variants)-1;p_value=chi_square_sf(stat,df)
    return SignificanceReport(test="chi_square",p_value=p_value,significant=p_value<alpha,alpha=alpha,uplift=None,confidence_interval=None,inputs={"variants":variants,"statistic":stat,"df":df},assumptions=assumptions)
def experiment_significance(exp:ExperimentOut,alpha:float=0.05)->SignificanceReport:
    variants=[v.model_dump() for v in exp.variants]
    counts=[{"key":v["key"],"trials":v["trials"],"successes":v["successes"]} for v in variants]
    if exp.kind=="ab":
        control=next((c for c in counts if c["key"]=="control"),counts[0])
        others=[c for c in counts if c is not control]
        treatment=max(others,key=lambda c:c["successes"]/c["trials"] if c["trials"] else 0)
        return z_test(control,treatment,alpha)
    return multivariate_test(counts,alpha)
