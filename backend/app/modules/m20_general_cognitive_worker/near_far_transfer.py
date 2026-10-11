"""Declared weighted feature agreement, independent exact answer scoring."""
from math import fsum
from .calibration_predictor import number,text
from .anchored_assessment import rows,keys

def compare(mode,p):
    schema={}
    for row in rows(p.get('transfer_schema'),'transfer_schema',minimum=1,maximum=64):
        ident=text(row.get('feature_id'),'feature_id');source=text(row.get('source'),'feature source');weight=number(row.get('weight'),'weight')
        if ident in schema or not 0<weight<=1000:raise ValueError('unique features and weight(0,1000] required')
        schema[ident]={'weight':weight,'source':source}
    values=[]
    for key in ('source_features','target_features'):
        value=p.get(key)
        if not isinstance(value,dict)or set(value)!=set(schema):raise ValueError(key+' must cover exactly declared feature schema')
        for name,entry in value.items():text(name,key);text(entry,key+' value')
        values.append(value)
    threshold=number(p.get('similarity_threshold'),'similarity_threshold')
    if not 0<=threshold<=1:raise ValueError('similarity_threshold[0,1] required')
    source,target=values;reports=[{'feature_id':key,'source_value':source[key],'target_value':target[key],'weight':schema[key]['weight'],'matches':source[key]==target[key],'source':schema[key]['source']}for key in sorted(schema)]
    total=fsum(r['weight']for r in reports);matched=fsum(r['weight']for r in reports if r['matches']);similarity=matched/total
    task=p.get('independent_target_task')
    if not isinstance(task,dict):raise ValueError('independent_target_task object required')
    task_id=text(task.get('task_id'),'task_id');task_source=text(task.get('source'),'answer key source');answers=keys(task.get('accepted_answers'),'accepted_answers',minimum=1)
    result={'status':'awaiting_independent_target_response','requested_mode':mode,'classification':'near'if similarity>=threshold else 'far','similarity':similarity,'threshold':threshold,'total_weight':total,'matching_weight':matched,'feature_reports':reports,'target_performance':None,'transfer_evidence_recorded':False,'source_truth_verified':False,'general_transfer':None,'boundary':'Caller-declared weighted exact feature agreement rubric; near/far is threshold classification, not semantic distance. Independent target exact-key response scoring is separate, independence/truth not verified; no general transfer claim.'}
    response=p.get('independent_target_response')
    if response is None:return result
    if not isinstance(response,dict):raise ValueError('independent_target_response object required')
    ident=text(response.get('response_id'),'response_id');source=text(response.get('source'),'response source');answer=text(response.get('answer'),'answer')
    if response.get('independent')is not True:raise ValueError('explicit independent target response required')
    performance={'task_id':task_id,'response_id':ident,'correct':answer in answers,'response_source':source,'answer_key_source':task_source,'independence_verified':False}
    return {**result,'status':'scored_target_performance','target_performance':performance,'transfer_evidence_recorded':True}
