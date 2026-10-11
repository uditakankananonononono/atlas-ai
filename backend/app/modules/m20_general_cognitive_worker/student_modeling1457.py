"""Row1457 strict supplied-parameter conditional BKT trace audit, PREP only."""
from __future__ import annotations
import json
import math
import unicodedata
_PARAMS=frozenset(('prior_mastery','learn_rate','slip','guess'))

def _refuse(code):raise ValueError('STUDEN1457:'+code)

def _fields(value,keys,path):
    if not isinstance(value,dict):_refuse('BAD_TYPE:'+path)
    for key in value:
        if key not in keys:_refuse('UNKNOWN:'+path+'.'+str(key))
    for key in sorted(keys-set(value)):_refuse('MISSING:'+path+'.'+key)

def _id(value,field):
    if not isinstance(value,str) or not value.strip() or any(unicodedata.category(c) in ('Cc','Zl','Zp') for c in value):_refuse('BAD_TYPE:'+field)
    if len(value)>120:_refuse('OVERSIZE:'+field)
    return value

def run(request):
    """Compute an auditable unfitted trace from explicit declarations, no actions."""
    _fields(request,{'parameters','events'},'request')
    params=request['parameters'];_fields(params,_PARAMS,'parameters')
    for key in sorted(_PARAMS):
        v=params[key]
        if isinstance(v,bool) or not isinstance(v,(int,float)) or not 0<=v<=1 or not math.isfinite(v):_refuse('BAD_TYPE:parameters.'+key)
    events=request['events']
    if not isinstance(events,list):_refuse('BAD_TYPE:events')
    if len(events)>1024:_refuse('OVERSIZE:events')
    ids=set();groups={};traces=[]
    for i,event in enumerate(events):
        path='events['+str(i)+']';_fields(event,{'event_id','learner_id','skill','correct'},path)
        eid=_id(event['event_id'],'event_id');learner=_id(event['learner_id'],'learner_id');skill=_id(event['skill'],'skill')
        if eid in ids:_refuse('DUPLICATE:event_id')
        ids.add(eid)
        if type(event['correct']) is not bool:_refuse('BAD_TYPE:'+path+'.correct')
        key=(learner,skill)
        if key not in groups:
            if len(groups)>=128:_refuse('OVERSIZE:pairs')
            groups[key]={'probability':params['prior_mastery'],'event_ids':[]}
        group=groups[key];prior=group['probability'];correct=event['correct']
        numerator=prior*(1-params['slip']) if correct else prior*params['slip']
        likelihood=numerator+(1-prior)*(params['guess'] if correct else 1-params['guess'])
        if likelihood==0:_refuse('IMPOSSIBLE:'+eid)
        posterior=numerator/likelihood
        after=posterior+(1-posterior)*params['learn_rate']
        group['event_ids'].append(eid);group['probability']=after
        traces.append({'event_id':eid,'learner_id':learner,'skill':skill,'correct':correct,'step':len(group['event_ids']),
            'prior':round(prior,6),'likelihood':round(likelihood,6),'posterior':round(posterior,6),'post_learning':round(after,6)})
    states=[{'learner_id':key[0],'skill':key[1],'event_ids':g['event_ids'],'attempts':len(g['event_ids']),
        'modeled_probability':round(g['probability'],6)} for key,g in sorted(groups.items())]
    result={'row_id':1457,'parameters':{k:round(params[k],6) for k in sorted(_PARAMS)},'parameter_source':'caller',
        'traces':traces,'states':states,'status':'conditional_unfitted_model_calculation','fitted_to_data':False,
        'learner_mastery_verified':False,'educator_review_required':True,
        'scope':{'mode':'PREP','inputs':'caller-supplied parameters and ordered pseudonymous attempt declarations',
            'limits':['not fitted or verified learner mastery','no educational advice or high-stakes decisions','no hidden-trait inference or efficacy claim','no persistence, disclosure or effects']}}
    return json.loads(json.dumps(result,sort_keys=True,ensure_ascii=False,allow_nan=False))
