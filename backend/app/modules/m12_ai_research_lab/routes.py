from fastapi import APIRouter,Depends,HTTPException
from app.auth.context import TenantContext,require_tenant
from .models import RouteRequest
from .schemas import RunIn,WorkflowIn
from .workflow import Workflow,WorkflowValidationError
router=APIRouter(prefix="/ai-research-lab",tags=["ai-research-lab"])
_service=None
_dag=None
def get_service():
 global _service
 if _service is None:
  from .wiring import build_service
  _service=build_service()
 return _service
def get_dag_engine():
 global _dag
 if _dag is None:
  from .wiring import build_dag_engine
  _dag=build_dag_engine(get_service())
 return _dag
@router.post("/run")
async def run(body:RunIn,tenant:TenantContext=Depends(require_tenant),service=Depends(get_service)):
    try:return await service.execute(RouteRequest(body.task_type,body.output_tokens,body.budget_cents,body.latency_tolerance_ms,tenant.tenant_id),body.prompt)
    except RuntimeError as error: raise HTTPException(422,str(error)) from error
@router.post("/workflows/run")
async def run_workflow(body:WorkflowIn,tenant:TenantContext=Depends(require_tenant),engine=Depends(get_dag_engine)):
    try:return await engine.run(Workflow.from_yaml(body.yaml),{**body.inputs,"tenant_id":tenant.tenant_id})
    except WorkflowValidationError as error: raise HTTPException(422,str(error)) from error

from pydantic import BaseModel,Field
from typing import Any,Literal
from .clinical_support import clinical_support
class ClinicalSupportIn(BaseModel):
    method:Literal['clinical_decision_support','differential_diagnosis','treatment_protocol_selection','drug_interaction_check','dosage_calculation','medical_image_analysis','radiology_report_generation','pathology_slide_analysis','ecg_interpretation','eeg_analysis','genomics_interpretation','pharmacogenomic_recommendations','clinical_trial_matching','adverse_event_detection','patient_risk_stratification','readmission_prediction','sepsis_early_warning','mortality_prediction','length_of_stay_prediction','icu_resource_allocation','emergency_triage','surgical_planning','anesthesia_monitoring','post_operative_care','rehabilitation_planning','physical_therapy_design','occupational_therapy_design','speech_therapy_design','mental_health_assessment','depression_screening','anxiety_assessment','ptsd_evaluation','addiction_treatment_planning','cognitive_assessment','dementia_screening','neuropsychological_testing','psychotherapy_planning','cbt_protocol_design','dbt_skill_selection','medication_management','chronic_disease_management','diabetes_management','hypertension_management','asthma_management','copd_management','heart_failure_management','cancer_care_coordination','chemotherapy_planning','radiation_therapy_planning','immunotherapy_selection','palliative_care_planning','hospice_care_coordination','pain_management','wound_care','infection_control','antimicrobial_stewardship','vaccination_scheduling','preventive_care_planning','health_screening_recommendations','genetic_counseling','fertility_treatment_planning','prenatal_care','labor_and_delivery_management','neonatal_care','pediatric_care','adolescent_medicine','geriatric_care','womens_health','mens_health','lgbtq_health','global_health','public_health_surveillance','epidemic_response','contact_tracing','quarantine_management','health_education','behavior_change_support','medication_adherence','lifestyle_modification','nutrition_planning','exercise_prescription','sleep_hygiene','stress_management','substance_abuse_treatment','harm_reduction','crisis_intervention','suicide_prevention','trauma_informed_care','culturally_competent_care','health_equity_analysis','social_determinants_assessment','community_health_assessment','health_policy_analysis','healthcare_quality_improvement','patient_safety','medical_error_prevention','healthcare_operations','hospital_administration','healthcare_finance','medical_education']
    data:dict[str,Any]=Field(default_factory=dict)
@router.post('/clinical/support')
def clinical_support_route(body:ClinicalSupportIn,tenant:TenantContext=Depends(require_tenant)):
    try:return {'tenant_id':tenant.tenant_id,'method':body.method,'result':clinical_support(body.method,body.data),'requires_clinician_review':True}
    except ValueError as error:raise HTTPException(422,str(error)) from error

from .legal_support import LEGAL_METHODS,legal_support
class LegalSupportIn(BaseModel):
    method:str
    data:dict[str,Any]=Field(default_factory=dict)
@router.post('/legal/support')
def legal_support_route(body:LegalSupportIn,tenant:TenantContext=Depends(require_tenant)):
    if body.method not in LEGAL_METHODS: raise HTTPException(422,'unsupported legal support method')
    try:return {'tenant_id':tenant.tenant_id,'method':body.method,'result':legal_support(body.method,body.data),'requires_counsel_review':True}
    except ValueError as error:raise HTTPException(422,str(error)) from error

from .education_support import education_support
class EducationSupportIn(BaseModel):
    feature_id:int=Field(ge=1460,le=1509)
    data:dict[str,Any]=Field(default_factory=dict)
@router.post('/education/support')
def education_support_route(body:EducationSupportIn,tenant:TenantContext=Depends(require_tenant)):
    try:return {'tenant_id':tenant.tenant_id,'actor_id':tenant.actor_id,**education_support(body.feature_id,body.data)}
    except ValueError as error:raise HTTPException(422,str(error)) from error

from .engineering_support_1560_1609 import engineering_support_1560_1609
class Engineering1560To1609In(BaseModel):
    feature_id:int=Field(ge=1560,le=1609)
    data:dict[str,Any]=Field(default_factory=dict)
@router.post('/engineering-1560-1609/support')
def engineering_1560_1609_route(body:Engineering1560To1609In,tenant:TenantContext=Depends(require_tenant)):
    try:return {'tenant_id':tenant.tenant_id,**engineering_support_1560_1609(body.feature_id,body.data)}
    except ValueError as error:raise HTTPException(422,str(error)) from error

# Research and scientific discovery workbench, owner-ledger rows 135-184.
from .research_methods_routes_135_184 import router as research_methods_router_135_184
router.include_router(research_methods_router_135_184)

# Emerging biomedical support rows 960-1009.
from .emerging_biomed_routes_960_1009 import router as emerging_biomed_router_960_1009
router.include_router(emerging_biomed_router_960_1009)

# Semantic-verification repair for specialized engineering rows 1560-1609.
from .engineering_semantic_fixes_1560_1609 import engineering_semantic_1560_1609
class EngineeringSemanticIn(BaseModel):
    feature_id:int
    data:dict=Field(default_factory=dict)
@router.post('/engineering-1560-1609/semantic-support')
def engineering_semantic_route(body:EngineeringSemanticIn,tenant:TenantContext=Depends(require_tenant)):
    try:return {'tenant_id':tenant.tenant_id,**engineering_semantic_1560_1609(body.feature_id,body.data)}
    except (ValueError,TypeError,KeyError,ZeroDivisionError) as exc:raise HTTPException(422,str(exc)) from exc

# Row-addressable clinical execution. This is deliberately separate from the
# legacy method endpoint so audits and clients can prove which named row ran.
from .clinical_rows_1110_1209 import ROW_METHODS, execute_clinical_row
class ClinicalRowIn(BaseModel):
    data:dict[str,Any]=Field(default_factory=dict)
@router.get('/clinical/rows')
def clinical_rows_catalog():
    return [{'row_id': row_id, 'method': method, 'route': f'/api/v1/ai-research-lab/clinical/{row_id}/execute'} for row_id,method in ROW_METHODS.items()]
@router.post('/clinical/{row_id}/execute')
def clinical_row_execute(row_id:int,body:ClinicalRowIn,tenant:TenantContext=Depends(require_tenant)):
    try:return {'tenant_id':tenant.tenant_id,**execute_clinical_row(row_id,body.data)}
    except (ValueError,TypeError,KeyError,ZeroDivisionError) as error:raise HTTPException(422,str(error)) from error

from .reproducible_run import ReproducibleRunRequest,checkpoint
@router.post('/reproducible-run/checkpoint')
def reproducible_run_checkpoint(body:ReproducibleRunRequest,tenant:TenantContext=Depends(require_tenant)):
 try:return {'tenant_id':tenant.tenant_id,**checkpoint(body)}
 except ValueError as error:raise HTTPException(422,str(error)) from error

from .resume_verification import ResumeVerificationRequest,verify_resume
@router.post('/reproducible-run/resume/verify')
def reproducible_run_resume_verify(body:ResumeVerificationRequest,tenant:TenantContext=Depends(require_tenant)):
 try:return {'tenant_id':tenant.tenant_id,**verify_resume(body)}
 except ValueError as error:raise HTTPException(422,str(error)) from error
