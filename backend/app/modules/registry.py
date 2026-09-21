from app.modules.m00_approval_center import spec as approval_center
from app.modules.m01_opportunity_discovery import spec as opportunity_discovery
from app.modules.m02_competition_manager import spec as competition_manager
from app.modules.m03_grant_writer import spec as grant_writer
from app.modules.m04_research_scientist import spec as research_scientist
from app.modules.m05_outreach_manager import spec as outreach_manager
from app.modules.m06_social_media_manager import spec as social_media_manager
from app.modules.m07_brand_collaboration import spec as brand_collaboration
from app.modules.m08_startup_growth import spec as startup_growth
from app.modules.m14_project_builder import spec as project_builder
from app.modules.m15_document_generator import spec as document_generator
from app.modules.m17_narrative_architect import spec as narrative_architect
from app.modules.m18_side_hustle_scraper import spec as side_hustle_scraper
from app.modules.m19_idea_incubator import spec as idea_incubator
from app.modules.m20_general_cognitive_worker import spec as general_cognitive_worker
from app.modules.m21_claire import spec as claire
from app.modules.m22_tools_hub import spec as tools_hub
from app.modules.m09_knowledge_workspace import spec as knowledge_workspace
from app.modules.m16_executive_dashboard import spec as executive_dashboard
from app.modules.m12_ai_research_lab import spec as ai_research_lab
from app.modules.m13_browser_agent import spec as browser_agent
from app.modules.m10_email_assistant import spec as email_assistant
from app.modules.m11_calendar_intelligence import spec as calendar_intelligence
from app.modules.m23_study_abroad import spec as study_abroad
from app.modules.m24_billing import spec as billing
from app.modules.m25_knowledge_copilot_training import spec as knowledge_copilot_training
from app.modules.types import ModuleSpec

IMPLEMENTED_SPECS: tuple[ModuleSpec, ...] = (approval_center, opportunity_discovery, competition_manager, grant_writer, research_scientist, outreach_manager, social_media_manager, brand_collaboration, startup_growth, project_builder, document_generator, narrative_architect, side_hustle_scraper, idea_incubator, general_cognitive_worker, claire, tools_hub, knowledge_workspace, executive_dashboard, ai_research_lab, browser_agent, email_assistant, calendar_intelligence, study_abroad, billing, knowledge_copilot_training)
BY_IMPLEMENTED_ID = {spec.id: spec for spec in IMPLEMENTED_SPECS}
