from fastapi import APIRouter,Depends,HTTPException
from app.auth.context import TenantContext,require_tenant
from .models import RouteRequest
from .schemas import RunIn,WorkflowIn
from .workflow import Workflow,WorkflowValidationError
router=APIRouter(prefix="/ai-research-lab",tags=["ai-research-lab"])
def get_service(): raise RuntimeError("bind Module 12 Service/provider in app dependency overrides")
def get_dag_engine(): raise RuntimeError("bind Celery-backed DagEngine in app dependency overrides")
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
    method:Literal['clinical_decision_support','differential_diagnosis','treatment_protocol_selection','drug_interaction_check','dosage_calculation','medical_image_analysis','radiology_report_generation','pathology_slide_analysis','ecg_interpretation','eeg_analysis','genomics_interpretation','pharmacogenomic_recommendations','clinical_trial_matching','adverse_event_detection','patient_risk_stratification','readmission_prediction','sepsis_early_warning','mortality_prediction','length_of_stay_prediction','icu_resource_allocation','emergency_triage','surgical_planning','anesthesia_monitoring','post_operative_care','rehabilitation_planning','physical_therapy_design','occupational_therapy_design','speech_therapy_design','mental_health_assessment','depression_screening','anxiety_assessment','ptsd_evaluation','addiction_treatment_planning','cognitive_assessment','dementia_screening','neuropsychological_testing','psychotherapy_planning','cbt_protocol_design','dbt_skill_selection','medication_management','chronic_disease_management','diabetes_management','hypertension_management','asthma_management','copd_management','heart_failure_management','cancer_care_coordination','chemotherapy_planning','radiation_therapy_planning','immunotherapy_selection','palliative_care_planning','hospice_care_coordination','pain_management','wound_care','infection_control','antimicrobial_stewardship','vaccination_scheduling','preventive_care_planning','health_screening_recommendations','genetic_counseling','fertility_treatment_planning','prenatal_care','labor_and_delivery_management','neonatal_care','pediatric_care','adolescent_medicine','geriatric_care','womens_health','mens_health','lgbtq_health','global_health','public_health_surveillance','epidemic_response','contact_tracing','quarantine_management','health_education','behavior_change_support','medication_adherence','lifestyle_modification','nutrition_planning','exercise_prescription','sleep_hygiene','stress_management','substance_abuse_treatment','harm_reduction','crisis_intervention','suicide_prevention','trauma_informed_care','culturally_competent_care']
    data:dict[str,Any]=Field(default_factory=dict)
@router.post('/clinical/support')
def clinical_support_route(body:ClinicalSupportIn,tenant:TenantContext=Depends(require_tenant)):
    try:return {'tenant_id':tenant.tenant_id,'method':body.method,'result':clinical_support(body.method,body.data),'requires_clinician_review':True}
    except ValueError as error:raise HTTPException(422,str(error)) from error
