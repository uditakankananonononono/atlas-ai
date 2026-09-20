"""Test harness stubs for app.* packages.

In the real repo these packages exist and every stub below is skipped (the
guard import succeeds). In a bare workspace they provide the minimal surface
the module package imports at load time so domain logic can be tested.
"""

import sys
import types


def _stub_app_core() -> None:
    try:  # real repo: nothing to do
        import app.auth.context  # noqa: F401
        import app.core.approvals  # noqa: F401
        import app.core.database  # noqa: F401
        import app.core.models  # noqa: F401
        import app.core.providers  # noqa: F401
        import app.modules.types  # noqa: F401
        return
    except ModuleNotFoundError:
        pass

    for name in (
        "app", "app.auth", "app.core", "app.modules",
    ):
        if name not in sys.modules:
            module = types.ModuleType(name)
            module.__path__ = []  # mark as package
            sys.modules[name] = module

    # app.modules must still find the real module packages on PYTHONPATH.
    import importlib.machinery
    import os

    backend = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "backend")
    )
    sys.modules["app"].__path__ = [os.path.join(backend, "app")]
    sys.modules["app.modules"].__path__ = [os.path.join(backend, "app", "modules")]

    auth_context = types.ModuleType("app.auth.context")

    class TenantContext:
        def __init__(self, tenant_id: str = "test-tenant"):
            self.tenant_id = tenant_id

    def require_tenant() -> TenantContext:
        return TenantContext()

    auth_context.TenantContext = TenantContext
    auth_context.require_tenant = require_tenant
    sys.modules["app.auth.context"] = auth_context

    core_models = types.ModuleType("app.core.models")

    class _Status:
        def __init__(self, value: str = "pending"):
            self.value = value

    class ApprovalRequest:
        def __init__(self, id, module_id, action_type, payload, status="pending"):
            self.id = id
            self.module_id = module_id
            self.action_type = action_type
            self.payload = payload
            self.status = _Status(status if isinstance(status, str) else status)

    core_models.ApprovalRequest = ApprovalRequest
    sys.modules["app.core.models"] = core_models

    core_approvals = types.ModuleType("app.core.approvals")

    class _ApprovalSink:
        def __init__(self):
            self.items = []

        def put(self, item):
            self.items.append(item)
            return item

    core_approvals.approvals = _ApprovalSink()
    sys.modules["app.core.approvals"] = core_approvals

    core_providers = types.ModuleType("app.core.providers")

    async def generate(prompt: str, provider: str, model):
        return provider, "{}"

    core_providers.generate = generate
    sys.modules["app.core.providers"] = core_providers

    core_database = types.ModuleType("app.core.database")
    from sqlalchemy import create_engine
    from sqlalchemy.orm import declarative_base, sessionmaker

    engine = create_engine("sqlite:///:memory:")
    SessionLocal = sessionmaker(bind=engine)
    Base = declarative_base()
    core_database.engine = engine
    core_database.SessionLocal = SessionLocal
    core_database.Base = Base
    sys.modules["app.core.database"] = core_database

    modules_types = types.ModuleType("app.modules.types")

    class ModuleSpec:
        def __init__(self, id, slug, name, router, service_type):
            self.id = id
            self.slug = slug
            self.name = name
            self.router = router
            self.service_type = service_type

    modules_types.ModuleSpec = ModuleSpec
    sys.modules["app.modules.types"] = modules_types


_stub_app_core()
