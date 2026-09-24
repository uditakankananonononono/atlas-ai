"""M01 live NLP stack: real spaCy, dateparser and embedding models.

The model-backed tests load the actual checkpoints (en_core_web_sm and
BAAI/bge-small-en-v1.5 via fastembed). They skip only when the optional
model cannot be installed/downloaded on the machine, and say so.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.modules.m01_opportunity_discovery import nlp_stack as ns
from app.modules.m01_opportunity_discovery.schemas import ProfileIn, SourceKind
from app.modules.m01_opportunity_discovery.service import Service, Source

NOW = datetime(2026, 9, 24, 6, 0, tzinfo=timezone.utc)

FEED = b"""<rss><channel>
<item><title>Global Robotics Challenge 2027</title><link>https://example.org/robotics</link>
<description>MIT and NASA invite high school teams to build autonomous rovers. Posted September 1, 2026. Applications close March 3, 2027. Finals in Boston.</description></item>
<item><title>Poetry Prize for Young Writers</title><link>https://example.org/poetry</link>
<description>A literary award for original sonnets and free verse. Deadline: 15 January 2027.</description></item>
</channel></rss>"""


@pytest.fixture(scope="module")
def nlp():
    spacy = pytest.importorskip("spacy")
    try:
        return spacy.load("en_core_web_sm")
    except OSError:
        pytest.skip("en_core_web_sm not installed")


@pytest.fixture(scope="module")
def fastembed_backend():
    pytest.importorskip("fastembed")
    try:
        return ns.FastEmbedBackend()
    except ns.EmbeddingBackendError as exc:
        pytest.skip(f"fastembed model unavailable: {exc}")


def _service(**kwargs):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    source = Source("feed", "Feed", SourceKind.RSS, "https://example.org/feed")
    return Service(session_factory=sessions, fetcher=lambda _: FEED, sources=[source], tenant_id="t1", **kwargs)


PROFILE = ProfileIn(interests=["robotics", "autonomous vehicles"], skills=["python", "embedded systems"])


# -- real models --------------------------------------------------------------


def test_spacy_entities_are_real_and_filtered(nlp):
    norm = ns.LiveNormalizer(nlp, now=lambda: NOW)
    tags = norm.entities("MIT and NASA invite teams to Boston for the rover finals on March 3, 2027.")
    assert "org:MIT" in tags and "org:NASA" in tags and "gpe:Boston" in tags
    assert not any(tag.startswith("date:") for tag in tags)  # dates go to dateparser, not tags
    assert norm.entity_engine == "spacy:en_core_web_sm"


def test_deadline_uses_cue_not_posting_date(nlp):
    norm = ns.LiveNormalizer(nlp, now=lambda: NOW)
    text = "Posted September 1, 2026. Applications close March 3, 2027 at 5pm. Finals in May."
    assert norm.deadline(text) == datetime(2027, 3, 3, 17, 0, tzinfo=timezone.utc)
    assert norm.deadline("Finals in Boston on 12 June 2027.") is None  # no deadline cue -> no guess


def test_deadline_respects_tenant_timezone(nlp):
    norm = ns.LiveNormalizer(nlp, timezone_name="Asia/Kolkata", now=lambda: NOW)
    assert norm.deadline("Apply by 10 October 2026 11:30 pm") == datetime(2026, 10, 10, 18, 0, tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        ns.LiveNormalizer(nlp, timezone_name="Mars/Olympus")


def test_relative_deadline_anchors_to_now(nlp):
    norm = ns.LiveNormalizer(nlp, now=lambda: NOW)
    found = norm.deadline("Registration closes in 2 weeks.")
    assert found is not None and 13 <= (found - NOW).days <= 14


def test_fastembed_similarity_ranks_by_meaning(fastembed_backend):
    matcher = ns.LiveEmbeddingMatcher(fastembed_backend)
    profile = "robotics, autonomous vehicles, python, embedded systems"
    rover = matcher.similarity("Build a self-driving rover with microcontrollers", profile)
    poem = matcher.similarity("Write a sonnet for a literary award", profile)
    assert 0.0 <= poem < rover <= 1.0
    assert rover - poem > 0.1
    assert matcher.engine == "embedding:fastembed:BAAI/bge-small-en-v1.5"


def test_full_scan_on_live_stack_records_provenance(nlp, fastembed_backend):
    stack = ns.build_nlp_stack(spacy_loader=lambda _: nlp, backend_factory=lambda _: fastembed_backend)
    assert stack.describe()["live"] is True
    stack.normalizer._now = lambda: NOW
    service = _service(nlp_stack=stack)
    result = service.run_scan(profile=PROFILE)
    assert result.new == 2
    items = {item.url: item for item in service.list_opportunities()}
    robot, poem = items["https://example.org/robotics"], items["https://example.org/poetry"]
    assert robot.match_score > poem.match_score
    assert robot.match_engine == poem.match_engine == "embedding:fastembed:BAAI/bge-small-en-v1.5"
    assert robot.deadline == datetime(2027, 3, 3, tzinfo=timezone.utc)
    assert poem.deadline == datetime(2027, 1, 15, tzinfo=timezone.utc)
    assert robot.deadline_engine == "dateparser:UTC"
    assert "org:NASA" in robot.tags and "gpe:Boston" in robot.tags
    assert service.nlp_status()["match_engine"].startswith("embedding:fastembed")


# -- fallbacks are explicit, never silent -------------------------------------


class _DownBackend:
    kind, model = "ollama", "bge-m3"

    def embed(self, texts):
        raise ns.EmbeddingBackendError("Ollama unreachable at http://ollama:11434: ConnectError")


def test_backend_failure_falls_back_per_item_with_reason():
    service = _service(embedding_matcher=ns.LiveEmbeddingMatcher(_DownBackend()))
    service.run_scan(profile=PROFILE)
    item = service.list_opportunities()[0]
    assert item.match_engine.startswith("token-cosine:fallback(Ollama unreachable")


def test_missing_components_are_reported_not_hidden():
    def no_model(name):
        raise OSError("not found")

    def no_backend(provider):
        raise ns.EmbeddingBackendError("fastembed is not installed (pip install fastembed)")

    stack = ns.build_nlp_stack(spacy_loader=no_model, backend_factory=no_backend)
    status = stack.describe()
    assert status["live"] is False
    assert "en_core_web_sm" in status["degraded"]["normalizer"]
    assert "fastembed" in status["degraded"]["matcher"]
    assert status["match_engine"] == "token-cosine" and status["deadline_engine"] == "regex-formats"


def test_token_opt_out_and_unknown_provider():
    assert "opted out" in ns.build_nlp_stack(embedding_provider="token", spacy_loader=lambda _: (_ for _ in ()).throw(OSError())).degraded["matcher"]
    stack = ns.build_nlp_stack(embedding_provider="bogus", spacy_loader=lambda _: (_ for _ in ()).throw(OSError()))
    assert "unsupported embedding provider" in stack.degraded["matcher"]


def test_openai_is_never_default_and_needs_key(monkeypatch):
    monkeypatch.delenv("ATLAS_M01_EMBEDDING_PROVIDER", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    chosen = []
    ns.build_nlp_stack(spacy_loader=lambda _: (_ for _ in ()).throw(OSError()), backend_factory=lambda p: chosen.append(p) or _DownBackend())
    assert chosen == ["fastembed"]
    with pytest.raises(ns.EmbeddingBackendError, match="OPENAI_API_KEY"):
        ns.OpenAIBackend()


def test_ollama_backend_against_mock_server():
    import httpx

    def handler(request):
        assert request.url.path == "/api/embed"
        return httpx.Response(200, json={"embeddings": [[1.0, 0.0], [0.0, 1.0]]})

    backend = ns.OllamaBackend("http://local", client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert backend.embed(["a", "b"]) == [[1.0, 0.0], [0.0, 1.0]]


def test_route_uses_live_stack(monkeypatch):
    from app.modules.m01_opportunity_discovery import routes

    sentinel = ns.NlpStack(None, None, "keyword-tags", "regex-formats", "token-cosine", {"matcher": "x"})
    monkeypatch.setattr(routes, "default_stack", lambda: sentinel)

    class Tenant:
        tenant_id = "t9"

    service = routes.get_service(Tenant())
    assert service._nlp_stack is sentinel
    assert routes.nlp_status(service).degraded == {"matcher": "x"}
