"""Twenty bounded, deterministic college-application planning operations.

These tools analyze student-supplied data. They do not predict admission,
write student essays, fetch private application records, or submit forms.
"""
from __future__ import annotations
from collections import Counter, defaultdict
from datetime import date, datetime
from math import ceil
from statistics import median
from urllib.parse import urlparse


def _day(value: str) -> date:
    return date.fromisoformat(value)


def _words(text: str) -> set[str]:
    return {w.strip(".,:;!?()[]\"'").casefold() for w in text.split() if len(w.strip(".,:;!?()[]\"'")) > 2}


def _records(data: dict, key: str) -> list[dict]:
    rows = data.get(key, [])
    if not isinstance(rows, list) or len(rows) > 500 or any(not isinstance(r, dict) for r in rows):
        raise ValueError(f'{key} must be a list of at most 500 objects')
    return rows


def _id(row: dict) -> str:
    return str(row.get('id', '')).strip()


def deadline_triage(d: dict) -> dict:
    today = _day(d['today']); rows = _records(d, 'deadlines')
    out = [{'id': _id(r), 'days_left': (_day(r['due'])-today).days, 'due': r['due']} for r in rows]
    return {'overdue': [r for r in out if r['days_left'] < 0], 'upcoming': sorted((r for r in out if r['days_left'] >= 0), key=lambda r:r['days_left'])}


def workload_calendar(d: dict) -> dict:
    weeks = int(d.get('weeks', 0)); hours = float(d.get('total_hours', 0))
    if not 1 <= weeks <= 52 or not 0 <= hours <= 10000: raise ValueError('weeks must be 1-52 and hours 0-10000')
    return {'weekly_hours': [round(hours/weeks, 2)]*weeks, 'capacity_warning': hours/weeks > float(d.get('max_hours_per_week', 12))}


def requirement_gap(d: dict) -> dict:
    have = set(d.get('completed', [])); required = set(d.get('required', []))
    return {'missing': sorted(required-have), 'complete': sorted(required&have), 'ready': required <= have}


def school_list_balance(d: dict) -> dict:
    rows = _records(d, 'schools'); counts = Counter(r.get('student_assessed_category', 'unknown') for r in rows)
    return {'counts': dict(counts), 'unclassified': [r.get('name') for r in rows if r.get('student_assessed_category') not in {'reach','target','likely'}], 'note':'Student-assessed labels only; not admission odds.'}


def program_language_fit(d: dict) -> dict:
    languages = {s.casefold() for s in d.get('languages', [])}; rows = _records(d, 'programs')
    return {'matches': [r for r in rows if str(r.get('instruction_language','')).casefold() in languages], 'needs_language_review': [r for r in rows if str(r.get('instruction_language','')).casefold() not in languages]}


def tuition_scenario(d: dict) -> dict:
    tuition = float(d.get('tuition', 0)); living = float(d.get('living', 0)); aid = float(d.get('confirmed_aid', 0)); years = int(d.get('years', 1))
    if min(tuition,living,aid) < 0 or not 1 <= years <= 10: raise ValueError('nonnegative costs and years 1-10 required')
    return {'annual_gap': max(0,tuition+living-aid), 'program_gap': max(0,(tuition+living-aid)*years), 'currency':d.get('currency','USD'), 'estimate_only':True}


def scholarship_eligibility(d: dict) -> dict:
    facts = d.get('student_facts', {}); rows = _records(d, 'scholarships'); out=[]
    for r in rows:
        req=r.get('requirements', {}); missing=[k for k in req if k not in facts]; mismatch=[k for k,v in req.items() if k in facts and facts[k]!=v]
        out.append({'id':_id(r),'status':'unknown' if missing else 'ineligible' if mismatch else 'candidate','missing_facts':missing,'mismatched_facts':mismatch,'source':r.get('source')})
    return {'results':out,'note':'Preliminary comparison; check current official eligibility.'}


def document_inventory(d: dict) -> dict:
    required = _records(d, 'requirements'); uploaded = {r.get('kind') for r in _records(d,'documents') if r.get('student_confirmed')}
    return {'needed': [r for r in required if r.get('kind') not in uploaded], 'present': sorted(uploaded)}


def recommender_timeline(d: dict) -> dict:
    days = int(d.get('lead_days', 21)); due = _day(d['due'])
    if not 1 <= days <= 365: raise ValueError('lead_days must be 1-365')
    from datetime import timedelta
    return {'request_by': (due-timedelta(days=days)).isoformat(), 'due':due.isoformat(),'request_sent':False}


def essay_prompt_matrix(d: dict) -> dict:
    prompts=_records(d,'prompts'); evidence=_records(d,'evidence'); out=[]
    for p in prompts:
        terms=_words(str(p.get('text',''))); ranked=sorted(({'id':_id(e),'overlap':len(terms&_words(str(e.get('description',''))))} for e in evidence if e.get('student_confirmed')),key=lambda x:(-x['overlap'],x['id']))
        out.append({'prompt_id':_id(p),'evidence_candidates':[r for r in ranked if r['overlap']>0][:5], 'student_writes_prose':True})
    return {'prompts':out}


def essay_overlap(d: dict) -> dict:
    drafts=_records(d,'drafts'); pairs=[]
    for i,a in enumerate(drafts):
        x=_words(str(a.get('student_text','')))
        for b in drafts[i+1:]:
            y=_words(str(b.get('student_text',''))); pairs.append({'ids':[_id(a),_id(b)],'jaccard':round(len(x&y)/len(x|y),3) if x|y else 0})
    return {'pairs':pairs,'caution':'Lexical overlap is not a plagiarism verdict.'}


def word_limit(d: dict) -> dict:
    text=str(d.get('student_text','')); limit=int(d.get('limit',0))
    if not 1 <= limit <= 100000: raise ValueError('limit must be 1-100000')
    n=len(text.split());return {'words':n,'limit':limit,'remaining':limit-n,'over_limit':n>limit}


def activity_evidence(d: dict) -> dict:
    return {'rows':[{'id':_id(r),'ready':bool(r.get('student_confirmed') and r.get('source') and r.get('description')),'missing':[k for k in ('student_confirmed','source','description') if not r.get(k)]} for r in _records(d,'activities')]}


def interview_question_bank(d: dict) -> dict:
    rows=_records(d,'activities'); questions=[]
    for r in rows:
        if r.get('student_confirmed'):
            questions.append({'activity_id':_id(r),'questions':[f"What was your personal role in {r.get('title','this activity')}?",'What changed because of your work, and what evidence shows that?']})
    return {'practice_questions':questions,'generated_answers':None}


def application_status(d: dict) -> dict:
    rows=_records(d,'applications'); return {'counts':dict(Counter(str(r.get('status','unknown')) for r in rows)),'follow_up':[r for r in rows if r.get('status') in ('in_progress','needs_review')]}


def decision_comparison(d: dict) -> dict:
    rows=_records(d,'offers'); out=[]
    for r in rows:
        cost=r.get('annual_cost');aid=r.get('confirmed_aid')
        out.append({'id':_id(r),'net_annual_cost':max(0,float(cost)-float(aid)) if cost is not None and aid is not None else None,'unknown_cost':cost is None or aid is None,'decision_deadline':r.get('decision_deadline')})
    return {'offers':out,'recommendation':None}


def visa_checklist(d: dict) -> dict:
    rows=_records(d,'requirements');return {'official_source_required':[r for r in rows if not r.get('official_url')],'reviewable':[r for r in rows if r.get('official_url')],'legal_advice':False}


def source_freshness(d: dict) -> dict:
    today=_day(d['today']); threshold=int(d.get('max_age_days',90)); rows=_records(d,'sources')
    if threshold<0:raise ValueError('max_age_days must be nonnegative')
    return {'stale':[r for r in rows if not r.get('checked_on') or (today-_day(r['checked_on'])).days>threshold], 'fresh':[r for r in rows if r.get('checked_on') and (today-_day(r['checked_on'])).days<=threshold]}


def source_domain_check(d: dict) -> dict:
    rows=_records(d,'sources'); out=[]
    for r in rows:
        u=urlparse(str(r.get('url','')));out.append({'id':_id(r),'https':u.scheme=='https' and bool(u.hostname),'domain':u.hostname,'official_claim_unverified':bool(r.get('official'))})
    return {'results':out}


def privacy_minimization(d: dict) -> dict:
    rows=_records(d,'records'); sensitive={'ssn','passport_number','date_of_birth','medical_history','home_address'}
    return {'records':[{'id':_id(r),'sensitive_fields_to_remove':sorted(sensitive & set(r)),'minimal':not bool(sensitive & set(r))} for r in rows]}

TOOLS={name:globals()[name] for name in ('deadline_triage','workload_calendar','requirement_gap','school_list_balance','program_language_fit','tuition_scenario','scholarship_eligibility','document_inventory','recommender_timeline','essay_prompt_matrix','essay_overlap','word_limit','activity_evidence','interview_question_bank','application_status','decision_comparison','visa_checklist','source_freshness','source_domain_check','privacy_minimization')}
