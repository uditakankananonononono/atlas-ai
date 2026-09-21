"""Non-diagnostic clinical decision support for feature rows 1110-1114.

This layer organizes clinician-supplied evidence. It never diagnoses, prescribes,
or executes treatment. Every output retains provenance, uncertainty and an
explicit clinician-review boundary.
"""
from __future__ import annotations
from dataclasses import dataclass,asdict
from math import isfinite
from datetime import date
from typing import Any

DISCLAIMER="Decision support only. A licensed clinician must verify inputs, context and recommendations before any clinical action."

def _require_citations(items:list[dict[str,Any]],label:str):
    if not items or any(not x.get('source_url') or not x.get('source_title') for x in items):raise ValueError(f'{label} requires source_url and source_title for every item')


def _num(value:Any,label:str)->float:
    try:result=float(value)
    except (TypeError,ValueError):raise ValueError(f'{label} must be numeric') from None
    if not isfinite(result):raise ValueError(f'{label} must be finite')
    return result

def _iso_date(value:Any,label:str)->date:
    try:return date.fromisoformat(str(value))
    except ValueError:raise ValueError(f'{label} must be an ISO date (YYYY-MM-DD)') from None

def differential(data:dict)->dict:
    findings=data.get('findings',[]);candidates=data.get('candidates',[])
    if not findings or not candidates:raise ValueError('findings and candidate conditions required')
    rows=[]
    for c in candidates:
        if not c.get('name') or not c.get('source_url'):raise ValueError('candidate name and source_url required')
        expected=set(c.get('supporting_findings',[]));against=set(c.get('contradicting_findings',[]));observed=set(findings);support=sorted(observed&expected);conflicts=sorted(observed&against);score=len(support)-1.5*len(conflicts);rows.append({'condition':c['name'],'supporting_findings':support,'contradictions':conflicts,'missing_discriminators':sorted(set(c.get('discriminating_tests',[]))-observed),'score':score,'source_url':c['source_url']})
    rows.sort(key=lambda r:r['score'],reverse=True)
    return {'ranked_differential':rows,'red_flags':data.get('red_flags',[]),'uncertainty':'Ranking reflects supplied findings/rules, not disease probability.','disclaimer':DISCLAIMER}

def protocol(data:dict)->dict:
    protocols=data.get('protocols',[]);facts=data.get('patient_facts',{})
    _require_citations(protocols,'protocols');eligible=[];excluded=[]
    for p in protocols:
        missing=[k for k,v in p.get('requires',{}).items() if facts.get(k)!=v];contra=[k for k,v in p.get('contraindications',{}).items() if facts.get(k)==v];row={'protocol_id':p.get('id'),'title':p.get('title'),'missing_requirements':missing,'matched_contraindications':contra,'source_url':p['source_url'],'source_title':p['source_title'],'version':p.get('version'),'effective_date':p.get('effective_date')};(eligible if not missing and not contra else excluded).append(row)
    return {'eligible_for_clinician_review':eligible,'excluded_or_incomplete':excluded,'patient_facts_used':facts,'disclaimer':DISCLAIMER}

def interactions(data:dict)->dict:
    meds=data.get('medications',[]);rules=data.get('interaction_rules',[])
    names={str(m.get('name','')).lower() for m in meds}
    _require_citations(rules,'interaction_rules');hits=[]
    for r in rules:
        pair=[str(x).lower() for x in r.get('pair',[])]
        if len(pair)!=2:raise ValueError('each interaction rule needs a pair')
        if set(pair)<=names:hits.append({'pair':r['pair'],'severity':r.get('severity','unknown'),'mechanism':r.get('mechanism'),'recommended_action':r.get('recommended_action'),'source_url':r['source_url'],'source_title':r['source_title']})
    severity_order={'contraindicated':0,'major':1,'moderate':2,'minor':3,'unknown':4};hits.sort(key=lambda h:severity_order.get(h['severity'],4));return {'interactions':hits,'medications_checked':sorted(names),'rule_count':len(rules),'coverage_warning':'No listed interaction means only that no supplied rule matched; it does not prove safety.','disclaimer':DISCLAIMER}

def dosage(data:dict)->dict:
    weight=float(data.get('weight_kg',0));mgkg=float(data.get('mg_per_kg',0));frequency=int(data.get('doses_per_day',0));max_daily=float(data.get('max_daily_mg',0));source=data.get('source',{})
    if any(not isfinite(v) for v in [weight,mgkg,max_daily]) or weight<=0 or mgkg<=0 or frequency<=0 or max_daily<=0 or not source.get('source_url'):raise ValueError('positive finite dose inputs and source_url required')
    raw=weight*mgkg;daily=raw*frequency;capped=min(raw,max_daily/frequency);return {'raw_mg_per_dose':raw,'raw_daily_mg':daily,'capped_mg_per_dose':capped,'capped_daily_mg':capped*frequency,'cap_applied':daily>max_daily,'frequency_per_day':frequency,'source':source,'verification_checks':['confirm current measured weight','confirm indication and route','confirm renal/hepatic adjustment','confirm concentration and rounding policy','independent clinician/pharmacist verification'],'disclaimer':DISCLAIMER}

def clinical_support(method:str,data:dict)->dict:
    methods={'differential_diagnosis':differential,'treatment_protocol_selection':protocol,'drug_interaction_check':interactions,'dosage_calculation':dosage}
    if method=='clinical_decision_support':
        result={'sections':{'differential':differential(data['differential']) if data.get('differential') else None,'protocols':protocol(data['protocols']) if data.get('protocols') else None,'interactions':interactions(data['interactions']) if data.get('interactions') else None,'dosage':dosage(data['dosage']) if data.get('dosage') else None},'disclaimer':DISCLAIMER}
    elif method in CLINICAL_EXTRA:result=CLINICAL_EXTRA[method](data)
    elif method in methods:result=methods[method](data)
    else:raise ValueError('unsupported clinical support method')
    result=dict(result)
    urgent=bool(result.get('immediate_human_response_required') or result.get('urgent') or result.get('red_flags'))
    result['evaluation']={'method_executed':method,'input_fields':sorted(data),'output_fields':sorted(result),'qualified_clinician_review_required':True,'urgent_human_response_required':urgent}
    result['uncertainty_report']={'caller_supplied_data_not_independently_verified':True,'diagnosis_or_treatment_authorized':False,'patient_exam_performed':False,'missing_or_unknown_fields':result.get('missing_safety_fields',result.get('unknowns',[])),'existing_uncertainty':result.get('uncertainty')}
    return result

def imaging_support(method:str,data:dict)->dict:
    """Validate externally-produced measurements/findings; no pixel-level diagnosis."""
    findings=data.get('findings',[]);metadata=data.get('study_metadata',{});source=data.get('source',{})
    if not isinstance(findings,list) or not findings or not metadata.get('modality') or not source.get('source_url'):raise ValueError('findings, study modality and source_url required')
    normalized=[]
    for f in findings:
        if not f.get('label') or 'confidence' not in f:raise ValueError('each finding needs label and confidence')
        confidence=float(f['confidence'])
        if not 0<=confidence<=1:raise ValueError('confidence must be in [0,1]')
        normalized.append({'label':f['label'],'confidence':confidence,'location':f.get('location'),'measurement':f.get('measurement'),'provenance':f.get('provenance','external_model_or_clinician')})
    normalized.sort(key=lambda x:x['confidence'],reverse=True)
    return {'mode':method,'study_metadata':metadata,'findings_for_specialist_review':normalized,'quality_flags':data.get('quality_flags',[]),'source':source,'coverage_warning':'Atlas did not inspect pixels/slides directly; it organizes supplied findings and cannot rule out unlisted abnormalities.','disclaimer':DISCLAIMER}

def waveform_support(method:str,data:dict)->dict:
    rate=float(data.get('sampling_rate_hz',0));samples=data.get('samples');annotations=data.get('annotations',[]);source=data.get('source',{})
    if rate<=0 or not isinstance(samples,list) or len(samples)<3 or any(not isinstance(v,(int,float)) or not isfinite(float(v)) for v in samples) or not source.get('source_url'):raise ValueError('finite samples, positive sampling rate and source_url required')
    values=[float(v) for v in samples];duration=len(values)/rate;mean=sum(values)/len(values);rms=(sum(v*v for v in values)/len(values))**.5;peak=max(abs(v) for v in values);zero_crossings=sum((a<mean)<(b<mean) for a,b in zip(values,values[1:]));return {'mode':method,'signal_summary':{'samples':len(values),'sampling_rate_hz':rate,'duration_seconds':duration,'mean':mean,'rms':rms,'absolute_peak':peak,'mean_crossing_rate_hz':zero_crossings/(2*duration) if duration else 0},'supplied_annotations':annotations,'quality_flags':data.get('quality_flags',[]),'source':source,'interpretation_boundary':'Signal statistics are not rhythm, seizure, or disease interpretation. Specialist review of the original tracing is required.','disclaimer':DISCLAIMER}

def genomics_support(data:dict)->dict:
    variants=data.get('variants',[]);knowledge=data.get('knowledge_records',[])
    if not isinstance(variants,list) or not variants:raise ValueError('variants required')
    _require_citations(knowledge,'knowledge_records');by_key={(str(r.get('gene')),str(r.get('variant'))):r for r in knowledge};rows=[]
    for v in variants:
        key=(str(v.get('gene')),str(v.get('variant')));record=by_key.get(key);rows.append({'gene':key[0],'variant':key[1],'classification':record.get('classification') if record else 'not_in_supplied_knowledge','evidence_level':record.get('evidence_level') if record else None,'condition':record.get('condition') if record else None,'source_url':record.get('source_url') if record else None,'review_status':'specialist_review_required'})
    return {'variant_interpretations':rows,'coverage_warning':'Absence from supplied knowledge is not benign evidence. Confirm nomenclature, zygosity, reference build and current expert-curated sources.','disclaimer':DISCLAIMER}

CLINICAL_EXTRA={'medical_image_analysis':lambda d:imaging_support('medical_image_analysis',d),'radiology_report_generation':lambda d:imaging_support('radiology_report_generation',d),'pathology_slide_analysis':lambda d:imaging_support('pathology_slide_analysis',d),'ecg_interpretation':lambda d:waveform_support('ecg_interpretation',d),'eeg_analysis':lambda d:waveform_support('eeg_analysis',d),'genomics_interpretation':genomics_support}

def pharmacogenomics(data:dict)->dict:
    genotypes=data.get('genotypes',[]);rules=data.get('guideline_rules',[]);_require_citations(rules,'guideline_rules');matched=[]
    for g in genotypes:
        for r in rules:
            if str(r.get('gene'))==str(g.get('gene')) and str(r.get('diplotype'))==str(g.get('diplotype')):matched.append({'gene':g.get('gene'),'diplotype':g.get('diplotype'),'phenotype':r.get('phenotype'),'drug':r.get('drug'),'guideline_text':r.get('guideline_text'),'source_url':r['source_url'],'source_title':r['source_title'],'version':r.get('version'),'review_status':'pharmacist_or_specialist_review_required'})
    return {'matched_guidelines':matched,'unmatched_genotypes':[g for g in genotypes if not any(m['gene']==g.get('gene') and m['diplotype']==g.get('diplotype') for m in matched)],'boundary':'Guideline lookup only. Confirm genotype calling, allele function, phenotype translation, drug indication, interactions and current guideline version.','disclaimer':DISCLAIMER}

def trial_match(data:dict)->dict:
    profile=data.get('profile',{});trials=data.get('trials',[]);_require_citations(trials,'trials');rows=[]
    for t in trials:
        unmet=[];excluded=[]
        for k,v in t.get('inclusion',{}).items():
            if k not in profile:unmet.append({'field':k,'reason':'missing'})
            elif profile[k]!=v:unmet.append({'field':k,'reason':'not_met'})
        for k,v in t.get('exclusion',{}).items():
            if profile.get(k)==v:excluded.append(k)
        status='potential_match' if not unmet and not excluded else 'needs_information' if any(x['reason']=='missing' for x in unmet) and not excluded else 'not_matched'
        rows.append({'trial_id':t.get('trial_id'),'title':t.get('title'),'status':status,'unmet_or_missing_inclusion':unmet,'matched_exclusions':excluded,'source_url':t['source_url'],'last_verified_at':t.get('last_verified_at')})
    order={'potential_match':0,'needs_information':1,'not_matched':2};rows.sort(key=lambda x:order[x['status']]);return {'matches':rows,'boundary':'Pre-screen only. Trial staff must confirm current recruitment, complete eligibility and consent. No enrollment or contact is performed.','disclaimer':DISCLAIMER}

def adverse_events(data:dict)->dict:
    notes=data.get('notes',[]);terms=data.get('event_terms',[])
    if not isinstance(notes,list) or not isinstance(terms,list) or not terms:raise ValueError('notes and event_terms required')
    hits=[]
    for i,note in enumerate(notes):
        text=str(note.get('text','')).lower()
        for term in terms:
            token=str(term).lower()
            if token and token in text:hits.append({'note_index':i,'term':term,'snippet':note.get('text'),'occurred_at':note.get('occurred_at'),'provenance':note.get('provenance')})
    return {'signals_for_review':hits,'signal_count':len(hits),'boundary':'Keyword surveillance only. A signal is not causality, severity or a reportable diagnosis. Clinicians/safety staff must review and follow applicable reporting rules.','disclaimer':DISCLAIMER}

def risk_stratification(data:dict)->dict:
    factors=data.get('factors',{});model=data.get('model',{});source=model.get('source',{})
    if not source.get('source_url') or not isinstance(model.get('coefficients'),dict):raise ValueError('cited model coefficients required')
    missing=[k for k in model['coefficients'] if k not in factors]
    if missing:return {'status':'insufficient_data','missing_factors':missing,'source':source,'disclaimer':DISCLAIMER}
    score=float(model.get('intercept',0))+sum(float(w)*float(factors[k]) for k,w in model['coefficients'].items());thresholds=sorted(model.get('thresholds',[]),key=lambda x:float(x['minimum']));band='unclassified'
    for t in thresholds:
        if score>=float(t['minimum']):band=t['label']
    return {'status':'scored','score':score,'risk_band':band,'factors_used':factors,'model_name':model.get('name'),'model_version':model.get('version'),'source':source,'calibration_context':model.get('calibration_context'),'boundary':'Use only in the population and setting for which the model is validated. Risk score is not a diagnosis or treatment order.','disclaimer':DISCLAIMER}

CLINICAL_EXTRA.update({'pharmacogenomic_recommendations':pharmacogenomics,'clinical_trial_matching':trial_match,'adverse_event_detection':adverse_events,'patient_risk_stratification':risk_stratification})

def validated_score(method:str,data:dict)->dict:
    outcome=data.get('outcome_name',method);factors=data.get('factors',{});model=data.get('model',{});source=model.get('source',{})
    if not source.get('source_url') or not isinstance(model.get('coefficients'),dict):raise ValueError('cited model coefficients required')
    missing=[k for k in model['coefficients'] if k not in factors]
    if missing:return {'status':'insufficient_data','missing_factors':missing,'outcome':outcome,'source':source,'disclaimer':DISCLAIMER}
    linear=float(model.get('intercept',0))+sum(float(w)*float(factors[k]) for k,w in model['coefficients'].items());kind=model.get('link','logistic')
    if kind=='logistic':probability=1/(1+__import__('math').exp(-max(-700,min(700,linear))))
    elif kind=='identity':probability=None
    else:raise ValueError('model link must be logistic or identity')
    thresholds=sorted(model.get('thresholds',[]),key=lambda x:float(x['minimum']));value=probability if probability is not None else linear;band='unclassified'
    for t in thresholds:
        if value>=float(t['minimum']):band=t['label']
    return {'status':'scored','outcome':outcome,'linear_predictor':linear,'probability':probability,'predicted_value':linear if kind=='identity' else None,'risk_band':band,'model_name':model.get('name'),'model_version':model.get('version'),'source':source,'validation_population':model.get('validation_population'),'calibration':model.get('calibration'),'factors_used':factors,'boundary':'Use only in the validated population/setting. This estimate does not determine disposition, treatment, resource access or prognosis by itself.','disclaimer':DISCLAIMER}

def triage_support(data:dict)->dict:
    observations=data.get('observations',{});rules=data.get('rules',[]);_require_citations(rules,'rules');matched=[]
    for r in rules:
        ok=True
        for field,condition in r.get('when',{}).items():
            value=observations.get(field)
            if value is None:ok=False;break
            if isinstance(condition,dict):
                if 'lt' in condition and not float(value)<float(condition['lt']):ok=False
                if 'lte' in condition and not float(value)<=float(condition['lte']):ok=False
                if 'gt' in condition and not float(value)>float(condition['gt']):ok=False
                if 'gte' in condition and not float(value)>=float(condition['gte']):ok=False
            elif value!=condition:ok=False
        if ok:matched.append({'level':r.get('level'),'reason':r.get('reason'),'recommended_next_step':r.get('recommended_next_step'),'source_url':r['source_url']})
    priority={'resuscitation':0,'emergent':1,'urgent':2,'less_urgent':3,'non_urgent':4};matched.sort(key=lambda x:priority.get(x['level'],99));return {'highest_priority_match':matched[0] if matched else None,'all_matched_rules':matched,'missing_observations':[x for x in data.get('required_observations',[]) if x not in observations],'boundary':'Rule transparency for trained clinical review. Never delay emergency services or use as autonomous disposition. If severe symptoms or uncertainty exist, escalate according to local emergency policy.','disclaimer':DISCLAIMER}

for _m in ['readmission_prediction','sepsis_early_warning','mortality_prediction','length_of_stay_prediction','icu_resource_allocation']:
    CLINICAL_EXTRA[_m]=lambda d,m=_m:validated_score(m,d)
CLINICAL_EXTRA['emergency_triage']=triage_support

def care_plan(method:str,data:dict)->dict:
    goals=data.get('goals',[]);interventions=data.get('interventions',[]);baseline=data.get('baseline',{});source=data.get('source',{})
    if not goals or not interventions or not source.get('source_url'):raise ValueError('goals, interventions and source_url required')
    rows=[]
    for g in goals:
        if not g.get('id') or not g.get('measure') or 'target' not in g:raise ValueError('each goal needs id, measure and target')
        linked=[i for i in interventions if g['id'] in i.get('goal_ids',[])];rows.append({'goal_id':g['id'],'measure':g['measure'],'baseline':baseline.get(g['measure']),'target':g['target'],'time_horizon':g.get('time_horizon'),'linked_interventions':linked,'review_cadence':g.get('review_cadence'),'stop_or_escalate_criteria':g.get('stop_or_escalate_criteria',[])})
    return {'mode':method,'goals':rows,'unlinked_interventions':[i for i in interventions if not i.get('goal_ids')],'source':source,'approval_status':'draft_for_multidisciplinary_review','boundary':'Planning structure only. The treating team and patient choose, authorize, adapt and stop interventions.','disclaimer':DISCLAIMER}

def anesthesia_monitoring(data:dict)->dict:
    observations=data.get('observations',[]);thresholds=data.get('thresholds',[]);_require_citations(thresholds,'thresholds')
    if not observations:raise ValueError('observations required')
    alerts=[]
    for obs in observations:
        for t in thresholds:
            if obs.get('metric')!=t.get('metric'):continue
            value=float(obs['value']);trigger=('lt' in t and value<float(t['lt'])) or ('gt' in t and value>float(t['gt']))
            if trigger:alerts.append({'metric':obs['metric'],'value':value,'observed_at':obs.get('observed_at'),'severity':t.get('severity'),'response_protocol':t.get('response_protocol'),'source_url':t['source_url']})
    return {'alerts_for_anesthesia_team':alerts,'observations_checked':len(observations),'boundary':'Supplemental threshold surveillance only. It does not control equipment, administer drugs or replace continuous anesthesiologist monitoring.','disclaimer':DISCLAIMER}

def postop(data:dict)->dict:
    observations=data.get('observations',{});milestones=data.get('milestones',[]);escalation=data.get('escalation_rules',[]);_require_citations(escalation,'escalation_rules');status=[]
    for m in milestones:status.append({'milestone':m.get('name'),'target_by':m.get('target_by'),'observed':observations.get(m.get('measure')),'met':observations.get(m.get('measure'))==m.get('target') if m.get('measure') in observations else None})
    flags=[]
    for r in escalation:
        value=observations.get(r.get('metric'))
        if value is None:continue
        if ('lt' in r and float(value)<float(r['lt'])) or ('gt' in r and float(value)>float(r['gt'])):flags.append({'metric':r['metric'],'value':value,'reason':r.get('reason'),'next_step':r.get('next_step'),'source_url':r['source_url']})
    return {'milestone_status':status,'escalation_flags':flags,'boundary':'Tracking and escalation prompts only. The surgical team controls discharge, medication and intervention decisions.','disclaimer':DISCLAIMER}

def therapy_design(method:str,data:dict)->dict:
    assessment=data.get('assessment',{});goals=data.get('goals',[]);activities=data.get('activities',[]);source=data.get('source',{})
    if not assessment or not goals or not source.get('source_url'):raise ValueError('assessment, goals and source_url required')
    sessions=[]
    for goal in goals:
        selected=[a for a in activities if goal.get('domain') in a.get('domains',[]) and not set(a.get('contraindications',[]))&set(assessment.get('contraindications',[]))];sessions.append({'goal':goal,'candidate_activities':selected,'progress_measure':goal.get('measure'),'review_after_sessions':goal.get('review_after_sessions',1)})
    return {'mode':method,'assessment_used':assessment,'goal_plans':sessions,'source':source,'approval_status':'draft_for_licensed_therapist_and_patient','boundary':'Candidate-plan generation only. Licensed therapists assess safety, personalize dosage/intensity and supervise execution.','disclaimer':DISCLAIMER}

CLINICAL_EXTRA.update({'surgical_planning':lambda d:care_plan('surgical_planning',d),'anesthesia_monitoring':anesthesia_monitoring,'post_operative_care':postop,'rehabilitation_planning':lambda d:care_plan('rehabilitation_planning',d),'physical_therapy_design':lambda d:therapy_design('physical_therapy_design',d),'occupational_therapy_design':lambda d:therapy_design('occupational_therapy_design',d),'speech_therapy_design':lambda d:therapy_design('speech_therapy_design',d)})

def scored_screen(method:str,data:dict)->dict:
    """Score a supplied, cited screening instrument without converting it to diagnosis."""
    instrument=data.get('instrument',{});answers=data.get('answers',{});items=instrument.get('items',[]);source=instrument.get('source',{})
    if not instrument.get('name') or not items or not source.get('source_url'):raise ValueError('named instrument with items and source_url required')
    missing=[str(i.get('id')) for i in items if str(i.get('id')) not in answers]
    invalid=[];score=0.0
    for item in items:
        key=str(item.get('id')); value=answers.get(key)
        if value is None:continue
        allowed=item.get('allowed_values')
        if allowed is not None and value not in allowed:invalid.append(key);continue
        score+=float(value)*float(item.get('weight',1))
    if missing or invalid:return {'mode':method,'status':'incomplete','missing_items':missing,'invalid_items':invalid,'instrument':instrument['name'],'source':source,'disclaimer':DISCLAIMER}
    bands=sorted(instrument.get('bands',[]),key=lambda x:float(x['minimum']));band='unclassified'
    for row in bands:
        if score>=float(row['minimum']):band=row['label']
    crisis_items=[]
    for item in items:
        key=str(item.get('id'))
        if item.get('urgent_if_at_or_above') is not None and float(answers[key])>=float(item['urgent_if_at_or_above']):crisis_items.append(key)
    return {'mode':method,'status':'scored','instrument':instrument['name'],'instrument_version':instrument.get('version'),'score':score,'screening_band':band,'urgent_response_required':bool(crisis_items),'urgent_items':crisis_items,'source':source,'boundary':'A screen is not a diagnosis. A qualified clinician must assess history, duration, impairment, differential causes and immediate safety. Any urgent response follows local crisis/emergency policy now, not a future automated workflow.','disclaimer':DISCLAIMER}

def mental_health_assessment(data:dict)->dict:
    domains=data.get('domains',[]);safety=data.get('safety',{});sources=data.get('sources',[]);_require_citations(sources,'sources')
    if not domains:raise ValueError('assessment domains required')
    required={'suicidal_intent','self_harm_risk','harm_to_others','unable_to_care_for_self'};missing=sorted(required-set(safety))
    urgent=[k for k,v in safety.items() if k in required and v is True]
    return {'domains':[{'name':d.get('name'),'observations':d.get('observations',[]),'patient_words':d.get('patient_words'),'unknowns':d.get('unknowns',[]),'functional_impact':d.get('functional_impact')} for d in domains],'safety_status':'incomplete' if missing else 'urgent' if urgent else 'no_supplied_urgent_flag','missing_safety_fields':missing,'urgent_safety_flags':urgent,'sources':sources,'boundary':'Structured documentation, not diagnosis or a substitute for direct clinical interview. Urgent flags require immediate local crisis/emergency response and human assessment.','disclaimer':DISCLAIMER}

def addiction_plan(data:dict)->dict:
    assessment=data.get('assessment',{});goals=data.get('goals',[]);options=data.get('options',[]);source=data.get('source',{})
    if not assessment or not goals or not source.get('source_url'):raise ValueError('assessment, patient goals and source_url required')
    risks=[k for k in ['overdose_risk','dangerous_withdrawal_risk','suicidality'] if assessment.get(k) is True]
    suitable=[o for o in options if assessment.get('readiness_stage') in o.get('readiness_stages',[]) and not set(o.get('contraindications',[]))&set(assessment.get('contraindications',[]))]
    return {'patient_goals':goals,'readiness_stage':assessment.get('readiness_stage'),'candidate_options_for_shared_decision':suitable,'urgent_medical_review':bool(risks),'urgent_risk_factors':risks,'source':source,'boundary':'Draft for licensed addiction care and shared decision-making. Dangerous withdrawal, overdose or suicidality needs immediate human medical/crisis response; Atlas does not detoxify, prescribe or place a patient.','disclaimer':DISCLAIMER}

def cognitive_profile(method:str,data:dict)->dict:
    results=data.get('test_results',[]);source=data.get('source',{})
    if not results or not source.get('source_url'):raise ValueError('test_results and source_url required')
    rows=[]
    for r in results:
        if not r.get('domain') or 'score' not in r or 'norm_mean' not in r or not float(r.get('norm_sd',0)):raise ValueError('each result needs domain, score, norm_mean and nonzero norm_sd')
        z=(float(r['score'])-float(r['norm_mean']))/float(r['norm_sd']);rows.append({'domain':r['domain'],'score':r['score'],'z_score':z,'norm_group':r.get('norm_group'),'validity_flags':r.get('validity_flags',[]),'interpretation':'below_expected' if z<=-1.5 else 'above_expected' if z>=1.5 else 'within_reference_range'})
    return {'mode':method,'domain_profile':rows,'context':data.get('context',{}),'source':source,'boundary':'Descriptive comparison to the supplied norms only. A qualified neuropsychologist must assess test validity, language, education, culture, effort, function, medical causes and longitudinal change before interpretation or diagnosis.','disclaimer':DISCLAIMER}

def psychotherapy_plan(method:str,data:dict)->dict:
    formulation=data.get('formulation',{});goals=data.get('goals',[]);interventions=data.get('interventions',[]);source=data.get('source',{})
    if not formulation or not goals or not source.get('source_url'):raise ValueError('formulation, collaborative goals and source_url required')
    selected=[]
    for i in interventions:
        if set(i.get('targets',[]))&{g.get('target') for g in goals} and not set(i.get('contraindications',[]))&set(formulation.get('contraindications',[])):selected.append(i)
    return {'mode':method,'collaborative_formulation':formulation,'goals':goals,'candidate_interventions':selected,'outcome_measures':data.get('outcome_measures',[]),'source':source,'approval_status':'draft_for_patient_and_licensed_therapist','boundary':'Collaborative planning aid only. It does not conduct psychotherapy, infer hidden mental states, or replace therapeutic alliance, consent, safety planning and clinician judgment.','disclaimer':DISCLAIMER}

def dbt_skills(data:dict)->dict:
    target=data.get('target');skills=data.get('skills',[]);source=data.get('source',{});crisis=data.get('crisis',False)
    if not target or not skills or not source.get('source_url'):raise ValueError('target, skills and source_url required')
    candidates=[s for s in skills if target in s.get('targets',[]) and not s.get('requires_supervision',False)]
    return {'target':target,'candidate_skills':candidates,'crisis':bool(crisis),'source':source,'boundary':'Skills reference for clinician/patient selection, not crisis care. If crisis is present, use the agreed safety plan and immediate local crisis/emergency support instead of relying on this output.','disclaimer':DISCLAIMER}

CLINICAL_EXTRA.update({
 'mental_health_assessment':mental_health_assessment,
 'depression_screening':lambda d:scored_screen('depression_screening',d),
 'anxiety_assessment':lambda d:scored_screen('anxiety_assessment',d),
 'ptsd_evaluation':lambda d:scored_screen('ptsd_evaluation',d),
 'addiction_treatment_planning':addiction_plan,
 'cognitive_assessment':lambda d:cognitive_profile('cognitive_assessment',d),
 'dementia_screening':lambda d:scored_screen('dementia_screening',d),
 'neuropsychological_testing':lambda d:cognitive_profile('neuropsychological_testing',d),
 'psychotherapy_planning':lambda d:psychotherapy_plan('psychotherapy_planning',d),
 'cbt_protocol_design':lambda d:psychotherapy_plan('cbt_protocol_design',d),
 'dbt_skill_selection':dbt_skills,
})

def medication_management(data:dict)->dict:
    lists=data.get('medication_lists',[]);rules=data.get('interaction_rules',[]);source=data.get('source',{})
    if len(lists)<2 or not source.get('source_url'):raise ValueError('at least two medication lists and source_url required')
    by_name={};conflicts=[]
    for record in lists:
        origin=record.get('origin')
        for med in record.get('medications',[]):
            name=str(med.get('name','')).strip().lower()
            if not name:raise ValueError('each medication needs name')
            row={**med,'origin':origin};by_name.setdefault(name,[]).append(row)
    reconciled=[]
    for name,records in by_name.items():
        signatures={(r.get('dose'),r.get('route'),r.get('frequency'),r.get('status')) for r in records}
        if len(signatures)>1:conflicts.append({'medication':name,'records':records,'resolution':'prescriber_or_pharmacist_review'})
        reconciled.append({'medication':name,'records':records,'consistent':len(signatures)==1})
    interaction_result=interactions({'medications':[{'name':x} for x in by_name],'interaction_rules':rules}) if rules else {'interactions':[],'coverage_warning':'No interaction rules supplied; interaction safety was not assessed.'}
    return {'reconciled_medications':reconciled,'discrepancies':conflicts,'interaction_review':interaction_result,'source':source,'approval_status':'draft_for_prescriber_or_pharmacist','boundary':'Reconciliation and cited rule matching only. Atlas does not start, stop, refill or change medication; verify indication, allergies, organ function, adherence, interactions and the actual containers with patient and clinician.','disclaimer':DISCLAIMER}

_CHRONIC_BOUNDARIES={
 'chronic_disease_management':'Longitudinal tracking across conditions against clinician-supplied targets only. Targets and actions require patient-specific licensed review; Atlas does not diagnose exacerbation, prescribe, titrate treatment or replace urgent assessment.',
 'diabetes_management':'Glucose tracking against clinician-supplied targets only. Below-range values, especially urgent lows, require licensed review and the patient hypoglycemia plan; Atlas does not diagnose exacerbation, dose insulin or replace urgent assessment.',
 'hypertension_management':'Blood-pressure reading organization against clinician-supplied targets only. Averages and thresholds require licensed review with measurement-protocol context; Atlas does not diagnose hypertension, titrate medication or replace urgent assessment.',
 'asthma_management':'Clinician-authored action-plan zone matching only. Zone changes and reliever use require licensed review; Atlas does not diagnose exacerbation, prescribe or replace urgent respiratory assessment.',
 'copd_management':'Symptom and history organization against clinician-supplied targets only. Exacerbation judgment and oxygen or inhaler changes require licensed review; Atlas does not diagnose exacerbation, prescribe or replace urgent assessment.',
 'heart_failure_management':'Weight and symptom tracking against clinician-supplied thresholds only. Weight alerts route to the heart-failure team for licensed review; Atlas does not diagnose exacerbation, adjust diuretics or replace urgent assessment.',
}

def _chronic_registry(data:dict,status:list)->dict:
    measured=[x for x in status if x['status']!='missing'];within=[x for x in measured if x['status']=='within_target']
    conditions=sorted({str((x.get('target') or {}).get('condition')) for x in status if (x.get('target') or {}).get('condition')})
    return {'condition_registry':conditions,'control_summary':{'metrics_measured':len(measured),'metrics_within_target':len(within),'control_fraction':round(len(within)/len(measured),4) if measured else None},'registry_note':'Coverage of supplied targets only; unmeasured conditions are not controlled.'}

def _diabetes_enrichment(data:dict,status:list)->dict:
    below=[]
    for row in status:
        t=row.get('target') or {};value=row.get('value')
        if value is None or t.get('minimum') is None:continue
        if _num(value,'observation')<_num(t['minimum'],'target minimum'):
            severe=t.get('severe_minimum');urgent=severe is not None and _num(value,'observation')<_num(severe,'severe_minimum')
            below.append({'metric':row['metric'],'value':value,'below_range':True,'urgent_low_glucose':urgent})
    readings=data.get('readings',[])
    if not isinstance(readings,list):raise ValueError('readings must be a list of supplied glucose values')
    tir=None
    ranged=[(x.get('target') or {}) for x in status if (x.get('target') or {}).get('minimum') is not None and (x.get('target') or {}).get('maximum') is not None]
    if readings and ranged:
        lo=_num(ranged[0]['minimum'],'target minimum');hi=_num(ranged[0]['maximum'],'target maximum')
        values=[_num(v,'reading') for v in readings]
        tir=round(sum(1 for v in values if lo<=v<=hi)/len(values),4)
    return {'glucose_safety_review':below,'time_in_range_fraction':tir,'time_in_range_note':'Computed only from supplied readings against the clinician-supplied range; not a diagnosis.'}

def _hypertension_enrichment(data:dict,status:list)->dict:
    readings=data.get('readings',[])
    if not isinstance(readings,list):raise ValueError('readings must be a list of systolic/diastolic pairs')
    pairs=[]
    for r in readings:
        if not isinstance(r,dict) or 'systolic' not in r or 'diastolic' not in r:raise ValueError('each reading needs systolic and diastolic')
        pairs.append({'systolic':_num(r['systolic'],'systolic'),'diastolic':_num(r['diastolic'],'diastolic'),'observed_at':r.get('observed_at')})
    summary=None
    if pairs:summary={'reading_count':len(pairs),'average_systolic':round(sum(p['systolic'] for p in pairs)/len(pairs),2),'average_diastolic':round(sum(p['diastolic'] for p in pairs)/len(pairs),2),'review_thresholds_as_supplied':data.get('review_thresholds')}
    return {'reading_pair_summary':summary,'readings_used':pairs,'averaging_note':'Averages only; clinicians interpret against measurement protocol and patient context.'}

def _asthma_enrichment(data:dict,status:list)->dict:
    rules=data.get('zone_rules',[])
    if not isinstance(rules,list):raise ValueError('zone_rules must be a clinician-authored list')
    zones=[]
    for row in status:
        value=row.get('value');assigned=None
        if value is not None:
            for z in rules:
                ok=True
                if z.get('minimum') is not None and _num(value,'observation')<_num(z['minimum'],'zone minimum'):ok=False
                if z.get('maximum') is not None and _num(value,'observation')>_num(z['maximum'],'zone maximum'):ok=False
                if ok:assigned=z.get('zone');break
        zones.append({'metric':row['metric'],'clinician_authored_zone':assigned})
    return {'action_plan_zones':zones,'zone_rules_supplied':bool(rules),'zone_note':'Zones come from the clinician-authored action plan only; Atlas never assigns severity.'}

def _copd_enrichment(data:dict,status:list)->dict:
    exacerbations=data.get('exacerbations',[])
    if not isinstance(exacerbations,list):raise ValueError('exacerbations must be a list')
    dated=sorted((x for x in exacerbations if isinstance(x,dict) and x.get('date')),key=lambda x:str(x['date']))
    scores=data.get('symptom_scores',[])
    if not isinstance(scores,list):raise ValueError('symptom_scores must be a list')
    trend=sorted(({'date':s.get('date'),'score':_num(s['score'],'symptom score'),'instrument':s.get('instrument')} for s in scores if isinstance(s,dict) and 'score' in s),key=lambda x:str(x['date']))
    return {'exacerbation_history_summary':{'recorded_count':len(exacerbations),'most_recent':dated[-1]['date'] if dated else None,'undated_records':len(exacerbations)-len(dated)},'symptom_score_trend':trend,'history_note':'History as recorded; clinicians judge exacerbation and control.'}

def _heart_failure_enrichment(data:dict,status:list)->dict:
    weights=data.get('daily_weights',[])
    if not isinstance(weights,list):raise ValueError('daily_weights must be a list')
    pts=sorted(({'date':w.get('date'),'weight_kg':_num(w['weight_kg'],'weight_kg')} for w in weights if isinstance(w,dict) and 'weight_kg' in w),key=lambda x:str(x['date']))
    gains=[]
    for i in range(len(pts)):
        for j in range(i+1,len(pts)):
            if j-i<=2:gains.append({'from':pts[i]['date'],'to':pts[j]['date'],'gain_kg':round(pts[j]['weight_kg']-pts[i]['weight_kg'],3)})
    max_gain=max((g['gain_kg'] for g in gains),default=None)
    threshold=data.get('alert_gain_kg');flag=None
    if threshold is not None and max_gain is not None:flag=max_gain>=_num(threshold,'alert_gain_kg')
    return {'daily_weight_trend':{'readings':pts,'max_window_gain_kg':max_gain,'alert_threshold_kg_as_supplied':threshold,'weight_review_flag':flag},'weight_note':'Weight alerts route to the care team; Atlas never adjusts diuretics.'}

_CHRONIC_ENRICHMENTS={
 'chronic_disease_management':_chronic_registry,'diabetes_management':_diabetes_enrichment,
 'hypertension_management':_hypertension_enrichment,'asthma_management':_asthma_enrichment,
 'copd_management':_copd_enrichment,'heart_failure_management':_heart_failure_enrichment,
}

def chronic_care_plan(method:str,data:dict)->dict:
    observations=data.get('observations',{});targets=data.get('targets',[]);actions=data.get('actions',[]);source=data.get('source',{})
    if not isinstance(observations,dict):raise ValueError('observations must be an object keyed by metric')
    if not isinstance(targets,list) or not isinstance(actions,list):raise ValueError('targets and actions must be lists')
    if not targets or not source.get('source_url'):raise ValueError('targets and source_url required')
    if method not in _CHRONIC_ENRICHMENTS:raise ValueError(f'unsupported chronic care method: {method}')
    status=[];missing=[];alerts=[]
    for t in targets:
        metric=t.get('metric');value=observations.get(metric)
        if value is None:missing.append(metric);status.append({'metric':metric,'status':'missing','value':None,'target':t});continue
        value=_num(value,'observation');within=True
        if t.get('minimum') is not None and value<_num(t['minimum'],'target minimum'):within=False
        if t.get('maximum') is not None and value>_num(t['maximum'],'target maximum'):within=False
        row={'metric':metric,'value':value,'status':'within_target' if within else 'outside_target','target':t,'observed_at':data.get('observed_at')};status.append(row)
        if not within:alerts.append(row)
    candidates=[]
    for a in actions:
        if a.get('trigger_metric') in {x['metric'] for x in alerts} and not set(a.get('contraindications',[]))&set(data.get('contraindications',[])):candidates.append(a)
    result={'mode':method,'metric_status':status,'missing_metrics':missing,'outside_target':alerts,'candidate_actions_for_shared_review':candidates,'patient_goals':data.get('patient_goals',[]),'source':source}
    result.update(_CHRONIC_ENRICHMENTS[method](data,status))
    if method=='diabetes_management' and any(x['urgent_low_glucose'] for x in result['glucose_safety_review']):result['immediate_human_response_required']=True
    result['boundary']=_CHRONIC_BOUNDARIES[method];result['disclaimer']=DISCLAIMER
    return result

CLINICAL_EXTRA.update({
 'medication_management':medication_management,
 'chronic_disease_management':lambda d:chronic_care_plan('chronic_disease_management',d),
 'diabetes_management':lambda d:chronic_care_plan('diabetes_management',d),
 'hypertension_management':lambda d:chronic_care_plan('hypertension_management',d),
 'asthma_management':lambda d:chronic_care_plan('asthma_management',d),
 'copd_management':lambda d:chronic_care_plan('copd_management',d),
 'heart_failure_management':lambda d:chronic_care_plan('heart_failure_management',d),
})

def oncology_coordination(data:dict)->dict:
    plan=data.get('plan',{});team=data.get('team',[]);milestones=data.get('milestones',[]);source=data.get('source',{})
    if not plan or not team or not source.get('source_url'):raise ValueError('oncology plan, team and source_url required')
    role_names={x.get('role') for x in team};tasks=[]
    for m in milestones:
        owner=m.get('owner_role');tasks.append({**m,'owner_known':owner in role_names,'status':m.get('status','pending'),'dependencies':m.get('dependencies',[])})
    gaps=[x['name'] for x in tasks if not x['owner_known'] or not x.get('due_at')]
    return {'diagnosis_and_stage_as_supplied':{'diagnosis':plan.get('diagnosis'),'stage':plan.get('stage'),'pathology_version':plan.get('pathology_version')},'team':team,'coordination_tasks':tasks,'coordination_gaps':gaps,'patient_priorities':data.get('patient_priorities',[]),'source':source,'boundary':'Coordination of a clinician-authored oncology plan only. Atlas does not establish diagnosis/stage, order therapy or replace tumor-board and specialist review.','disclaimer':DISCLAIMER}

def _chemo_enrichment(data:dict)->dict:
    regimen=data.get('regimen',{});cycles=regimen.get('cycles',[])
    if not isinstance(cycles,list):raise ValueError('regimen cycles must be a list')
    incomplete=[{'cycle':c.get('cycle'),'missing':[k for k in ('days','agents') if not c.get(k)]} for c in cycles if isinstance(c,dict) and (not c.get('days') or not c.get('agents'))]
    facts=data.get('patient_facts',{})
    return {'cycle_structure_review':{'cycles_supplied':len(cycles),'incomplete_cycles':incomplete},'dosing_input_fields_for_pharmacist_review':{k:facts.get(k) for k in ('body_surface_area','weight_kg','renal_function','hepatic_function')},'dosing_note':'Presence of inputs only; Atlas never calculates or verifies a chemotherapy dose.'}

def _radiation_enrichment(data:dict)->dict:
    regimen=data.get('regimen',{});total=regimen.get('total_dose_gy');fractions=regimen.get('fractions');stated=regimen.get('dose_per_fraction_gy')
    missing=[k for k,v in (('total_dose_gy',total),('fractions',fractions)) if v is None]
    out={'missing_fractionation_inputs':missing,'dose_per_fraction_gy':None,'consistency_with_stated':None}
    if not missing:
        t=_num(total,'total_dose_gy');f=_num(fractions,'fractions')
        if f<=0:raise ValueError('fractions must be positive')
        dpf=round(t/f,4);out['dose_per_fraction_gy']=dpf
        if stated is not None:out['consistency_with_stated']='consistent' if abs(dpf-_num(stated,'dose_per_fraction_gy'))<1e-6 else 'inconsistent'
    out['arithmetic_note']='Division only; the planning team verifies prescription, technique and constraints.'
    return out

def _immunotherapy_enrichment(data:dict)->dict:
    criteria=data.get('criteria',[]);facts=data.get('patient_facts',{})
    biomarkers=[{'field':c.get('field'),'patient_value':facts.get(c.get('field')),'result_documented':c.get('field') in facts,'assay_and_report_for_specialist_review':True} for c in criteria if isinstance(c,dict) and (c.get('biomarker') or 'biomarker' in str(c.get('reason','')).lower())]
    risk_fields=data.get('immune_risk_fields',[])
    if not isinstance(risk_fields,list):raise ValueError('immune_risk_fields must be a list')
    return {'biomarker_panel_review':biomarkers,'immune_risk_checklist':[{'field':f,'value':facts.get(f),'documented':f in facts} for f in risk_fields],'immune_note':'Immune-related risk review belongs to the oncology team; Atlas never predicts response or toxicity.'}

_ONCOLOGY_ENRICHMENTS={'chemotherapy_planning':_chemo_enrichment,'radiation_therapy_planning':_radiation_enrichment,'immunotherapy_selection':_immunotherapy_enrichment}
_ONCOLOGY_BOUNDARIES={
 'chemotherapy_planning':'Cited eligibility and checklist support only. Oncology specialists must confirm pathology, stage, biomarkers, organ function, interactions, consent and patient goals. Atlas never selects, doses, schedules or administers anticancer treatment.',
 'radiation_therapy_planning':'Cited eligibility and fractionation arithmetic support only. Radiation oncologists and physicists confirm prescription, contours, technique and constraints. Atlas never selects, doses, schedules or delivers radiation treatment.',
 'immunotherapy_selection':'Cited biomarker and eligibility organization only. Oncology specialists confirm assays, pathology, contraindications, immune risk and patient goals. Atlas never selects, doses, schedules or administers anticancer treatment.',
}

def oncology_plan(method:str,data:dict)->dict:
    regimen=data.get('regimen',{});patient=data.get('patient_facts',{});criteria=data.get('criteria',[]);source=data.get('source',{})
    if not isinstance(patient,dict) or not isinstance(criteria,list):raise ValueError('patient_facts object and criteria list required')
    if not regimen or not source.get('source_url'):raise ValueError('regimen and source_url required')
    if method not in _ONCOLOGY_ENRICHMENTS:raise ValueError(f'unsupported oncology method: {method}')
    checks=[]
    for c in criteria:
        field=c.get('field');value=patient.get(field);passed=None
        if value is not None:
            passed=True
            if 'minimum' in c:passed=passed and _num(value,'criterion value')>=_num(c['minimum'],'criterion minimum')
            if 'maximum' in c:passed=passed and _num(value,'criterion value')<=_num(c['maximum'],'criterion maximum')
            if 'equals' in c:passed=passed and value==c['equals']
        checks.append({'field':field,'value':value,'passed':passed,'reason':c.get('reason')})
    blockers=[x for x in checks if x['passed'] is False];missing=[x['field'] for x in checks if x['passed'] is None]
    result={'mode':method,'regimen':regimen,'eligibility_checks':checks,'blockers':blockers,'missing_facts':missing,'status':'incomplete' if missing else 'not_eligible_for_reviewed_option' if blockers else 'eligible_for_specialist_review','source':source}
    result.update(_ONCOLOGY_ENRICHMENTS[method](data))
    result['boundary']=_ONCOLOGY_BOUNDARIES[method];result['disclaimer']=DISCLAIMER
    return result

def _palliative_enrichment(data:dict)->dict:
    symptoms=data.get('symptoms',[])
    if not isinstance(symptoms,list):raise ValueError('symptoms must be a list')
    ordered=sorted(symptoms,key=lambda s:(not bool(s.get('urgent')),-(_num(s['severity'],'severity') if s.get('severity') is not None else 0)))
    return {'symptom_burden_summary':{'symptom_count':len(symptoms),'urgent_count':sum(1 for s in symptoms if s.get('urgent') is True),'unscored_count':sum(1 for s in symptoms if s.get('severity') is None),'review_order':[s.get('name') for s in ordered]},'symptom_note':'Counts of supplied entries only; the palliative team assesses symptoms in person.'}

def _hospice_enrichment(data:dict)->dict:
    team=data.get('team',[]);milestones=data.get('milestones',[])
    if not isinstance(team,list) or not isinstance(milestones,list):raise ValueError('team and milestones must be lists')
    roles={m.get('role') for m in team if isinstance(m,dict)}
    tasks=[{'milestone':m.get('name'),'owner_role':m.get('owner_role'),'owner_known':m.get('owner_role') in roles,'status':m.get('status','pending')} for m in milestones if isinstance(m,dict)]
    eligibility=data.get('eligibility_fields',[])
    if not isinstance(eligibility,list):raise ValueError('eligibility_fields must be a list')
    documented=data.get('eligibility_documentation',{})
    if not isinstance(documented,dict):raise ValueError('eligibility_documentation must be an object')
    return {'coordination_task_map':tasks,'unowned_milestones':[t['milestone'] for t in tasks if not t['owner_known']],'eligibility_documentation_status':[{'field':f,'documented':f in documented} for f in eligibility],'hospice_note':'Eligibility and enrollment are determined by the hospice team and physician; Atlas only tracks supplied documentation.'}

_PALLIATIVE_ENRICHMENTS={'palliative_care_planning':_palliative_enrichment,'hospice_care_coordination':_hospice_enrichment}
_PALLIATIVE_BOUNDARIES={
 'palliative_care_planning':'Patient-goal documentation and symptom-burden organization only. A palliative team assesses symptoms, capacity and treatment. Atlas never enrolls, changes code status, withdraws treatment or makes end-of-life decisions.',
 'hospice_care_coordination':'Coordination and documentation tracking only. The hospice team and physician determine eligibility, enrollment and plan of care. Atlas never enrolls, changes code status, withdraws treatment or makes end-of-life decisions.',
}

def palliative_plan(method:str,data:dict)->dict:
    symptoms=data.get('symptoms',[]);goals=data.get('goals',[]);preferences=data.get('preferences',{});options=data.get('options',[]);source=data.get('source',{})
    if not isinstance(symptoms,list) or not isinstance(options,list) or not isinstance(preferences,dict):raise ValueError('symptoms list, options list and preferences object required')
    if not goals or not source.get('source_url'):raise ValueError('patient goals and source_url required')
    if method not in _PALLIATIVE_ENRICHMENTS:raise ValueError(f'unsupported palliative method: {method}')
    urgent=[s for s in symptoms if isinstance(s,dict) and s.get('urgent') is True];matched=[]
    for o in options:
        if set(o.get('goal_tags',[]))&set(goals) and not set(o.get('conflicts_with',[]))&set(preferences.get('declined',[])):matched.append(o)
    result={'mode':method,'symptom_summary':symptoms,'urgent_review':urgent,'patient_goals':goals,'preferences':preferences,'candidate_support_for_shared_decision':matched,'unresolved_decisions':data.get('unresolved_decisions',[]),'source':source}
    result.update(_PALLIATIVE_ENRICHMENTS[method](data))
    result['boundary']=_PALLIATIVE_BOUNDARIES[method];result['disclaimer']=DISCLAIMER
    return result

def pain_plan(data:dict)->dict:
    observations=data.get('observations',[]);goals=data.get('goals',[]);options=data.get('options',[]);source=data.get('source',{})
    if not observations or not goals or not source.get('source_url'):raise ValueError('pain observations, functional goals and source_url required')
    selected=[o for o in options if not set(o.get('contraindications',[]))&set(data.get('contraindications',[]))]
    return {'pain_trajectory':sorted(observations,key=lambda x:x.get('observed_at','')),'functional_goals':goals,'candidate_options_for_shared_review':selected,'red_flags':data.get('red_flags',[]),'source':source,'boundary':'Tracking and shared-decision support only. Pain score alone does not determine treatment; clinicians assess cause, function, sedation, substance-use and overdose risk. Atlas never prescribes or changes analgesics.','disclaimer':DISCLAIMER}

CLINICAL_EXTRA.update({
 'cancer_care_coordination':oncology_coordination,
 'chemotherapy_planning':lambda d:oncology_plan('chemotherapy_planning',d),
 'radiation_therapy_planning':lambda d:oncology_plan('radiation_therapy_planning',d),
 'immunotherapy_selection':lambda d:oncology_plan('immunotherapy_selection',d),
 'palliative_care_planning':lambda d:palliative_plan('palliative_care_planning',d),
 'hospice_care_coordination':lambda d:palliative_plan('hospice_care_coordination',d),
 'pain_management':pain_plan,
})

def wound_care(data:dict)->dict:
    observations=data.get('observations',[]);plan=data.get('plan',{});rules=data.get('escalation_rules',[]);source=data.get('source',{})
    if not observations or not source.get('source_url'):raise ValueError('wound observations and source_url required')
    ordered=sorted(observations,key=lambda x:x.get('observed_at',''));latest=ordered[-1];previous=ordered[-2] if len(ordered)>1 else None
    changes={}
    if previous:
        for key in ('length_cm','width_cm','depth_cm'):
            if key in latest and key in previous:changes[key]=float(latest[key])-float(previous[key])
    flags=[]
    for r in rules:
        value=latest.get(r.get('field'))
        if value is None:continue
        hit=value==r.get('equals') if 'equals' in r else ('gt' in r and float(value)>float(r['gt'])) or ('lt' in r and float(value)<float(r['lt']))
        if hit:flags.append({'field':r['field'],'reason':r.get('reason'),'next_step':r.get('next_step')})
    return {'trajectory':ordered,'latest_dimension_changes_cm':changes,'current_clinician_plan':plan,'escalation_flags':flags,'source':source,'boundary':'Structured wound documentation and clinician-authored escalation rules only. Atlas cannot assess the wound directly, debride, culture, diagnose infection or select dressings/therapy.','disclaimer':DISCLAIMER}

def infection_control(data:dict)->dict:
    exposures=data.get('exposures',[]);policies=data.get('policies',[]);_require_citations(policies,'policies');recommendations=[]
    for e in exposures:
        matches=[]
        for p in policies:
            if p.get('pathogen')==e.get('pathogen') and p.get('setting')==e.get('setting'):matches.append({'policy_id':p.get('id'),'precautions':p.get('precautions',[]),'duration_rule':p.get('duration_rule'),'source_url':p['source_url'],'version':p.get('version')})
        recommendations.append({'exposure':e,'matching_policies':matches,'status':'policy_match' if matches else 'unresolved'})
    return {'exposure_reviews':recommendations,'boundary':'Current cited-policy lookup only. Infection prevention professionals confirm organism, transmission route, isolation, reporting and duration; unresolved exposures must not be treated as cleared.','disclaimer':DISCLAIMER}

def antimicrobial_stewardship(data:dict)->dict:
    order=data.get('antimicrobial_order',{});micro=data.get('microbiology',{});rules=data.get('rules',[]);_require_citations(rules,'rules')
    if not order:raise ValueError('antimicrobial_order required')
    findings=[]
    for r in rules:
        when=r.get('when',{});matches=all((order|micro).get(k)==v for k,v in when.items())
        if matches:findings.append({'type':r.get('type'),'message':r.get('message'),'source_url':r['source_url'],'review_by':r.get('review_by','prescriber_or_pharmacist')})
    missing=[x for x in ['indication','drug','dose','route','started_at','planned_review_at'] if not order.get(x)]
    return {'order':order,'microbiology':micro,'missing_stewardship_fields':missing,'rule_findings':findings,'boundary':'Audit prompts, not prescribing. A qualified prescriber/pharmacist reviews diagnosis, cultures, allergies, organ function, dose, route, duration, de-escalation and local resistance data before any change.','disclaimer':DISCLAIMER}

def vaccination_schedule(data:dict)->dict:
    history=data.get('history',[]);recommendations=data.get('recommendations',[]);patient=data.get('patient',{});source=data.get('source',{})
    if not recommendations or not source.get('source_url'):raise ValueError('cited recommendations required')
    given={(x.get('vaccine'),x.get('dose_number')) for x in history};due=[];blocked=[]
    for r in recommendations:
        age=patient.get('age_years');eligible=(age is not None and float(r.get('min_age_years',0))<=float(age)<=float(r.get('max_age_years',999)))
        row={**r,'already_recorded':(r.get('vaccine'),r.get('dose_number')) in given}
        if set(r.get('contraindications',[]))&set(patient.get('contraindications',[])):blocked.append({**row,'reason':'contraindication_review'})
        elif eligible and not row['already_recorded']:due.append(row)
    return {'due_for_clinician_review':due,'blocked_for_review':blocked,'history_used':history,'source':source,'boundary':'Scheduling against supplied history and cited recommendations only. A clinician verifies records, age, indication, intervals, contraindications, precautions and current local guidance before administration.','disclaimer':DISCLAIMER}

def _preventive_plan_enrichment(data:dict,due:list)->dict:
    def key(row):
        priority=row.get('priority')
        return (1,0) if priority is None else (0,_num(priority,'priority'))
    ordered=sorted(due,key=key)
    return {'plan_sequence':[r.get('service') for r in ordered],'shared_decision_topics':[r.get('service') for r in due if r.get('shared_decision')],'plan_note':'Sequencing uses supplied priorities only; clinicians and patients decide timing.'}

def _screening_enrichment(data:dict,due:list)->dict:
    profile=data.get('profile',{});last_done=profile.get('last_done',{})
    if not isinstance(last_done,dict):raise ValueError('profile.last_done must be an object keyed by service')
    as_of=data.get('as_of');ref=_iso_date(as_of,'as_of') if as_of is not None else None
    rows=[]
    for r in due:
        interval=r.get('interval_months');done=last_done.get(r.get('service'))
        entry={'service':r.get('service'),'interval_months':interval,'last_done':done,'due_status':'not_computed'}
        if interval is not None:
            iv=_num(interval,'interval_months')
            if iv<=0:raise ValueError('interval_months must be positive')
            if done is None:entry['due_status']='last_done_unknown'
            elif ref is None:entry['due_status']='as_of_not_supplied'
            else:
                d=_iso_date(done,'last_done');months=(ref.year-d.year)*12+(ref.month-d.month)
                entry['months_since_last_done']=months;entry['due_status']='due_for_review' if months>=iv else 'not_yet_due'
        rows.append(entry)
    return {'screening_due_review':rows,'due_note':'Date arithmetic on supplied records only; an unrecorded test is never treated as done.'}

_PREVENTIVE_ENRICHMENTS={'preventive_care_planning':_preventive_plan_enrichment,'health_screening_recommendations':_screening_enrichment}
_PREVENTIVE_BOUNDARIES={
 'preventive_care_planning':'Cited population-guideline matching and sequencing support only. Clinicians and patients account for prior tests, symptoms, life expectancy, harms, preferences and local guidance; Atlas does not order or perform screening.',
 'health_screening_recommendations':'Cited screening-interval arithmetic on supplied records only. An unrecorded test is never treated as done; clinicians verify history, risk and current guidance before ordering. Atlas does not order or perform screening.',
}

def preventive_care(method:str,data:dict)->dict:
    profile=data.get('profile',{});recommendations=data.get('recommendations',[]);_require_citations(recommendations,'recommendations')
    if not isinstance(profile,dict):raise ValueError('profile must be an object')
    if method not in _PREVENTIVE_ENRICHMENTS:raise ValueError(f'unsupported preventive care method: {method}')
    due=[];unknown=[]
    for r in recommendations:
        eligible=True;missing=[]
        for field,condition in r.get('eligibility',{}).items():
            value=profile.get(field)
            if value is None:missing.append(field);eligible=False;continue
            if isinstance(condition,dict):
                if 'minimum' in condition and _num(value,'profile value')<_num(condition['minimum'],'eligibility minimum'):eligible=False
                if 'maximum' in condition and _num(value,'profile value')>_num(condition['maximum'],'eligibility maximum'):eligible=False
            elif value!=condition:eligible=False
        row={'service':r.get('service'),'source_url':r['source_url'],'grade':r.get('grade'),'shared_decision':r.get('shared_decision',False),'priority':r.get('priority'),'interval_months':r.get('interval_months'),'missing_fields':missing}
        (unknown if missing else due if eligible else []).append(row)
    result={'mode':method,'recommendations_for_review':due,'insufficient_information':unknown,'profile_used':profile}
    result.update(_PREVENTIVE_ENRICHMENTS[method](data,due))
    result['boundary']=_PREVENTIVE_BOUNDARIES[method];result['disclaimer']=DISCLAIMER
    return result

CLINICAL_EXTRA.update({
 'wound_care':wound_care,
 'infection_control':infection_control,
 'antimicrobial_stewardship':antimicrobial_stewardship,
 'vaccination_scheduling':vaccination_schedule,
 'preventive_care_planning':lambda d:preventive_care('preventive_care_planning',d),
 'health_screening_recommendations':lambda d:preventive_care('health_screening_recommendations',d),
})

def genetic_counseling(data:dict)->dict:
    pedigree=data.get('pedigree',[]);results=data.get('test_results',[]);knowledge=data.get('knowledge',[]);_require_citations(knowledge,'knowledge')
    if not pedigree and not results:raise ValueError('pedigree or test_results required')
    indexed={(str(k.get('gene')),str(k.get('variant'))):k for k in knowledge};interpreted=[]
    for r in results:
        k=indexed.get((str(r.get('gene')),str(r.get('variant'))));interpreted.append({**r,'classification':k.get('classification') if k else 'not_in_supplied_knowledge','inheritance':k.get('inheritance') if k else None,'source_url':k.get('source_url') if k else None,'uncertainty':k.get('uncertainty') if k else 'unresolved'})
    return {'pedigree_as_supplied':pedigree,'result_context':interpreted,'patient_questions':data.get('patient_questions',[]),'values_and_preferences':data.get('values_and_preferences',[]),'consent_status':data.get('consent_status','unknown'),'boundary':'Educational preparation for a certified genetics professional. Atlas does not calculate undocumented familial risk, establish parentage, diagnose, order testing, or make reproductive decisions. Variants absent from supplied knowledge remain unresolved.','disclaimer':DISCLAIMER}

def reproductive_plan(method:str,data:dict)->dict:
    timeline=data.get('timeline',[]);goals=data.get('goals',[]);options=data.get('options',[]);source=data.get('source',{})
    if not goals or not source.get('source_url'):raise ValueError('patient goals and source_url required')
    facts=data.get('patient_facts',{});rows=[]
    for o in options:
        missing=[x for x in o.get('required_facts',[]) if x not in facts];contra=set(o.get('contraindications',[]))&set(facts.get('contraindications',[]));rows.append({**o,'missing_facts':missing,'matched_contraindications':sorted(contra),'review_status':'incomplete' if missing else 'blocked_for_review' if contra else 'candidate_for_specialist_discussion'})
    return {'mode':method,'timeline':timeline,'patient_goals':goals,'option_review':rows,'source':source,'boundary':'Goal-sensitive education and checklist support only. A reproductive specialist confirms diagnosis, prognosis, eligibility, risks, consent, costs and local law. Atlas never selects treatment, creates embryos, transfers gametes/embryos or makes reproductive choices.','disclaimer':DISCLAIMER}

def _prenatal_enrichment(data:dict)->dict:
    completed=data.get('completed_visits',[])
    if not isinstance(completed,list):raise ValueError('completed_visits must be a list')
    done={str(v) for v in completed}
    review=[{'milestone':m.get('name'),'due_at':m.get('due_at'),'recorded':'completed' if str(m.get('name')) in done else 'not_recorded'} for m in data.get('milestones',[]) if isinstance(m,dict)]
    return {'visit_schedule_review':review,'unrecorded_visits':[r['milestone'] for r in review if r['recorded']!='completed'],'schedule_note':'A missing record is not a missed visit; the care team verifies the chart.'}

def _labor_enrichment(data:dict)->dict:
    events=data.get('events',[])
    if not isinstance(events,list):raise ValueError('events must be a list')
    timeline=sorted((e for e in events if isinstance(e,dict)),key=lambda e:str(e.get('at','')))
    return {'labor_timeline':[{'event':e.get('event'),'at':e.get('at'),'documented_by':e.get('documented_by')} for e in timeline],'timeline_note':'Documentation order only; Atlas does not interpret labor progress or fetal status.'}

def _neonatal_enrichment(data:dict)->dict:
    required=data.get('required_screenings',[]);screenings=data.get('screenings',[])
    if not isinstance(required,list) or not isinstance(screenings,list):raise ValueError('required_screenings and screenings must be lists')
    recorded={s.get('name'):s for s in screenings if isinstance(s,dict)}
    return {'newborn_screening_review':[{'screening':name,'status':recorded.get(name,{}).get('status','not_recorded'),'result_for_clinician_review':recorded.get(name,{}).get('result')} for name in required],'screening_note':'Screening performance and follow-up belong to the newborn care team.'}

_PERINATAL_ENRICHMENTS={'prenatal_care':_prenatal_enrichment,'labor_and_delivery_management':_labor_enrichment,'neonatal_care':_neonatal_enrichment}
_PERINATAL_BOUNDARIES={
 'prenatal_care':'Checklist and escalation support for licensed maternal care teams. Atlas does not interpret fetal monitoring, determine labor status, choose delivery mode, resuscitate, discharge or delay emergency care.',
 'labor_and_delivery_management':'Labor documentation and escalation support for licensed delivery teams. Atlas does not interpret fetal monitoring, determine labor status, choose delivery mode, resuscitate, discharge or delay emergency care.',
 'neonatal_care':'Newborn checklist and documentation support for licensed neonatal teams. Atlas does not interpret monitoring, choose delivery mode, resuscitate, discharge or delay emergency care.',
}

def perinatal_plan(method:str,data:dict)->dict:
    observations=data.get('observations',{});milestones=data.get('milestones',[]);rules=data.get('escalation_rules',[]);source=data.get('source',{})
    if not isinstance(observations,dict) or not isinstance(milestones,list) or not isinstance(rules,list):raise ValueError('observations object, milestones list and escalation_rules list required')
    if not milestones or not source.get('source_url'):raise ValueError('milestones and source_url required')
    if method not in _PERINATAL_ENRICHMENTS:raise ValueError(f'unsupported perinatal method: {method}')
    status=[]
    for m in milestones:
        value=observations.get(m.get('measure'));status.append({'name':m.get('name'),'measure':m.get('measure'),'observed':value,'due_at':m.get('due_at'),'status':'unknown' if value is None else 'documented'})
    flags=[]
    for r in rules:
        value=observations.get(r.get('field'))
        if value is None:continue
        hit=(r.get('equals')==value if 'equals' in r else False) or ('gt' in r and _num(value,'observation')>_num(r['gt'],'rule threshold')) or ('lt' in r and _num(value,'observation')<_num(r['lt'],'rule threshold'))
        if hit:flags.append({'field':r['field'],'reason':r.get('reason'),'urgency':r.get('urgency'),'next_step':r.get('next_step')})
    result={'mode':method,'milestone_status':status,'escalation_flags':flags,'birth_or_care_preferences':data.get('preferences',{}),'source':source}
    result.update(_PERINATAL_ENRICHMENTS[method](data))
    result['boundary']=_PERINATAL_BOUNDARIES[method];result['disclaimer']=DISCLAIMER
    return result

def _pediatric_enrichment(data:dict)->dict:
    profile=data.get('profile',{});age=profile.get('age_years');band='age_not_supplied'
    if age is not None:
        a=_num(age,'age_years')
        if a<0:raise ValueError('age_years must be non-negative')
        band='infant' if a<1 else 'child' if a<12 else 'adolescent' if a<18 else 'adult_record_review'
    growth=data.get('growth_measurements',[])
    if not isinstance(growth,list):raise ValueError('growth_measurements must be a list')
    return {'age_band_from_supplied_age':band,'growth_inputs':[{'metric':g.get('metric'),'value':g.get('value'),'unit':g.get('unit'),'percentile_source':g.get('percentile_source'),'observed_at':g.get('observed_at')} for g in growth if isinstance(g,dict)],'pediatric_note':'Banding is a data label from the supplied age; growth interpretation belongs to the pediatric clinician.'}

def _adolescent_enrichment(data:dict)->dict:
    recs=data.get('recommendations',[])
    confidential=[r.get('topic') for r in recs if isinstance(r,dict) and ('confidential' in str(r.get('topic','')).lower() or r.get('confidential'))]
    consent=data.get('consent',{})
    if not isinstance(consent,dict):raise ValueError('consent must be an object when supplied')
    return {'confidentiality_review':{'confidentiality_topics':confidential,'consent_fields_supplied':sorted(consent.keys())},'adolescent_note':'Confidentiality and consent rules vary by jurisdiction and topic; clinicians apply local law with the young person.'}

def _geriatric_enrichment(data:dict)->dict:
    profile=data.get('profile',{});meds=profile.get('medications',[])
    if not isinstance(meds,list):raise ValueError('profile.medications must be a list')
    threshold=_num(data.get('polypharmacy_review_threshold',5),'polypharmacy_review_threshold')
    return {'medication_count':len(meds),'polypharmacy_review_prompt':len(meds)>=threshold,'geriatric_screen_fields':[{'field':f,'documented':f in profile} for f in ('fall_history','gait_balance','orthostatic','cognition')],'geriatric_note':'Counts and field presence only; no frailty or falls diagnosis.'}

def _anatomy_keyed(data:dict)->dict:
    profile=data.get('profile',{});organs=profile.get('organs',[])
    if not isinstance(organs,list):raise ValueError('profile.organs must be a list')
    present=set(organs)
    keyed=[{'topic':r.get('topic'),'organ':r.get('organ'),'applicable':(r.get('organ') in present) if r.get('organ') else None,'source_url':r.get('source_url')} for r in data.get('recommendations',[]) if isinstance(r,dict) and r.get('organ')]
    return {'anatomy_keyed_screening':keyed,'organs_as_supplied':sorted(str(o) for o in present)}

def _womens_enrichment(data:dict)->dict:
    result=_anatomy_keyed(data)
    result['womens_health_note']='Screening follows organs present and clinician judgment, never assumptions from identity.'
    return result

def _mens_enrichment(data:dict)->dict:
    result=_anatomy_keyed(data)
    result['symptom_review_inputs']=list(data.get('concerns',[]))
    result['mens_health_note']='Symptoms and anatomy are documented for clinician review; no diagnosis is made.'
    return result

def _lgbtq_enrichment(data:dict)->dict:
    profile=data.get('profile',{})
    return {'affirming_care_inputs':{'chosen_name':profile.get('chosen_name'),'pronouns':profile.get('pronouns'),'organ_inventory':profile.get('organs',[]),'partners_as_stated':profile.get('partners')},'lgbtq_note':'Care follows patient-stated identity, anatomy and goals without inference.'}

_LIFE_STAGE_ENRICHMENTS={'pediatric_care':_pediatric_enrichment,'adolescent_medicine':_adolescent_enrichment,'geriatric_care':_geriatric_enrichment,'womens_health':_womens_enrichment,'mens_health':_mens_enrichment,'lgbtq_health':_lgbtq_enrichment}
_LIFE_STAGE_BOUNDARIES={
 'pediatric_care':'Inclusive cited-guideline matching for pediatric review, not identity inference or diagnosis. Use anatomy, organs present, medications, age, exposures, goals and preferences relevant to care rather than assumptions from sex, gender, orientation or age alone. Licensed pediatric clinicians individualize care.',
 'adolescent_medicine':'Inclusive cited-guideline matching with confidentiality preserved, not identity inference or diagnosis. Use anatomy, organs present, medications, age, exposures, goals and preferences relevant to care rather than assumptions from sex, gender, orientation or age alone. Licensed clinicians individualize care within local consent law.',
 'geriatric_care':'Inclusive cited-guideline matching for older-adult review, not identity inference or diagnosis. Use anatomy, organs present, medications, age, exposures, goals and preferences relevant to care rather than assumptions from sex, gender, orientation or age alone. Licensed clinicians individualize care.',
 'womens_health':'Inclusive cited-guideline matching keyed to organs present, not identity inference or diagnosis. Use anatomy, organs present, medications, age, exposures, goals and preferences relevant to care rather than assumptions from sex, gender, orientation or age alone. Licensed clinicians individualize care.',
 'mens_health':'Inclusive cited-guideline matching keyed to organs present and stated symptoms, not identity inference or diagnosis. Use anatomy, organs present, medications, age, exposures, goals and preferences relevant to care rather than assumptions from sex, gender, orientation or age alone. Licensed clinicians individualize care.',
 'lgbtq_health':'Inclusive cited-guideline matching honoring patient-stated identity, not identity inference or diagnosis. Use anatomy, organs present, medications, age, exposures, goals and preferences relevant to care rather than assumptions from sex, gender, orientation or age alone. Licensed clinicians individualize care.',
}

def life_stage_care(method:str,data:dict)->dict:
    profile=data.get('profile',{});concerns=data.get('concerns',[]);recommendations=data.get('recommendations',[]);_require_citations(recommendations,'recommendations')
    if not isinstance(profile,dict) or not isinstance(concerns,list):raise ValueError('profile object and concerns list required')
    if method not in _LIFE_STAGE_ENRICHMENTS:raise ValueError(f'unsupported life stage method: {method}')
    selected=[];unknown=[]
    for r in recommendations:
        missing=[f for f in r.get('required_fields',[]) if f not in profile]
        applicable=not missing and all(profile.get(k)==v for k,v in r.get('match',{}).items())
        row={'topic':r.get('topic'),'source_url':r['source_url'],'shared_decision':r.get('shared_decision',False),'missing_fields':missing}
        if missing:unknown.append(row)
        elif applicable:selected.append(row)
    result={'mode':method,'profile_used':profile,'patient_concerns':concerns,'recommendations_for_shared_review':selected,'insufficient_information':unknown}
    result.update(_LIFE_STAGE_ENRICHMENTS[method](data))
    result['boundary']=_LIFE_STAGE_BOUNDARIES[method];result['disclaimer']=DISCLAIMER
    return result

CLINICAL_EXTRA.update({
 'genetic_counseling':genetic_counseling,
 'fertility_treatment_planning':lambda d:reproductive_plan('fertility_treatment_planning',d),
 'prenatal_care':lambda d:perinatal_plan('prenatal_care',d),
 'labor_and_delivery_management':lambda d:perinatal_plan('labor_and_delivery_management',d),
 'neonatal_care':lambda d:perinatal_plan('neonatal_care',d),
 'pediatric_care':lambda d:life_stage_care('pediatric_care',d),
 'adolescent_medicine':lambda d:life_stage_care('adolescent_medicine',d),
 'geriatric_care':lambda d:life_stage_care('geriatric_care',d),
 'womens_health':lambda d:life_stage_care('womens_health',d),
 'mens_health':lambda d:life_stage_care('mens_health',d),
 'lgbtq_health':lambda d:life_stage_care('lgbtq_health',d),
})

def global_health(data:dict)->dict:
    needs=data.get('needs',[]);resources=data.get('resources',[]);constraints=data.get('constraints',{});sources=data.get('sources',[]);_require_citations(sources,'sources')
    if not needs:raise ValueError('population needs required')
    ranked=sorted(needs,key=lambda x:(-float(x.get('severity',0)),-float(x.get('people_affected',0)),str(x.get('name',''))))
    allocations=[]
    for n in ranked:
        matches=[r for r in resources if n.get('name') in r.get('addresses',[]) and not set(r.get('constraints',[]))&set(constraints.get('active',[]))];allocations.append({'need':n,'candidate_resources':matches,'unmet':not bool(matches)})
    return {'prioritized_needs':ranked,'resource_options':allocations,'constraints':constraints,'sources':sources,'boundary':'Transparent planning aid from supplied aggregate data. Local public-health authorities and affected communities validate needs, equity, feasibility and allocation; Atlas does not ration care or act on individual records.','disclaimer':DISCLAIMER}

def public_health_surveillance(data:dict)->dict:
    series=data.get('series',[]);baseline=data.get('baseline',{});source=data.get('source',{})
    if not series or not source.get('source_url'):raise ValueError('aggregate series and source_url required')
    threshold=float(data.get('z_threshold',2));mean=float(baseline.get('mean',0));sd=float(baseline.get('sd',0));alerts=[];normalized=[]
    for point in series:
        count=float(point.get('count',0));z=(count-mean)/sd if sd>0 else None;row={**point,'z_score':z};normalized.append(row)
        if z is not None and z>=threshold:alerts.append(row)
    return {'aggregate_series':normalized,'statistical_signals':alerts,'baseline':baseline,'privacy_check':{'minimum_cell_size':data.get('minimum_cell_size'),'suppressed_cells':[x.get('period') for x in series if data.get('minimum_cell_size') and float(x.get('count',0))<float(data['minimum_cell_size'])]},'source':source,'boundary':'Statistical signal detection on aggregate supplied data, not outbreak confirmation or individual identification. Epidemiologists verify data quality, reporting delays, denominators and confounding before response.','disclaimer':DISCLAIMER}

def epidemic_response(data:dict)->dict:
    scenario=data.get('scenario',{});interventions=data.get('interventions',[]);source=data.get('source',{})
    if not scenario or not source.get('source_url'):raise ValueError('scenario and source_url required')
    assumptions=data.get('assumptions',{});rows=[]
    for i in interventions:
        projected=None
        if all(k in assumptions for k in ('baseline_cases','effectiveness','uptake')):projected=float(assumptions['baseline_cases'])*(1-float(assumptions['effectiveness'])*float(assumptions['uptake']))
        rows.append({**i,'projected_cases_under_shared_assumptions':projected,'equity_considerations':i.get('equity_considerations',[]),'operational_dependencies':i.get('operational_dependencies',[])})
    return {'scenario':scenario,'response_options':rows,'assumptions':assumptions,'decision_status':'draft_for_public_health_authority','source':source,'boundary':'Scenario planning only. Authorities validate transmission evidence, legal authority, proportionality, equity, logistics and current guidance before public action; Atlas does not issue orders or restrictions.','disclaimer':DISCLAIMER}

def contact_tracing(data:dict)->dict:
    index_case=data.get('index_case',{});encounters=data.get('encounters',[]);definition=data.get('exposure_definition',{});source=data.get('source',{})
    if not index_case.get('consent_or_legal_basis') or not definition or not source.get('source_url'):raise ValueError('documented authority, exposure definition and source_url required')
    contacts=[]
    for e in encounters:
        duration=float(e.get('duration_minutes',0));distance=float(e.get('distance_meters',999));qualifies=duration>=float(definition.get('min_duration_minutes',0)) and distance<=float(definition.get('max_distance_meters',999));contacts.append({'contact_token':e.get('contact_token'),'qualifies':qualifies,'encounter_at':e.get('encounter_at'),'reason':'definition_matched' if qualifies else 'definition_not_matched'})
    return {'potential_exposures':contacts,'retention_until':data.get('retention_until'),'source':source,'boundary':'Use only with documented consent/legal authority, data minimization, access control and retention limits. Public-health staff verify exposure and handle notification; Atlas never deanonymizes, tracks location, contacts people or enforces isolation.','disclaimer':DISCLAIMER}

def quarantine_management(data:dict)->dict:
    cases=data.get('cases',[]);policy=data.get('policy',{});source=policy.get('source',{})
    if not cases or not policy or not source.get('source_url'):raise ValueError('cases and cited policy required')
    reviews=[]
    for case in cases:
        missing=[x for x in policy.get('required_fields',[]) if x not in case];reviews.append({'case_token':case.get('case_token'),'status':'insufficient_information' if missing else 'policy_review_ready','missing_fields':missing,'support_needs':case.get('support_needs',[]),'appeal_or_review_route':policy.get('appeal_or_review_route')})
    return {'case_reviews':reviews,'policy_version':policy.get('version'),'source':source,'boundary':'Administrative checklist only. Authorized public-health officials determine lawful, least-restrictive measures and provide support, review and appeal. Atlas does not order, monitor or enforce quarantine.','disclaimer':DISCLAIMER}

def _education_enrichment(data:dict)->dict:
    return {'teach_back_checklist':[{'topic':m.get('topic'),'plain_language_present':bool(m.get('plain_language')),'uncertainty_stated':bool(m.get('uncertainty')),'cited':bool(m.get('source_ids'))} for m in data.get('messages',[]) if isinstance(m,dict)],'education_note':'Teach-back confirms understanding with the learner; materials never substitute for individual clinical care.'}

def _behavior_change_enrichment(data:dict)->dict:
    stage=data.get('readiness_stage');options=data.get('options',[])
    if not isinstance(options,list):raise ValueError('options must be a list')
    matched=[];deferred=[]
    for o in options:
        if not isinstance(o,dict):raise ValueError('each option must be an object')
        stages=o.get('stages')
        if stages is None or stage is None or stage in stages:matched.append(o)
        else:deferred.append({'name':o.get('name'),'deferred_for_stage':stage})
    return {'readiness_stage_as_supplied':stage,'stage_matched_options':matched,'deferred_options':deferred,'behavior_note':'Voluntary, stage-matched support only; ambivalence is respected, never argued away.'}

_EDUCATION_ENRICHMENTS={'health_education':_education_enrichment,'behavior_change_support':_behavior_change_enrichment}
_EDUCATION_BOUNDARIES={
 'health_education':'Cited education and voluntary support only. Preserve uncertainty, accessibility and audience context; never shame, coerce, manipulate or substitute generic education for individual clinical care.',
 'behavior_change_support':'Cited voluntary behavior-change support only. Match the person stated readiness; never shame, coerce, manipulate or substitute generic education for individual clinical care.',
}

def health_education(method:str,data:dict)->dict:
    audience=data.get('audience',{});messages=data.get('messages',[]);sources=data.get('sources',[]);_require_citations(sources,'sources')
    if not isinstance(audience,dict) or not isinstance(messages,list):raise ValueError('audience object and messages list required')
    if not audience or not messages:raise ValueError('audience and messages required')
    if method not in _EDUCATION_ENRICHMENTS:raise ValueError(f'unsupported education method: {method}')
    rendered=[]
    for m in messages:rendered.append({'topic':m.get('topic'),'plain_language':m.get('plain_language'),'action':m.get('action'),'uncertainty':m.get('uncertainty'),'source_ids':m.get('source_ids',[]),'reading_level':m.get('reading_level')})
    result={'mode':method,'audience':audience,'educational_messages':rendered,'cultural_and_accessibility_review':data.get('review',{}),'sources':sources}
    result.update(_EDUCATION_ENRICHMENTS[method](data))
    result['boundary']=_EDUCATION_BOUNDARIES[method];result['disclaimer']=DISCLAIMER
    return result

CLINICAL_EXTRA.update({
 'global_health':global_health,
 'public_health_surveillance':public_health_surveillance,
 'epidemic_response':epidemic_response,
 'contact_tracing':contact_tracing,
 'quarantine_management':quarantine_management,
 'health_education':lambda d:health_education('health_education',d),
 'behavior_change_support':lambda d:health_education('behavior_change_support',d),
})

def adherence_support(data:dict)->dict:
    regimen=data.get('regimen',[]);checkins=data.get('checkins',[]);source=data.get('source',{})
    if not regimen or not source.get('source_url'):raise ValueError('regimen and source_url required')
    summary=[]
    for med in regimen:
        relevant=[x for x in checkins if x.get('medication')==med.get('name')];taken=sum(1 for x in relevant if x.get('taken') is True);expected=len(relevant);barriers=sorted({b for x in relevant for b in x.get('barriers',[])})
        summary.append({'medication':med.get('name'),'taken_checkins':taken,'expected_checkins':expected,'observed_fraction':taken/expected if expected else None,'patient_reported_barriers':barriers,'preferences':med.get('preferences',[])})
    return {'adherence_summary':summary,'support_options':data.get('support_options',[]),'source':source,'boundary':'Nonjudgmental tracking of supplied check-ins only. Missing data is not nonadherence. Patient and clinician choose supports and any regimen changes; Atlas never pressures, penalizes or changes medication.','disclaimer':DISCLAIMER}

def _lifestyle_enrichment(data:dict)->dict:
    return {'goal_quality_review':[{'goal_id':g.get('id'),'well_specified':all(g.get(k) is not None for k in ('target','timeframe')),'missing_elements':[k for k in ('target','timeframe') if g.get(k) is None]} for g in data.get('goals',[]) if isinstance(g,dict)],'lifestyle_note':'Goals stay in the patient words; a professional checks realism and safety.'}

def _nutrition_enrichment(data:dict)->dict:
    baseline=data.get('baseline',{});keys=('weight_kg','daily_intake_kcal','daily_expenditure_kcal')
    missing=[k for k in keys if baseline.get(k) is None];estimate=None
    if not missing:
        _num(baseline['weight_kg'],'weight_kg')
        estimate=round(_num(baseline['daily_intake_kcal'],'daily_intake_kcal')-_num(baseline['daily_expenditure_kcal'],'daily_expenditure_kcal'),2)
    return {'energy_balance_inputs':{k:baseline.get(k) for k in keys},'missing_energy_inputs':missing,'energy_balance_kcal_estimate':estimate,'nutrition_note':'Arithmetic on supplied values only; not a metabolic measurement or diet prescription.'}

def _exercise_enrichment(data:dict)->dict:
    components=[{'name':o.get('name'),'frequency':o.get('frequency'),'intensity':o.get('intensity'),'time':o.get('time'),'type':o.get('type'),'fitt_complete':all(o.get(k) for k in ('frequency','intensity','time','type'))} for o in data.get('options',[]) if isinstance(o,dict)]
    screen=data.get('safety_screen',{})
    if not isinstance(screen,dict):raise ValueError('safety_screen must be an object when supplied')
    return {'fitt_components':components,'safety_screen_fields':[{'field':f,'documented':f in screen} for f in ('cardiac_symptoms','injury','pregnancy','physician_clearance')],'exercise_note':'FITT completeness is clerical; a qualified professional clears and individualizes exercise.'}

def _sleep_enrichment(data:dict)->dict:
    diary=data.get('sleep_diary',[])
    if not isinstance(diary,list):raise ValueError('sleep_diary must be a list')
    entries=[];skipped=0
    for e in diary:
        if not isinstance(e,dict) or 'time_in_bed_minutes' not in e or 'time_asleep_minutes' not in e:skipped+=1;continue
        bed=_num(e['time_in_bed_minutes'],'time_in_bed_minutes');asleep=_num(e['time_asleep_minutes'],'time_asleep_minutes')
        if bed<=0:raise ValueError('time_in_bed_minutes must be positive')
        entries.append({'date':e.get('date'),'sleep_efficiency':round(asleep/bed,4)})
    return {'sleep_diary_metrics':{'entries':entries,'average_sleep_efficiency':round(sum(x['sleep_efficiency'] for x in entries)/len(entries),4) if entries else None,'entries_skipped_missing_fields':skipped},'sleep_note':'Efficiency arithmetic only; insomnia assessment and treatment need a clinician.'}

def _stress_enrichment(data:dict)->dict:
    scores=data.get('stress_scores',[])
    if not isinstance(scores,list):raise ValueError('stress_scores must be a list')
    ordered=sorted(({'date':s.get('date'),'score':_num(s['score'],'stress score'),'instrument':s.get('instrument')} for s in scores if isinstance(s,dict) and 'score' in s),key=lambda x:str(x['date']))
    deltas=[{'from':ordered[i]['date'],'to':ordered[i+1]['date'],'delta':round(ordered[i+1]['score']-ordered[i]['score'],4)} for i in range(len(ordered)-1)]
    return {'stress_score_trend':{'scores':ordered,'deltas':deltas},'stress_note':'Score trends invite conversation; they never diagnose or escalate on their own.'}

_WELLBEING_ENRICHMENTS={'lifestyle_modification':_lifestyle_enrichment,'nutrition_planning':_nutrition_enrichment,'exercise_prescription':_exercise_enrichment,'sleep_hygiene':_sleep_enrichment,'stress_management':_stress_enrichment}
_WELLBEING_BOUNDARIES={
 'lifestyle_modification':'Small-step goal planning from patient goals and cited guidance. A qualified professional checks safety and clinical needs; Atlas does not prescribe diet, exercise, sleep treatment or stress therapy.',
 'nutrition_planning':'Intake arithmetic from patient goals and cited guidance only. A qualified professional checks medical nutrition needs, deficiencies and eating-disorder risk; Atlas does not prescribe diet.',
 'exercise_prescription':'Activity-component organization from patient goals and cited guidance only. A qualified professional clears cardiac, injury and pregnancy safety before exercise; Atlas does not prescribe exercise treatment.',
 'sleep_hygiene':'Sleep-diary arithmetic and cited guidance only. A qualified professional assesses insomnia, apnea and medication effects; Atlas does not prescribe sleep treatment.',
 'stress_management':'Stress-score tracking and cited guidance only. A qualified professional assesses anxiety, depression and trauma; Atlas does not provide stress therapy.',
}

def wellbeing_plan(method:str,data:dict)->dict:
    baseline=data.get('baseline',{});goals=data.get('goals',[]);options=data.get('options',[]);source=data.get('source',{})
    if not isinstance(baseline,dict) or not isinstance(goals,list) or not isinstance(options,list):raise ValueError('baseline object, goals list and options list required')
    if not goals or not source.get('source_url'):raise ValueError('goals and source_url required')
    if method not in _WELLBEING_ENRICHMENTS:raise ValueError(f'unsupported wellbeing method: {method}')
    contraindications=set(data.get('contraindications',[]));selected=[]
    for o in options:
        if not set(o.get('contraindications',[]))&contraindications and set(o.get('goal_ids',[]))&{g.get('id') for g in goals}:selected.append(o)
    result={'mode':method,'baseline':baseline,'goals':goals,'candidate_steps':selected,'monitoring':data.get('monitoring',[]),'patient_preferences':data.get('patient_preferences',[]),'source':source,'approval_status':'draft_for_patient_and_qualified_professional'}
    result.update(_WELLBEING_ENRICHMENTS[method](data))
    result['boundary']=_WELLBEING_BOUNDARIES[method];result['disclaimer']=DISCLAIMER
    return result

def _treatment_enrichment(data:dict)->dict:
    dims=data.get('placement_dimensions',[])
    if not isinstance(dims,list):raise ValueError('placement_dimensions must be a list')
    return {'level_of_care_review':[{'dimension':d.get('dimension'),'status_as_supplied':d.get('status'),'documented':d.get('status') is not None} for d in dims if isinstance(d,dict)],'treatment_note':'Level-of-care placement is a clinician decision using validated criteria; Atlas only tracks supplied dimensions.'}

def _harm_reduction_enrichment(data:dict)->dict:
    services=data.get('services',[])
    supplies=[s for s in services if isinstance(s,dict) and s.get('kind')=='supply']
    overdose=[s for s in services if isinstance(s,dict) and (s.get('overdose_response') or 'overdose' in [str(t).lower() for t in s.get('goal_tags',[])])]
    return {'supply_review':[{'name':s.get('name'),'available_as_supplied':s.get('available')} for s in supplies],'overdose_response_resources':[{'name':s.get('name'),'type':s.get('type')} for s in overdose],'harm_reduction_note':'Supplies and naloxone access need no abstinence precondition; local programs confirm availability.'}

_SUBSTANCE_ENRICHMENTS={'substance_abuse_treatment':_treatment_enrichment,'harm_reduction':_harm_reduction_enrichment}
_SUBSTANCE_BOUNDARIES={
 'substance_abuse_treatment':'Nonjudgmental treatment navigation only. Overdose, dangerous withdrawal, suicidality or instability requires immediate local human emergency/clinical response. Atlas does not detoxify, prescribe, compel abstinence or contact services.',
 'harm_reduction':'Nonjudgmental harm-reduction navigation only. Overdose risk requires immediate local human emergency response and naloxone access. Atlas does not detoxify, prescribe, compel abstinence or contact services.',
}

def substance_support(method:str,data:dict)->dict:
    assessment=data.get('assessment',{});goals=data.get('goals',[]);services=data.get('services',[]);source=data.get('source',{})
    if not isinstance(assessment,dict) or not isinstance(goals,list) or not isinstance(services,list):raise ValueError('assessment object, goals list and services list required')
    if not assessment or not goals or not source.get('source_url'):raise ValueError('assessment, goals and source_url required')
    if method not in _SUBSTANCE_ENRICHMENTS:raise ValueError(f'unsupported substance support method: {method}')
    urgent=[k for k in ('overdose','dangerous_withdrawal','suicidal_intent','medical_instability') if assessment.get(k) is True]
    choices=[s for s in services if not set(s.get('exclusions',[]))&set(assessment.get('constraints',[])) and (not s.get('goal_tags') or set(s['goal_tags'])&set(goals))]
    result={'mode':method,'patient_goals':goals,'readiness':assessment.get('readiness'),'urgent_risks':urgent,'immediate_human_response_required':bool(urgent),'candidate_services_and_supplies':choices,'source':source}
    result.update(_SUBSTANCE_ENRICHMENTS[method](data))
    result['boundary']=_SUBSTANCE_BOUNDARIES[method];result['disclaimer']=DISCLAIMER
    return result

def _crisis_intervention_enrichment(data:dict)->dict:
    plan=data.get('safety_plan',{});resources=data.get('resources',[])
    if not isinstance(plan,dict) or not isinstance(resources,list):raise ValueError('safety_plan object and resources list required')
    steps=[]
    if plan.get('contact'):steps.append({'step':'contact trusted person','detail':plan.get('contact'),'source':'safety_plan'})
    for r in resources:
        if isinstance(r,dict):steps.append({'step':'use local resource','detail':r.get('name'),'source':'supplied_resources'})
    return {'handoff_steps':steps,'crisis_note':'A person in danger needs human help now; Atlas stays out of the way of local emergency response.'}

def _suicide_prevention_enrichment(data:dict)->dict:
    means=data.get('means',[])
    if not isinstance(means,list):raise ValueError('means must be a list')
    review=[]
    for m in means:
        if not isinstance(m,dict):raise ValueError('each means entry must be an object')
        secured=m.get('secured')
        review.append({'item':m.get('item'),'secured_status':'secured' if secured is True else 'not_secured' if secured is False else 'not_assessed'})
    return {'means_safety_review':review,'unsecured_means':[r['item'] for r in review if r['secured_status']!='secured'],'means_note':'Unassessed means are never treated as safe; a caring human confirms storage and distance.'}

_CRISIS_ENRICHMENTS={'crisis_intervention':_crisis_intervention_enrichment,'suicide_prevention':_suicide_prevention_enrichment}
_CRISIS_BOUNDARIES={
 'crisis_intervention':'Triage support, never autonomous crisis care. Atlas does not promise confidentiality, monitor a person, contact emergency services, or treat absence of a supplied flag as safety. Immediate danger requires local human emergency/crisis response now.',
 'suicide_prevention':'Safety-planning support, never autonomous crisis care. Unassessed means are never treated as safe; Atlas does not promise confidentiality, monitor a person, or contact emergency services. Immediate danger requires local human emergency/crisis response now.',
}

def crisis_support(method:str,data:dict)->dict:
    safety=data.get('safety',{});plan=data.get('safety_plan',{});resources=data.get('resources',[]);source=data.get('source',{})
    if not isinstance(safety,dict):raise ValueError('safety must be an object of direct assessment fields')
    if not safety or not source.get('source_url'):raise ValueError('direct safety assessment and source_url required')
    if method not in _CRISIS_ENRICHMENTS:raise ValueError(f'unsupported crisis method: {method}')
    imminent=any(safety.get(k) is True for k in ('imminent_intent','active_attempt','immediate_danger','cannot_stay_safe'))
    missing=[k for k in ('imminent_intent','active_attempt','immediate_danger','cannot_stay_safe') if k not in safety]
    result={'mode':method,'safety_status':'incomplete' if missing else 'immediate_response' if imminent else 'no_supplied_imminent_flag','missing_safety_fields':missing,'immediate_human_response_required':imminent,'existing_safety_plan':plan,'local_resources':resources,'next_step':'contact local emergency/crisis support now and stay with a trusted human if safe' if imminent else 'qualified human follow-up and collaborative safety planning','source':source}
    result.update(_CRISIS_ENRICHMENTS[method](data))
    result['boundary']=_CRISIS_BOUNDARIES[method];result['disclaimer']=DISCLAIMER
    return result

def _trauma_enrichment(data:dict)->dict:
    coping=data.get('coping_options',[])
    if not isinstance(coping,list):raise ValueError('coping_options must be a list')
    return {'choice_and_control_map':{'consent_checkpoints':data.get('consent_checkpoints',[]),'declinable_options':[o.get('name') for o in data.get('options',[]) if isinstance(o,dict)]},'grounding_options':[{'name':c.get('name'),'patient_endorsed':c.get('patient_endorsed')} for c in coping if isinstance(c,dict)],'trauma_note':'Choice, collaboration and pacing belong to the patient; nothing proceeds without consent.'}

def _cultural_enrichment(data:dict)->dict:
    resources=data.get('language_resources',[])
    if not isinstance(resources,list):raise ValueError('language_resources must be a list')
    languages={r.get('language') for r in resources if isinstance(r,dict)}
    language=data.get('preferences',{}).get('language')
    return {'language_access_review':{'preferred_language':language,'resource_available':(language in languages) if language else None,'unmatched_needs':[n for n in data.get('needs',[]) if n=='interpreter' and language and language not in languages]},'cultural_note':'Language access is a right, not a preference; professional interpreters replace ad-hoc translation.'}

_TRAUMA_CULTURAL_ENRICHMENTS={'trauma_informed_care':_trauma_enrichment,'culturally_competent_care':_cultural_enrichment}
_TRAUMA_CULTURAL_BOUNDARIES={
 'trauma_informed_care':'Use patient-stated needs, identity and preferences without inference or stereotypes. Preserve choice, control, privacy, language access and consent; clinicians and patients decide care and may decline any option.',
 'culturally_competent_care':'Use patient-stated needs, identity and preferences without inference or stereotypes. Provide language access and cultural humility; clinicians and patients decide care and may decline any option.',
}

def trauma_cultural_care(method:str,data:dict)->dict:
    preferences=data.get('preferences',{});needs=data.get('needs',[]);options=data.get('options',[]);source=data.get('source',{})
    if not isinstance(preferences,dict) or not isinstance(needs,list) or not isinstance(options,list):raise ValueError('preferences object, needs list and options list required')
    if not source.get('source_url'):raise ValueError('source_url required')
    if method not in _TRAUMA_CULTURAL_ENRICHMENTS:raise ValueError(f'unsupported trauma/cultural care method: {method}')
    selected=[o for o in options if not set(o.get('conflicts_with',[]))&set(preferences.get('declined',[]))]
    result={'mode':method,'patient_stated_preferences':preferences,'needs':needs,'candidate_accommodations':selected,'consent_checkpoints':data.get('consent_checkpoints',[]),'source':source}
    result.update(_TRAUMA_CULTURAL_ENRICHMENTS[method](data))
    result['boundary']=_TRAUMA_CULTURAL_BOUNDARIES[method];result['disclaimer']=DISCLAIMER
    return result

CLINICAL_EXTRA.update({
 'medication_adherence':adherence_support,
 'lifestyle_modification':lambda d:wellbeing_plan('lifestyle_modification',d),
 'nutrition_planning':lambda d:wellbeing_plan('nutrition_planning',d),
 'exercise_prescription':lambda d:wellbeing_plan('exercise_prescription',d),
 'sleep_hygiene':lambda d:wellbeing_plan('sleep_hygiene',d),
 'stress_management':lambda d:wellbeing_plan('stress_management',d),
 'substance_abuse_treatment':lambda d:substance_support('substance_abuse_treatment',d),
 'harm_reduction':lambda d:substance_support('harm_reduction',d),
 'crisis_intervention':lambda d:crisis_support('crisis_intervention',d),
 'suicide_prevention':lambda d:crisis_support('suicide_prevention',d),
 'trauma_informed_care':lambda d:trauma_cultural_care('trauma_informed_care',d),
 'culturally_competent_care':lambda d:trauma_cultural_care('culturally_competent_care',d),
})

def equity_analysis(data:dict)->dict:
    groups=data.get('groups',[]);metrics=data.get('metrics',[]);source=data.get('source',{})
    if len(groups)<2 or not metrics or not source.get('source_url'):raise ValueError('at least two groups, metrics and source_url required')
    rows=[]
    for metric in metrics:
        values={g.get('group_token'):g.get('values',{}).get(metric) for g in groups};known=[float(v) for v in values.values() if v is not None];rows.append({'metric':metric,'values':values,'absolute_gap':max(known)-min(known) if len(known)>=2 else None,'missing_groups':[k for k,v in values.items() if v is None]})
    return {'metric_gaps':rows,'stratification_dimensions':data.get('stratification_dimensions',[]),'community_interpretation':data.get('community_interpretation',[]),'source':source,'boundary':'Descriptive disparity analysis on supplied aggregate data. Gaps do not identify causes or justify individual decisions. Affected communities and domain experts validate categories, denominators, privacy, structural context and remedies.','disclaimer':DISCLAIMER}

def social_needs(data:dict)->dict:
    responses=data.get('responses',{});domains=data.get('domains',[]);resources=data.get('resources',[]);source=data.get('source',{})
    if not domains or not source.get('source_url'):raise ValueError('domains and source_url required')
    needs=[];declined=[];unknown=[]
    for d in domains:
        key=d.get('id');value=responses.get(key)
        if value is None:unknown.append(key)
        elif value=='decline_to_answer':declined.append(key)
        elif value in d.get('need_values',[]):needs.append({'domain':key,'response':value,'resources':[r for r in resources if key in r.get('domains',[])]})
    return {'identified_needs':needs,'unknown_domains':unknown,'declined_domains':declined,'consent_to_referral':data.get('consent_to_referral',{}),'source':source,'boundary':'Voluntary needs screening, never a worthiness or risk score. Declining or missing answers cannot reduce care. Human staff verify resources and obtain specific consent before any referral or disclosure.','disclaimer':DISCLAIMER}

def community_assessment(data:dict)->dict:
    indicators=data.get('indicators',[]);voices=data.get('community_inputs',[]);source=data.get('source',{})
    if not indicators or not voices or not source.get('source_url'):raise ValueError('indicators, community inputs and source_url required')
    priorities=[]
    for i in indicators:
        supporting=[v for v in voices if i.get('topic') in v.get('topics',[])];priorities.append({'indicator':i,'community_inputs':supporting,'evidence_complete':bool(supporting)})
    return {'candidate_priorities':priorities,'represented_groups':sorted({x.get('group') for x in voices if x.get('group')}),'missing_representation':data.get('missing_representation',[]),'source':source,'boundary':'Participatory assessment draft, not a substitute for community governance. Do not rank a priority as settled without affected-community input, representative data, privacy review and transparent limitations.','disclaimer':DISCLAIMER}

def policy_analysis(data:dict)->dict:
    options=data.get('options',[]);criteria=data.get('criteria',[]);source=data.get('source',{})
    if not options or not criteria or not source.get('source_url'):raise ValueError('options, criteria and source_url required')
    rows=[]
    for o in options:
        values=o.get('scores',{});missing=[c.get('id') for c in criteria if c.get('id') not in values];total=None if missing else sum(float(values[c['id']])*float(c.get('weight',1)) for c in criteria);rows.append({'option':o.get('name'),'criterion_scores':values,'weighted_score':total,'missing_criteria':missing,'distributional_effects':o.get('distributional_effects',[]),'legal_or_operational_dependencies':o.get('dependencies',[])})
    return {'option_matrix':rows,'criteria':criteria,'assumptions':data.get('assumptions',[]),'source':source,'boundary':'Transparent comparison under supplied criteria, not advocacy or legal authority. Decision-makers and affected communities review evidence quality, rights, equity, costs, uncertainty and implementation before policy action.','disclaimer':DISCLAIMER}

def quality_improvement(method:str,data:dict)->dict:
    measures=data.get('measures',[]);changes=data.get('change_ideas',[]);source=data.get('source',{})
    if not measures or not source.get('source_url'):raise ValueError('measures and source_url required')
    evaluated=[]
    for m in measures:
        numerator=float(m.get('numerator',0));denominator=float(m.get('denominator',0));evaluated.append({**m,'rate':numerator/denominator if denominator>0 else None,'valid_denominator':denominator>0})
    return {'mode':method,'measure_results':evaluated,'change_ideas_for_review':changes,'balancing_measures':data.get('balancing_measures',[]),'source':source,'boundary':'Quality-learning support, not individual blame or autonomous clinical/operational change. Teams validate measure definitions, case mix, data quality, balancing harms and human-factors causes before testing a change.','disclaimer':DISCLAIMER}

def _patient_safety_enrichment(data:dict,actions:list)->dict:
    factors=data.get('contributing_factors',[])
    return {'just_culture_inputs':[{'factor_id':f.get('id'),'factor_type_as_supplied':f.get('factor_type'),'typed':f.get('factor_type') is not None} for f in factors if isinstance(f,dict)],'patient_safety_note':'System factors and individual choices are recorded as supplied; culpability is never inferred.'}

def _error_prevention_enrichment(data:dict,actions:list)->dict:
    factors=data.get('contributing_factors',[])
    addressed={mf for c in actions for mf in c.get('matched_factors',[])}
    unmitigated=[f.get('id') for f in factors if isinstance(f,dict) and f.get('id') not in addressed]
    return {'prevention_gap_analysis':{'unmitigated_factors':unmitigated,'control_coverage':round(len(addressed)/len(factors),4) if factors else None},'prevention_note':'Prospective hazard review; unmitigated factors route to the safety team before rollout.'}

_SAFETY_ENRICHMENTS={'patient_safety':_patient_safety_enrichment,'medical_error_prevention':_error_prevention_enrichment}
_SAFETY_BOUNDARIES={
 'patient_safety':'Just-culture systems analysis, not culpability, diagnosis or disciplinary evidence. Preserve uncertainty and separate facts from hypotheses; authorized safety teams investigate and approve controls.',
 'medical_error_prevention':'Prospective failure-mode review, not culpability, diagnosis or disciplinary evidence. Unmitigated hazards require authorized safety-team review before changes; Atlas never assigns blame or executes controls.',
}

def safety_review(method:str,data:dict)->dict:
    event=data.get('event',{});factors=data.get('contributing_factors',[]);controls=data.get('controls',[]);source=data.get('source',{})
    if not isinstance(event,dict) or not isinstance(factors,list) or not isinstance(controls,list):raise ValueError('event object, contributing_factors list and controls list required')
    if not event or not source.get('source_url'):raise ValueError('event and source_url required')
    if method not in _SAFETY_ENRICHMENTS:raise ValueError(f'unsupported safety method: {method}')
    actions=[]
    for c in controls:
        matched=set(c.get('addresses',[]))&{f.get('id') for f in factors};actions.append({**c,'matched_factors':sorted(matched),'review_status':'candidate' if matched else 'unlinked'})
    result={'mode':method,'event_timeline':event.get('timeline',[]),'known_facts':event.get('known_facts',[]),'unknowns':event.get('unknowns',[]),'contributing_factors':factors,'candidate_system_controls':actions,'source':source}
    result.update(_SAFETY_ENRICHMENTS[method](data,actions))
    result['boundary']=_SAFETY_BOUNDARIES[method];result['disclaimer']=DISCLAIMER
    return result

def _operations_enrichment(data:dict,totals:dict)->dict:
    scenarios=data.get('scenarios',[])
    if not isinstance(scenarios,list):raise ValueError('scenarios must be a list')
    rows=[]
    for s in scenarios:
        if not isinstance(s,dict):raise ValueError('each scenario must be an object')
        mult=_num(s.get('demand_multiplier',1),'demand_multiplier')
        if mult<0:raise ValueError('demand_multiplier must be non-negative')
        rows.append({'scenario':s.get('name'),'demand_multiplier':mult,'projected_demand':round(totals['demand']*mult,4),'projected_gap':round(totals['capacity']-totals['demand']*mult,4)})
    return {'scenario_review':rows,'operations_note':'Scenario arithmetic on supplied aggregates; leaders validate feasibility, safety and labor rules.'}

def _administration_enrichment(data:dict,totals:dict)->dict:
    policies=data.get('policies',[])
    if not isinstance(policies,list):raise ValueError('policies must be a list')
    return {'policy_checklist':[{'policy':p.get('name'),'owner':p.get('owner'),'review_date':p.get('review_date'),'status':p.get('status','unspecified')} for p in policies if isinstance(p,dict)],'administration_note':'Policy status as supplied; administrators confirm currency and compliance.'}

def _finance_enrichment(data:dict,totals:dict)->dict:
    lines=data.get('budget_lines',[])
    if not isinstance(lines,list):raise ValueError('budget_lines must be a list')
    rows=[]
    for l in lines:
        if not isinstance(l,dict):raise ValueError('each budget line must be an object')
        budgeted=_num(l.get('budgeted',0),'budgeted');actual=_num(l.get('actual',0),'actual')
        rows.append({'line':l.get('line'),'budgeted':budgeted,'actual':actual,'variance':round(actual-budgeted,4),'variance_note':'over' if actual>budgeted else 'under' if actual<budgeted else 'on_budget'})
    return {'budget_variance':rows,'finance_note':'Variance arithmetic only; no payment, transfer, or accounting change is executed.'}

_OPERATIONS_ENRICHMENTS={'healthcare_operations':_operations_enrichment,'hospital_administration':_administration_enrichment,'healthcare_finance':_finance_enrichment}
_OPERATIONS_BOUNDARIES={
 'healthcare_operations':'Aggregate capacity planning only. Administrators and clinical leaders validate staffing, acuity, labor rules, safety and equity. Atlas does not schedule staff, allocate individual care or admit/discharge patients.',
 'hospital_administration':'Aggregate policy and operations checklists only. Administrators validate compliance, staffing, safety and equity. Atlas does not schedule staff, allocate individual care or admit/discharge patients.',
 'healthcare_finance':'Aggregate budget arithmetic only. Finance and clinical leaders validate coding, contracts and policy. Atlas does not schedule staff, allocate individual care, admit/discharge patients or execute financial changes.',
}

def healthcare_operations(method:str,data:dict)->dict:
    demand=data.get('demand',[]);capacity=data.get('capacity',[]);constraints=data.get('constraints',[]);source=data.get('source',{})
    if not isinstance(demand,list) or not isinstance(capacity,list):raise ValueError('demand and capacity must be lists')
    if not demand or not capacity or not source.get('source_url'):raise ValueError('demand, capacity and source_url required')
    if method not in _OPERATIONS_ENRICHMENTS:raise ValueError(f'unsupported healthcare operations method: {method}')
    totals={'demand':sum(_num(x.get('units',0),'demand units') for x in demand),'capacity':sum(_num(x.get('units',0),'capacity units') for x in capacity)};gap=totals['capacity']-totals['demand']
    result={'mode':method,'totals':totals,'capacity_gap':gap,'constraints':constraints,'options':data.get('options',[]),'equity_and_safety_checks':data.get('equity_and_safety_checks',[]),'source':source}
    result.update(_OPERATIONS_ENRICHMENTS[method](data,totals))
    result['boundary']=_OPERATIONS_BOUNDARIES[method];result['disclaimer']=DISCLAIMER
    return result

def medical_education(data:dict)->dict:
    objectives=data.get('objectives',[]);cases=data.get('cases',[]);rubric=data.get('rubric',[]);source=data.get('source',{})
    if not objectives or not cases or not rubric or not source.get('source_url'):raise ValueError('objectives, cases, rubric and source_url required')
    mapped=[]
    for c in cases:mapped.append({'case_id':c.get('id'),'objective_ids':[o.get('id') for o in objectives if o.get('id') in c.get('objective_ids',[])],'deidentified_or_synthetic':c.get('deidentified_or_synthetic',False),'answer_key':c.get('answer_key')})
    return {'objectives':objectives,'case_map':mapped,'assessment_rubric':rubric,'source':source,'boundary':'Educator-reviewed learning support. Use deidentified or synthetic cases, distinguish evidence from uncertainty, and do not treat scores as licensure, credentialing or permission for unsupervised patient care.','disclaimer':DISCLAIMER}

CLINICAL_EXTRA.update({
 'health_equity_analysis':equity_analysis,'social_determinants_assessment':social_needs,'community_health_assessment':community_assessment,'health_policy_analysis':policy_analysis,
 'healthcare_quality_improvement':lambda d:quality_improvement('healthcare_quality_improvement',d),
 'patient_safety':lambda d:safety_review('patient_safety',d),'medical_error_prevention':lambda d:safety_review('medical_error_prevention',d),
 'healthcare_operations':lambda d:healthcare_operations('healthcare_operations',d),'hospital_administration':lambda d:healthcare_operations('hospital_administration',d),'healthcare_finance':lambda d:healthcare_operations('healthcare_finance',d),
 'medical_education':medical_education,
})

# Depth-sweep contract: preserve every method's distinctive output while adding a
# common, explicit uncertainty and review report.  Wrapping at module load also
# covers direct Python callers, not only the HTTP route.
from functools import wraps as _wraps
from app.core.depth_quality import attach_quality as _attach_quality

_DEPTH_CLINICAL_METHODS = (
 'medication_management','chronic_care_plan','oncology_coordination','oncology_plan',
 'palliative_plan','pain_plan','wound_care','infection_control','antimicrobial_stewardship',
 'vaccination_schedule','preventive_care','genetic_counseling','reproductive_plan',
 'perinatal_plan','life_stage_care','global_health','public_health_surveillance',
 'epidemic_response','contact_tracing','quarantine_management','health_education',
 'adherence_support','wellbeing_plan','substance_support','crisis_support',
 'trauma_cultural_care','equity_analysis','social_needs','community_assessment',
 'policy_analysis','quality_improvement','safety_review','healthcare_operations',
 'medical_education'
)

def _depth_clinical_wrap(name, fn):
    @_wraps(fn)
    def wrapped(*args, **kwargs):
        out=fn(*args, **kwargs)
        payload=next((x for x in reversed(args) if isinstance(x,dict)), kwargs.get('data',{}))
        evidence=[]
        for key in ('sources','evidence','guidelines','authorities'):
            value=payload.get(key,[]) if isinstance(payload,dict) else []
            if isinstance(value,list): evidence.extend(x for x in value if isinstance(x,dict))
        source=payload.get('source') if isinstance(payload,dict) else None
        if isinstance(source,dict): evidence.append(source)
        required=[k for k in payload if k not in {'source','sources','evidence','guidelines','authorities'}]
        return _attach_quality(out,domain='clinical',method=name,inputs=payload,
            required_inputs=required,evidence=evidence,
            assumptions=payload.get('assumptions',[]) if isinstance(payload,dict) else [],
            limitations=['Decision support does not diagnose, prescribe, or execute care.',
                         'Urgent symptoms require local emergency or clinical services.'])
    return wrapped

for _name in _DEPTH_CLINICAL_METHODS:
    globals()[_name]=_depth_clinical_wrap(_name,globals()[_name])
