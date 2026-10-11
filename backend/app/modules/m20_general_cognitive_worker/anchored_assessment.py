"""Declared feature evidence against observable rubric anchors."""
from copy import deepcopy
from .calibration_predictor import text

def rows(value,label,minimum=0,maximum=1000):
    if not isinstance(value,list)or not minimum<=len(value)<=maximum:raise ValueError(label+' requires bounded object list')
    if any(not isinstance(row,dict)for row in value):raise ValueError(label+' requires objects')
    return value

def keys(value,label,minimum=0,maximum=64):
    if not isinstance(value,list)or not minimum<=len(value)<=maximum:raise ValueError(label+' requires bounded text list')
    for key in value:text(key,label)
    if len(set(value))!=len(value):raise ValueError(label+' requires unique keys')
    return set(value)

def assess(mode,p):
    artifact=text(p.get('artifact_id'),'artifact_id');author=text(p.get('author_id'),'author_id');rubric={}
    for row in rows(p.get('assessment_rubric'),'assessment_rubric',minimum=1,maximum=32):
        ident=text(row.get('criterion_id'),'criterion_id');source=text(row.get('source'),'rubric source');anchors={}
        if ident in rubric:raise ValueError('duplicate criterion_id')
        for anchor in rows(row.get('anchors'),'anchors',minimum=2,maximum=16):
            level=anchor.get('level');description=text(anchor.get('description'),'anchor description');features=keys(anchor.get('required_features'),'required_features')
            if type(level)is not int or not 0<=level<=100 or level in anchors:raise ValueError('unique integer anchor levels[0,100] required')
            anchors[level]={'level':level,'description':description,'required_features':sorted(features)}
        rubric[ident]={'criterion_id':ident,'source':source,'anchors':[anchors[level]for level in sorted(anchors)]}
    evidence={}
    for row in rows(p.get('assessment_evidence'),'assessment_evidence'):
        ident=text(row.get('evidence_id'),'evidence_id');owner=text(row.get('artifact_id'),'evidence artifact_id');source=text(row.get('source'),'evidence source');features=keys(row.get('features'),'evidence features')
        if ident in evidence or owner!=artifact:raise ValueError('unique evidence IDs bound to assessed artifact required')
        evidence[ident]={'evidence_id':ident,'artifact_id':owner,'source':source,'features':sorted(features)}
    controls=p.get('assessment_controls')
    if not isinstance(controls,dict):raise ValueError('assessment_controls object required')
    if type(controls.get('anonymized'))is not bool or controls.get('conflict_checked')is not True:raise ValueError('boolean anonymization and explicit conflict check required')
    conflicts=keys(controls.get('conflicted_rater_ids'),'conflicted_rater_ids');response=text(controls.get('author_response'),'author_response')
    if mode=='peer'and controls['anonymized']is not True:raise ValueError('peer assessment requires declared anonymization')
    normalized_controls={'anonymized':controls['anonymized'],'conflict_checked':True,'conflicted_rater_ids':sorted(conflicts),'author_response':response}
    reports=[];ids=set();pairs=set()
    for row in rows(p.get('assessment_ratings'),'assessment_ratings'):
        ident=text(row.get('rating_id'),'rating_id');criterion=text(row.get('criterion_id'),'rating criterion_id');rater=text(row.get('rater_id'),'rater_id');level=row.get('level');refs=keys(row.get('evidence_ids'),'rating evidence_ids')
        if ident in ids or (criterion,rater)in pairs:raise ValueError('unique rating IDs and criterion/rater pairs required')
        ids.add(ident);pairs.add((criterion,rater))
        if criterion not in rubric or type(level)is not int:raise ValueError('known criterion and integer anchor level required')
        anchors={a['level']:a for a in rubric[criterion]['anchors']}
        if level not in anchors or not refs<=set(evidence):raise ValueError('known anchor level/evidence IDs required')
        if mode=='self'and rater!=author or mode=='peer'and rater==author:raise ValueError('rater identity differs from self/peer mode')
        observed=set().union(*(set(evidence[key]['features'])for key in refs))if refs else set();missing=sorted(set(anchors[level]['required_features'])-observed);conflicted=rater in conflicts
        reports.append({'rating_id':ident,'criterion_id':criterion,'rater_id':rater,'level':level,'evidence_ids':sorted(refs),'missing_required_features':missing,'supported':bool(refs)and not missing and not conflicted,'missing_evidence':not refs,'conflicted':conflicted})
    criterion_reports=[]
    for key in sorted(rubric):
        rr=[r for r in reports if r['criterion_id']==key];levels=sorted({r['level']for r in rr if r['supported']});disagreement=len(levels)>1
        criterion_reports.append({'criterion_id':key,'supported_levels':levels,'disagreement':disagreement,'highest_anchor_supported':None if disagreement else bool(levels and levels[0]==max(a['level']for a in rubric[key]['anchors'])),'missing_ratings':not rr})
    return {'status':'assessed','mode':mode,'artifact_id':artifact,'author_id':author,'rubric':[rubric[k]for k in sorted(rubric)],'evidence':[evidence[k]for k in sorted(evidence)],'controls':normalized_controls,'rating_reports':sorted(reports,key=lambda r:(r['criterion_id'],r['rater_id'],r['rating_id'])),'criterion_reports':criterion_reports,'source_truth_verified':False,'mastery':None,'credential_decision':None,'boundary':'Declared observable-feature rubric anchors and supplied artifact evidence only; self/peer identity/control declarations are not independently verified. Disagreement retained without averaging, no mastery, psychometrics or credential decision.'}
