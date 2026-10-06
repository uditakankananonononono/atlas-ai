"""Deterministic no-adjacent-skill scheduling of an explicit exercise multiset.

Mixing is measured in output, not asserted by a constant. This does not prove
learning gains or generate exercises; an imbalanced catalog may be impossible.
"""
from __future__ import annotations
import heapq
from collections import defaultdict
from .measured_learning import text


def interleave(p):
    exercises=p.get('practice_items')
    if not isinstance(exercises,list) or not 1<=len(exercises)<=10000:raise ValueError('1..10000 explicit practice_items required')
    groups=defaultdict(list);seen=set()
    for item in exercises:
        ident=text(item.get('id'),'exercise id');skill=text(item.get('skill'),'skill');task=text(item.get('task'),'task')
        if ident in seen:raise ValueError('unique exercise ids required')
        seen.add(ident);groups[skill].append({'id':ident,'skill':skill,'task':task})
    heap=[(-len(items),skill) for skill,items in groups.items()];heapq.heapify(heap)
    held=None;out=[];positions={skill:0 for skill in groups}
    while heap:
        count,skill=heapq.heappop(heap)
        out.append(groups[skill][positions[skill]]);positions[skill]+=1;count+=1
        if held is not None:heapq.heappush(heap,held)
        held=(count,skill) if count<0 else None
    # Impossibility is explicit. Append remaining same-skill exercises, not fake
    # variety, missing exercises or silently discarded practice.
    if held:
        _,skill=held;out.extend(groups[skill][positions[skill]:])
    repeats=[i for i in range(1,len(out)) if out[i]['skill']==out[i-1]['skill']]
    return {'exercises':out,'sequence':[item['skill'] for item in out],'adjacent_repeat_positions':repeats,
            'avoids_same_skill_runs':not repeats,'status':'interleaved' if not repeats else 'catalog_imbalance_requires_repeats',
            'counts':{skill:len(items) for skill,items in sorted(groups.items())},
            'boundary':'Schedules only supplied real exercises by largest remaining skill count, deferring the preceding skill. Every exercise used once. Avoids adjacent repeats when the multiset permits; otherwise repeats remain visible. Not a learned curriculum, empirically optimized order or proof of learning gains.'}
