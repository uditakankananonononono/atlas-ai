"""hz30: approval decide() is a single atomic claim.

Pre-repair, repository.decide ran the pending check and the decision write
in two separate transactions, and the write transaction re-read the row
without the pending filter: a competing decision committed between the two
transactions was silently overwritten, and both callers were told their
decision landed. The repair makes the pending check and the write one
conditional UPDATE (the mark_command pattern): only the first claim lands
and the loser gets None, which the service surfaces with the same
not-pending LookupError contract as a sequential second decide.

Establishes repository/service claim behavior with real engines (SQLite
always; PostgreSQL when pgserver and psycopg are importable), not
DB-vendor isolation guarantees or whole-module concurrency acceptance.
"""
import sqlite3
import threading

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.modules.m16_executive_dashboard.repository import (
    ApprovalRow, SqlDashboardRepository,
)
from app.modules.m16_executive_dashboard.schemas import (
    Approval, ApprovalDecision, ApprovalState,
)
from app.modules.m16_executive_dashboard.service import Service
from datetime import datetime, timezone

NOW = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)


def pending_approval(aid):
    return Approval(id=aid, module_id=16, action_type='deploy',
                    title=f'Deploy {aid}', summary='summary', risk='medium',
                    evidence={}, proposed_payload={}, created_at=NOW)


def make_repo(url, actor='reviewer'):
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    return SqlDashboardRepository('t', actor, session_factory=sessions), sessions


def raw_row(db_path, aid):
    raw = sqlite3.connect(str(db_path))
    row = raw.execute(
        'SELECT state, reviewed_by, review_note FROM m16_approvals WHERE id=?',
        (aid,)).fetchone()
    raw.close()
    return row


def test_decide_pending_approval_records_decision(tmp_path):
    repo, _ = make_repo(f"sqlite:///{tmp_path}/d.db")
    a = pending_approval('a1')
    repo.save_approval(a)
    decided = repo.decide(a.id, ApprovalState.APPROVED, 'looks good', NOW)
    assert decided is not None and decided.state is ApprovalState.APPROVED
    assert decided.reviewed_at == NOW
    assert raw_row(tmp_path / 'd.db', a.id) == ('approved', 'reviewer', 'looks good')


def test_second_decide_returns_none_and_preserves_first(tmp_path):
    repo, _ = make_repo(f"sqlite:///{tmp_path}/d.db")
    a = pending_approval('a2')
    repo.save_approval(a)
    first = repo.decide(a.id, ApprovalState.APPROVED, 'first', NOW)
    assert first is not None
    assert repo.decide(a.id, ApprovalState.REJECTED, 'second', NOW) is None
    assert raw_row(tmp_path / 'd.db', a.id) == ('approved', 'reviewer', 'first')


def test_competitor_decision_between_check_and_write_wins(tmp_path):
    """The deterministic lost race: a competing decision commits after the
    loser's pending check and before its write. The loser must not overwrite
    it. Pre-repair the write re-read the row without the pending filter and
    overwrote the competitor; both callers were told they decided."""
    db_path = tmp_path / 'd.db'
    engine = create_engine(f'sqlite:///{db_path}')
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    repo = SqlDashboardRepository('t', 'reviewer', session_factory=sessions)
    a = pending_approval('a3')
    repo.save_approval(a)
    fired = {'done': False}

    def competitor(conn, cursor, statement, parameters, context, executemany):
        if fired['done']:
            return
        s = statement.lstrip().upper()
        if 'M16_APPROVALS' not in s:
            return
        if s.startswith('SELECT') and 'STATE' in s:
            return  # the old pending check: let it pass, then race it
        if not s.startswith(('SELECT', 'UPDATE')):
            return
        fired['done'] = True
        raw = sqlite3.connect(str(db_path))
        raw.execute(
            'UPDATE m16_approvals SET state=?, reviewed_by=?, review_note=? '
            'WHERE tenant_id=? AND id=?',
            ('rejected', 'competitor', 'competitor won', 't', a.id))
        raw.commit()
        raw.close()

    event.listen(engine, 'before_cursor_execute', competitor)
    result = repo.decide(a.id, ApprovalState.APPROVED, 'approved note', NOW)
    assert fired['done']
    assert result is None
    assert raw_row(db_path, a.id) == ('rejected', 'competitor', 'competitor won')


class LostRaceRepo:
    """Repository stub: the pre-check sees a pending approval, but the
    conditional claim comes back empty because a competitor won the row."""

    def __init__(self, approval):
        self.approval = approval

    def pending_approvals(self):
        return [self.approval]

    def decide(self, *args):
        return None


def test_service_lost_race_raises_not_pending():
    svc = Service(LostRaceRepo(pending_approval('a4')))
    with pytest.raises(LookupError):
        svc.decide('a4', ApprovalDecision(approve=True, note='n'))


def test_concurrent_decides_exactly_one_claim_lands_postgres(tmp_path):
    pgserver = pytest.importorskip('pgserver')
    pytest.importorskip('psycopg')
    server = pgserver.get_server(str(tmp_path / 'pg'))
    try:
        repo, sessions = make_repo(server.get_uri())
        workers = 8
        for round_no in range(5):
            a = pending_approval(f'a-pg-{round_no}')
            repo.save_approval(a)
            barrier = threading.Barrier(workers)
            results = [None] * workers
            errors = []

            def worker(i):
                try:
                    barrier.wait()
                    results[i] = repo.decide(
                        a.id,
                        ApprovalState.APPROVED if i % 2 else ApprovalState.REJECTED,
                        f'note-{i}', NOW)
                except Exception as err:  # noqa: BLE001 - asserted below
                    errors.append(err)

            threads = [threading.Thread(target=worker, args=(i,))
                       for i in range(workers)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            assert not errors
            winners = [r for r in results if r is not None]
            assert len(winners) == 1
            final = repo.approval_by_id(a.id)
            assert final.state is winners[0].state
            with sessions() as db:
                row = db.scalar(select(ApprovalRow).where(
                    ApprovalRow.tenant_id == 't', ApprovalRow.id == a.id))
            winner_index = next(i for i, r in enumerate(results) if r is not None)
            assert row.review_note == f'note-{winner_index}'
    finally:
        server.cleanup()
