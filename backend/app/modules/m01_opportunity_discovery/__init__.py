"""Module 1: Opportunity Discovery Engine.

Discovers competitions, hackathons, grants, fellowships, and scholarships
from compliant sources (RSS/Atom feeds and official APIs), normalizes and
scores them against the user's profile, stores them, and drafts daily digest
emails whose sending is always gated behind the Human Approval Center.
"""

from app.modules.types import ModuleSpec

from .routes import router
from .service import Service

spec = ModuleSpec(id=1, slug="opportunity-discovery", name="Opportunity Discovery Engine", router=router, service_type=Service)
