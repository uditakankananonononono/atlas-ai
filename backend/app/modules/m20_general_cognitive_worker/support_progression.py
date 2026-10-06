"""Observed-evidence support progression over an explicit exercise catalog.

This is a bounded policy, not a learned mastery model or assessment of free text.
Input grades are caller evidence. No automatically executed teaching action.
"""
from __future__ import annotations
from .measured_learning import text

LEVELS=('model','guided','prompted','independent')


def progress_support(p):
    catalog=p.get('support_catalog');attempts=p.get('support_attempts')
    if not isinstance(catalog,list) or not catalog or not isinstance(attempts,list):raise ValueError('explicit support_catalog and support_attempts required')
    required=p.get('successes_to_fade',2)
    if type(required) is not int or not 1<=required<=100:raise ValueError('successes_to_fade must be integer in [1,100]')
    initial=p.get('initial_support','model')
    if initial not in LEVELS:raise ValueError('unknown initial_support')
    tasks={};ids=set()
    for task in catalog:
        ident=text(task.get('id'),'task id');level=task.get('support_level')
        if ident in ids or level not in LEVELS:raise ValueError('unique task ids and known support levels required')
        ids.add(ident);tasks.setdefault(level,[]).append({'id':ident,'task':text(task.get('task'),'task'),'support_level':level})
    level=LEVELS.index(initial);streak=0;seen=set();history=[]
    for attempt in attempts:
        ev=text(attempt.get('evidence_id'),'evidence id');observed_level=attempt.get('support_level')
        if ev in seen or type(attempt.get('succeeded')) is not bool:raise ValueError('unique evidence and boolean success required')
        if observed_level!=LEVELS[level]:raise ValueError('attempt must match active support level; no skipping evidence')
        if attempt.get('task_id') not in {t['id'] for t in tasks.get(observed_level,[])}:raise ValueError('attempt must identify supplied task at active level')
        seen.add(ev);before=LEVELS[level]
        if attempt['succeeded']:
            streak+=1
            if streak>=required and level<3:level+=1;streak=0
        else:level=max(0,level-1);streak=0
        history.append({'evidence_id':ev,'task_id':attempt['task_id'],'succeeded':attempt['succeeded'],'previous_support':before,'next_support':LEVELS[level],'success_streak':streak})
    active=LEVELS[level]
    return {'active_support':active,'success_streak':streak,'history':history,'selected_tasks':tasks.get(active,[]),
            'missing_tasks_at_active_level':active not in tasks,'support_levels':[{'phase':name,'support':(3-i)/3} for i,name in enumerate(LEVELS)],
            'fade_on_evidence_not_time':True,
            'boundary':'Explicit consecutive-success policy advances one supplied support level; failure restores one level. Scores are caller evidence, not verified grading. No latent mastery, optimized threshold or guaranteed learning gain. Missing exercise levels remain empty, not invented.'}
