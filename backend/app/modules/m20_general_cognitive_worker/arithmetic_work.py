"""Finite one-register rational arithmetic traces and breadth-first search."""
from fractions import Fraction
from collections import deque
from .calibration_predictor import text

def rational(value,label):
    if type(value)is int:result=Fraction(value)
    elif isinstance(value,str)and len(value)<=64:
        try:result=Fraction(value)
        except (ValueError,ZeroDivisionError)as exc:raise ValueError(label+' requires rational string/integer')from exc
    else:raise ValueError(label+' requires rational string/integer')
    if abs(result.numerator)>10**12 or result.denominator>10**12:raise ValueError(label+' rational components exceed10**12')
    return result

def task(value):
    if not isinstance(value,dict):raise ValueError('arithmetic_task requires object')
    initial=rational(value.get('initial'),'initial');goal=rational(value.get('goal'),'goal');bound=rational(value.get('state_bound'),'state_bound');depth=value.get('max_depth');rows=value.get('operations')
    if not 0<bound<=10**6 or abs(initial)>bound or abs(goal)>bound:raise ValueError('initial/goal within positive state_bound<=10**6 required')
    if type(depth)is not int or not 0<=depth<=8:raise ValueError('max_depth integer[0,8] required')
    if not isinstance(rows,list)or not 1<=len(rows)<=8:raise ValueError('operations requires1..8 records')
    operations={}
    for row in rows:
        if not isinstance(row,dict):raise ValueError('operation object required')
        key=text(row.get('id'),'operation id');source=text(row.get('source'),'operation source');kind=row.get('kind');operand=rational(row.get('operand'),'operand')
        if key in operations or kind not in ('add','subtract','multiply','divide')or kind=='divide'and operand==0:raise ValueError('unique supported operations and nonzero divisor required')
        operations[key]={'id':key,'kind':kind,'operand':operand,'source':source}
    return {'initial':initial,'goal':goal,'state_bound':bound,'max_depth':depth,'operations':operations}

def apply(op,value):
    if op['kind']=='add':return value+op['operand']
    if op['kind']=='subtract':return value-op['operand']
    if op['kind']=='multiply':return value*op['operand']
    return value/op['operand']

def allowed(value,t):return abs(value)<=t['state_bound']and abs(value.numerator)<=10**12 and value.denominator<=10**12

def solve(t):
    agenda=deque([(t['initial'],[])]);seen={t['initial']};expanded=0
    while agenda:
        value,path=agenda.popleft()
        if value==t['goal']:return {'status':'solved','solution':path,'final_value':str(value),'solution_depth':len(path),'states_seen':len(seen),'states_expanded':expanded}
        if len(path)>=t['max_depth']:continue
        expanded+=1
        for key,op in sorted(t['operations'].items()):
            new=apply(op,value)
            if not allowed(new,t)or new in seen:continue
            if len(seen)>=10000:return {'status':'search_budget_exhausted','solution':None,'final_value':None,'solution_depth':None,'states_seen':len(seen),'states_expanded':expanded}
            seen.add(new);step={'pre':str(value),'operation_id':key,'post':str(new),'rationale':'apply:'+op['kind'],'operation_source':op['source']}
            agenda.append((new,path+[step]))
    return {'status':'no_solution_within_bounds','solution':None,'final_value':None,'solution_depth':None,'states_seen':len(seen),'states_expanded':expanded}

def exported(t):return {'initial':str(t['initial']),'goal':str(t['goal']),'operations':[{'id':key,'kind':op['kind'],'operand':str(op['operand']),'source':op['source']}for key,op in t['operations'].items()],'max_depth':t['max_depth'],'state_bound':str(t['state_bound']),'source_truth_verified':False}

def work(mode,p):
    t=task(p.get('arithmetic_task'));boundary='Exact one-register rational add/subtract/multiply/nonzero-divide tasks within declared depth/state bounds and10000-state search budget. Rationale labels checked against operations, not natural-language reasoning or learner understanding.'
    honesty={'source_truth_verified':False,'learner_understanding':None,'boundary':boundary,'task':exported(t)}
    if mode=='problem_solving':return {**honesty,**solve(t)}
    rows=p.get('worked_trace')
    if not isinstance(rows,list)or len(rows)>t['max_depth']:raise ValueError('worked_trace list within max_depth required')
    current=t['initial'];reports=[]
    for i,row in enumerate(rows):
        if not isinstance(row,dict):raise ValueError('worked step object required')
        pre=rational(row.get('pre'),'pre');post=rational(row.get('post'),'post');key=text(row.get('operation_id'),'operation_id');rationale=text(row.get('rationale'),'rationale');source=text(row.get('source'),'step source');op=t['operations'].get(key)
        expected=None if op is None else apply(op,current);pre_ok=pre==current;post_ok=expected is not None and post==expected and allowed(post,t);rationale_ok=op is not None and rationale=='apply:'+op['kind'];accepted=pre_ok and post_ok and rationale_ok
        reports.append({'step_index':i,'pre':str(pre),'operation_id':key,'expected_post':None if expected is None else str(expected),'submitted_post':str(post),'pre_matches':pre_ok,'post_matches':post_ok,'rationale_matches':rationale_ok,'accepted':accepted,'operation_source':None if op is None else op['source'],'step_source':source})
        if accepted:current=post
    valid=all(r['accepted']for r in reports);reached=current==t['goal'];completion=None;status='not_supplied'
    # Validate a supplied completion task even after failed work, but never emit
    # it until the worked trace reaches its goal and a bounded solution exists.
    next_task=None if p.get('completion_task')is None else task(p['completion_task'])
    if not valid or not reached:status='worked_trace_not_verified'
    elif next_task is not None:
        result=solve(next_task);status=result['status']
        if status=='solved':completion=exported(next_task)
    return {**honesty,'status':'verified_worked_example'if valid and reached else 'invalid_worked_trace','trace_valid':valid,'goal_reached':reached,'step_reports':reports,'final_value':str(current),'completion_problem':completion,'completion_status':status}
