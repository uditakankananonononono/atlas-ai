"""Source-grounded legal workbench for additional-feature rows 1210-1259.

This module prepares structured attorney work product.  It deliberately does not
claim attorney-client status, decide a person's rights, file papers, contact a
counterparty, or execute a transaction.  Every proposition remains traceable to
the supplied authority and every missing fact remains visible.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Callable
from urllib.parse import urlparse

DISCLAIMER = (
    "Attorney review required. This is source-grounded legal workbench output, not "
    "legal advice or a prediction of outcome. It does not file, sign, negotiate, "
    "contact a party, or create an attorney-client relationship."
)


def _profile(domain: str, artifact: str, workflow: list[str], questions: list[str],
             gates: list[str] | None = None) -> dict[str, Any]:
    return {"domain": domain, "artifact": artifact, "workflow": workflow,
            "questions": questions, "gates": gates or []}

# Every ledger row has its own domain workflow and review artifact.  Profiles are
# data, while the engines below implement drafting, authority analysis, controls,
# transactions, and contested-matter strategy with shared provenance guarantees.
PROFILES: dict[str, dict[str, Any]] = {
 "contract_drafting":_profile("contracts","clause-indexed draft",["identify parties, capacity and authority","map business terms to obligations","draft definitions, performance, remedies and boilerplate","cross-reference and consistency review"],["governing law and forum","consideration and effective date","signatory authority"]),
 "contract_review":_profile("contracts","risk-ranked clause review",["extract clauses and defined terms","compare obligations against stated playbook","identify conflicts, omissions and one-sided terms","propose redlines with rationale"],["client role and priorities","governing law","complete agreement and exhibits"]),
 "contract_negotiation":_profile("contracts","negotiation issue sheet",["separate positions, interests and constraints","set target, fallback and walk-away for each issue","prepare truthful rationale and trade packages","record open terms without implying agreement"],["negotiation authority","approved concessions","communications channel"],["human approval before any counterparty communication"]),
 "legal_research":_profile("research","research memorandum",["frame issue and jurisdiction","build primary-source search plan","validate authority and subsequent history","synthesize rule, application and uncertainty"],["jurisdiction and court level","as-of date","material facts"]),
 "case_law_analysis":_profile("research","case synthesis table",["extract posture, issue, holding and disposition","separate holding from dicta","compare legally material facts","check treatment and subsequent history"],["controlling court hierarchy","procedural posture","negative treatment"]),
 "statutory_interpretation":_profile("research","interpretation memorandum",["preserve exact enacted text","analyze definitions, syntax and whole-act context","check amendments, effective date and implementing rules","present competing readings and consequences"],["version in force","cross-references and exceptions","binding interpretive authority"]),
 "regulatory_compliance":_profile("compliance","obligation-control matrix",["inventory applicable obligations","map each obligation to owner, evidence and cadence","test control design and evidence gaps","create remediation queue"],["regulated entity and activity","jurisdictions","effective dates"]),
 "legal_risk_assessment":_profile("compliance","legal risk register",["state risk scenario without inventing probability","link facts to authority and elements","score impact and evidence quality separately","identify mitigations and decision owner"],["risk appetite","privilege handling","known disputes"]),
 "due_diligence":_profile("transaction","diligence exception report",["define scope and data-room index","verify documents and ownership","flag missing, inconsistent and expired items","route exceptions to specialist review"],["transaction scope","cutoff date","reliance and materiality thresholds"]),
 "mergers_acquisitions":_profile("transaction","M&A issue and closing tracker",["capture structure, parties and consideration","map approvals, consents and regulatory conditions","track diligence findings into deal protections","build signing and closing dependency list"],["deal structure","antitrust and foreign-investment exposure","board and shareholder authority"],["human approval for signing, filing, payment or communication"]),
 "corporate_governance":_profile("corporate","governance action matrix",["inventory governing documents and entity law","map reserved powers and fiduciary process","verify notice, quorum, vote and conflicts","prepare approval record and follow-up obligations"],["entity type and domicile","cap table and voting rights","conflicts and recusals"]),
 "securities_law":_profile("corporate","offering/disclosure issue matrix",["classify instrument and transaction","identify registration or exemption path","map disclosure and anti-fraud duties","track filings, legends and transfer restrictions"],["issuer and investor status","offer locations and manner","use of proceeds and conflicts"],["securities counsel approval before offer or filing"]),
 "intellectual_property":_profile("ip","IP asset and rights matrix",["identify asset, creator and chain of title","classify protectable subject matter","check registrations, licenses and encumbrances","prioritize protection and clearance steps"],["territories","creation and employment history","public disclosure dates"]),
 "patent_drafting":_profile("ip","invention disclosure and claim map",["capture inventors and conception evidence","describe embodiments and alternatives","map support for each proposed claim element","flag enablement, definiteness and prior-art questions"],["inventorship","priority and disclosure dates","known prior art"],["registered patent practitioner review before filing"]),
 "patent_prosecution":_profile("ip","office-action response matrix",["parse every rejection and objection","map cited art to claim limitations","develop amendment and argument alternatives","check support, estoppel and deadline consequences"],["official action and deadline","complete file history","claim strategy"],["patent practitioner approval before submission"]),
 "trademark_registration":_profile("ip","clearance and filing worksheet",["normalize mark and goods/services","search confusingly similar marks by class and channel","assess distinctiveness and use basis","prepare owner, specimen and filing checklist"],["owner identity","territory and filing basis","first-use evidence"],["trademark counsel approval before filing"]),
 "copyright_analysis":_profile("ip","copyright ownership/use analysis",["identify work and protectable expression","trace authorship, employment and assignments","map proposed uses to exclusive rights and exceptions","record registration and license evidence"],["work version and authors","publication facts","license scope"]),
 "trade_secret_protection":_profile("ip","trade-secret safeguards register",["define information with particularity","document independent economic value","evaluate reasonable secrecy measures","map access, disclosure and exit controls"],["authorized access","public disclosures","jurisdictional definition"]),
 "licensing_agreements":_profile("ip","license term sheet and clause map",["identify licensed rights and exclusions","define field, territory, term and sublicensing","model consideration, reporting and audit terms","map warranties, indemnities, termination and transition"],["chain of title","exclusivity and retained rights","third-party restrictions"]),
 "technology_transfer":_profile("ip","technology-transfer readiness plan",["inventory IP, know-how, materials and data","confirm ownership and sponsor obligations","select transfer vehicle and diligence needs","map export, privacy, publication and benefit-sharing constraints"],["institution policies","funding and sponsor terms","recipient and destination"]),
 "employment_law":_profile("employment","employment-law issue matrix",["classify worker and employing entities","build chronology from records","map facts to jurisdiction-specific duties","separate legal, HR and evidence actions"],["work location and employer size","worker status","policies and agreements"]),
 "labor_relations":_profile("employment","labor-relations obligations tracker",["identify bargaining unit and representatives","map contract, statutory and past-practice obligations","classify mandatory bargaining issues","track notices, meetings, grievances and deadlines"],["CBA and recognition scope","affected employees","protected concerted activity"]),
 "discrimination_analysis":_profile("employment","elements and comparator analysis",["preserve chronology and decision records","identify protected basis and legal theory","compare similarly situated evidence without inferring identity","test legitimate reasons, consistency and pretext evidence"],["jurisdiction and limitations period","decision makers","comparators and accommodations"]),
 "harassment_investigation":_profile("employment","neutral investigation plan",["define allegations without prejudging credibility","preserve evidence and anti-retaliation safeguards","sequence trauma-informed interviews","corroborate, document credibility factors and apply stated standard"],["investigator independence","applicable policy and standard","support and interim safety measures"]),
 "wrongful_termination":_profile("employment","termination-claim assessment",["build employment and termination chronology","identify contract, statutory and public-policy theories","test documented reason and consistency","calculate deadlines without asserting entitlement"],["termination date and location","agreements and policies","administrative exhaustion"]),
 "employment_contracts":_profile("employment","employment agreement draft/review",["identify employer, worker and classification","define role, compensation and benefits precisely","map confidentiality, IP and post-employment terms","check mandatory-law and policy consistency"],["work jurisdictions","compensation approvals","existing obligations"]),
 "non_compete_agreements":_profile("employment","restrictive-covenant enforceability matrix",["parse activity, geography, duration and consideration","identify statutory bans and exceptions","assess protectable interest and tailoring","separate noncompete, nonsolicit and confidentiality terms"],["worker location at signing and enforcement","effective-date law","sale-of-business exception"]),
 "immigration_law":_profile("immigration","immigration options and evidence matrix",["record nationality, status and complete chronology","identify possible classifications without promising eligibility","map each element to evidence and authority","flag deadlines, inadmissibility and licensed-counsel questions"],["current location and status","entry and filing history","family, employment and protection facts"]),
 "visa_applications":_profile("immigration","visa petition/application checklist",["select jurisdiction and visa classification","map eligibility elements to authentic evidence","check consistency across forms and history","track filing, biometrics, interview and validity dates"],["passport and nationality","prior refusals and status violations","sponsor and travel purpose"],["human review before filing; never fabricate evidence"]),
 "asylum_cases":_profile("immigration","asylum claim and corroboration map",["use trauma-informed, non-leading chronology","map protected ground, nexus, persecution and state protection","separate testimony, corroboration and country evidence","flag filing deadline, bars and immediate safety needs"],["safe communication and interpreter needs","filing deadline","confidentiality and licensed representation"]),
 "refugee_law":_profile("immigration","refugee protection analysis",["identify governing protection framework","map well-founded fear and protected ground","assess exclusion, cessation and non-refoulement separately","source current country and procedural evidence"],["jurisdiction and procedure","status and route","family unity and vulnerability"]),
 "family_law":_profile("family","family-law issue and safety plan",["identify relationships, orders and proceedings","prioritize safety, coercion and child welfare","map property, support and parenting issues","track disclosures, service and hearing dates"],["jurisdiction and residency","existing orders","immediate safety risk"]),
 "divorce_proceedings":_profile("family","divorce case checklist",["confirm jurisdiction and grounds","inventory assets, debts, income and separate-property claims","map support and parenting issues","track disclosure, service, settlement and hearing steps"],["marriage/separation dates","residency","prenup and current orders"]),
 "child_custody":_profile("family","best-interests evidence matrix",["identify jurisdiction and existing orders","center child safety, stability and development","map statutory best-interest factors to admissible facts","avoid diagnoses, coaching or unsupported parental labels"],["child residence history","safety concerns and protective orders","decision-making and parenting schedule"]),
 "adoption":_profile("family","adoption eligibility and consent checklist",["identify adoption type and jurisdictions","verify consents, relinquishments and representation","map home-study, background and placement requirements","track ICWA/indigenous, immigration and post-placement issues where applicable"],["child status and ancestry inquiries","parental rights","agency/court requirements"]),
 "estate_planning":_profile("estates","estate-planning design worksheet",["inventory family, assets, ownership and beneficiaries","capture goals, incapacity and tax questions","map documents and fiduciary roles","check coordination with beneficiary designations and entity documents"],["domicile","capacity and undue influence safeguards","asset titles and beneficiary forms"]),
 "wills_and_trusts":_profile("estates","will/trust drafting checklist",["confirm dispositive instructions in client's own words","map gifts, residuary, fiduciaries and contingencies","check execution formalities and trust funding","flag tax, creditor, family and capacity issues"],["domicile and governing law","family tree and omitted-heir risks","witness/notary rules"],["lawyer-supervised execution where required"]),
 "probate":_profile("estates","probate administration tracker",["verify death, domicile and original instruments","identify fiduciary authority and interested persons","calendar notice, inventory, claim and tax deadlines","track assets, claims, accountings and distributions"],["court and procedure","will status","estate assets and liabilities"]),
 "real_estate_law":_profile("property","real-estate legal issue matrix",["identify property, parties and interests","review title, survey, leases and restrictions","map land-use, environmental and finance issues","track recording, possession and post-closing duties"],["legal description and jurisdiction","title evidence","current occupancy"]),
 "property_transactions":_profile("property","property closing checklist",["verify parties, authority and property description","track diligence, title objections and contingencies","reconcile closing deliverables and funds","confirm recording, keys and survival obligations"],["purchase agreement version","title/escrow contacts","financing and tax adjustments"],["human approval for signing, funds and recording"]),
 "landlord_tenant":_profile("property","tenancy rights/obligations timeline",["identify tenancy, unit and governing regime","build notice, payment, repair and communication chronology","map habitability, access, deposit and termination rules","flag anti-retaliation, eviction-process and emergency issues"],["property location","lease and notices","subsidy or rent-control status"]),
 "zoning_and_land_use":_profile("property","entitlement pathway matrix",["identify parcel, zoning map and proposed use","check permitted/conditional use and dimensional standards","map variances, hearings, environmental review and appeals","track agency findings, conditions and deadlines"],["authoritative parcel data","project description","overlay districts and prior approvals"]),
 "environmental_law":_profile("environment","environmental obligations matrix",["identify facility/activity and media","map permits, standards, reporting and liability regimes","trace ownership/operator history and releases","separate compliance, remediation and disclosure duties"],["locations and operational dates","permits and sampling data","agency correspondence"]),
 "climate_regulation":_profile("environment","climate-regulation applicability map",["inventory entities, facilities and emissions boundaries","identify disclosure, cap, tax and performance regimes","map calculation methods, assurance and deadlines","track transition-plan claims and greenwashing controls"],["reporting perimeter","jurisdictions and thresholds","verified emissions data"]),
 "pollution_control":_profile("environment","pollution control compliance plan",["identify pollutant, source, pathway and receptor","compare permits and standards to measured data","map monitoring, reporting and corrective actions","preserve exceedance and incident chronology"],["validated sampling methods","permit limits","release notifications"]),
 "natural_resources":_profile("environment","natural-resource rights/permit matrix",["identify resource, land status and claimed rights","map permits, concessions, royalties and use limits","check indigenous/community consultation and biodiversity duties","track reclamation, bonding and closure obligations"],["location and tenure","resource and project phase","treaty/indigenous rights"]),
 "energy_law":_profile("environment","energy regulatory pathway",["classify generation, network, sale and customer activity","map licenses, tariffs and market rules","identify siting, interconnection and environmental approvals","track reliability, consumer and decommissioning duties"],["technology and capacity","market/jurisdictions","site and grid connection"]),
 "criminal_law":_profile("criminal","offense/defense elements matrix",["preserve exact charge and procedural posture","map each element to admissible evidence and authority","identify defenses, burdens and suppression issues","calendar custody, limitation and court deadlines"],["jurisdiction and charging instrument","custody and counsel status","complete discovery"]),
 "criminal_defense":_profile("criminal","defense case theory and motion tracker",["protect privilege and client safety","test prosecution proof element by element","investigate lawful defenses and impeachment evidence","map bail, discovery, suppression, plea and trial decisions"],["client's informed objectives","custody and deadlines","conflicts and discovery completeness"],["licensed defense counsel controls strategy and filings"]),
 "prosecution_strategy":_profile("criminal","ethical prosecution review",["assess admissible evidence for each element","document charging standard and proportionality","identify exculpatory/impeachment disclosure duties","test witness reliability, alternatives and collateral consequences"],["lawful authority and venue","disclosure status","victim and witness safety"],["prosecutor approval; never suppress exculpatory evidence or pursue unsupported charges"]),
}


def _authority(raw: dict[str, Any], index: int) -> dict[str, Any]:
    url=str(raw.get("url", "")).strip(); parsed=urlparse(url)
    valid=parsed.scheme in {"http","https"} and bool(parsed.netloc)
    return {"id":str(raw.get("id") or f"A{index}"), "title":str(raw.get("title", "")).strip(),
            "url":url, "jurisdiction":str(raw.get("jurisdiction", "")).strip(),
            "court_or_issuer":str(raw.get("court_or_issuer", "")).strip(),
            "citation":str(raw.get("citation", "")).strip(), "as_of":raw.get("as_of"),
            "authority_type":str(raw.get("authority_type", "unknown")),
            "treatment":str(raw.get("treatment", "unverified")), "url_valid":valid,
            "verified":bool(valid and raw.get("title") and raw.get("jurisdiction") and raw.get("as_of"))}


def _issue(issue: dict[str, Any], authority_ids: set[str]) -> dict[str, Any]:
    supporting=[str(x) for x in issue.get("supporting_authority_ids", [])]
    contrary=[str(x) for x in issue.get("contrary_authority_ids", [])]
    missing=[x for x in supporting+contrary if x not in authority_ids]
    facts=[str(x) for x in issue.get("facts", []) if str(x).strip()]
    unknowns=[str(x) for x in issue.get("unknowns", []) if str(x).strip()]
    return {"issue":str(issue.get("issue", "Unspecified issue")), "rule":issue.get("rule"),
            "facts":facts, "unknowns":unknowns, "supporting_authority_ids":supporting,
            "contrary_authority_ids":contrary, "missing_authority_ids":missing,
            "analysis":issue.get("analysis"),
            "confidence":"blocked" if missing or not supporting else ("limited" if unknowns else "supported")}


def _clauses(data: dict[str, Any]) -> list[dict[str, Any]]:
    out=[]
    for i, c in enumerate(data.get("clauses", []), 1):
        text=str(c.get("text", "")).strip(); fallback=str(c.get("fallback", "")).strip()
        out.append({"id":str(c.get("id") or f"C{i}"), "heading":str(c.get("heading", "Untitled")),
                    "text":text, "business_purpose":c.get("business_purpose"),
                    "fallback":fallback or None, "defined_terms":c.get("defined_terms", []),
                    "review_flags":(["missing clause text"] if not text else [])+(["undefined placeholder"] if "[" in text else [])})
    return out


def _controls(data: dict[str, Any], authorities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ids={a["id"] for a in authorities}; out=[]
    for row in data.get("obligations", []):
        aid=[str(x) for x in row.get("authority_ids", [])]
        evidence=[str(x) for x in row.get("evidence", []) if str(x).strip()]
        owner=row.get("owner")
        gaps=[]
        if not aid or any(x not in ids for x in aid): gaps.append("authority not linked")
        if not owner: gaps.append("control owner missing")
        if not evidence: gaps.append("operating evidence missing")
        out.append({"obligation":row.get("obligation"),"authority_ids":aid,"owner":owner,
                    "control":row.get("control"),"evidence":evidence,"cadence":row.get("cadence"),
                    "status":"gap" if gaps else "evidenced","gaps":gaps})
    return out


def _deadlines(data: dict[str, Any]) -> list[dict[str, Any]]:
    out=[]
    for d in data.get("deadlines", []):
        out.append({"name":d.get("name"),"date":d.get("date"),"source_authority_id":d.get("source_authority_id"),
                    "calculation":d.get("calculation"),"verified_by_human":bool(d.get("verified_by_human")),
                    "status":"verified" if d.get("verified_by_human") else "human verification required"})
    return out


def legal_support(method: str, data: dict[str, Any]) -> dict[str, Any]:
    """Build auditable legal work product for one exact ledger capability."""
    if method not in PROFILES:
        raise ValueError(f"unsupported legal method: {method}")
    p=PROFILES[method]
    tenant_id=str(data.get("tenant_id","default")).strip()
    if not tenant_id: raise ValueError("tenant_id must not be empty")
    for ref in data.get("resource_refs",[]):
        if str(ref.get("tenant_id","")).strip()!=tenant_id:
            raise ValueError("cross-tenant resource reference rejected")
    authorities=[_authority(a,i) for i,a in enumerate(data.get("authorities", []),1)]
    authority_ids={a["id"] for a in authorities}
    issues=[_issue(x,authority_ids) for x in data.get("issues", [])]
    missing_inputs=[q for q in p["questions"] if q not in data.get("confirmed_inputs", [])]
    facts=[str(x) for x in data.get("facts", []) if str(x).strip()]
    unknowns=[str(x) for x in data.get("unknowns", []) if str(x).strip()]
    result: dict[str, Any]={
        "tenant_id":tenant_id,"method":method,"domain":p["domain"],"artifact":p["artifact"],
        "matter_name":data.get("matter_name"),"jurisdiction":data.get("jurisdiction"),
        "as_of":data.get("as_of") or date.today().isoformat(),"client_role":data.get("client_role"),
        "facts":facts,"unknowns":unknowns,"workflow":p["workflow"],
        "intake_questions":p["questions"],"missing_confirmed_inputs":missing_inputs,
        "authorities":authorities,"issues":issues,"deadlines":_deadlines(data),
        "source_quality":{"total":len(authorities),"verified":sum(a["verified"] for a in authorities),
                          "unverified_ids":[a["id"] for a in authorities if not a["verified"]]},
        "approval_gates":p["gates"],"privilege_label":data.get("privilege_label","not_assessed"),
        "disclaimer":DISCLAIMER,
    }
    if p["domain"]=="contracts" or method in {"employment_contracts","non_compete_agreements","licensing_agreements","wills_and_trusts"}:
        result["clauses"]=_clauses(data)
        result["defined_terms"]=data.get("defined_terms",{})
        result["execution_blocked"]=True
    if p["domain"] in {"compliance","corporate","environment"}:
        result["obligation_control_matrix"]=_controls(data,authorities)
    if p["domain"] in {"transaction","property"} or method in {"due_diligence","mergers_acquisitions","technology_transfer","probate"}:
        result["checklist"]=[{"item":x.get("item"),"owner":x.get("owner"),"status":x.get("status","open"),
                              "dependency_ids":x.get("dependency_ids",[]),"evidence":x.get("evidence",[])}
                             for x in data.get("checklist",[])]
        result["execution_blocked"]=True
    if p["domain"] in {"research","criminal","immigration","family","employment"}:
        result["chronology"]=sorted(data.get("chronology",[]),key=lambda x:str(x.get("date","")))
        result["evidence_matrix"]=[{"proposition":x.get("proposition"),"support":x.get("support",[]),
                                    "contrary":x.get("contrary",[]),"admissibility":x.get("admissibility","not assessed")}
                                   for x in data.get("evidence_matrix",[])]
    if method in {"contract_negotiation","criminal_defense","prosecution_strategy","patent_prosecution"}:
        result["strategy_options"]=[{"option":x.get("option"),"benefits":x.get("benefits",[]),
                                     "risks":x.get("risks",[]),"authority_ids":x.get("authority_ids",[]),
                                     "requires_approval":True} for x in data.get("strategy_options",[])]
    blockers=[]
    if not data.get("jurisdiction"): blockers.append("jurisdiction not confirmed")
    if not authorities: blockers.append("no legal authorities supplied")
    if any(not a["verified"] for a in authorities): blockers.append("one or more authorities lack provenance fields")
    if unknowns: blockers.append("material facts remain unknown")
    blockers.extend(str(x) for x in data.get("blockers",[]))
    proposition_count=len(issues)
    supported=sum(x["confidence"]=="supported" for x in issues)
    result["evaluation"]={"authority_verification_rate":round(sum(a["verified"] for a in authorities)/max(1,len(authorities)),3),
                          "issue_support_rate":round(supported/max(1,proposition_count),3),
                          "unknown_fact_count":len(unknowns),"uncertainty_status":"material_gaps" if unknowns or any(not a["verified"] for a in authorities) else "bounded"}
    result["review"]={"status":"blocked" if blockers else "ready_for_attorney_review",
                      "blockers":list(dict.fromkeys(blockers)),
                      "can_file_or_send":False,"can_sign_or_pay":False,
                      "required_reviewer":data.get("required_reviewer","licensed lawyer in the relevant jurisdiction")}
    return result

# Practitioner-depth envelope for rows 1210-1259. It measures source and input
# coverage; it never predicts a legal outcome or authorizes filing/contact.
_original_legal_support = legal_support
from app.core.depth_quality import attach_quality as _attach_quality

def legal_support(method:str, data:dict[str,Any])->dict[str,Any]:
    out=_original_legal_support(method,data)
    evidence=[x for key in ('authorities','sources','evidence') for x in data.get(key,[]) if isinstance(x,dict)]
    required=['jurisdiction'] + [k for k in ('facts','document','issues','transaction','parties') if k in data]
    return _attach_quality(out,domain='legal',method=method,inputs=data,
        required_inputs=required,evidence=evidence,assumptions=data.get('assumptions',[]),
        limitations=['Draft research work product only; no filing, signature, negotiation, contact, or legal advice.',
                     'Counsel must verify current law, jurisdiction, deadlines, privilege, conflicts, and facts.'])
