"""Explicit symbolic maps/constraints and checked supplied-action case reuse."""
from math import fsum
from .calibration_predictor import text,number
from .anchored_assessment import rows,keys

def features(value,label):
    if not isinstance(value,dict)or not 1<=len(value)<=64:raise ValueError(label+' requires1..64 feature dictionary')
    for key,val in value.items():text(key,label+' key');text(val,label+' value')
    return dict(value)

def analogy(p):
    source=features(p.get('analogy_source_features'),'analogy_source_features');target=features(p.get('analogy_target_features'),'analogy_target_features');mapping={};counts={}
    for row in rows(p.get('analogy_correspondences'),'analogy_correspondences',maximum=64):
        a=text(row.get('source_feature'),'source_feature');b=text(row.get('target_feature'),'target_feature')
        if a not in source or b not in target or a in mapping:raise ValueError('known feature references and unique source mapping required')
        mapping[a]=b;counts[b]=counts.get(b,0)+1
    missing_source=sorted(set(source)-set(mapping));missing_target=sorted(set(target)-set(counts));many=sorted(key for key,n in counts.items()if n>1);complete=not(missing_source or missing_target or many)
    constraints={};seen=set()
    for row in rows(p.get('target_constraints'),'target_constraints',maximum=64):
        key=text(row.get('feature_id'),'constraint feature');allowed=keys(row.get('allowed_values'),'allowed_values',minimum=1);provenance=text(row.get('source'),'constraint source')
        if key not in target:raise ValueError('unknown constraint feature')
        constraints.setdefault(key,[]).append({'allowed_values':allowed,'source':provenance})
    reports=[]
    for row in rows(p.get('candidate_inferences'),'candidate_inferences',maximum=256):
        key=text(row.get('inference_id'),'inference_id');atom=text(row.get('source_feature'),'inference source feature');value=text(row.get('value'),'inference value');provenance=text(row.get('source'),'inference source')
        if key in seen or atom not in source:raise ValueError('unique inference IDs and known source features required')
        seen.add(key);mapped=mapping.get(atom);checks=constraints.get(mapped,[]);matches=source[atom]==value
        reports.append({'inference_id':key,'source_feature':atom,'target_feature':mapped,'value':value,'source_value_matches':matches,'target_constraints_present':bool(checks),'constraint_sources':sorted(c['source']for c in checks),'supported':complete and matches and bool(checks)and all(value in c['allowed_values']for c in checks),'source':provenance})
    return {'status':'mapped'if complete else 'mapping_gaps','mapping_complete':complete,'unmapped_source_features':missing_source,'unmapped_target_features':missing_target,'many_to_one_targets':many,'correspondences':[{'source_feature':a,'target_feature':mapping[a]}for a in sorted(mapping)],'inference_reports':sorted(reports,key=lambda r:r['inference_id']),'source_truth_verified':False,'general_analogy':None,'boundary':'Explicit supplied symbolic correspondences and target allowed-value constraints only. Mapping gaps/many-to-one preserved; no semantic analogy discovery or independently verified inferences.'}

def reuse(p):
    weights=p.get('case_feature_weights')
    if not isinstance(weights,dict)or not 1<=len(weights)<=64:raise ValueError('case_feature_weights requires1..64 entries')
    for key,val in weights.items():
        text(key,'weight feature');number(val,'weight')
        if not 0<val<=1000:raise ValueError('weight(0,1000] required')
    target=p.get('case_target')
    if not isinstance(target,dict):raise ValueError('case_target object required')
    target_features=features(target.get('features'),'target features');target_source=text(target.get('source'),'target source')
    if set(target_features)!=set(weights):raise ValueError('target features must cover exactly weighted schema')
    bank={};ranked=[];total=fsum(weights.values())
    for row in rows(p.get('case_bank'),'case_bank',minimum=1,maximum=256):
        key=text(row.get('case_id'),'case_id');values=features(row.get('features'),'case features');action=text(row.get('proposed_action'),'proposed_action');source=text(row.get('source'),'case source')
        if key in bank or set(values)!=set(weights):raise ValueError('unique cases with exact weighted feature schema required')
        matches=sorted(k for k in weights if values[k]==target_features[k]);score=fsum(weights[k]for k in matches)/total;bank[key]={'action':action,'source':source}
        ranked.append({'case_id':key,'similarity':score,'matched_features':matches,'source':source})
    result={'status':'awaiting_target_checks','ranked_cases':sorted(ranked,key=lambda r:(-r['similarity'],r['case_id'])),'target_source':target_source,'adapted_action':None,'selected_case_id':None,'checks':[],'checks_passed':None,'action_executed':False,'source_truth_verified':False,'boundary':'Declared weighted exact feature case retrieval and supplied action reuse only after caller-recorded target checks. No invented adaptation, execution, semantic similarity or general case learning.'}
    supplied=p.get('case_target_checks')
    if supplied is None:return result
    if not isinstance(supplied,dict):raise ValueError('case_target_checks object required')
    selected=text(supplied.get('selected_case_id'),'selected_case_id')
    if selected not in bank:raise ValueError('unknown selected case')
    checks=[];seen=set()
    for row in rows(supplied.get('checks'),'checks',minimum=1,maximum=64):
        key=text(row.get('check_id'),'check_id');source=text(row.get('source'),'check source');passed=row.get('passed')
        if key in seen or type(passed)is not bool:raise ValueError('unique check IDs and boolean passed required')
        seen.add(key);checks.append({'check_id':key,'passed':passed,'source':source})
    passed=all(row['passed']for row in checks)
    return {**result,'status':'checked_case_reuse'if passed else 'target_checks_failed','selected_case_id':selected,'checks':sorted(checks,key=lambda r:r['check_id']),'checks_passed':passed,'adapted_action':bank[selected]['action']if passed else None}
