"""Module 0 - Human Approval Center.

Every irreversible action in Atlas AI passes through this module before a
human releases it to execution. Other modules use the request_approval
SDK function rather than talking to the store directly.
"""
from app.modules.m00_approval_center.routes import router
from app.modules.m00_approval_center.service import Service, request_approval
from app.modules.types import ModuleSpec

spec = ModuleSpec(id=0, slug="approval-center", name="Human Approval Center", router=router, service_type=Service)

__all__ = ["spec", "router", "Service", "request_approval"]
