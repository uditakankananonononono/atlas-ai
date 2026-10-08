"""Error-boundary contracts for story versions and interview answers.

Supersedes the hz28 pre-repair characterization: recognized non-unique
integrity errors are no longer retried or collision-labeled
(IntegrityWriteError, first attempt), and commit-time or post-commit
failures now carry the CommitOutcomeUnknown outward contract (failed call,
write may have persisted, no automatic retry/compensation/dedup). Temporary
SQLite only. Injected driver errors are controlled fixtures, not real
concurrent writes, crash recovery, or cross-driver proof; the
driver-identification evidence for SQLite and PostgreSQL lives in
tests/modules/test_m23_hz29_driver_constraint_and_commit_contract.py.
Ordinary expected-UNIQUE compatibility is kept in separately named tests.
"""
from contextlib import contextmanager
import sqlite3

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.modules.m23_study_abroad import interview, story
from app.modules.m23_study_abroad._commit_contract import (
    CommitOutcomeUnknown, IntegrityWriteError,
)
from app.modules.m23_study_abroad.interview import IdentityInterviewRepository, QUESTIONS
from app.modules.m23_study_abroad.story import BrandIdRow, StoryRepository, StoryVersionRow

ANSWER = 'I organized a neighborhood science club after our school lab closed.'


class CountingSessions:
    """Delegate real session creation; count attempts only when armed."""
    def __init__(self, factory):
        self.factory = factory
        self.armed = False
        self.attempts = 0

    def __call__(self):
        if self.armed:
            self.attempts += 1
        return self.factory()

    @contextmanager
    def begin(self):
        # Setup paths (project/start) still use begin(); pass through
        # uncounted - attempts are the outer version/answer calls.
        with self.factory.begin() as db:
            yield db


@pytest.fixture
def local(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path/'hz28.db'}")
    # Repository constructors call create_all on their imported engine. Keep
    # that operation local too, rather than touching the default atlas.db.
    monkeypatch.setattr(story, 'engine', engine)
    monkeypatch.setattr(interview, 'engine', engine)
    Base.metadata.create_all(engine)
    sessions = CountingSessions(sessionmaker(bind=engine))
    yield engine, sessions
    engine.dispose()


def _story(local):
    engine, sessions = local
    repo = StoryRepository('hz28', sessions)
    project = repo.project('Student story', 'college', {})
    return repo, project, engine, sessions


def _interview(local):
    engine, sessions = local
    repo = IdentityInterviewRepository('hz28', sessions)
    started = repo.start('college')
    return repo, started['id'], engine, sessions


def _story_versions(sessions, project):
    with sessions() as db:
        return list(db.scalars(select(StoryVersionRow.version).where(
            StoryVersionRow.project_id == project).order_by(StoryVersionRow.version)))


def _no_brand(sessions):
    with sessions() as db:
        assert db.get(BrandIdRow, 'hz28') is None


def _sql_fault(engine, sessions, predicate, error_type, cause):
    errors = []

    @event.listens_for(engine, 'before_cursor_execute')
    def fail(conn, cursor, statement, parameters, context, executemany):
        if sessions.armed and predicate(statement.upper()):
            exc = error_type(statement, parameters, cause())
            errors.append(exc)
            raise exc

    return errors


@pytest.mark.parametrize('stage', ['read', 'insert'])
def test_repair_story_nonunique_integrity_first_attempt_not_collision_labeled(local, stage):
    repo, project, engine, sessions = _story(local)
    predicate = (lambda sql: sql.lstrip().startswith('SELECT') and 'M23_STORY_VERSIONS' in sql
                 ) if stage == 'read' else (lambda sql: sql.lstrip().startswith('INSERT INTO M23_STORY_VERSIONS'))
    errors = _sql_fault(engine, sessions, predicate, IntegrityError,
                        lambda: sqlite3.IntegrityError('CHECK constraint failed: unrelated_story_check'))
    sessions.armed = True
    with pytest.raises(IntegrityWriteError, match='not a version collision') as failed:
        repo.add_student_version(project, ANSWER, {})
    sessions.armed = False
    assert sessions.attempts == len(errors) == 1
    assert failed.value.__cause__ is errors[-1]
    assert 'unrelated_story_check' in str(failed.value.__cause__.orig)
    assert _story_versions(sessions, project) == []


def test_repair_interview_brand_nonunique_first_attempt_not_collision_labeled(local, monkeypatch):
    repo, ident, engine, sessions = _interview(local)
    errors = []

    def fail_brand(self, *args, **kwargs):
        assert kwargs['_db'] is not None
        exc = IntegrityError('brand refresh', {}, sqlite3.IntegrityError(
            'CHECK constraint failed: unrelated_brand_check'))
        errors.append(exc)
        raise exc

    monkeypatch.setattr(StoryRepository, 'evolve_brand', fail_brand)
    sessions.armed = True
    with pytest.raises(IntegrityWriteError, match='not an answer collision') as failed:
        repo.answer(ident, ANSWER)
    sessions.armed = False
    assert sessions.attempts == len(errors) == 1
    assert failed.value.__cause__ is errors[-1]
    assert 'unrelated_brand_check' in str(failed.value.__cause__.orig)
    view = repo.get(ident)
    assert view['question_index'] == 0 and view['turns'] == []
    _no_brand(sessions)


@pytest.mark.parametrize('kind', ['story', 'interview'])
def test_characterization_prewrite_operational_error_escapes_without_success_or_write(local, kind):
    if kind == 'story':
        repo, ident, engine, sessions = _story(local)
        call = lambda: repo.add_student_version(ident, ANSWER, {})
        table = 'M23_STORY_PROJECTS'
    else:
        repo, ident, engine, sessions = _interview(local)
        call = lambda: repo.answer(ident, ANSWER)
        table = 'M23_IDENTITY_INTERVIEWS'
    errors = _sql_fault(engine, sessions,
                        lambda sql: sql.lstrip().startswith('SELECT') and table in sql,
                        OperationalError, lambda: sqlite3.OperationalError('injected prewrite read failure'))
    sessions.armed = True
    with pytest.raises(OperationalError) as failed:
        call()
    sessions.armed = False
    assert sessions.attempts == len(errors) == 1
    assert failed.value is errors[0]
    if kind == 'story':
        assert _story_versions(sessions, ident) == []
    else:
        view = repo.get(ident)
        assert view['question_index'] == 0 and view['turns'] == []
        _no_brand(sessions)


@pytest.mark.parametrize('kind', ['story', 'interview'])
def test_contract_commit_error_raises_commit_outcome_unknown_single_attempt(local, kind, monkeypatch):
    if kind == 'story':
        repo, ident, engine, sessions = _story(local)
        call = lambda: repo.add_student_version(ident, ANSWER, {})
    else:
        repo, ident, engine, sessions = _interview(local)
        call = lambda: repo.answer(ident, ANSWER, evidence_tags=['initiative'])
    raised = []

    def failing_commit(self, _real=Session.commit):
        error = OperationalError('synthetic commit failure', {}, sqlite3.OperationalError('commit failed'))
        raised.append(error)
        raise error

    monkeypatch.setattr(Session, 'commit', failing_commit)
    sessions.armed = True
    with pytest.raises(CommitOutcomeUnknown, match='may have persisted') as failed:
        call()
    sessions.armed = False
    assert sessions.attempts == 1 and len(raised) == 1
    assert failed.value.__cause__ is raised[0]
    # The persisted state is deliberately NOT asserted here: a commit-time
    # failure is exactly the ambiguous case, and the contract is the outward
    # type plus no automatic retry, not a state guarantee.


@pytest.mark.parametrize('kind', ['story', 'interview'])
def test_contract_postcommit_error_raises_commit_outcome_unknown_with_persisted_state(local, kind, monkeypatch):
    if kind == 'story':
        repo, ident, engine, sessions = _story(local)
        call = lambda: repo.add_student_version(ident, ANSWER, {})
    else:
        repo, ident, engine, sessions = _interview(local)
        call = lambda: repo.answer(ident, ANSWER, evidence_tags=['initiative'])
    raised = []

    def failing_close(self, _real=Session.close):
        error = RuntimeError('synthetic postcommit close failure')
        raised.append(error)
        raise error

    monkeypatch.setattr(Session, 'close', failing_close)
    sessions.armed = True
    with pytest.raises(CommitOutcomeUnknown, match='persisted while the call failed') as failed:
        call()
    sessions.armed = False
    assert sessions.attempts == 1 and len(raised) == 1
    assert failed.value.__cause__ is raised[0]
    monkeypatch.undo()
    if kind == 'story':
        assert _story_versions(sessions, ident) == [1]
        with sessions() as db:
            saved = db.scalar(select(StoryVersionRow).where(StoryVersionRow.project_id == ident))
            assert saved.student_text == ANSWER and saved.coach_feedback == {}
    else:
        view = repo.get(ident)
        assert view['question_index'] == 1 and view['next_question'] == QUESTIONS[1]
        assert len(view['turns']) == 1
        assert view['turns'][0]['question'] == QUESTIONS[0]
        assert view['turns'][0]['student_response'] == ANSWER
        with sessions() as db:
            brand = db.get(BrandIdRow, 'hz28')
            assert brand.evidence == [{'session_id': ident, 'turn': 1,
                                       'modality': 'chat', 'student_response': ANSWER}]
            assert brand.values == ['initiative']
    # No follow-up answer/version call: no automatic retry, deduplication,
    # compensation, cross-call binding, or outward status policy is asserted.


@pytest.mark.parametrize('kind', ['story', 'interview'])
def test_expected_unique_compatibility_one_collision_then_success(local, kind):
    if kind == 'story':
        repo, ident, engine, sessions = _story(local)
        table = 'M23_STORY_VERSIONS'
        constraint = 'm23_story_versions.project_id, m23_story_versions.version'
        call = lambda: repo.add_student_version(ident, ANSWER, {})
    else:
        repo, ident, engine, sessions = _interview(local)
        table = 'M23_IDENTITY_INTERVIEW_TURNS'
        constraint = 'm23_identity_interview_turns.session_id, m23_identity_interview_turns.ordinal'
        call = lambda: repo.answer(ident, ANSWER)
    errors = []

    @event.listens_for(engine, 'before_cursor_execute')
    def collide_once(conn, cursor, statement, parameters, context, executemany):
        if sessions.armed and not errors and statement.upper().lstrip().startswith(f'INSERT INTO {table}'):
            exc = IntegrityError(statement, parameters, sqlite3.IntegrityError(
                f'UNIQUE constraint failed: {constraint}'))
            errors.append(exc)
            raise exc

    sessions.armed = True
    view = call()
    sessions.armed = False
    assert sessions.attempts == 2 and len(errors) == 1
    if kind == 'story':
        assert view == 1 and _story_versions(sessions, ident) == [1]
    else:
        assert view['question_index'] == 1 and len(view['turns']) == 1
        assert view['turns'][0]['student_response'] == ANSWER
