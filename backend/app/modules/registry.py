from app.modules.m00_approval_center import spec as approval_center
from app.modules.m01_opportunity_discovery import spec as opportunity_discovery
from app.modules.m02_competition_manager import spec as competition_manager
from app.modules.m03_grant_writer import spec as grant_writer
from app.modules.m04_research_scientist import spec as research_scientist
from app.modules.m05_outreach_manager import spec as outreach_manager
from app.modules.m06_social_media_manager import spec as social_media_manager
from app.modules.m07_brand_collaboration import spec as brand_collaboration
from app.modules.m08_startup_growth import spec as startup_growth
from app.modules.types import ModuleSpec

IMPLEMENTED_SPECS: tuple[ModuleSpec, ...] = (approval_center, opportunity_discovery, competition_manager, grant_writer, research_scientist, outreach_manager, social_media_manager, brand_collaboration, startup_growth)
BY_IMPLEMENTED_ID = {spec.id: spec for spec in IMPLEMENTED_SPECS}
