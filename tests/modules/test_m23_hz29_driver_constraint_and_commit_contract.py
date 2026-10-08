"""hz29: supported-driver constraint identification - real driver evidence.

The UNIQUE-collision classifier used by story versions and interview
answers is identified for exactly two drivers, with real violations raised
by real engines here: SQLite (extended result codes 2067/1555 unique vs
other constraint codes) and PostgreSQL (SQLSTATE 23505 vs other 23xxx).
Any other driver signal is refused classification. PostgreSQL evidence
skips when pgserver or psycopg is absent; SQLite evidence always runs.
Nothing here establishes crash recovery, real-race closure, or coverage of
drivers beyond these two.
"""
import sqlite3

import pytest
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.modules.m23_study_abroad import interview, story
from app.modules.m23_study_abroad._commit_contract import (
    UnclassifiedIntegrityError, classify_integrity_error,
)
from app.modules.m23_study_abroad.interview import IdentityInterviewRepository
from app.modules.m23_study_abroad.story import StoryRepository, StoryVersionRow

ANSWER = 'I organized a neighborhood science club after our school lab closed.'


def _violations(url):
    """Raise one real UNIQUE, CHECK and NOT NULL violation on a scratch
    table against the given engine URL; return the captured IntegrityErrors."""
    engine = create_engine(url)
    captured = {}
    with engine.begin() as db:
        db.execute(text('CREATE TABLE hz29_probe ('
                        'v INTEGER UNIQUE CHECK (v > 0), n INTEGER NOT NULL)'))
        db.execute(text('INSERT INTO hz29_probe (v, n) VALUES (1, 1)'))
    for label, statement in (
        ('unique', 'INSERT INTO hz29_probe (v, n) VALUES (1, 1)'),
        ('check', 'INSERT INTO hz29_probe (v, n) VALUES (-1, 1)'),
        ('notnull', 'INSERT INTO hz29_probe (v, n) VALUES (5, NULL)'),
    ):
        try:
            with engine.begin() as db:
                db.execute(text(statement))
        except IntegrityError as exc:
            captured[label] = exc
    engine.dispose()
    return captured


def test_sqlite_real_violations_classified(tmp_path):
    captured = _violations(f"sqlite:///{tmp_path/'hz29.db'}")
    assert captured['unique'].orig.sqlite_errorcode == 2067  # SQLITE_CONSTRAINT_UNIQUE
    assert captured['check'].orig.sqlite_errorcode == 275    # SQLITE_CONSTRAINT_CHECK
    assert captured['notnull'].orig.sqlite_errorcode == 1299  # SQLITE_CONSTRAINT_NOTNULL
    assert classify_integrity_error(captured['unique']) == 'unique'
    assert classify_integrity_error(captured['check']) == 'non_unique'
    assert classify_integrity_error(captured['notnull']) == 'non_unique'


def test_postgres_real_violations_classified(tmp_path):
    pgserver = pytest.importorskip('pgserver')
    pytest.importorskip('psycopg')
    server = pgserver.get_server(tmp_path / 'pg', cleanup_mode='stop')
    url = server.get_uri().replace('postgresql://', 'postgresql+psycopg://')
    captured = _violations(url)
    assert captured['unique'].orig.sqlstate == '23505'  # unique_violation
    assert captured['check'].orig.sqlstate == '23514'   # check_violation
    assert captured['notnull'].orig.sqlstate == '23502'  # not_null_violation
    assert classify_integrity_error(captured['unique']) == 'unique'
    assert classify_integrity_error(captured['check']) == 'non_unique'
    assert classify_integrity_error(captured['notnull']) == 'non_unique'


def test_sqlite_manual_construction_message_fallback():
    # Manually constructed sqlite3 errors carry no result codes; the legacy
    # message form still identifies the unique case. This is a fallback for
    # synthetic/old-style exceptions, not the primary identification path.
    assert classify_integrity_error(sqlite3.IntegrityError(
        'UNIQUE constraint failed: t.v')) == 'unique'
    assert classify_integrity_error(sqlite3.IntegrityError(
        'CHECK constraint failed: t.v')) == 'non_unique'


def test_unsupported_driver_signal_refused():
    class UnknownDriverError(Exception):
        pass
    exc = IntegrityError('INSERT INTO t VALUES (1)', {}, UnknownDriverError('foreign driver'))
    assert classify_integrity_error(exc) == 'unsupported'


@pytest.fixture
def local(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path/'hz29_repo.db'}")
    monkeypatch.setattr(story, 'engine', engine)
    monkeypatch.setattr(interview, 'engine', engine)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    yield engine, sessions
    engine.dispose()


@pytest.mark.parametrize('kind', ['story', 'interview'])
def test_repo_refuses_unclassifiable_integrity_single_attempt(local, kind):
    """An integrity error outside the identified drivers is rolled back
    without write, never collision-labeled, never retried."""
    engine, sessions = local
    attempts = 0
    armed = False

    class ForeignDriverError(Exception):
        pass

    @event.listens_for(engine, 'before_cursor_execute')
    def fail(conn, cursor, statement, parameters, context, executemany):
        nonlocal attempts
        if armed and statement.upper().lstrip().startswith('INSERT INTO M23_'):
            attempts += 1
            raise IntegrityError(statement, parameters, ForeignDriverError('unmapped constraint signal'))

    if kind == 'story':
        repo = StoryRepository('hz29', sessions)
        project = repo.project('Student story', 'college', {})
        call = lambda: repo.add_student_version(project, ANSWER, {})
    else:
        repo = IdentityInterviewRepository('hz29', sessions)
        started = repo.start('college')
        call = lambda: repo.answer(started['id'], ANSWER)
    armed = True
    with pytest.raises(UnclassifiedIntegrityError, match='cannot classify'):
        call()
    armed = False
    assert attempts == 1
    if kind == 'story':
        with sessions() as db:
            assert list(db.scalars(select(StoryVersionRow.version))) == []
    else:
        assert repo.get(started['id'])['turns'] == []
