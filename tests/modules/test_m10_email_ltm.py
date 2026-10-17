"""Module 10 spec seam: incoming emails embedded and stored in the tenant LTM.

Spec (Module 10, Email Assistant): "Incoming emails are ingested, embedded,
and stored in the LTM." The LTM is core.vector_store.memory_embeddings
(tenant_id + namespace scoped; account scope travels in metadata_json).

These tests run against a real embedded PostgreSQL with pgvector (pgserver)
and fixture GmailRawMessage inputs only - no Gmail network access, no real
private email.
"""

import asyncio
import hashlib
import math
import re

import httpx
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core.token_crypto import TokenCipher
from app.core.vector_store import MemoryEmbeddingRow
from app.modules.m10_email_assistant.gmail import GmailRawMessage
from app.modules.m10_email_assistant.ltm import (
    NAMESPACE,
    EmailLtmStore,
    SyncProviderEmbedder,
    configured_email_ltm,
)
from app.modules.m10_email_assistant.service import NullEmbedder, Service
from app.modules.m10_email_assistant.sql_repository import SqlEmailRepository

MASTER = "test-master-secret"
MODEL_ID = "deterministic-hashing-bow-1024d-fixture-v1"


class HashingBow1024:
    """Truthful fixture provider: a deterministic hashing bag-of-words, not a
    trained model. The model_id says exactly what it is. Mirrors m20's
    DeterministicEmbedding algorithm; defined locally so this lane's tests do
    not import the m20 package closure."""

    dimensions = 1024
    model_id = MODEL_ID

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        tokens = re.findall(r"[a-z0-9]+", text.lower())
        if not tokens:
            return vector
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(v * v for v in vector))
        if norm == 0.0:
            return vector
        return [v / norm for v in vector]


def fixture_embedder() -> SyncProviderEmbedder:
    return SyncProviderEmbedder(HashingBow1024())


class FakeGmailClient:
    def __init__(self, profile=None, history=None, messages=None):
        self.profile = profile or {"emailAddress": "me@example.com", "historyId": "100"}
        self.history = history or {}
        self.messages = messages or {}

    async def get_profile(self, access_token):
        return self.profile

    async def list_history(self, access_token, start_history_id):
        return self.history.get(start_history_id, [])

    async def get_message(self, access_token, message_id):
        return self.messages[message_id]


class ApprovalSpy:
    def __init__(self):
        self.items = []

    def put(self, item, *, user_id=None):
        self.items.append((item, user_id))
        return item


async def fake_generate(prompt, provider, model):
    if prompt.startswith("Extract action items"):
        return model or "test-model", "[]"
    return model or "test-model", "Subject: Re: hello\nThanks, I will handle it."


def raw_message(gmail_id, subject, body, sender="someone@example.com", thread="t1"):
    return GmailRawMessage(
        gmail_id=gmail_id, thread_id=thread, history_id="101", subject=subject,
        sender=sender, recipients=["me@example.com"], snippet=body[:40],
        body_text=body, received_at=1730000000.0, labels=["INBOX"], headers={},
    )


@pytest.fixture
def pg(tmp_path):
    pgserver = pytest.importorskip("pgserver")
    server = pgserver.get_server(tmp_path / "pg", cleanup_mode="stop")
    engine = sa.create_engine(server.get_uri().replace("postgresql://", "postgresql+psycopg://"))
    try:
        with engine.begin() as conn:
            conn.execute(sa.text("CREATE EXTENSION vector"))
        Base.metadata.create_all(engine)
        yield engine
    finally:
        engine.dispose()
        server.cleanup()


def make_service(engine, tenant="tenant-a", gmail=None, ltm_store=None):
    sessions = sessionmaker(bind=engine)
    repo = SqlEmailRepository(tenant, sessions)
    approvals = ApprovalSpy()
    client = httpx.AsyncClient(transport=httpx.MockTransport(
        lambda req: httpx.Response(200, json={"access_token": "at", "expires_in": 3600})))
    service = Service(
        repo, approvals, gmail or FakeGmailClient(), client,
        cipher=TokenCipher(tenant, master_secret=MASTER),
        google_client_id="cid", google_client_secret="sec",
        pubsub_verification_token="good-token",
        llm_generate=fake_generate,
        ltm_store=ltm_store,
    )
    return service, repo, approvals, client


def add_account(repo, account_id, email):
    repo.save_account(
        account_id=account_id, email_address=email,
        encrypted_refresh_token=TokenCipher("tenant-a", master_secret=MASTER).encrypt("rt"),
        history_id="100", watch_expiration=None,
    )


def ltm_rows(engine, tenant):
    with engine.connect() as conn:
        return list(conn.execute(
            sa.select(MemoryEmbeddingRow).where(MemoryEmbeddingRow.tenant_id == tenant)
        ).mappings())


def test_incoming_email_embedded_and_stored_in_tenant_ltm(pg):
    store = EmailLtmStore(
        tenant_id="tenant-a", session_factory=sessionmaker(bind=pg),
        embedder=fixture_embedder(),
    )
    raw = raw_message("gmail-1", "Grant deadline Friday",
                      "Please submit the proposal before Friday noon.")
    gmail = FakeGmailClient(history={"100": ["gmail-1"]}, messages={"gmail-1": raw})
    service, repo, _, client = make_service(pg, gmail=gmail, ltm_store=store)
    add_account(repo, "acct-a", "me@example.com")

    result = asyncio.run(service.ingest_from_history("me@example.com", "105"))
    assert result.new_messages == 1

    rows = ltm_rows(pg, "tenant-a")
    assert rows, "spec: incoming emails are embedded and stored in the LTM"
    row = rows[0]
    assert row["namespace"] == NAMESPACE == "m10-email-v1"
    metadata = row["metadata_json"]
    assert metadata["account_id"] == "acct-a"
    assert metadata["gmail_id"] == "gmail-1"
    assert metadata["model_id"] == MODEL_ID
    assert len(metadata["sha256"]) == 64
    embedding = list(row["embedding"])
    assert len(embedding) == 1024 and any(embedding)

    hits = asyncio.run(store.retrieve(
        account_id="acct-a", query="grant proposal deadline", limit=4))
    assert hits, "stored email must be retrievable from the LTM"
    citation = hits[0]["citation"]
    assert citation["source_id"] == "gmail-1"
    assert citation["account_id"] == "acct-a"
    assert citation["sha256"] == metadata["sha256"]
    asyncio.run(client.aclose())


def test_cross_account_retrieval_returns_nothing(pg):
    sessions = sessionmaker(bind=pg)
    store = EmailLtmStore(tenant_id="tenant-a", session_factory=sessions,
                          embedder=fixture_embedder())
    asyncio.run(store.store_message(
        account_id="acct-a", gmail_id="gmail-1",
        subject="Quarterly budget review", body_text="The budget numbers are ready."))

    hits = asyncio.run(store.retrieve(
        account_id="acct-b", query="quarterly budget numbers", limit=8))
    assert hits == [], "account-scoped retrieval must fail closed across accounts"


def test_cross_tenant_retrieval_returns_nothing(pg):
    sessions = sessionmaker(bind=pg)
    store_a = EmailLtmStore(tenant_id="tenant-a", session_factory=sessions,
                            embedder=fixture_embedder())
    store_b = EmailLtmStore(tenant_id="tenant-b", session_factory=sessions,
                            embedder=fixture_embedder())
    asyncio.run(store_a.store_message(
        account_id="acct-a", gmail_id="gmail-1",
        subject="Secret tenant-a plans", body_text="tenant-a roadmap details"))

    assert asyncio.run(store_b.retrieve(
        account_id="acct-a", query="secret tenant-a roadmap", limit=8)) == []
    assert ltm_rows(pg, "tenant-b") == []


def test_reingestion_upserts_deterministic_ids(pg):
    sessions = sessionmaker(bind=pg)
    store = EmailLtmStore(tenant_id="tenant-a", session_factory=sessions,
                          embedder=fixture_embedder())
    kwargs = dict(account_id="acct-a", gmail_id="gmail-1",
                  subject="Weekly sync", body_text="Agenda for the weekly sync.")
    first = asyncio.run(store.store_message(**kwargs))
    second = asyncio.run(store.store_message(**kwargs))
    assert first["ids"] == second["ids"], "ids must be deterministic per (tenant, account, gmail message)"
    rows = ltm_rows(pg, "tenant-a")
    assert len(rows) == len(first["ids"]), "re-ingestion must upsert, not duplicate"


def test_account_filter_applies_before_limit(pg):
    """With more account-B rows than `candidates`, an account-A row still
    surfaces for account A: the account filter runs in SQL before ranking
    limits, not as a post-filter after them."""
    sessions = sessionmaker(bind=pg)
    store = EmailLtmStore(tenant_id="tenant-a", session_factory=sessions,
                          embedder=fixture_embedder())
    for index in range(5):
        asyncio.run(store.store_message(
            account_id="acct-b", gmail_id=f"gmail-b-{index}",
            subject=f"invoice {index}",
            body_text="invoice payment remittance advice wire transfer"))
    asyncio.run(store.store_message(
        account_id="acct-a", gmail_id="gmail-a-1",
        subject="invoice question",
        body_text="one question about the invoice timeline"))

    hits = asyncio.run(store.retrieve(
        account_id="acct-a", query="invoice remittance", limit=1, candidates=2))
    assert [hit["citation"]["source_id"] for hit in hits] == ["gmail-a-1"]


def test_ltm_store_refuses_unqualified_embedder(pg):
    sessions = sessionmaker(bind=pg)
    class WrongDims(HashingBow1024):
        dimensions = 256

    class NoModelId(HashingBow1024):
        model_id = None

    with pytest.raises(ValueError, match="1024"):
        EmailLtmStore(tenant_id="tenant-a", session_factory=sessions,
                      embedder=SyncProviderEmbedder(WrongDims()))
    with pytest.raises(ValueError, match="model_id"):
        # A provider with no stable model_id is refused at binding.
        EmailLtmStore(tenant_id="tenant-a", session_factory=sessions,
                      embedder=SyncProviderEmbedder(NoModelId()))
    with pytest.raises(ValueError):
        EmailLtmStore(tenant_id="tenant-a", session_factory=sessions, embedder=None)
    with pytest.raises(ValueError):
        EmailLtmStore(tenant_id="tenant-a", session_factory=sessions,
                      embedder=NullEmbedder())


def test_ltm_store_fails_closed_on_unknown_account(pg):
    sessions = sessionmaker(bind=pg)
    store = EmailLtmStore(tenant_id="tenant-a", session_factory=sessions,
                          embedder=fixture_embedder())
    with pytest.raises(ValueError, match="account_id"):
        asyncio.run(store.store_message(
            account_id="", gmail_id="gmail-1", subject="s", body_text="b"))
    with pytest.raises(ValueError, match="account_id"):
        asyncio.run(store.retrieve(account_id="  ", query="q"))
    with pytest.raises(ValueError, match="gmail_id"):
        asyncio.run(store.store_message(
            account_id="acct-a", gmail_id="", subject="s", body_text="b"))


def test_ingestion_without_ltm_store_stays_truthful(pg):
    """No configured LTM store: ingestion still lands in the module tables and
    memory_embeddings stays empty. Nothing claims LTM storage that did not
    happen, and no placeholder vectors are invented."""
    raw = raw_message("gmail-1", "Hello", "a plain hello")
    gmail = FakeGmailClient(history={"100": ["gmail-1"]}, messages={"gmail-1": raw})
    service, repo, _, client = make_service(pg, gmail=gmail, ltm_store=None)
    add_account(repo, "acct-a", "me@example.com")

    result = asyncio.run(service.ingest_from_history("me@example.com", "105"))
    assert result.new_messages == 1
    assert ltm_rows(pg, "tenant-a") == []
    asyncio.run(client.aclose())


def test_ltm_failure_leaves_nothing_durable_and_retry_is_clean(pg):
    """An embedding/storage failure must not strand half-ingested state: no
    saved message, no action items, no draft, no LTM row. The Pub/Sub retry
    then reprocesses cleanly and redelivery upserts instead of duplicating."""
    class FailingEmbedder:
        dimensions = 1024
        model_id = MODEL_ID

        async def embed(self, texts):
            raise RuntimeError("embedding backend unavailable")

    sessions = sessionmaker(bind=pg)
    failing = EmailLtmStore(tenant_id="tenant-a", session_factory=sessions,
                            embedder=FailingEmbedder())
    raw = raw_message("gmail-1", "Grant deadline Friday",
                      "Please submit the proposal before Friday noon.")
    gmail = FakeGmailClient(history={"100": ["gmail-1"]}, messages={"gmail-1": raw})
    service, repo, _, client = make_service(pg, gmail=gmail, ltm_store=failing)
    add_account(repo, "acct-a", "me@example.com")

    with pytest.raises(RuntimeError, match="embedding backend unavailable"):
        asyncio.run(service.ingest_from_history("me@example.com", "105"))
    assert repo.has_message("gmail-1", "acct-a") is False
    assert repo.list_drafts() == []
    assert ltm_rows(pg, "tenant-a") == []

    working = EmailLtmStore(tenant_id="tenant-a", session_factory=sessions,
                            embedder=fixture_embedder())
    service, repo, _, client = make_service(pg, gmail=gmail, ltm_store=working)
    result = asyncio.run(service.ingest_from_history("me@example.com", "105"))
    assert result.new_messages == 1
    rows_after_ingest = ltm_rows(pg, "tenant-a")
    assert rows_after_ingest, "retry must complete the LTM write"

    redelivery = asyncio.run(service.ingest_from_history("me@example.com", "106"))
    assert redelivery.new_messages == 0
    assert [row["id"] for row in ltm_rows(pg, "tenant-a")] == [row["id"] for row in rows_after_ingest]
    asyncio.run(client.aclose())


def test_configured_email_ltm_defaults_to_free_local(pg, monkeypatch):
    """Free-on-PC is settled: with no M10-scoped selection the factory binds
    the local Ollama provider. A globally present OPENAI_API_KEY must NOT
    activate paid embedding for M10 - paid requires an explicit M10 grant."""
    monkeypatch.delenv("ATLAS_M10_EMBEDDING_PROVIDER", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-should-not-be-inferred")
    store = configured_email_ltm("tenant-a", sessionmaker(bind=pg))
    assert isinstance(store, EmailLtmStore)
    assert store.model_id == "ollama:bge-m3"
    assert store.embedder.dimensions == 1024


def test_configured_email_ltm_explicit_paid_grant(pg, monkeypatch):
    """Explicit M10-scoped paid selection binds OpenAI. Construction only -
    no paid call is made by binding."""
    monkeypatch.setenv("ATLAS_M10_EMBEDDING_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-explicit-grant")
    store = configured_email_ltm("tenant-a", sessionmaker(bind=pg))
    assert store.model_id == "openai:text-embedding-3-large"


def test_configured_email_ltm_paid_grant_without_credential_raises(pg, monkeypatch):
    monkeypatch.setenv("ATLAS_M10_EMBEDDING_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        configured_email_ltm("tenant-a", sessionmaker(bind=pg))


def test_configured_email_ltm_refuses_unverified_model(pg, monkeypatch):
    monkeypatch.setenv("ATLAS_OLLAMA_EMBEDDING_MODEL", "some-unverified-model")
    with pytest.raises(ValueError, match="1024-dimension"):
        configured_email_ltm("tenant-a", sessionmaker(bind=pg))


def test_configured_email_ltm_refuses_unknown_provider(pg, monkeypatch):
    monkeypatch.setenv("ATLAS_M10_EMBEDDING_PROVIDER", "bogus-provider")
    with pytest.raises(ValueError, match="misconfigured"):
        configured_email_ltm("tenant-a", sessionmaker(bind=pg))


def _route_service_or_error(monkeypatch):
    monkeypatch.setenv("ATLAS_TOKEN_KEY", MASTER)
    from fastapi import HTTPException
    from app.auth.context import TenantContext
    from app.modules.m10_email_assistant import routes

    async def build():
        agen = routes.get_service(TenantContext(tenant_id="tenant-a", actor_id="tester"))
        try:
            service = await agen.__anext__()
        except HTTPException as exc:
            return exc
        await agen.aclose()
        return service

    return asyncio.run(build())


def test_route_wires_free_local_ltm_store_by_default(monkeypatch):
    """Production wiring: default configuration binds a real local store on
    the route-constructed Service - not None, not a Null object."""
    monkeypatch.delenv("ATLAS_M10_EMBEDDING_PROVIDER", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    service = _route_service_or_error(monkeypatch)
    assert isinstance(service.ltm_store, EmailLtmStore)
    assert service.ltm_store.model_id == "ollama:bge-m3"
    assert service.ltm_store.tenant_id == "tenant-a"


def test_route_reports_misconfiguration_as_503(monkeypatch):
    """Unknown provider: truthful 503 with the reason, not hidden absence."""
    from fastapi import HTTPException

    monkeypatch.setenv("ATLAS_M10_EMBEDDING_PROVIDER", "bogus-provider")
    result = _route_service_or_error(monkeypatch)
    assert isinstance(result, HTTPException)
    assert result.status_code == 503
    assert "bogus-provider" in result.detail


def test_midbatch_embedding_failure_commits_no_partial_chunks(pg):
    """A failure partway through embedding a multi-chunk message happens
    before the single storage transaction opens: zero LTM rows, not a
    partial chunk set."""
    class MidBatchFailingEmbedder:
        dimensions = 1024
        model_id = MODEL_ID

        def __init__(self):
            self.calls = 0

        async def embed(self, texts):
            vectors = []
            for text in texts:
                self.calls += 1
                if self.calls == 2:
                    raise RuntimeError("embedder failed mid-batch")
                vectors.append(HashingBow1024().embed(text))
            return vectors

    sessions = sessionmaker(bind=pg)
    store = EmailLtmStore(tenant_id="tenant-a", session_factory=sessions,
                          embedder=MidBatchFailingEmbedder())
    long_body = "quarterly report details " * 400  # forces multiple chunks
    with pytest.raises(RuntimeError, match="mid-batch"):
        asyncio.run(store.store_message(
            account_id="acct-a", gmail_id="gmail-long",
            subject="Long report", body_text=long_body))
    assert ltm_rows(pg, "tenant-a") == []


def test_post_ltm_commit_failure_leaves_vectors_only_and_retry_converges(pg):
    """Accurate partial-memory semantics: store_message commits its own
    transaction BEFORE the module rows. If save_message then raises, the LTM
    rows exist without the module message - NOT zero durable state. The
    retry reprocesses (has_message gate is still False), the vector upsert
    lands on the same deterministic ids, and nothing duplicates."""
    sessions = sessionmaker(bind=pg)
    store = EmailLtmStore(tenant_id="tenant-a", session_factory=sessions,
                          embedder=fixture_embedder())
    raw = raw_message("gmail-1", "Grant deadline Friday",
                      "Please submit the proposal before Friday noon.")
    gmail = FakeGmailClient(history={"100": ["gmail-1"]}, messages={"gmail-1": raw})
    service, repo, _, client = make_service(pg, gmail=gmail, ltm_store=store)
    add_account(repo, "acct-a", "me@example.com")

    original_save = repo.save_message
    def failing_save(**kwargs):
        raise RuntimeError("module table write failed")
    repo.save_message = failing_save
    with pytest.raises(RuntimeError, match="module table write failed"):
        asyncio.run(service.ingest_from_history("me@example.com", "105"))

    orphaned = ltm_rows(pg, "tenant-a")
    assert orphaned, "vector rows commit before the module message: partial state is real"
    assert repo.has_message("gmail-1", "acct-a") is False
    assert repo.list_drafts() == []

    repo.save_message = original_save
    result = asyncio.run(service.ingest_from_history("me@example.com", "105"))
    assert result.new_messages == 1
    converged = ltm_rows(pg, "tenant-a")
    assert [row["id"] for row in converged] == [row["id"] for row in orphaned]
    assert len(converged) == len(orphaned), "retry upserts: no duplicate vectors"
    asyncio.run(client.aclose())
