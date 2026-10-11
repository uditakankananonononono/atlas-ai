"""Supplied additive count-goal decomposition with DAG/coverage checks."""
from copy import deepcopy
from datetime import datetime
from .calibration_predictor import text,number

def names(value,label,minimum=0,maximum=64):
    if not isinstance(value,list)or not minimum<=len(value)<=maximum:raise ValueError(label+' requires bounded text list')
    for key in value:text(key,label)
    if len(set(value))!=len(value):raise ValueError(label+' requires unique keys')
    return list(value)
def timestamp(value,label):
    text(value,label)
    try:dt=datetime.fromisoformat(value)
    except ValueError as exc:raise ValueError(label+' requires ISO timezone date/time')from exc
    if dt.tzinfo is None:raise ValueError(label+' requires timezone')
    return dt

def plan(p):
    goal=p.get('plan_goal')
    if not isinstance(goal,dict):raise ValueError('plan_goal object required')
    goal={key:text(goal.get(key),key)for key in ('goal_id','description','metric','deadline','source')}|{'target':number(goal.get('target'),'goal target')}
    goal_time=timestamp(goal['deadline'],'goal deadline')
    if type(goal['target'])is not int or not 1<=goal['target']<=1000000:raise ValueError('additive count target integer[1,1000000] required')
    required=names(p.get('required_elements'),'required_elements',minimum=1);rows=p.get('plan_chunks')
    if not isinstance(rows,list)or not 1<=len(rows)<=64:raise ValueError('plan_chunks requires1..64 records')
    chunks={};times={}
    for row in rows:
        if not isinstance(row,dict):raise ValueError('chunk object required')
        ident=text(row.get('chunk_id'),'chunk_id');metric=text(row.get('metric'),'chunk metric');source=text(row.get('source'),'chunk source');subgoal=text(row.get('observable_subgoal'),'observable_subgoal');deadline=text(row.get('deadline'),'chunk deadline');target=number(row.get('target'),'chunk target')
        if ident in chunks or metric!=goal['metric']or type(target)is not int or not 1<=target<=1000000:raise ValueError('unique chunk IDs, same additive metric and positive integer target required')
        elements=names(row.get('elements'),'chunk elements');prerequisites=names(row.get('prerequisites'),'prerequisites');intention=row.get('if_then')
        if not isinstance(intention,dict):raise ValueError('if_then object required')
        intention={key:text(intention.get(key),'if_then '+key)for key in ('if','then')}
        chunks[ident]={'chunk_id':ident,'elements':sorted(elements),'observable_subgoal':subgoal,'metric':metric,'target':target,'deadline':deadline,'prerequisites':sorted(prerequisites),'if_then':intention,'source':source};times[ident]=timestamp(deadline,'chunk deadline')
    if any(not set(row['prerequisites'])<=set(chunks)for row in chunks.values()):raise ValueError('unknown prerequisite chunk')
    remaining=set(chunks);ordered=[]
    while remaining:
        ready=sorted(k for k in remaining if set(chunks[k]['prerequisites'])<=set(ordered))
        if not ready:raise ValueError('chunk prerequisite graph must be acyclic')
        ordered.extend(ready);remaining-=set(ready)
    counts={}
    for row in chunks.values():
        for element in row['elements']:counts[element]=counts.get(element,0)+1
    missing=sorted(set(required)-set(counts));unexpected=sorted(set(counts)-set(required));duplicates=sorted(key for key,count in counts.items()if count>1)
    conflicts=[]
    for key in sorted(chunks):
        if times[key]>goal_time:conflicts.append({'chunk_id':key,'reason':'chunk_deadline_after_goal'})
        for prerequisite in chunks[key]['prerequisites']:
            if times[prerequisite]>times[key]:conflicts.append({'chunk_id':key,'prerequisite_id':prerequisite,'reason':'prerequisite_deadline_after_chunk'})
    total=sum(row['target']for row in chunks.values());matches=total==goal['target'];valid=not(missing or unexpected or duplicates or conflicts)and matches
    return {'status':'validated'if valid else 'gaps_or_conflicts','valid':valid,'goal':deepcopy(goal),'ordered_chunk_ids':ordered,'chunks':[chunks[k]for k in ordered],'coverage':{'required_elements':sorted(required),'covered_elements':sorted(counts),'missing_elements':missing,'unexpected_elements':unexpected,'multiply_assigned_elements':duplicates},'goal_aggregation':{'metric':goal['metric'],'target':goal['target'],'chunk_target_total':total,'target_matches':matches},'deadline_conflicts':conflicts,'source_truth_verified':False,'scheduled':False,'goal_chosen_autonomously':False,'boundary':'Supplied additive count-goal DAG decomposition and coverage/deadline/if-then validation only. No autonomous goal choice, feasibility prediction, scheduling or verified achievement.'}
