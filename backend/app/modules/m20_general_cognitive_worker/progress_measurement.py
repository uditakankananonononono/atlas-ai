"""Chronological progress measurement from evidence-linked scalar observations."""
from __future__ import annotations
import math
from datetime import datetime
from .measured_learning import text


def measure_progress(p):
    records=p.get('records');direction=p.get('direction','increase');unit=text(p.get('unit'),'unit')
    if direction not in ('increase','decrease'):raise ValueError('direction must be increase/decrease')
    if not isinstance(records,list) or not records:raise ValueError('nonempty progress records required')
    seen=set();observed=[];previous=None
    for r in records:
        evidence=text(r.get('evidence_id'),'evidence id');value=r.get('value')
        if evidence in seen or type(value) not in (int,float) or not math.isfinite(value):raise ValueError('unique evidence and finite scalar value required')
        try:at=datetime.fromisoformat(r['observed_at'])
        except (ValueError,TypeError,KeyError) as exc:raise ValueError('ISO observed_at required') from exc
        if at.tzinfo is None or (previous is not None and at<=previous):raise ValueError('strictly chronological timezone-aware observations required')
        if r.get('unit',unit)!=unit:raise ValueError('mixed measurement units rejected')
        seen.add(evidence);previous=at;observed.append((at,value,evidence))
    first,last=observed[0],observed[-1];change=last[1]-first[1];sign=1 if direction=='increase' else -1
    days=(last[0]-first[0]).total_seconds()/86400
    target=p.get('target');deadline=p.get('deadline')
    if target is not None and (type(target) not in (int,float) or not math.isfinite(target)):raise ValueError('finite scalar target required')
    end=None
    if deadline is not None:
        try:end=datetime.fromisoformat(deadline)
        except (TypeError,ValueError) as exc:raise ValueError('ISO deadline required') from exc
        if end.tzinfo is None:raise ValueError('deadline requires timezone')
    rate=change/days if days>0 else None;projection=None
    if rate is not None and end is not None and end>=last[0]:projection=last[1]+rate*(end-last[0]).total_seconds()/86400
    if not all(math.isfinite(v) for v in (change,rate,projection) if v is not None):raise ValueError('progress arithmetic overflowed')
    reached=(sign*(last[1]-target)>=0) if target is not None else None
    projected_reached=(sign*(projection-target)>=0) if projection is not None and target is not None else None
    return {'latest':last[1],'change':change,'improvement':sign*change,'observations':len(observed),'unit':unit,'direction':direction,
            'target':target,'target_reached':reached,'on_track':projected_reached,'linear_rate_per_day':rate,'projected_at_deadline':projection,
            'deadline':end.isoformat() if end else None,'records':records,
            'boundary':'Observed change and endpoint linear extrapolation only; not a predictive model or calibrated forecast. on_track is null without sufficient dated evidence, target and future deadline. Evidence and measurement units are caller supplied, not independently verified.'}
