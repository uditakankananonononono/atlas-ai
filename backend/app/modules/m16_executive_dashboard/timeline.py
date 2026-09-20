"""Timeline (Gantt) analytics: critical path, cycle detection, risk flags."""
from __future__ import annotations
from datetime import datetime
from .schemas import TimelineItem
def critical_path(items:list[TimelineItem])->list[str]:
    by={i.id:i for i in items};memo={};visiting=set()
    def walk(i):
        if i in memo:return memo[i]
        if i in visiting:raise ValueError("timeline dependency cycle")
        visiting.add(i);best=(0,[])
        for d in by[i].dependencies:
            if d in by and walk(d)[0]>best[0]:best=walk(d)
        visiting.remove(i);duration=max(0,(by[i].end-by[i].start).total_seconds());memo[i]=(best[0]+duration,best[1]+[i]);return memo[i]
    return max((walk(i) for i in by),default=(0,[]),key=lambda x:x[0])[1]
def find_cycle(items:list[TimelineItem])->list[str]:
    """Return one dependency cycle (the item ids involved), or []."""
    by={i.id:i for i in items};state:dict[str,int]={};stack:list[str]=[]
    def visit(i):
        state[i]=1;stack.append(i)
        for d in by[i].dependencies:
            if d not in by:continue
            if state.get(d)==1:return stack[stack.index(d):]+[d]
            if state.get(d,0)==0:
                r=visit(d)
                if r:return r
        stack.pop();state[i]=2;return []
    for i in by:
        if state.get(i,0)==0:
            r=visit(i)
            if r:return r
    return []
def mark_critical_and_risk(items:list[TimelineItem],now:datetime)->list[TimelineItem]:
    """Annotate copies of items with critical-path membership and overdue risk."""
    try:path=set(critical_path(items))
    except ValueError:path=set()
    out=[]
    for item in items:
        copy=item.model_copy(update={"critical":item.id in path,"at_risk":item.end<now and item.progress<1})
        out.append(copy)
    return out
def overdue_items(items:list[TimelineItem],now:datetime,critical_only:bool=False)->list[TimelineItem]:
    marked=mark_critical_and_risk(items,now)
    return [i for i in marked if i.at_risk and (not critical_only or i.critical)]
