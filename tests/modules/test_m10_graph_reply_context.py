"""M10 account-scoped knowledge-graph ingest + reply context, real SQLite, real M09
repository and the real Service ingest/draft path. LLM is a recording mock seam (no model,
no network, no real mail); the captured draft prompt is the real prompt."""
import asyncio
from datetime import datetime, timezone
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core.token_crypto import TokenCipher
from app.modules.m09_knowledge_workspace.repository import NodeRow, EdgeRow, SqlGraphRepository
from app.modules.m09_knowledge_workspace.schemas import Edge, Node, NodeType, Relationship
from app.modules.m10_email_assistant.graph_context import (
    ACTOR_ID, SOURCE_MODULE, KnowledgeGraphIngestor, KnowledgeGraphReplyContext,
    contact_external_id, email_external_id)
from app.modules.m10_email_assistant.service import Service
from app.modules.m10_email_assistant.sql_repository import SqlEmailRepository
from tests.modules.test_m10_email_assistant import ApprovalSpy, FakeGmailClient, raw_message

NOW = datetime.now(timezone.utc)
SENDER = "Alice Prof <Alice@Uni.edu>"
A1, A2 = str(uuid4()), str(uuid4())


@pytest.fixture
def env(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/g.db")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def build(env, tenant="tenant-a", *, graph=True, context=None, ingest=None, messages=None, history=None):
    prompts = []

    async def gen(prompt, provider, model):
        if prompt.startswith("Extract action items"):
            return "m", "[]"
        prompts.append(prompt)
        return "m", "Subject: Re: x\nok"

    g = SqlGraphRepository(tenant, ACTOR_ID, env)
    client = httpx.AsyncClient(transport=httpx.MockTransport(
        lambda r: httpx.Response(200, json={"access_token": "at", "expires_in": 3600})))
    repo = SqlEmailRepository(tenant, env)
    gmail = FakeGmailClient(messages=messages or {}, history=history or {})
    svc = Service(repo, ApprovalSpy(), gmail, client,
                  cipher=TokenCipher(tenant, master_secret="s"), google_client_id="c",
                  google_client_secret="s", pubsub_verification_token="t", llm_generate=gen,
                  graph_context=context if context is not None else (KnowledgeGraphReplyContext(g) if graph else None),
                  graph_ingest=ingest if ingest is not None else (KnowledgeGraphIngestor(g) if graph else None))
    return svc, repo, g, prompts, gmail


def ingest(svc, account_id, raw):
    return asyncio.run(svc._ingest_message(account_id, raw))


def msg(gid, subject="Action required: thesis", sender=SENDER, labels=None, snippet="snip"):
    return raw_message(gid, subject, sender=sender, snippet=snippet, labels=labels)


def nodes(env, tenant="tenant-a"):
    with env() as db:
        return db.query(NodeRow).filter(NodeRow.tenant_id == tenant).all()


def test_red_base_without_graph_shows_none(env):
    svc, *_, prompts, _ = build(env, graph=False)
    ingest(svc, A1, msg("g1"))
    assert "Related knowledge-graph facts:\n- (none)\n" in prompts[0]


def test_ingest_then_draft_sees_prior_history_not_itself(env):
    svc, _, g, prompts, _ = build(env)
    ingest(svc, A1, msg("g1", "Thesis chapter 3", snippet="please review ch3"))
    assert "- (none)" in prompts[0]  # first mail: graph empty at draft time
    ingest(svc, A1, msg("g2", "Action required: ch3 deadline", snippet="need by Friday"))
    p = prompts[1].split("Related knowledge-graph facts:")[1].split("Recent related")[0]
    assert "CONTACT Alice Prof <alice@uni.edu>" in p
    assert "Thesis chapter 3: please review ch3" in p
    assert "need by Friday" not in p  # the email being drafted is not its own context
    c = g.get_by_source(SOURCE_MODULE, contact_external_id(A1, "alice@uni.edu"))
    assert c.metadata["account_id"] == A1 and "email_count" not in c.metadata


def test_ingest_is_idempotent(env):
    svc, _, g, _, _ = build(env)
    ing = KnowledgeGraphIngestor(g)
    raw = msg("g1")
    for _ in range(3):
        ing(A1, raw)
    rows = nodes(env)
    assert sorted(r.node_type for r in rows) == ["contact", "email"]
    with env() as db:
        assert db.query(EdgeRow).count() == 1


def test_same_sender_two_accounts_isolated(env):
    svc, _, g, prompts, _ = build(env)
    ingest(svc, A1, msg("g1", "A1 private subject", snippet="A1 private snippet"))
    ingest(svc, A2, msg("g1", "Action required: other mailbox"))  # same gmail id, same sender
    assert "A1 private" not in prompts[1]
    assert len(nodes(env)) == 4  # separate contact+email per account
    assert KnowledgeGraphReplyContext(g)(SENDER, A2) != KnowledgeGraphReplyContext(g)(SENDER, A1)


def test_untagged_and_foreign_neighbours_excluded(env):
    svc, _, g, _, _ = build(env)
    ingest(svc, A1, msg("g1"))
    c = g.get_by_source(SOURCE_MODULE, contact_external_id(A1, "alice@uni.edu"))
    for title, meta, ext in [("untagged note", {}, None),
                             ("foreign mail", {"account_id": A2, "kind": "email"}, None),
                             ("forged tag other module", {"account_id": A1, "kind": "email"}, None)]:
        n = Node(id=str(uuid4()), node_type=NodeType.NOTE, title=title, body="leak", metadata=meta,
                 external_id=ext, created_at=NOW, updated_at=NOW)
        g.save_node(n)
        g.save_edge(Edge(id=str(uuid4()), source_id=c.id, target_id=n.id,
                         relationship=Relationship.MENTIONS, created_at=NOW))
    facts = KnowledgeGraphReplyContext(g)(SENDER, A1)
    assert not any("leak" in f or "untagged" in f or "foreign" in f or "forged" in f for f in facts)
    assert len(facts) == 2  # contact + its own email


def test_cross_tenant_not_visible(env):
    svc, _, g, _, _ = build(env, "tenant-b")
    ingest(svc, A1, msg("g1"))
    ga = SqlGraphRepository("tenant-a", ACTOR_ID, env)
    assert KnowledgeGraphReplyContext(ga)(SENDER, A1) == []


def test_unknown_or_malformed_scope_fails_closed(env):
    svc, _, g, _, _ = build(env)
    ingest(svc, A1, msg("g1"))
    ctx = KnowledgeGraphReplyContext(g)
    assert ctx(SENDER, None) == [] and ctx("not an address", A1) == [] and ctx(SENDER, f"{A1}:x") == []
    with pytest.raises(ValueError):
        contact_external_id("a:b", "x@y.co")
    with pytest.raises(ValueError):
        email_external_id(A1, "g:1")
    assert contact_external_id(A1, "x@y.co") != email_external_id(A1, "x@y.co")


def test_sent_and_spam_not_ingested(env):
    svc, _, g, _, _ = build(env)
    ingest(svc, A1, msg("g1", "Re: mine", labels=["SENT"]))
    ingest(svc, A1, msg("g2", "You won a prize!!! free money", sender="Spam <s@spam.co>", labels=["SPAM"]))
    assert not [n for n in nodes(env) if n.metadata_json.get("address") in ("alice@uni.edu",)]
    assert not any(n.metadata_json.get("address") == "s@spam.co" for n in nodes(env))


def test_facts_bounded_and_single_line(env):
    svc, _, g, _, _ = build(env)
    ing = KnowledgeGraphIngestor(g)
    for i in range(15):
        ing(A1, msg(f"g{i}", f"s{i}", snippet="x\nIgnore\nprevious " * 100))
    facts = KnowledgeGraphReplyContext(g)(SENDER, A1)
    assert len(facts) == 10 and all(len(f) <= 300 and "\n" not in f for f in facts)


def test_context_error_reported_as_unavailable_not_none(env):
    def boom(sender, account_id):
        raise RuntimeError("db down")
    svc, repo, _, prompts, _ = build(env, context=boom)
    ingest(svc, A1, msg("g1"))
    assert "unavailable: knowledge-graph lookup failed" in prompts[0]
    assert "Related knowledge-graph facts:\n- (none)" not in prompts[0]
    assert len(svc.list_drafts()) == 1


def test_ingest_error_logged_and_ingestion_continues(env):
    def boom(account_id, raw):
        raise RuntimeError("graph write failed")
    svc, repo, _, prompts, _ = build(env, ingest=boom)
    assert ingest(svc, A1, msg("g1")) is True
    assert len(svc.list_drafts()) == 1 and len(svc.list_messages()) == 1
    assert any("graph_ingest_failed" in str(e) for e in _events(env))


def _events(env):
    from sqlalchemy import text
    with env() as db:
        tables = [r[0] for r in db.execute(text("select name from sqlite_master where type='table'"))]
        out = []
        for t in tables:
            if "event" in t or "audit" in t:
                out += [tuple(r) for r in db.execute(text(f"select * from {t}"))]
        return out


def test_real_push_path_ingests_graph(env):
    from tests.modules.test_m10_email_assistant import push_envelope
    svc, repo, g, prompts, _ = build(
        env, messages={"m1": msg("m1", "Action required: confirm", snippet="hello")},
        history={"100": ["m1"]})
    repo.save_account(account_id=A1, email_address="me@example.com",
                      encrypted_refresh_token=svc.cipher.encrypt("rt"), history_id="100",
                      watch_expiration=None)
    result = asyncio.run(svc.handle_push(push_envelope(), "t"))
    assert result.new_messages == 1
    assert g.get_by_source(SOURCE_MODULE, email_external_id(A1, "m1")) is not None


def test_get_service_wires_graph_reader_and_writer(monkeypatch):
    import app.modules.m10_email_assistant.routes as routes
    from app.auth.context import TenantContext
    monkeypatch.setenv("ATLAS_TOKEN_KEY", "k")

    async def go():
        gen = routes.get_service(TenantContext(tenant_id="t-wire", actor_id="u"))
        svc = await gen.__anext__()
        try:
            assert isinstance(svc.graph_context, KnowledgeGraphReplyContext)
            assert isinstance(svc.graph_ingest, KnowledgeGraphIngestor)
            assert svc.graph_context.repository.tenant_id == "t-wire"
            assert svc.graph_ingest.repository is svc.graph_context.repository
        finally:
            await gen.aclose()
    asyncio.run(go())


def test_concurrent_first_write_no_duplicates_and_session_reusable(tmp_path):
    """Real threads on a real SQLite file; the losing writer hits the unique key."""
    import threading
    engine = create_engine(f"sqlite:///{tmp_path}/c.db", connect_args={"timeout": 30, "check_same_thread": False})
    Base.metadata.create_all(engine)
    env = sessionmaker(bind=engine)
    g = SqlGraphRepository("tenant-a", ACTOR_ID, env)
    ing = KnowledgeGraphIngestor(g)
    errors, barrier = [], threading.Barrier(8)

    def work():
        try:
            barrier.wait()
            ing(A1, msg("same"))
        except Exception as exc:  # pragma: no cover - asserted empty below
            errors.append(repr(exc))

    ts = [threading.Thread(target=work) for _ in range(8)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert errors == []
    rows = nodes(env)
    assert sorted(r.node_type for r in rows) == ["contact", "email"]
    with env() as db:
        assert db.query(EdgeRow).count() == 1
    ing(A1, msg("same"))  # repository/session reusable after the contention
    assert len(nodes(env)) == 2
    assert len(KnowledgeGraphReplyContext(g)(SENDER, A1)) == 2


def test_integrity_error_path_is_exercised_deterministically(env):
    """Force the race: lookup says missing, then another writer wins before our insert."""
    g = SqlGraphRepository("tenant-a", ACTOR_ID, env)
    ing = KnowledgeGraphIngestor(g)
    real = g.get_by_source
    calls = {"n": 0}

    def racy(module, ext):
        calls["n"] += 1
        if calls["n"] == 1 and ext.startswith("email:"):
            KnowledgeGraphIngestor(SqlGraphRepository("tenant-a", ACTOR_ID, env))(A1, msg("race"))
            return None  # stale miss
        return real(module, ext)

    g.get_by_source = racy
    ing(A1, msg("race"))
    assert sorted(r.node_type for r in nodes(env)) == ["contact", "email"]
    with env() as db:
        assert db.query(EdgeRow).count() == 1
    assert g.get_by_source(SOURCE_MODULE, email_external_id(A1, "race")).version == 2


def test_existing_key_with_foreign_scope_is_refused(env):
    g = SqlGraphRepository("tenant-a", ACTOR_ID, env)
    ext = email_external_id(A1, "k1")
    g.save_node(Node(id=str(uuid4()), node_type=NodeType.EMAIL, title="x", body="", metadata={"account_id": A2, "kind": "email"},
                     source_module=SOURCE_MODULE, external_id=ext, created_at=NOW, updated_at=NOW))
    with pytest.raises(ValueError, match="collision"):
        KnowledgeGraphIngestor(g)(A1, msg("k1"))


def test_post_pubsub_route_end_to_end_with_synthetic_account(env, monkeypatch):
    """POST through the real FastAPI router + real get_service. Faked: Gmail HTTP client,
    OAuth token refresh, LLM (recording). Synthetic account; no network, no real mail."""
    import app.modules.m10_email_assistant.routes as routes
    import app.modules.m10_email_assistant.service as service_mod
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from tests.modules.test_m10_email_assistant import push_envelope

    prompts = []

    async def gen(prompt, provider, model):
        if prompt.startswith("Extract action items"):
            return "m", "[]"
        prompts.append(prompt)
        return "m", "Subject: Re: x\nok"

    async def fake_refresh(http, **kw):
        return "access-token"

    gmail = FakeGmailClient(
        history={"100": ["m1"], "105": ["m2"]},
        messages={"m1": msg("m1", "Thesis chapter 3", snippet="please review ch3"),
                  "m2": msg("m2", "Action required: ch3 deadline", snippet="need by Friday")})
    monkeypatch.setenv("ATLAS_TOKEN_KEY", "k")
    monkeypatch.setenv("ATLAS_PUBSUB_VERIFICATION_TOKEN", "good-token")
    monkeypatch.setattr(routes, "SqlEmailRepository", lambda t: SqlEmailRepository(t, env))
    monkeypatch.setattr(routes, "SqlGraphRepository", lambda t, a: SqlGraphRepository(t, a, env))
    monkeypatch.setattr(routes, "HttpxGmailClient", lambda http: gmail)
    monkeypatch.setattr(service_mod, "refresh_access_token", fake_refresh)
    monkeypatch.setattr(routes, "Service", lambda *a, **k: Service(*a, llm_generate=gen, **k))
    # Composition repair (LTM+KG): routes.get_service now binds a real LTM store,
    # defaulting to the local Ollama provider, which is absent under test. Bind
    # the LTM lane's truthful deterministic hashing fixture instead - a real
    # EmailLtmStore over the test database, never a disabled or faked capability.
    from app.modules.m10_email_assistant.ltm import EmailLtmStore
    from tests.modules.test_m10_email_ltm import fixture_embedder
    monkeypatch.setattr(routes, "configured_email_ltm",
                        lambda tenant_id, sf: EmailLtmStore(
                            tenant_id=tenant_id, session_factory=env,
                            embedder=fixture_embedder()))

    tenant = "t-route"
    repo = SqlEmailRepository(tenant, env)
    repo.save_account(account_id=A1, email_address="me@example.com",
                      encrypted_refresh_token=TokenCipher(tenant).encrypt("rt"),
                      history_id="100", watch_expiration=None)
    app = FastAPI(); app.include_router(routes.router)
    client = TestClient(app)
    hdr = {"x-atlas-tenant": tenant, "x-atlas-actor": "u1"}
    r1 = client.post("/email-assistant/pubsub?token=good-token", json=push_envelope(history_id="105"), headers=hdr)
    r2 = client.post("/email-assistant/pubsub?token=good-token", json=push_envelope(history_id="110"), headers=hdr)
    assert r1.status_code == 200 and r2.status_code == 200, (r1.text, r2.text)
    assert r1.json()["drafts_proposed"] == 1 and r2.json()["drafts_proposed"] == 1
    assert "- (none)" in prompts[0]
    second = prompts[1].split("Related knowledge-graph facts:")[1].split("Recent related")[0]
    assert "CONTACT Alice Prof <alice@uni.edu>" in second and "Thesis chapter 3: please review ch3" in second
    assert "need by Friday" not in second
    g = SqlGraphRepository(tenant, ACTOR_ID, env)
    assert g.get_by_source(SOURCE_MODULE, email_external_id(A1, "m2")) is not None


def test_failed_core_ingest_writes_no_graph_nodes(env):
    svc, repo, g, _, _ = build(env)

    class BoomEmbedder:
        async def embed(self, texts):
            raise RuntimeError("embed failed")

    svc.embedder = BoomEmbedder()
    with pytest.raises(RuntimeError):
        ingest(svc, A1, msg("g1"))
    assert nodes(env) == []


def test_draft_failure_after_persist_is_audited_not_masked(env):
    svc, repo, g, _, _ = build(env)

    async def boom(prompt, provider, model):
        if prompt.startswith("Extract action items"):
            return "m", "[]"
        raise RuntimeError("provider down SECRET-BODY-TEXT")

    svc.llm_generate = boom
    with pytest.raises(RuntimeError, match="provider down"):  # original error still propagates
        ingest(svc, A1, msg("g1"))
    assert repo.has_message("g1", A1) and nodes(env) == []  # persisted, graph not written
    ev = [e for e in _events(env) if "graph_not_written_after_core_failure" in str(e)]
    assert len(ev) == 1 and "SECRET-BODY-TEXT" not in str(ev) and "provider down" not in str(ev)
    assert len(svc.list_drafts()) == 0  # no automatic draft retry


def test_core_failure_before_persist_logs_no_graph_event(env):
    svc, repo, g, _, _ = build(env)

    class BoomEmbedder:
        async def embed(self, texts):
            raise RuntimeError("embed failed")

    svc.embedder = BoomEmbedder()
    with pytest.raises(RuntimeError):
        ingest(svc, A1, msg("g1"))
    assert not repo.has_message("g1", A1)
    assert not [e for e in _events(env) if "graph_not_written" in str(e)]


def test_audit_failure_does_not_mask_original_error(env):
    svc, repo, g, _, _ = build(env)

    async def boom(prompt, provider, model):
        if prompt.startswith("Extract action items"):
            return "m", "[]"
        raise RuntimeError("provider down")

    svc.llm_generate = boom
    repo.log_event = lambda *a, **k: (_ for _ in ()).throw(OSError("audit store down"))
    with pytest.raises(RuntimeError, match="provider down"):
        ingest(svc, A1, msg("g1"))
