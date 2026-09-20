from app.modules.m03_grant_writer import spec as grant_writer
from app.modules.m04_research_scientist import spec as research_scientist
from app.modules.types import ModuleSpec

IMPLEMENTED_SPECS: tuple[ModuleSpec, ...] = (grant_writer, research_scientist)
BY_IMPLEMENTED_ID = {spec.id: spec for spec in IMPLEMENTED_SPECS}
