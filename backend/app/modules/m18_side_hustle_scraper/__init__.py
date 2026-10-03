"""Module 18 - Side Hustle & Knowledge Scraper."""
from .routes import router
from .login_routes import router as login_router
from fastapi import APIRouter
_root_router = APIRouter()
_root_router.include_router(router)
_root_router.include_router(login_router)
router = _root_router
from .service import Service
from app.modules.types import ModuleSpec
spec=ModuleSpec(id=18,slug="side-hustle-scraper",name="Side Hustle & Knowledge Scraper",router=router,service_type=Service)
