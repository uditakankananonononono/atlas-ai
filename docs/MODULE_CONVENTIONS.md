# Module lane conventions

Each lane owns one directory: `backend/app/modules/mNN_<slug>/` and its matching test file `tests/modules/test_mNN_<slug>.py`.

Required files:

- `__init__.py` exports `spec`
- `service.py` contains domain logic without FastAPI imports
- `routes.py` defines a local `APIRouter`
- `schemas.py` contains Pydantic request/response models

Each `__init__.py` must expose:

```python
from .routes import router
from .service import Service
from app.modules.types import ModuleSpec

spec = ModuleSpec(id=N, slug="spec-slug", name="Spec Name", router=router, service_type=Service)
```

Rules:

- IDs/slugs/names must exactly match `backend/app/modules/catalog.py`.
- Routes live under `/{slug}` and use nouns/actions local to the module. The integrator adds the global `/api/v1` prefix.
- The service constructor takes dependencies explicitly. No global API clients, credentials, DB sessions, or network work at import time.
- External effects return a typed proposed action or call the shared approval service. Sending, publishing, submitting, deleting, browser form submission, and payment cannot execute directly.
- BYOK model work calls `app.core.providers.generate`; never read/log/return a key.
- Use official APIs, RSS, licensed sources, site-permitted automation, or user-authorized sessions. No self-bots, unofficial social wrappers, rotating residential proxies, or stealth/evasion.
- Tests must mock all network calls, cover a success path and a failure/safety path, and run with `pytest` offline.

Do not edit these shared conflict magnets in a module lane:

- `backend/app/main.py`
- `backend/app/api/routes.py`
- `backend/app/core/*`
- `backend/app/modules/catalog.py`
- `pyproject.toml`, `docker-compose.yml`, `.env.example`
- root `README.md`

If a new shared dependency/config field is required, put the request in `backend/app/modules/mNN_<slug>/INTEGRATION.md`; the integrator makes the shared edit. Keep generated files, caches, local DBs, secrets, and provider keys out of the patch.
