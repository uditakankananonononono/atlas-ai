"""Declared concept activation and one-rule symbolic target transfer check."""
from .calibration_predictor import text
from .anchored_assessment import rows,keys

def activate(p):
    concepts={}
    for row in rows(p.get('activation_concepts'),'activation_concepts',minimum=1,maximum=64):
        key=text(row.get('concept_id'),'concept_id');source=text(row.get('source'),'concept source');values=keys(row.get('accepted_values'),'accepted_values',minimum=1)
        if key in concepts:raise ValueError('duplicate concept_id')
        concepts[key]={'concept_id':key,'accepted_values':sorted(values),'source':source}
    prior=[];new=[];seen=set()
    for field,out,ident in [('prior_responses',prior,'response_id'),('new_evidence',new,'evidence_id')]:
        local=set()
        for row in rows(p.get(field,[]),field,maximum=1000):
            key=text(row.get(ident),ident);concept=text(row.get('concept_id'),'concept_id');value=text(row.get('value'),'value');source=text(row.get('source'),'record source')
            if key in local or concept not in concepts:raise ValueError('unique records and known concepts required')
            local.add(key);result={ident:key,'concept_id':concept,'value':value,'source':source}
            if field=='prior_responses':
                matches=value in concepts[concept]['accepted_values'];result.update(matches_supplied_key=matches,misconception_candidate=not matches)
            out.append(result)
    reports=[{'concept_id':key,'prior_response_ids':sorted(r['response_id']for r in prior if r['concept_id']==key),'new_evidence_ids':sorted(r['evidence_id']for r in new if r['concept_id']==key),'unactivated':not any(r['concept_id']==key for r in prior)}for key in sorted(concepts)]
    return {'status':'activated','concepts':[concepts[k]for k in sorted(concepts)],'prior_reports':sorted(prior,key=lambda r:r['response_id']),'new_evidence':sorted(new,key=lambda r:r['evidence_id']),'concept_reports':reports,'grade':None,'source_truth_verified':False,'learner_understanding':None,'boundary':'Exact supplied concept-key comparisons of prior responses, separate from new evidence; mismatches are misconception candidates, not grades or verified beliefs/understanding.'}

def transfer(p):
    rule=p.get('transfer_rule');target=p.get('target_task')
    if not isinstance(rule,dict):raise ValueError('transfer_rule object required')
    if not isinstance(target,dict):raise ValueError('target_task object required')
    ident=text(rule.get('rule_id'),'rule_id');source=text(rule.get('source'),'rule source');premises=keys(rule.get('if'),'rule premises');conclusion=text(rule.get('then'),'rule conclusion')
    if rule.get('unless'):raise ValueError('positive single Horn rule only')
    task_id=text(target.get('task_id'),'task_id');task_source=text(target.get('source'),'task source');facts=keys(target.get('facts'),'target facts');query=text(target.get('query'),'target query')
    mapping={};targets=set();source_atoms=premises|{conclusion}
    for row in rows(p.get('feature_correspondences'),'feature_correspondences',minimum=1,maximum=64):
        a=text(row.get('source_feature'),'source_feature');b=text(row.get('target_feature'),'target_feature')
        if a in mapping or b in targets:raise ValueError('one-to-one unique correspondences required')
        mapping[a]=b;targets.add(b)
    if set(mapping)!=source_atoms:raise ValueError('correspondences must cover exactly rule atoms')
    adapted={'rule_id':ident,'if':sorted(mapping[a]for a in premises),'then':mapping[conclusion],'source':source}
    if query!=adapted['then']:raise ValueError('target query must equal mapped conclusion')
    expected=query in facts or set(adapted['if'])<=facts
    output={'status':'awaiting_independent_target_response','adapted_rule':adapted,'target_task':{'task_id':task_id,'facts':sorted(facts),'query':query,'source':task_source},'feature_correspondences':[{'source_feature':a,'target_feature':mapping[a]}for a in sorted(mapping)],'expected_target_entailment':expected,'target_response':None,'correct':None,'transfer_evidence_recorded':False,'source_truth_verified':False,'general_transfer':None,'boundary':'One explicit supplied positive Horn rule mapped bijectively to a symbolic target task; independent response is caller-declared, exact boolean entailment scoring only, not general cross-domain learning or verified truth.'}
    response=p.get('target_response')
    if response is None:return output
    if not isinstance(response,dict):raise ValueError('target_response object required')
    response={key:text(response.get(key),key)for key in ('response_id','source')}|{'entailed':response.get('entailed'),'independent':response.get('independent')}
    if type(response['entailed'])is not bool or response['independent']is not True:raise ValueError('boolean entailment and explicit independent target response required')
    return {**output,'status':'scored_transfer_evidence','target_response':response,'correct':response['entailed']==expected,'transfer_evidence_recorded':True}
