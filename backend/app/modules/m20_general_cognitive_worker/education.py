"""Evidence-preserving education design and learning analytics (audit rows 1410-1459).

The engine is deterministic and side-effect free.  It produces reviewable plans rather
than enrolling learners, grading them, or making high-stakes decisions.  Learner data
is deliberately pseudonymous and affect signals are never treated as facts.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import prod
import math
import re
from typing import Any

class EducationError(ValueError):
    """Invalid or unsafe education request."""

@dataclass(frozen=True)
class Capability:
    row_id: int
    name: str
    family: str
    stages: tuple[str, ...]
    evidence: tuple[str, ...]

_CAPABILITY_ROWS = {
1410:"Curriculum Design",1411:"Learning Objective Writing",1412:"Assessment Design",1413:"Rubric Creation",1414:"Lesson Planning",1415:"Unit Planning",1416:"Course Design",1417:"Syllabus Creation",1418:"Instructional Design",1419:"ADDIE Model",1420:"SAM Model",1421:"Backward Design",1422:"Universal Design for Learning",1423:"Differentiated Instruction",1424:"Personalized Learning",1425:"Adaptive Learning",1426:"Intelligent Tutoring",1427:"Scaffolding",1428:"Zone of Proximal Development",1429:"Cognitive Apprenticeship",1430:"Situated Learning",1431:"Anchored Instruction",1432:"Problem-Based Learning",1433:"Project-Based Learning",1434:"Inquiry-Based Learning",1435:"Discovery Learning",1436:"Experiential Learning",1437:"Service Learning",1438:"Cooperative Learning",1439:"Collaborative Learning",1440:"Peer Instruction",1441:"Flipped Classroom",1442:"Blended Learning",1443:"Online Learning",1444:"Distance Education",1445:"MOOCs",1446:"Microlearning",1447:"Mobile Learning",1448:"Game-Based Learning",1449:"Gamification",1450:"Simulation-Based Learning",1451:"Virtual Reality Learning",1452:"Augmented Reality Learning",1453:"Mixed Reality Learning",1454:"Artificial Intelligence in Education",1455:"Learning Analytics",1456:"Educational Data Mining",1457:"Student Modeling",1458:"Knowledge Tracing",1459:"Affect Detection"}

def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")

NAME_TO_ROW={_slug(v):k for k,v in _CAPABILITY_ROWS.items()}

_STAGE_OVERRIDES = {
 "addie_model":("analyze","design","develop","implement","evaluate"),
 "sam_model":("savvy_start","iterative_design","iterative_development","evaluate"),
 "backward_design":("desired_results","acceptable_evidence","learning_experiences"),
 "cognitive_apprenticeship":("modeling","coaching","scaffolding","articulation","reflection","exploration"),
 "inquiry_based_learning":("question","investigate","analyze","explain","reflect"),
 "experiential_learning":("concrete_experience","reflective_observation","abstract_conceptualization","active_experimentation"),
 "problem_based_learning":("problem_launch","know_need_to_know","self_directed_inquiry","solution","debrief"),
 "project_based_learning":("driving_question","sustained_inquiry","critique_revision","public_product","reflection"),
 "peer_instruction":("individual_vote","peer_discussion","revote","explanation"),
 "flipped_classroom":("pre_class_acquisition","readiness_check","active_classwork","feedback"),
 "service_learning":("community_need","co_design","service","structured_reflection","reciprocity_review"),
 "simulation_based_learning":("prebrief","scenario","decision_points","debrief","transfer"),
}

_FAMILIES={
 **{_slug(_CAPABILITY_ROWS[i]):"design" for i in range(1410,1422)},
 **{_slug(_CAPABILITY_ROWS[i]):"inclusion" for i in range(1422,1430)},
 **{_slug(_CAPABILITY_ROWS[i]):"pedagogy" for i in range(1430,1441)},
 **{_slug(_CAPABILITY_ROWS[i]):"delivery" for i in range(1441,1448)},
 **{_slug(_CAPABILITY_ROWS[i]):"immersive" for i in range(1448,1454)},
 **{_slug(_CAPABILITY_ROWS[i]):"analytics" for i in range(1454,1460)},
}

_EVIDENCE={
 "design":("objective_assessment_alignment","prerequisite_progression","formative_feedback"),
 "inclusion":("learner_variability","accessible_alternatives","agency_and_support"),
 "pedagogy":("authentic_task","active_practice","reflection_and_transfer"),
 "delivery":("presence_and_access","interaction_cadence","continuity_plan"),
 "immersive":("learning_mechanic_alignment","safe_failure","debrief_and_transfer"),
 "analytics":("data_minimization","uncertainty","human_review"),
}

def capabilities() -> list[dict[str,Any]]:
    return [{"row_id":i,"key":_slug(n),"name":n,"family":_FAMILIES[_slug(n)]} for i,n in _CAPABILITY_ROWS.items()]

def _require(payload: dict[str,Any], key: str, typ: type) -> Any:
    value=payload.get(key)
    if not isinstance(value,typ) or (typ in (str,list,dict) and not value):
        raise EducationError(f"{key} must be a non-empty {typ.__name__}")
    return value

def _source(payload: dict[str,Any]) -> dict[str,str]:
    src=_require(payload,"source",dict)
    url=src.get("url") or src.get("source_url")
    title=src.get("title") or src.get("source_title")
    if not isinstance(url,str) or not url.startswith(("https://","http://")) or not title:
        raise EducationError("source requires title and http(s) url")
    return {"title":str(title),"url":url}

def _objective(item: Any, index:int) -> dict[str,Any]:
    if isinstance(item,str): item={"statement":item}
    if not isinstance(item,dict): raise EducationError(f"objectives[{index}] must be text or object")
    statement=str(item.get("statement") or item.get("text") or "").strip()
    if not statement: raise EducationError(f"objectives[{index}] is empty")
    verb=statement.split()[0].lower().strip(".,")
    vague={"know","understand","learn","appreciate","be","become","familiarize"}
    return {"id":str(item.get("id") or f"obj-{index+1}"),"statement":statement,
            "observable":verb not in vague,"verb":verb,
            "condition":item.get("condition"),"criterion":item.get("criterion")}

def _design(cap:Capability,p:dict[str,Any]) -> dict[str,Any]:
    topic=_require(p,"topic",str)
    learners=_require(p,"learners",dict)
    objectives=[_objective(x,i) for i,x in enumerate(_require(p,"objectives",list))]
    assessments=p.get("assessments",[])
    if not isinstance(assessments,list): raise EducationError("assessments must be a list")
    mapped=[]
    for a in assessments:
        if not isinstance(a,dict) or not a.get("name"): raise EducationError("each assessment needs a name")
        ids=[str(x) for x in a.get("objective_ids",[])]
        mapped.append({"name":a["name"],"kind":a.get("kind","formative"),"objective_ids":ids,
                       "valid_objective_ids":[x for x in ids if x in {o['id'] for o in objectives}]})
    gaps=[o["id"] for o in objectives if not any(o["id"] in a["valid_objective_ids"] for a in mapped)]
    durations=p.get("duration_minutes",60)
    if not isinstance(durations,(int,float)) or durations<=0: raise EducationError("duration_minutes must be positive")
    allocation=[]
    remaining=float(durations)
    for index, stage in enumerate(cap.stages):
        minutes = round(remaining, 1) if index == len(cap.stages)-1 else round(float(durations)/len(cap.stages), 1)
        allocation.append({"stage":stage,"minutes":minutes})
        remaining -= minutes
    out={"topic":topic,"learner_profile":learners,"objectives":objectives,"assessments":mapped,
         "unassessed_objective_ids":gaps,"sequence":allocation,
         "review_checks":["subject_matter_accuracy","accessibility","assessment_validity"]}
    if cap.row_id==1411: out["objective_quality"]={"observable":sum(o['observable'] for o in objectives),"total":len(objectives),"needs_revision":[o['id'] for o in objectives if not o['observable']]}
    if cap.row_id==1413:
        criteria=_require(p,"criteria",list); levels=p.get("levels",["exceeds","meets","developing","beginning"])
        out["rubric"]=[{"criterion":c if isinstance(c,str) else c.get("name"),"weight":(c.get("weight",1) if isinstance(c,dict) else 1),"levels":levels} for c in criteria]
        total=sum(x["weight"] for x in out["rubric"]); out["normalized_weights"]=[{"criterion":x["criterion"],"weight":round(x["weight"]/total,4)} for x in out["rubric"]]
    if cap.row_id==1417: out["syllabus_sections"]=["course_description","learning_outcomes","schedule","assessment_and_grading","accessibility","academic_integrity","support_and_communication"]
    return out

def _inclusion(cap:Capability,p:dict[str,Any])->dict[str,Any]:
    objectives=[_objective(x,i) for i,x in enumerate(_require(p,"objectives",list))]
    profile=_require(p,"learner_profile",dict)
    supports=p.get("supports",[])
    if not isinstance(supports,list): raise EducationError("supports must be a list")
    out={"objectives":objectives,"learner_profile":profile,"supports":supports,
         "choice_architecture":{"engagement":["interest_choice","collaboration_or_independent"],"representation":["text","audio_or_captioned_video","worked_example"],"action_expression":["written","oral","demonstration"]},
         "privacy":"Use pseudonymous learner IDs; do not infer protected traits."}
    if cap.row_id==1425:
        score=float(p.get("mastery",0)); low=float(p.get("support_below",.6)); high=float(p.get("advance_at",.85))
        if not 0<=score<=1 or not 0<=low<high<=1: raise EducationError("mastery and thresholds must be in [0,1], low < high")
        out["adaptation"]="scaffold" if score<low else "advance" if score>=high else "practice"; out["mastery"]=score
    if cap.row_id==1426: out["tutor_loop"]=["diagnose_from_evidence","select_hint_not_answer","elicit_explanation","update_model","offer_human_help"]
    if cap.row_id==1427: out["fading_plan"]=[{"step":"model","support":1.0},{"step":"prompt","support":.66},{"step":"cue","support":.33},{"step":"independent","support":0.0}]
    if cap.row_id==1428:
        independent=set(p.get("independent_skills",[])); assisted=set(p.get("assisted_skills",[])); out["zpd_candidates"]=sorted(assisted-independent)
    if cap.row_id==1429: out["apprenticeship_cycle"]=list(cap.stages)
    return out

def _pedagogy(cap:Capability,p:dict[str,Any])->dict[str,Any]:
    challenge=_require(p,"challenge",str); objectives=[_objective(x,i) for i,x in enumerate(_require(p,"objectives",list))]
    out={"challenge":challenge,"objectives":objectives,"learning_cycle":list(cap.stages),"facilitator_moves":[],"learner_artifacts":p.get("artifacts",["investigation_log","solution_or_product","reflection"])}
    moves={"problem_based_learning":["withhold_solution","probe_reasoning","surface_need_to_know"],"project_based_learning":["milestone_conferences","critique_protocol","public_audience_check"],"inquiry_based_learning":["question_formulation","evidence_quality_prompt","claim_evidence_reasoning"],"discovery_learning":["contrasting_cases","productive_struggle_limit","explicit_consolidation"],"cooperative_learning":["positive_interdependence","individual_accountability","group_processing"],"collaborative_learning":["shared_problem_space","negotiated_roles","coauthored_synthesis"],"peer_instruction":["concept_question","anonymous_vote","peer_explanation","revote"]}
    out["facilitator_moves"]=moves.get(_slug(cap.name),["authentic_context","guided_practice","reflection_prompt"])
    if cap.row_id==1437: out["community_safeguards"]=["partner_defined_need","reciprocity","do_no_harm","consent","community_feedback"]
    if cap.row_id==1438: out["roles"]=p.get("roles",["facilitator","recorder","checker","reporter"]); out["individual_accountability"]=True
    return out

def _delivery(cap:Capability,p:dict[str,Any])->dict[str,Any]:
    units=_require(p,"units",list); constraints=p.get("constraints",{})
    if not isinstance(constraints,dict): raise EducationError("constraints must be an object")
    out={"units":units,"constraints":constraints,"delivery_plan":[],"accessibility":["captions_or_transcript","keyboard_access","downloadable_low_bandwidth_option"],"continuity":["asynchronous_equivalent","timezone_window","technical_support"]}
    for i,u in enumerate(units):
        title=u if isinstance(u,str) else u.get("title")
        out["delivery_plan"].append({"unit":title,"before":"short preparation","live_or_connected":"active application","after":"feedback and reflection"})
    if cap.row_id==1445: out["mooc_operations"]={"cohort_scale":p.get("cohort_scale"),"peer_review_calibration":True,"forum_moderation":True,"identity_optional_except_credentials":True}
    if cap.row_id==1446: out["micro_units"]=[{"unit":x["unit"],"target_minutes":min(10,int(p.get("target_minutes",7))),"retrieval_check":True} for x in out["delivery_plan"]]
    if cap.row_id==1447: out["mobile_requirements"]=["responsive","offline_resume","touch_target_44px","data_saver","no_notification_dark_patterns"]
    return out

def _immersive(cap:Capability,p:dict[str,Any])->dict[str,Any]:
    objective=_objective(_require(p,"objective",str),0)
    mechanic=_require(p,"mechanic",str)
    out={"objective":objective,"mechanic":mechanic,"alignment":{"mechanic_practices_objective":bool(p.get("alignment_rationale")),"rationale":p.get("alignment_rationale")},"safe_failure":p.get("safe_failure",True),"debrief":["what_happened","why_it_happened","how_it_transfers"]}
    if cap.row_id==1449:
        out["motivation_design"]={"meaningful_goal":p.get("meaningful_goal"),"feedback":p.get("feedback","informational"),"autonomy":p.get("choices",[]),"avoids_coercive_rewards":True}
    if cap.row_id>=1451: out["xr_safety"]=["seated_or_boundary_mode","motion_sickness_exit","accessible_2d_equivalent","privacy_notice"]
    if cap.row_id==1452: out["registration"]="Anchor overlays to verified physical targets and provide non-AR equivalent."
    if cap.row_id==1453: out["reality_continuum"]=["physical","augmented","virtual"]
    return out

def _events(p:dict[str,Any])->list[dict[str,Any]]:
    events=_require(p,"events",list)
    clean=[]
    for i,e in enumerate(events):
        if not isinstance(e,dict) or not e.get("learner_id") or not e.get("skill") or not e.get("event_type"): raise EducationError(f"events[{i}] missing learner_id, skill, or event_type")
        clean.append(e)
    return clean

def _analytics(cap:Capability,p:dict[str,Any])->dict[str,Any]:
    if cap.row_id==1454:
        return {"use_case":_require(p,"use_case",str),"human_oversight":["teacher can inspect evidence","learner can contest recommendation","no autonomous high-stakes decision"],"model_card_required":True,"data_minimization":True}
    events=_events(p); grouped={}
    for e in events:
        key=(str(e["learner_id"]),str(e["skill"])); g=grouped.setdefault(key,{"attempts":0,"correct":0,"durations":[]})
        if e["event_type"]=="attempt": g["attempts"]+=1; g["correct"]+=int(bool(e.get("correct")))
        if isinstance(e.get("duration_seconds"),(int,float)) and e["duration_seconds"]>=0:g["durations"].append(e["duration_seconds"])
    summaries=[]
    for (learner,skill),g in sorted(grouped.items()):
        summaries.append({"learner_id":learner,"skill":skill,"attempts":g["attempts"],"accuracy":round(g["correct"]/g["attempts"],4) if g["attempts"] else None,"mean_duration_seconds":round(sum(g["durations"])/len(g["durations"]),2) if g["durations"] else None})
    out={"summaries":summaries,"event_count":len(events),"limitations":["observed activity is not learning itself","missing events can bias results","do not use alone for high-stakes decisions"]}
    if cap.row_id==1456:
        min_support=int(p.get("min_support",2)); counts={};
        for e in events: counts[e["event_type"]]=counts.get(e["event_type"],0)+1
        out["frequent_patterns"]=[{"event_type":k,"support":v} for k,v in sorted(counts.items()) if v>=min_support]
    if cap.row_id in (1457,1458):
        prior=float(p.get("prior_mastery",.2)); learn=float(p.get("learn_rate",.1)); slip=float(p.get("slip",.1)); guess=float(p.get("guess",.2))
        if not all(0<=x<=1 for x in (prior,learn,slip,guess)): raise EducationError("BKT probabilities must be in [0,1]")
        traces=[]
        for key in sorted(grouped):
            m=prior
            for e in [x for x in events if (str(x['learner_id']),str(x['skill']))==key and x['event_type']=='attempt']:
                correct=bool(e.get("correct")); likelihood=m*(1-slip)+(1-m)*guess if correct else m*slip+(1-m)*(1-guess)
                posterior=(m*(1-slip)/likelihood) if correct and likelihood else (m*slip/likelihood if likelihood else m)
                m=posterior+(1-posterior)*learn
            traces.append({"learner_id":key[0],"skill":key[1],"mastery_probability":round(m,4),"model":"Bayesian knowledge tracing","not_a_grade":True})
        out["knowledge_state"]=traces
    if cap.row_id==1459:
        allowed={"self_report","voluntary_check_in","interaction_signal"}; signals=[]
        for e in events:
            if e["event_type"] in allowed:
                signals.append({"learner_id":e["learner_id"],"signal":e["event_type"],"value":e.get("value"),"confidence":e.get("confidence"),"interpretation":"uncertain"})
        out["affect_signals"]=signals; out["prohibited"]=["facial emotion diagnosis","mental health diagnosis","punitive action","protected-trait inference"]; out["response"]="Offer an optional check-in or support; never label emotion as fact."
    return out

def _distinctive(cap:Capability,p:dict[str,Any],result:dict[str,Any])->dict[str,Any]:
    """Compute one auditable, row-specific pedagogy measure from supplied evidence."""
    k=_slug(cap.name); stages=max(1,len(cap.stages))
    objectives=result.get("objectives",[]); n_obj=len(objectives)
    assessments=result.get("assessments",[]); mapped=sum(bool(a.get("valid_objective_ids")) for a in assessments)
    supports=result.get("supports",[]); units=result.get("units",[]); events=p.get("events",[])
    computations={
      "curriculum_design":("curriculum_alignment_rate",1-len(result.get("unassessed_objective_ids",[]))/max(1,n_obj),"1 - unassessed objectives / objectives"),
      "learning_objective_writing":("observable_objective_rate",sum(o.get("observable",False) for o in objectives)/max(1,n_obj),"observable objectives / objectives"),
      "assessment_design":("assessment_mapping_precision",sum(len(a.get("valid_objective_ids",[])) for a in assessments)/max(1,sum(len(a.get("objective_ids",[])) for a in assessments)),"valid objective links / all assessment links"),
      "rubric_creation":("rubric_weight_concentration",sum(x["weight"]**2 for x in result.get("normalized_weights",[])),"sum of squared normalized criterion weights"),
      "lesson_planning":("minutes_per_instructional_stage",float(p.get("duration_minutes",60))/stages,"duration minutes / lesson stages"),
      "unit_planning":("objectives_per_unit_stage",n_obj/stages,"objectives / unit stages"),
      "course_design":("course_assessment_coverage",mapped/max(1,len(assessments)),"assessments with valid mappings / assessments"),
      "syllabus_creation":("syllabus_section_coverage",len(result.get("syllabus_sections",[]))/7,"present required syllabus sections / 7"),
      "instructional_design":("instructional_evidence_density",(n_obj+len(assessments))/stages,"objectives plus assessments / design stages"),
      "addie_model":("addie_minutes_per_phase",float(p.get("duration_minutes",60))/5,"duration minutes / five ADDIE phases"),
      "sam_model":("sam_iteration_capacity",float(p.get("duration_minutes",60))/4,"duration minutes / four SAM stages"),
      "backward_design":("backward_alignment_rate",mapped/max(1,n_obj),"mapped assessments / desired-result objectives"),
      "universal_design_for_learning":("udl_option_count",sum(len(v) for v in result.get("choice_architecture",{}).values()),"engagement + representation + action/expression options"),
      "differentiated_instruction":("support_to_objective_ratio",len(supports)/max(1,n_obj),"declared supports / objectives"),
      "personalized_learning":("learner_choice_density",sum(len(v) for v in result.get("choice_architecture",{}).values())/max(1,n_obj),"learner choices / objectives"),
      "adaptive_learning":("mastery_distance_to_advance",round(float(p.get("advance_at",.85))-float(p.get("mastery",0)),6),"advance threshold - observed mastery"),
      "intelligent_tutoring":("tutor_loop_steps",len(result.get("tutor_loop",[])),"count of diagnose-hint-explain-update-help steps"),
      "scaffolding":("scaffold_fade_area",sum(x["support"] for x in result.get("fading_plan",[]))/max(1,len(result.get("fading_plan",[]))),"mean support across fading steps"),
      "zone_of_proximal_development":("zpd_skill_count",len(result.get("zpd_candidates",[])),"assisted skills minus independently demonstrated skills"),
      "cognitive_apprenticeship":("apprenticeship_cycle_length",len(result.get("apprenticeship_cycle",[])),"modeling through exploration stage count"),
      "situated_learning":("situated_artifact_density",len(result.get("learner_artifacts",[]))/stages,"authentic-context artifacts / learning-cycle stages"),
      "anchored_instruction":("anchor_transfer_ratio",len(result.get("learner_artifacts",[]))/max(1,len(str(p.get("challenge"," ")).split())),"artifacts / anchor challenge words"),
      "problem_based_learning":("pbl_inquiry_move_rate",len(result.get("facilitator_moves",[]))/stages,"inquiry facilitator moves / PBL stages"),
      "project_based_learning":("project_milestone_density",len(result.get("facilitator_moves",[]))/stages,"critique and milestone moves / project stages"),
      "inquiry_based_learning":("inquiry_evidence_move_rate",len(result.get("facilitator_moves",[]))/stages,"evidence prompts / inquiry stages"),
      "discovery_learning":("discovery_guidance_ratio",len(result.get("facilitator_moves",[]))/stages,"guidance moves / discovery stages"),
      "experiential_learning":("kolb_cycle_coverage",len(result.get("learning_cycle",[]))/4,"represented experiential stages / four Kolb stages"),
      "service_learning":("reciprocity_safeguard_count",len(result.get("community_safeguards",[])),"community co-design and reciprocity safeguards"),
      "cooperative_learning":("accountable_role_count",len(result.get("roles",[])),"assigned roles with individual accountability"),
      "collaborative_learning":("collaboration_artifact_rate",len(result.get("learner_artifacts",[]))/stages,"coauthored artifacts / collaboration stages"),
      "peer_instruction":("peer_instruction_cycle_length",len(result.get("learning_cycle",[])),"vote-discuss-revote-explain stages"),
      "flipped_classroom":("connected_touchpoints_per_unit",3*len(units),"before + connected + after touchpoints per unit"),
      "blended_learning":("modality_continuity_ratio",len(result.get("continuity",[]))/max(1,len(units)),"continuity provisions / units"),
      "online_learning":("online_accessibility_per_unit",len(result.get("accessibility",[]))/max(1,len(units)),"accessibility provisions / online units"),
      "distance_education":("distance_support_density",(len(result.get("continuity",[]))+len(result.get("accessibility",[])))/max(1,len(units)),"continuity plus accessibility provisions / units"),
      "moocs":("learners_per_moderation_channel",float(p.get("cohort_scale") or 0)/max(1,int(p.get("moderation_channels",1))),"cohort scale / moderation channels"),
      "microlearning":("microlearning_total_minutes",sum(x["target_minutes"] for x in result.get("micro_units",[])),"sum of bounded micro-unit minutes"),
      "mobile_learning":("mobile_resilience_requirements",len(result.get("mobile_requirements",[])),"offline, responsive, touch, data and notification safeguards"),
      "game_based_learning":("mechanic_alignment_score",int(result.get("alignment",{}).get("mechanic_practices_objective",False)),"1 when mechanic has supplied objective-alignment rationale"),
      "gamification":("autonomy_choice_count",len(result.get("motivation_design",{}).get("autonomy",[])),"meaningful learner choices, excluding coercive rewards"),
      "simulation_based_learning":("simulation_transfer_steps",len(result.get("debrief",[])),"what-why-transfer debrief steps"),
      "virtual_reality_learning":("vr_safety_control_count",len(result.get("xr_safety",[])),"VR boundary, exit, 2D and privacy controls"),
      "augmented_reality_learning":("ar_registration_control_count",len(result.get("xr_safety",[]))+int(bool(result.get("registration"))),"XR controls plus physical-target registration requirement"),
      "mixed_reality_learning":("reality_continuum_coverage",len(result.get("reality_continuum",[])),"physical, augmented and virtual modes represented"),
      "artificial_intelligence_in_education":("ai_oversight_control_count",len(result.get("human_oversight",[]))+int(result.get("model_card_required",False)),"human oversight controls plus model-card gate"),
      "learning_analytics":("attempt_weighted_accuracy",sum(int(bool(e.get("correct"))) for e in events if e.get("event_type")=="attempt")/max(1,sum(e.get("event_type")=="attempt" for e in events)),"correct attempts / recorded attempts"),
      "educational_data_mining":("frequent_pattern_count",len(result.get("frequent_patterns",[])),"event types meeting caller-supplied minimum support"),
      "student_modeling":("mean_modeled_mastery",sum(x["mastery_probability"] for x in result.get("knowledge_state",[]))/max(1,len(result.get("knowledge_state",[]))),"mean bounded formative mastery probability"),
      "knowledge_tracing":("knowledge_trace_span",(max((x["mastery_probability"] for x in result.get("knowledge_state",[])),default=0)-min((x["mastery_probability"] for x in result.get("knowledge_state",[])),default=0)),"maximum minus minimum traced mastery probability"),
      "affect_detection":("voluntary_signal_rate",len(result.get("affect_signals",[]))/max(1,len(events)),"voluntary non-diagnostic signals / all events"),
    }
    name,value,formula=computations[k]
    if not isinstance(value,(int,float)) or not math.isfinite(float(value)): raise EducationError(f"{name} is not finite")
    return {"name":name,"value":round(float(value),6),"formula":formula,"inputs":"caller supplied only","educator_review_required":True,"privacy":"pseudonymous aggregates; no protected-trait inference"}

def execute(capability:str,payload:dict[str,Any])->dict[str,Any]:
    key=_slug(capability); row=NAME_TO_ROW.get(key)
    if row is None: raise EducationError(f"unknown capability: {capability}")
    if not isinstance(payload,dict): raise EducationError("payload must be an object")
    src=_source(payload); family=_FAMILIES[key]
    default=("analyze","design","practice","assess","reflect")
    cap=Capability(row,_CAPABILITY_ROWS[row],family,_STAGE_OVERRIDES.get(key,default),_EVIDENCE[family])
    handler={"design":_design,"inclusion":_inclusion,"pedagogy":_pedagogy,"delivery":_delivery,"immersive":_immersive,"analytics":_analytics}[family]
    result=handler(cap,payload)
    result["distinctive_computation"]=_distinctive(cap,payload,result)
    evaluation={
        "criteria":list(cap.evidence),
        "observed_evidence":sorted(k for k,v in result.items() if v not in (None,[],{})),
        "open_questions":list(payload.get("open_questions",[])),
        "reviewer":"qualified educator and affected learner",
    }
    uncertainty={
        "level":"not_quantified",
        "drivers":["caller-supplied learner context","transfer beyond observed work","accessibility and cultural fit"],
        "not_a_mastery_or_credential_claim":True,
    }
    return {"row_id":row,"capability":cap.name,"key":key,"family":family,"source":src,"evidence_checks":list(cap.evidence),"result":result,"evaluation":evaluation,"uncertainty":uncertainty,"boundary":"Decision support only. A qualified educator reviews accuracy, accessibility, fairness, privacy, and high-stakes uses."}

# Education rows preserve method-specific artifacts and report evidence/input
# coverage without inferring learner ability, affect, disability, or grades.
_original_execute = execute
from app.core.depth_quality import attach_quality as _attach_quality

def execute(capability:str|int,payload:dict[str,Any])->dict[str,Any]:
    out=_original_execute(capability,payload)
    evidence=[x for key in ('sources','evidence','learner_evidence') for x in payload.get(key,[]) if isinstance(x,dict)]
    required=[k for k in payload if k not in {'assumptions','sources','evidence','learner_evidence'}]
    method=str(capability)
    return _attach_quality(out,domain='education',method=method,inputs=payload,
        required_inputs=required,evidence=evidence,assumptions=payload.get('assumptions',[]),
        limitations=['Planning and formative support only; no enrollment, credential, high-stakes grade, diagnosis, or learner profiling.',
                     'An educator must review pedagogy, accessibility, culture, privacy, evidence, and learner agency.'])
