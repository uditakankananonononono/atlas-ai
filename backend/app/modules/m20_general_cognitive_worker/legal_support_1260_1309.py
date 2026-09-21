"""Tenant-neutral, source-grounded legal analysis for owner rows 1260-1309.

Each ledger row has a distinct analysis specification and result key. The engine only
organizes supplied material for counsel: it never reaches a legal conclusion, files,
serves, contacts anyone, changes a matter, or treats a user assertion as evidence.
"""
from __future__ import annotations

from datetime import date
from typing import Any
from urllib.parse import urlparse

DISCLAIMER = "Legal-support analysis for licensed-counsel review; not legal advice, a legal conclusion, a filing, or authority to act."

# (feature id, method, output key, row-specific mechanism)
_SPECS = [
(1260,"sentencing_guidelines","guideline_calculation_map","map guideline edition, offense characteristics, adjustments and departures without computing a sentence"),
(1261,"criminal_appeals","appeal_preservation_map","map orders, preservation, review standards, record cites and remedy limits"),
(1262,"constitutional_law","constitutional_scrutiny_map","map state action, right, scrutiny level, governmental interest and tailoring"),
(1263,"first_amendment","speech_forum_map","classify speech, speaker, forum, restriction and scrutiny without deciding constitutionality"),
(1264,"fourth_amendment","search_seizure_map","map government conduct, standing, warrant, exception, scope and suppression questions"),
(1265,"due_process","process_entitlement_map","map protected interest, deprivation, notice, hearing and balancing factors"),
(1266,"equal_protection","classification_scrutiny_map","map classification, comparator, intent, scrutiny and fit"),
(1267,"administrative_law","agency_authority_map","map statutory delegation, procedure, record, deference and remedy questions"),
(1268,"regulatory_practice","regulatory_obligation_map","map regulated activity to rule text, effective date, regulator and control evidence"),
(1269,"agency_proceedings","agency_record_map","map tribunal authority, pleadings, administrative record, hearing steps and exhaustion"),
(1270,"judicial_review","reviewability_map","map finality, standing, exhaustion, review standard and record boundaries"),
(1271,"international_law","international_source_map","separate treaty, custom, domestic implementation, forum and actor obligations"),
(1272,"treaties","treaty_status_map","map signature, ratification, reservations, entry into force and domestic effect"),
(1273,"human_rights","rights_obligation_map","map right, duty bearer, derogation, exhaustion, remedy and monitoring source"),
(1274,"international_trade","trade_measure_map","map product, measure, schedule, exception, forum and retaliation constraints"),
(1275,"arbitration","arbitration_clause_map","map consent, seat, rules, scope, arbitrability, tribunal and award-review issues"),
(1276,"mediation","mediation_preparation_map","separate interests, positions, authority, confidentiality and nonbinding options"),
(1277,"dispute_resolution","forum_options_map","compare forum, process, cost inputs, enforceability and approval gates"),
(1278,"litigation_strategy","litigation_option_map","map objectives, claims, defenses, proof, procedural options and decision gates"),
(1279,"discovery","discovery_scope_map","map request, relevance basis, proportionality, custody, objection and response approval"),
(1280,"depositions","deposition_record_map","map witness topics, exhibits, record support, privilege flags and noncoaching boundaries"),
(1281,"trial_preparation","trial_readiness_map","map elements, witnesses, exhibits, motions, stipulations and unresolved proof gaps"),
(1282,"evidence_analysis","admissibility_issue_map","map item provenance, purpose, relevance, foundation, exclusion and objection issues"),
(1283,"witness_preparation","witness_source_map","separate firsthand recollection, documents, uncertainty and prohibited coaching"),
(1284,"jury_selection","voir_dire_issue_map","map case-neutral topics, cause grounds and equal-protection review without profiling"),
(1285,"appellate_practice","appellate_issue_map","map appealability, preservation, record cites, review standard and requested relief"),
(1286,"legal_writing","legal_document_structure","structure question, short answer alternatives, facts, sourced rules and analysis gaps"),
(1287,"legal_citations","citation_validation_map","validate supplied citation components, pinpoints, links, court and currency"),
(1288,"brief_writing","brief_argument_map","map record proposition, authority, counterauthority, analysis and requested relief"),
(1289,"oral_argument","oral_argument_question_map","map likely questions to record cites, authorities, concessions and unknowns"),
(1290,"legal_ethics","ethics_duty_map","map actor, role, duty, rule source, facts and required ethics review"),
(1291,"professional_responsibility","responsibility_obligation_map","map competence, diligence, candor, supervision and communication issues"),
(1292,"conflicts_of_interest","conflict_relationship_map","map clients, former clients, adverse parties, matters and consent questions"),
(1293,"attorney_client_privilege","privilege_element_map","map communication, participants, purpose, confidentiality, waiver and exceptions"),
(1294,"legal_malpractice","malpractice_element_map","map duty, standard evidence, breach allegation, causation and damages assertions"),
(1295,"pro_bono_practice","pro_bono_matter_map","map scope, eligibility source, competence, capacity and engagement approval"),
(1296,"legal_aid","legal_aid_eligibility_map","map provider criteria, applicant assertions, documents, conflicts and referral status"),
(1297,"access_to_justice","justice_barrier_map","map language, disability, cost, geography, procedure and service-resource evidence"),
(1298,"legal_technology","legal_technology_control_map","map use case, data flow, vendor evidence, access, retention and human review"),
(1299,"e_discovery","ediscovery_custody_map","map hold scope, custodians, sources, collection provenance, processing and production gates"),
(1300,"legal_analytics","analytics_validation_map","map dataset provenance, target, metric, bias limits and nonpredictive use"),
(1301,"predictive_coding","coding_validation_map","map protocol, seed decisions, sampling metrics, drift and pending human review"),
(1302,"document_review","document_review_map","map document hash, custodian, issue labels, responsiveness and privilege candidates"),
(1303,"legal_operations","matter_operations_map","map matter owner, phase, milestones, budget inputs, controls and approvals"),
(1304,"law_firm_management","firm_management_map","map staffing, capacity, supervision, access and approval-controlled changes"),
(1305,"legal_billing","billing_review_map","map time entry, rate source, fee term, variance and invoice approval status"),
(1306,"alternative_fee_arrangements","fee_arrangement_map","map scope, fee formula, assumptions, triggers, exclusions and approval"),
(1307,"legal_project_management","legal_project_map","map deliverables, owners, dependencies, milestones, risks and decision gates"),
(1308,"knowledge_management","legal_knowledge_map","map artifact provenance, jurisdiction, currency, access and supersession"),
(1309,"legal_education","legal_learning_map","map audience, learning objective, source authority, exercise and assessment limits"),
]
SPECS = {fid:{"method":m,"output_key":k,"mechanism":z} for fid,m,k,z in _SPECS}
METHOD_TO_ID = {v["method"]:k for k,v in SPECS.items()}


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _authority(raw: dict[str, Any], expected_jurisdiction: str) -> dict[str, Any]:
    if not isinstance(raw, dict): raise ValueError("each authority must be an object")
    required=("id","title","citation","source_url","jurisdiction","effective_date","last_checked_at","authority_type")
    missing=[k for k in required if not isinstance(raw.get(k),str) or not raw[k].strip()]
    if missing: raise ValueError("authority missing provenance: "+", ".join(missing))
    try:
        effective=date.fromisoformat(raw["effective_date"]); checked=date.fromisoformat(raw["last_checked_at"])
    except ValueError as exc: raise ValueError("authority dates must be ISO dates") from exc
    parsed=urlparse(raw["source_url"])
    if parsed.scheme not in {"http","https"} or not parsed.netloc: raise ValueError("authority source_url must be http(s)")
    return {k:raw.get(k) for k in required}|{
        "pinpoint":raw.get("pinpoint"),"issuer":raw.get("issuer"),"treatment":raw.get("treatment","unverified"),
        "contrary":bool(raw.get("contrary")),"jurisdiction_match":raw["jurisdiction"]==expected_jurisdiction,
        "stale":(date.fromisoformat(raw.get("valid_through",raw["effective_date"])) < checked),
        "provenance_complete":True,
    }


def analyze_legal_feature(feature_id: int, data: dict[str, Any], *, tenant_id: str, actor_id: str) -> dict[str, Any]:
    """Produce the row-specific review artifact from supplied data only."""
    if feature_id not in SPECS: raise ValueError("feature_id must be between 1260 and 1309")
    if not isinstance(data,dict): raise ValueError("data must be an object")
    tenant=_text(tenant_id,"tenant_id"); actor=_text(actor_id,"actor_id")
    payload_tenant=data.get("tenant_id")
    if payload_tenant is not None and payload_tenant != tenant: raise ValueError("cross-tenant payload rejected")
    jurisdiction=_text(data.get("jurisdiction"),"jurisdiction")
    as_of_text=_text(data.get("as_of"),"as_of")
    try: as_of=date.fromisoformat(as_of_text)
    except ValueError as exc: raise ValueError("as_of must be an ISO date") from exc
    authorities=[_authority(x,jurisdiction) for x in data.get("authorities",[])]
    if not authorities: raise ValueError("at least one provenance-complete authority is required")
    authority_ids={a["id"] for a in authorities}
    user_assertions=[_text(x,"user_assertion") for x in data.get("user_assertions",[])]
    sourced_facts=[]
    for fact in data.get("sourced_facts",[]):
        if not isinstance(fact,dict): raise ValueError("each sourced fact must be an object")
        text=_text(fact.get("text"),"sourced fact text"); refs=fact.get("source_ids",[])
        if not isinstance(refs,list) or not refs: raise ValueError("sourced fact requires source_ids")
        unknown=[x for x in refs if x not in authority_ids]
        sourced_facts.append({"text":text,"source_ids":refs,"missing_source_ids":unknown,"status":"unsupported" if unknown else "sourced"})
    analysis=[]
    for item in data.get("analysis",[]):
        if not isinstance(item,dict): raise ValueError("each analysis item must be an object")
        proposition=_text(item.get("proposition"),"analysis proposition")
        refs=item.get("authority_ids",[]); unknown=[x for x in refs if x not in authority_ids]
        analysis.append({"proposition":proposition,"authority_ids":refs,"counteranalysis":item.get("counteranalysis"),
                         "missing_authority_ids":unknown,"status":"needs_authority" if not refs or unknown else "for_counsel_review"})
    conflicts=[{"authority_id":a["id"],"reason":"contrary authority supplied"} for a in authorities if a["contrary"]]
    conflicts += [{"authority_id":a["id"],"reason":"jurisdiction mismatch"} for a in authorities if not a["jurisdiction_match"]]
    stale=[a["id"] for a in authorities if a["stale"] or date.fromisoformat(a["last_checked_at"]) < as_of]
    missing=[x["proposition"] for x in analysis if x["status"]=="needs_authority"]
    spec=SPECS[feature_id]
    artifact={
        "mechanism":spec["mechanism"],"inputs":data.get("row_inputs",{}),"sourced_facts":sourced_facts,
        "user_assertions":user_assertions,"analysis":analysis,"unknowns":data.get("unknowns",[]),
        "conflicts":conflicts,"missing_authority":missing,"stale_source_ids":stale,
        "review_state":"blocked" if conflicts or missing or stale or any(x["status"]=="unsupported" for x in sourced_facts) else "counsel_review_required",
    }
    return {"feature_id":feature_id,"method":spec["method"],"jurisdiction":jurisdiction,"as_of":as_of_text,
            "provenance":{"authority_count":len(authorities),"authorities":authorities},spec["output_key"]:artifact,
            "isolation":{"tenant_id":tenant,"actor_id":actor,"cross_tenant_data":False},
            "legal_conclusion":None,"filing_or_external_effect":False,"requires_licensed_counsel":True,"disclaimer":DISCLAIMER}
