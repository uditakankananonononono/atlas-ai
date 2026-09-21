"""Non-diagnostic clinical decision support for feature rows 1110-1114.

This layer organizes clinician-supplied evidence. It never diagnoses, prescribes,
or executes treatment. Every output retains provenance, uncertainty and an
explicit clinician-review boundary.
"""
from __future__ import annotations
from dataclasses import dataclass,asdict
from math import isfinite
from typing import Any

DISCLAIMER="Decision support only. A licensed clinician must verify inputs, context and recommendations before any clinical action."

def _require_citations(items:list[dict[str,Any]],label:str):
    if not items or any(not x.get('source_url') or not x.get('source_title') for x in items):raise ValueError(f'{label} requires source_url and source_title for every item')

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
        return {'sections':{'differential':differential(data['differential']) if data.get('differential') else None,'protocols':protocol(data['protocols']) if data.get('protocols') else None,'interactions':interactions(data['interactions']) if data.get('interactions') else None,'dosage':dosage(data['dosage']) if data.get('dosage') else None},'disclaimer':DISCLAIMER}
    if method in CLINICAL_EXTRA:return CLINICAL_EXTRA[method](data)
    if method not in methods:raise ValueError('unsupported clinical support method')
    return methods[method](data)

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
