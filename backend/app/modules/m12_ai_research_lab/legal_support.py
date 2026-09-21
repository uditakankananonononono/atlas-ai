"""Source-grounded legal workbench for owner feature rows 1260-1309.

The workbench structures lawyer-supplied facts and primary/secondary authorities. It is
jurisdiction/date aware, preserves contrary authority and unknown facts, and never files,
submits, communicates, predicts an outcome, or substitutes for licensed counsel.
"""
from __future__ import annotations
from datetime import date
from typing import Any, Callable

DISCLAIMER = "Legal work product for review, not legal advice. Licensed counsel must verify jurisdiction, currency, citations, facts, duties, deadlines and strategy before use."

DOCTRINE = {
 "sentencing_guidelines","criminal_appeals","constitutional_law","first_amendment","fourth_amendment","due_process","equal_protection","administrative_law","regulatory_practice","agency_proceedings","judicial_review","international_law","treaties","human_rights","international_trade"
}
DISPUTE = {"arbitration","mediation","dispute_resolution","litigation_strategy","discovery","depositions","trial_preparation","evidence_analysis","witness_preparation","jury_selection","appellate_practice","legal_writing","legal_citations","brief_writing","oral_argument"}
ETHICS = {"legal_ethics","professional_responsibility","conflicts_of_interest","attorney_client_privilege","legal_malpractice","pro_bono_practice","legal_aid","access_to_justice"}
TECH = {"legal_technology","e_discovery","legal_analytics","predictive_coding","document_review"}
OPS = {"legal_operations","law_firm_management","legal_billing","alternative_fee_arrangements","legal_project_management","knowledge_management","legal_education"}
LEGAL_METHODS = DOCTRINE | DISPUTE | ETHICS | TECH | OPS

LABELS = {x:x.replace('_',' ').title() for x in LEGAL_METHODS}
ROW_IDS = {name:1260+i for i,name in enumerate([
 "sentencing_guidelines","criminal_appeals","constitutional_law","first_amendment","fourth_amendment","due_process","equal_protection","administrative_law","regulatory_practice","agency_proceedings","judicial_review","international_law","treaties","human_rights","international_trade","arbitration","mediation","dispute_resolution","litigation_strategy","discovery","depositions","trial_preparation","evidence_analysis","witness_preparation","jury_selection","appellate_practice","legal_writing","legal_citations","brief_writing","oral_argument","legal_ethics","professional_responsibility","conflicts_of_interest","attorney_client_privilege","legal_malpractice","pro_bono_practice","legal_aid","access_to_justice","legal_technology","e_discovery","legal_analytics","predictive_coding","document_review","legal_operations","law_firm_management","legal_billing","alternative_fee_arrangements","legal_project_management","knowledge_management","legal_education"])}

def _base(method:str,data:dict)->dict:
    jurisdiction=data.get("jurisdiction")
    as_of=data.get("as_of")
    if not jurisdiction or not as_of: raise ValueError("jurisdiction and as_of are required")
    try: date.fromisoformat(as_of)
    except (TypeError,ValueError): raise ValueError("as_of must be an ISO date")
    return {"row_id":ROW_IDS[method],"method":method,"concept":LABELS[method],"jurisdiction":jurisdiction,"as_of":as_of,"assumptions":data.get("assumptions",[]),"unknowns":data.get("unknowns",[]),"review_required":True,"disclaimer":DISCLAIMER}

def _authorities(data:dict)->list[dict]:
    authorities=data.get("authorities",[])
    if not authorities: raise ValueError("at least one authority is required")
    out=[]
    for a in authorities:
        if not all(a.get(k) for k in ("title","citation","source_url","authority_type")): raise ValueError("every authority needs title, citation, source_url and authority_type")
        out.append({k:a.get(k) for k in ("title","citation","source_url","authority_type","court_or_body","jurisdiction","effective_date","last_checked_at","precedential_status","pinpoint","holding_or_rule")}|{"treatment":a.get("treatment","unverified"),"is_contrary":bool(a.get("is_contrary",False))})
    return out

def _doctrine(method:str,data:dict)->dict:
    result=_base(method,data); authorities=_authorities(data); issues=data.get("issues",[])
    if not issues: raise ValueError("issues are required")
    matrix=[]
    for issue in issues:
        if not issue.get("issue"): raise ValueError("each issue needs issue")
        ids=issue.get("authority_citations",[]); matched=[a for a in authorities if a["citation"] in ids]
        matrix.append({"issue":issue["issue"],"elements_or_standard":issue.get("elements_or_standard",[]),"facts_supporting":issue.get("facts_supporting",[]),"facts_against":issue.get("facts_against",[]),"missing_facts":issue.get("missing_facts",[]),"authorities":matched,"analysis":issue.get("analysis"),"status":"incomplete" if issue.get("missing_facts") or not matched else "ready_for_counsel_review"})
    result.update({"issue_matrix":matrix,"authorities":authorities,"contrary_authorities":[a for a in authorities if a["is_contrary"]],"currency_warnings":[a["citation"] for a in authorities if not a.get("last_checked_at")],"boundary":"Research synthesis only. Do not infer governing law, omit adverse authority, calculate a filing deadline, or state an outcome as certain."}); return result

def _dispute(method:str,data:dict)->dict:
    result=_base(method,data); objectives=data.get("objectives",[]); tasks=data.get("tasks",[])
    if not objectives: raise ValueError("objectives are required")
    authorities=_authorities(data)
    work=[]
    for t in tasks:
        work.append({"id":t.get("id"),"task":t.get("task"),"owner":t.get("owner"),"due_at":t.get("due_at"),"dependencies":t.get("dependencies",[]),"evidence_refs":t.get("evidence_refs",[]),"authority_citations":t.get("authority_citations",[]),"approval_status":"pending"})
    result.update({"objectives":objectives,"authorities":authorities,"workplan":work,"record":data.get("record",[]),"positions_or_themes":data.get("positions_or_themes",[]),"risks":data.get("risks",[]),"protected_material":data.get("protected_material",[]),"boundary":"Preparation and analysis only. Counsel controls candor, preservation, privilege, witness coaching limits, tribunal rules, deadlines, service, filing, settlement and communications. No task is executed by this endpoint."}); return result

def _ethics(method:str,data:dict)->dict:
    result=_base(method,data); parties=data.get("parties",[]); duties=data.get("duties",[]); facts=data.get("facts",[]); authorities=_authorities(data)
    if not parties or not duties: raise ValueError("parties and duties are required")
    checks=[]
    for duty in duties:
        needed=duty.get("required_facts",[]); missing=[x for x in needed if x not in facts]
        checks.append({"duty":duty.get("duty"),"rule_citation":duty.get("rule_citation"),"triggered_by":duty.get("triggered_by",[]),"missing_facts":missing,"status":"needs_facts" if missing else "counsel_determination_required"})
    result.update({"parties":parties,"duty_checks":checks,"authorities":authorities,"information_boundaries":data.get("information_boundaries",[]),"consents":data.get("consents",[]),"boundary":"Issue spotting only. Never create a conflict clearance, privilege determination, waiver, representation, malpractice conclusion or eligibility decision. Authorized counsel must decide and document it."}); return result

def _tech(method:str,data:dict)->dict:
    result=_base(method,data); corpus=data.get("documents",[]); protocol=data.get("protocol",{})
    if not corpus or not protocol: raise ValueError("documents and protocol are required")
    labels=protocol.get("labels",[]); reviewed=[]
    for doc in corpus:
        assigned=[x for x in doc.get("labels",[]) if x in labels]
        reviewed.append({"document_id":doc.get("id"),"sha256":doc.get("sha256"),"custodian":doc.get("custodian"),"collected_at":doc.get("collected_at"),"labels":assigned,"confidence":doc.get("confidence"),"privilege_candidate":bool(doc.get("privilege_candidate")),"human_review_status":"pending"})
    metrics=data.get("validation_set",{})
    tp,fp,fn=(int(metrics.get(x,0)) for x in ("true_positive","false_positive","false_negative"))
    precision=tp/(tp+fp) if tp+fp else None; recall=tp/(tp+fn) if tp+fn else None
    result.update({"protocol":protocol,"documents":reviewed,"validation":{"precision":precision,"recall":recall,"sample_size":tp+fp+fn},"chain_of_custody":data.get("chain_of_custody",[]),"exceptions":data.get("exceptions",[]),"boundary":"Decision support only. Preserve originals and metadata. Counsel approves scope, holds, collection, search, sampling, responsiveness and privilege calls. Analytics are not outcome predictions; no document is produced or deleted."}); return result

def _ops(method:str,data:dict)->dict:
    result=_base(method,data); matters=data.get("matters",[]); controls=data.get("controls",[])
    if not matters: raise ValueError("matters are required")
    rows=[]
    for m in matters:
        budget=m.get("budget"); actual=sum(float(e.get("amount",0)) for e in m.get("entries",[])); rows.append({"matter_id":m.get("id"),"owner":m.get("owner"),"phase":m.get("phase"),"budget":budget,"actual":actual,"variance":(float(budget)-actual) if budget is not None else None,"milestones":m.get("milestones",[]),"knowledge_refs":m.get("knowledge_refs",[]),"billing_review_status":"pending"})
    result.update({"matter_summary":rows,"controls":controls,"fee_terms":data.get("fee_terms",[]),"curriculum_or_playbooks":data.get("curriculum_or_playbooks",[]),"access_policy":data.get("access_policy",{}),"boundary":"Planning and reporting only. Authorized humans approve staffing, fees, invoices, write-offs, client changes, retention, access, education credentials and operational changes."}); return result

def legal_support(method:str,data:dict[str,Any])->dict[str,Any]:
    if method not in LEGAL_METHODS: raise ValueError("unsupported legal support method")
    if method in DOCTRINE:return _doctrine(method,data)
    if method in DISPUTE:return _dispute(method,data)
    if method in ETHICS:return _ethics(method,data)
    if method in TECH:return _tech(method,data)
    return _ops(method,data)
