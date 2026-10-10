"""Tests for bounded_journal_retrieval - AUTHORED, NOT RUN.

Per the work-unit constraints these tests were written without executing
pytest, any test runner, or any database beyond static review. They are
handed to the integrating side to run. Style mirrors
tests/modules/test_m21_persistent_journal.py (SQLite via tmp_path).
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.modules.m21_claire.persistent_journal import JournalBase, JournalEntry, PersistentJournal
from app.modules.m21_claire.bounded_journal_retrieval import (
    MAX_LIMIT,
    MAX_SCAN_CAP,
    bounded_retrieve,
    validate_retrieval_bounds,
)


class _ExplodingSession:
    """Any database use fails the test: validation must happen before reads."""

    def scalar(self, *args, **kwargs):  # pragma: no cover - must never run
        raise AssertionError("database read attempted before validation")

    def scalars(self, *args, **kwargs):  # pragma: no cover - must never run
        raise AssertionError("database read attempted before validation")


def _sessions(tmp_path, name="bounded.db"):
    sessions = sessionmaker(bind=create_engine(f"sqlite:///{tmp_path/name}"))
    JournalBase.metadata.create_all(sessions.kw["bind"])
    return sessions


def _entry(tenant, actor, kind, decision, entry_id=None, created_at=None):
    from app.modules.m21_claire.persistent_journal import lexical_vector

    row = JournalEntry(tenant_id=tenant, actor_id=actor, kind=kind, decision=decision,
                       reason="r", context="c", source_reference="owner-msg-x",
                       vector=lexical_vector(decision + " r c"))
    if entry_id is not None:
        row.id = entry_id
    if created_at is not None:
        row.created_at = created_at
    return row


def test_validation_happens_before_any_read():
    bad_calls = [
        dict(query=""),
        dict(query="   "),
        dict(query="x" * 4001),
        dict(query="q", limit=0),
        dict(query="q", limit=MAX_LIMIT + 1),
        dict(query="q", limit=1.5),
        dict(query="q", kind="note"),
        dict(query="q", since=datetime(2026, 1, 1)),  # naive datetime rejected
        dict(query="q", until=datetime(2026, 1, 1)),
        dict(query="q", since=datetime(2026, 2, 1, tzinfo=timezone.utc),
             until=datetime(2026, 1, 1, tzinfo=timezone.utc)),
        dict(query="q", after_id=0),
        dict(query="q", after_id=9, before_id=9),
        dict(query="q", after_id=10, before_id=9),
        dict(query="q", scan_cap=0),
        dict(query="q", scan_cap=MAX_SCAN_CAP + 1),
        dict(query="q", limit=5, scan_cap=4),
    ]
    for kwargs in bad_calls:
        with pytest.raises(ValueError):
            validate_retrieval_bounds(**kwargs)
        with pytest.raises(ValueError):
            bounded_retrieve(_ExplodingSession(), tenant_id="t", actor_id="a", **kwargs)
    with pytest.raises(ValueError):
        bounded_retrieve(_ExplodingSession(), tenant_id=" ", actor_id="a", query="q")


def test_bounded_scan_reports_honest_truncation(tmp_path):
    sessions = _sessions(tmp_path)
    with sessions.begin() as db:
        for i in range(1, 31):
            db.add(_entry("t", "a", "decision", "shared lexical overlap", entry_id=i))
    with sessions() as db:
        out = bounded_retrieve(db, tenant_id="t", actor_id="a", query="shared lexical overlap",
                               limit=5, scan_cap=10)
    assert out["matched_total"] == 30
    assert out["rows_read"] == 10
    assert out["scored"] == 10
    assert out["truncated"] is True
    assert out["omitted_by_scan_cap"] == 20
    assert out["omitted_by_limit"] == 5  # 10 positive scores, 5 returned
    assert len(out["hits"]) == 5
    # newest-first scan window, ties broken by ascending id like retrieve()
    assert [h["id"] for h in out["hits"]] == [21, 22, 23, 24, 25]
    assert out["retrieval"] == "lexical_not_semantic"
    assert out["external_action_permission"] is False


def test_time_and_id_window_predicates(tmp_path):
    sessions = _sessions(tmp_path)
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with sessions.begin() as db:
        for i in range(1, 11):
            db.add(_entry("t", "a", "decision", "windowed entry", entry_id=i,
                          created_at=base + timedelta(days=i)))
    with sessions() as db:
        by_id = bounded_retrieve(db, tenant_id="t", actor_id="a", query="windowed",
                                 limit=20, scan_cap=100, after_id=3, before_id=8)
        assert by_id["matched_total"] == 4
        assert sorted(h["id"] for h in by_id["hits"]) == [4, 5, 6, 7]
        by_time = bounded_retrieve(db, tenant_id="t", actor_id="a", query="windowed",
                                   limit=20, scan_cap=100,
                                   since=base + timedelta(days=3),
                                   until=base + timedelta(days=5))
        assert sorted(h["id"] for h in by_time["hits"]) == [3, 4, 5]
        # paging older rows: before_id walks backwards from the oldest id seen
        page1 = bounded_retrieve(db, tenant_id="t", actor_id="a", query="windowed",
                                 limit=4, scan_cap=4)
        oldest = min(h["id"] for h in page1["hits"])
        page2 = bounded_retrieve(db, tenant_id="t", actor_id="a", query="windowed",
                                 limit=4, scan_cap=4, before_id=oldest)
        assert max(h["id"] for h in page2["hits"]) < oldest


def test_tenant_actor_kind_isolation_and_threshold_accounting(tmp_path):
    sessions = _sessions(tmp_path)
    with sessions.begin() as db:
        db.add(_entry("t", "a", "decision", "matching decision", entry_id=1))
        db.add(_entry("t", "a", "decision", "unrelated zzz qqq", entry_id=2))
        db.add(_entry("t", "a", "correction", "matching decision", entry_id=3))
        db.add(_entry("t", "other", "decision", "matching decision", entry_id=4))
        db.add(_entry("other-tenant", "a", "decision", "matching decision", entry_id=5))
    with sessions() as db:
        out = bounded_retrieve(db, tenant_id="t", actor_id="a", query="matching decision",
                               limit=20, scan_cap=100)
    assert out["matched_total"] == 2  # only t/a/decision rows
    assert out["below_threshold"] == 1  # zero-overlap row scored but dropped
    assert [h["id"] for h in out["hits"]] == [1]
    assert all(h["retrieval"] == "lexical_not_semantic" for h in out["hits"])
    with sessions() as db:
        corr = bounded_retrieve(db, tenant_id="t", actor_id="a", query="matching decision",
                                kind="correction", limit=20, scan_cap=100)
    assert [h["id"] for h in corr["hits"]] == [3]


def test_scoring_parity_with_persistent_journal_retrieve(tmp_path):
    sessions = _sessions(tmp_path, "parity.db")
    journal = PersistentJournal("t", "a", sessions)
    journal.capture("Choose competition", "Mission fit", "scholarships", "owner-msg-1")
    journal.capture("Write an essay", "Writing practice", "admissions", "owner-msg-2")
    journal.capture("Revise essay draft", "Feedback loop", "admissions", "owner-msg-3")
    with sessions() as db:
        bounded = bounded_retrieve(db, tenant_id="t", actor_id="a",
                                   query="essay admissions", limit=20, scan_cap=500)
    legacy = journal.retrieve("essay admissions", k=20)
    assert [h["id"] for h in bounded["hits"]] == [h["id"] for h in legacy]
    assert [h["score"] for h in bounded["hits"]] == [h["score"] for h in legacy]
    assert bounded["truncated"] is False


def test_paging_cursor_uses_scanned_rows_even_if_no_hits(tmp_path):
    sessions=_sessions(tmp_path)
    with sessions.begin() as db:
        for i in range(1,7):db.add(_entry('t','a','decision','zzz qqq',entry_id=i))
    with sessions() as db:
        first=bounded_retrieve(db,tenant_id='t',actor_id='a',query='matching',limit=1,scan_cap=3)
        assert first['hits']==[] and first['oldest_scanned_id']==4
        second=bounded_retrieve(db,tenant_id='t',actor_id='a',query='matching',limit=1,scan_cap=3,before_id=first['oldest_scanned_id'])
        assert second['oldest_scanned_id']==1 and second['rows_read']==3
        assert first['count_consistency']=='single_statement_window_count'


def test_journal_session_owned_additive_binding(tmp_path):
    sessions=_sessions(tmp_path);journal=PersistentJournal('t','a',sessions)
    journal.capture('write essay','fit','admissions','source1')
    out=journal.retrieve_bounded('essay',limit=1,scan_cap=1)
    assert len(out['hits'])==1 and out['external_action_permission'] is False
    assert out['global_top_k_claimed'] is False


def test_additive_route_calls_owned_store_and_rejects_bad_bound(tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.modules.m21_claire.persistent_journal_routes import router,store
    sessions=_sessions(tmp_path);journal=PersistentJournal('t','a',sessions)
    journal.capture('essay','reason','admissions','source')
    app=FastAPI();app.include_router(router);app.dependency_overrides[store]=lambda:journal
    with TestClient(app) as client:
        out=client.get('/claire/journal/decisions/bounded',params={'query':'essay','limit':1,'scan_cap':1})
        assert out.status_code==200 and out.json()['rows_read']==1
        assert client.get('/claire/journal/decisions/bounded',params={'query':'essay','scan_cap':0}).status_code==422
