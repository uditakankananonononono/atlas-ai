"""SM-2 interval state transitions from supplied observed review grades.

Pure schedule computation, not review notifications or proven retention gains.
Reference: https://super-memory.com/english/ol/sm2.htm
"""
from __future__ import annotations
import math
from datetime import datetime,timedelta


def schedule_reviews(p):
    items=p.get('items')
    if not isinstance(items,list) or not items:raise ValueError('nonempty observed review items required')
    seen=set();evidence=set();out=[]
    for item in items:
        ident=item.get('id');ev=item.get('evidence_id')
        if not isinstance(ident,str) or not ident or ident in seen:raise ValueError('unique nonempty item ids required')
        if not isinstance(ev,str) or not ev or ev in evidence:raise ValueError('unique observed review evidence ids required')
        seen.add(ident);evidence.add(ev)
        q=item.get('quality');n=item.get('repetitions',0);interval=item.get('interval_days',0);ease=item.get('ease',2.5)
        if type(q) is not int or not 0<=q<=5:raise ValueError('review quality must be integer in [0,5]')
        if type(n) is not int or not 0<=n<=100000 or type(interval) is not int or not 0<=interval<=100000:raise ValueError('bounded nonnegative integer repetition/interval state required')
        if type(ease) not in (int,float) or not math.isfinite(ease) or not 1.3<=ease<=100:raise ValueError('finite ease in [1.3,100] required')
        if n>0 and interval<1:raise ValueError('repeated item requires positive previous interval')
        try:at=datetime.fromisoformat(item['reviewed_at'])
        except (KeyError,TypeError,ValueError) as exc:raise ValueError('ISO reviewed_at required') from exc
        if at.tzinfo is None:raise ValueError('reviewed_at must have timezone')
        next_ease=max(1.3,ease+.1-(5-q)*(.08+(5-q)*.02))
        if q<3:next_n=0;days=1
        else:
            next_n=n+1
            days=1 if next_n==1 else 6 if next_n==2 else math.ceil(interval*ease)
        try:due=at+timedelta(days=days)
        except OverflowError as exc:raise ValueError('review date exceeds supported calendar') from exc
        out.append({'id':ident,'evidence_id':ev,'quality':q,'repetitions':next_n,'interval_days':days,'ease':next_ease,
                    'previous_state':{'repetitions':n,'interval_days':interval,'ease':ease},'reviewed_at':at.isoformat(),
                    'due_at':due.isoformat(),'lapse':q<3,'same_session_retry_required':q<4})
    return {'schedule':out,'algorithm':'SM-2 interval/state calculation',
            'algorithm_source':'https://super-memory.com/english/ol/sm2.htm',
            'boundary':'Supplied quality grades, timestamps and prior state are not independently verified. Due dates are plan data, not scheduled reminders. No empirically optimal timing or retention gain claim. Same-session repeats flagged, not simulated.'}
