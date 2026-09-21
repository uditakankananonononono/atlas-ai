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
    if method not in methods:raise ValueError('unsupported clinical support method')
    return methods[method](data)
