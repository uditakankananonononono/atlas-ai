from uuid import uuid4

from app.modules.m17_advice_essay.in_memory_repository import InMemoryModule17Repository
from app.modules.m17_advice_essay.schemas import AdviceSource, IdentityMaterial, SourceKind


def test_repository_never_crosses_owner_boundary_and_defensively_copies():
    repo = InMemoryModule17Repository(); owner_a = uuid4(); owner_b = uuid4()
    source = AdviceSource(owner_id=owner_a, source_kind=SourceKind.USER_SUBMITTED, platform="notes", content="Original", permission_basis="owner upload")
    repo.add_source(source)
    source.content = "mutated by caller"
    assert repo.list_sources(owner_a)[0].content == "Original"
    assert repo.list_sources(owner_b) == []
    material = IdentityMaterial(owner_id=owner_a, label="Lab", description="Built a sensor", user_confirmed=True)
    repo.add_material(material)
    assert repo.list_materials(owner_b, [material.id]) == []
