from dataclasses import dataclass
from fastapi import APIRouter

@dataclass(frozen=True)
class ModuleSpec:
    id: int
    slug: str
    name: str
    router: APIRouter
    service_type: type
