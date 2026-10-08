"""Test helper: an in-memory repository that owns idea 'x', wired over the ownership guard."""
from datetime import datetime,timezone
from app.modules.m19_idea_incubator.idea_ownership import get_idea_repository
from app.modules.m19_idea_incubator.repository import MemoryIdeaRepository
from app.modules.m19_idea_incubator.schemas import Idea
def own_idea_x(app,idea_id="x"):
 repo=MemoryIdeaRepository();now=datetime.now(timezone.utc);repo.save_idea(Idea(id=idea_id,title="t",problem="p",proposed_solution="s",created_at=now,updated_at=now));app.dependency_overrides[get_idea_repository]=lambda:repo;return app
