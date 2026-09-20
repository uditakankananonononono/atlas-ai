"""Lane-built competition workflow API, kept separate from mounted Service."""
from .models import *
from .parser import parse_competition_document, validate_rubric
from .repository import CompetitionRepository, InMemoryCompetitionRepository, ConflictError, NotFoundError
from .lane_service import CompetitionManager, payload_digest
from .analysis import GroundingConflict, grounding_conflicts, checklist_dependency_order
