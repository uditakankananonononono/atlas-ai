"""Module 18 - Side Hustle & Knowledge Scraper."""
from .routes import router
from .service import Service
from app.modules.types import ModuleSpec
spec=ModuleSpec(id=18,slug="side-hustle-scraper",name="Side Hustle & Knowledge Scraper",router=router,service_type=Service)
