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
