from datetime import datetime, timezone
import asyncio, json
from app.modules.m06_social_media_manager.creative import CreativeEngine
from app.modules.m06_social_media_manager.service import MemorySocialRepository
from app.modules.m15_document_generator.creative_production_306_332 import plan
from app.modules.m15_document_generator.design_support_333_359 import design_support_333_359
from app.modules.m19_idea_incubator.business_service import BusinessAnalysisService
from app.modules.m19_idea_incubator.business_models import BusinessAnalysisRequest
from app.modules.m19_idea_incubator.operations_service import OperationsAnalysisService
from app.modules.m19_idea_incubator.operations_models import OperationsAnalysisRequest
from app.modules.m14_project_builder.engineering import generate_design

def source(): return {"source_id":"s","source_type":"user_input","observed_at":datetime.now(timezone.utc)}

def test_creative_and_design_families_expose_evaluation_and_uncertainty():
 async def gen(*_): return "m",json.dumps({"hierarchy":"clear","navigation":"tested","content_model":"typed","accessibility":"reviewed"})
 a=asyncio.run(CreativeEngine(repository=MemorySocialRepository(),generate=gen).generate("information-architecture",business="b",subject="s"))
 assert a.evaluation["human_review_required"] and not a.uncertainty["render_or_physical_result_claimed"]
 c=plan(306,{"tracks":["t"],"sample_rate":48000,"target_platform":"web","sources":[{"source_id":"s","observed_at":"2026-09-21"}]})
 assert c["evaluation"]["open_stages"] and not c["uncertainty"]["rendered_recorded_built_or_certified_claimed"]
 d=design_support_333_359(334,{"brief":"toy","decision_owner":"owner","requirements":["safe"],"hazards":[{"id":"h","severity":4,"likelihood":2}]})
 assert d["evaluation"] is not None and not d["uncertainty"]["release_or_safety_claimed"]

def test_business_operations_and_engineering_expose_review_envelopes():
 b=BusinessAnalysisService().analyze("i",BusinessAnalysisRequest(feature=360,inputs={"total_entities":10,"annual_revenue_per_entity":2,"serviceable_fraction":.5,"obtainable_fraction":.1},provenance=[source()],confidence=.7))
 assert b.evaluation["human_review_required"] and b.uncertainty.confidence==.7
 o=OperationsAnalysisService().analyze("i",OperationsAnalysisRequest(feature=453,inputs={"annual_demand":10,"order_cost":2,"annual_holding_cost_per_unit":1,"lead_time_days":1,"daily_demand":1},provenance=[source()],confidence=.8))
 assert o.evaluation["pilot_measurement_required"] and o.execution_status=="not_executed"
 e=generate_design("requirements","build a system")
 assert e.evaluation["validation_required"] and not e.uncertainty["deployment_or_performance_claimed"]
