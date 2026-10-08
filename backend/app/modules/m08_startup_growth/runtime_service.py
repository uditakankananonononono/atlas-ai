"""HTTP service with buildable landing generation; other generators unchanged."""
from .landing_runtime import landing_files
from .schemas import LandingPageIn
from .service import Service as BaseService


class Service(BaseService):
    def landing_page(self, data: LandingPageIn):
        return self._store(data.project_id, "landing_page", landing_files(data))
