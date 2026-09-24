import asyncio

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.integrations.google_grounding import GroundedSource
from app.modules.m02_competition_manager.evidence import score_from_corpus
from app.modules.m02_competition_manager.profile_corpus import ProfileCorpus


class Emb:
    async def embed(self, texts):
        return [[1, 0] if "club" in t.lower() else [0, 1] for t in texts]


def _corpora(tmp_path):
    e = create_engine(f"sqlite:///{tmp_path/'c.db'}")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)
    a, b = ProfileCorpus("a", Emb(), s), ProfileCorpus("b", Emb(), s)
    asyncio.run(a.ingest([
        GroundedSource("google_doc", "d1", "p1", "In 2025 I founded the Bioplex reading club and grew it to 40 members.", {"title": "Activities"}),
        GroundedSource("google_sheet", "s1", "A4", "Regional science fair 2024: second place for a protein folding poster.", {"title": "Awards"}),
    ]))
    asyncio.run(b.ingest([GroundedSource("google_doc", "x", "p1", "Tenant b private note.", {})]))
    return a, b


def _ids(corpus):
    return [s["id"] for s in asyncio.run(corpus.retrieve("anything", 10))]


def test_source_ids_load_from_stored_corpus_in_marker_order(tmp_path):
    a, _ = _corpora(tmp_path)
    club = asyncio.run(a.retrieve("reading club", 1))[0]["id"]
    fair = [i for i in _ids(a) if i != club][0]
    out = asyncio.run(score_from_corpus(a, {"why": {
        "draft": "I founded the Bioplex reading club in 2025. [2] I placed second at the regional science fair in 2024. [1]",
        "source_ids": [fair, club]}}))
    assert out["complete"] is True
    assert out["fields"]["why"]["source_resolution"] == {"origin": "corpus_ids", "missing_source_ids": []}


def test_other_tenant_ids_are_missing_not_leaked(tmp_path):
    a, b = _corpora(tmp_path)
    foreign = _ids(b)[0]
    club = asyncio.run(a.retrieve("reading club", 1))[0]["id"]
    out = asyncio.run(score_from_corpus(a, {"why": {
        "draft": "I founded the Bioplex reading club in 2025. [1] Tenant b private note. [2]",
        "source_ids": [club, foreign]}}))
    assert out["complete"] is False and out["blocking_fields"] == ["why"]
    assert out["fields"]["why"]["source_resolution"]["missing_source_ids"] == [foreign]
    assert "private" not in str([s for s in asyncio.run(a.retrieve("x", 10))])


def test_question_reruns_drafter_query_and_flags_drift(tmp_path):
    a, _ = _corpora(tmp_path)
    out = asyncio.run(score_from_corpus(a, {"why": {
        "draft": "I founded the Bioplex reading club in 2025. [1]",
        "question": "Tell us about a club you started", "evidence_limit": 1}}))
    assert out["complete"] is True
    assert out["fields"]["why"]["source_resolution"] == {"origin": "corpus_query", "marker_drift_possible": True}


def test_empty_corpus_or_no_source_path_blocks(tmp_path):
    _, _ = _corpora(tmp_path)
    e = create_engine(f"sqlite:///{tmp_path/'empty.db'}"); Base.metadata.create_all(e)
    empty = ProfileCorpus("z", Emb(), sessionmaker(bind=e))
    out = asyncio.run(score_from_corpus(empty, {
        "q": {"draft": "I won a national award. [1]", "question": "Awards?"},
        "n": {"draft": "I won a national award. [1]"}}))
    assert out["complete"] is False and set(out["blocking_fields"]) == {"q", "n"}
    assert out["fields"]["n"]["source_resolution"]["blocking"]
