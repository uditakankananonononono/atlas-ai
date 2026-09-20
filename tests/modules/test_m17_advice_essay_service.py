from uuid import uuid4

import pytest

from app.modules.m17_advice_essay.schemas import (
    AdviceSource,
    EssayBrief,
    IdentityMaterial,
    MediaKind,
    SourceKind,
)
from app.modules.m17_advice_essay.service import AdviceEssayService


class MemoryRepository:
    def __init__(self):
        self.sources = []
        self.materials = []
        self.tips = []
        self.concepts = []

    def add_source(self, value): self.sources.append(value); return value
    def list_sources(self, owner_id): return [x for x in self.sources if x.owner_id == owner_id]
    def add_material(self, value): self.materials.append(value); return value
    def list_materials(self, owner_id, ids): return [x for x in self.materials if x.owner_id == owner_id and x.id in ids and x.user_confirmed]
    def add_tip(self, value): self.tips.append(value); return value
    def list_tips(self, owner_id): return [x for x in self.tips if x.owner_id == owner_id]
    def add_concept(self, value): self.concepts.append(value); return value


def test_public_source_requires_provenance_url():
    with pytest.raises(ValueError, match="canonical_url"):
        AdviceSource(owner_id=uuid4(), source_kind=SourceKind.PUBLIC_WEB, platform="web", content="Use scenes.", permission_basis="public page")


def test_rejects_prohibited_collection_basis():
    service = AdviceEssayService(MemoryRepository())
    source = AdviceSource(owner_id=uuid4(), source_kind=SourceKind.PUBLIC_WEB, platform="web", canonical_url="https://example.org/a", content="Use scenes.", permission_basis="rotating proxy bypass")
    with pytest.raises(ValueError, match="prohibited"):
        service.ingest_source(source)


def test_compiles_traceable_advice_and_coaching_scaffolds():
    owner = uuid4(); repo = MemoryRepository(); service = AdviceEssayService(repo)
    for content in ("Specific scenes reveal character. Add detail.", "Specific choices make reflection credible."):
        service.ingest_source(AdviceSource(owner_id=owner, source_kind=SourceKind.USER_SUBMITTED, media_kind=MediaKind.TEXT, platform="notes", content=content, permission_basis="uploaded by owner"))
    tips = service.compile_advice(owner)
    assert tips and all(tip.source_ids for tip in tips)
    material = service.add_identity_material(IdentityMaterial(owner_id=owner, label="Robotics repair", description="I rebuilt the drive train before our final match.", user_confirmed=True))
    concepts = service.create_concepts(EssayBrief(owner_id=owner, prompt="Describe a challenge.", word_limit=650, material_ids=[material.id], requested_concepts=3))
    assert len(concepts) == 3
    assert all("Coaching scaffold only" in concept.coaching_notice for concept in concepts)
    assert all(concept.opening_scaffold.startswith("Writer prompt:") for concept in concepts)


def test_unconfirmed_identity_material_is_rejected():
    service = AdviceEssayService(MemoryRepository())
    with pytest.raises(ValueError, match="confirmed"):
        service.add_identity_material(IdentityMaterial(owner_id=uuid4(), label="Claim", description="Unverified story", user_confirmed=False))


def test_critique_flags_cliche_without_rewriting_draft():
    owner = uuid4(); service = AdviceEssayService(MemoryRepository())
    critique = service.critique(owner, "Describe intellectual curiosity", "Since I was a child, science changed my life.")
    assert any(f.dimension.value == "cliches" for f in critique.findings)
    assert "writer remains responsible" in critique.authorship_notice.lower()
