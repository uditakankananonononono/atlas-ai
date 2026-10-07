"""Local error-boundary characterizations, not repair kills or retry policy.

Temporary SQLite only. Injected driver errors and a transaction wrapper are
controlled fixtures, not real concurrent writes, crash recovery, or proof of
supported-driver classification. Commit-then-exit fixtures deliberately model
one known persisted outcome of a failed call; other failed calls can roll back.
Ordinary expected-UNIQUE compatibility is kept in separately named tests.
"""
from contextlib import contextmanager
import sqlite3

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.modules.m23_study_abroad import interview, story
from app.modules.m23_study_abroad.interview import IdentityInterviewRepository, QUESTIONS
from app.modules.m23_study_abroad.story import BrandIdRow, StoryRepository, StoryVersionRow

ANSWER = 'I organized a neighborhood science club after our school lab closed.'


class CountingSessions:
    """Delegate real local transactions; count attempts only when armed."""
    def __init__(self, factory):
        self.factory = factory
        self.armed = False
        self.attempts = 0
        self.exit_error = None

    def __call__(self):
        return self.factory()

    @contextmanager
    def begin(self):
        armed = self.armed
        if armed:
            self.attempts += 1
        with self.factory.begin() as db:
            yield db
        # Inner context has returned normally: the local transaction committed.
        # This is a synthetic wrapper-exit failure, not a DB driver guarantee.
        if armed and self.exit_error is not None:
            raise self.exit_error


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
def test_characterization_story_unrelated_integrity_retried_and_collision_labeled(local, stage):
    repo, project, engine, sessions = _story(local)
    predicate = (lambda sql: sql.lstrip().startswith('SELECT') and 'M23_STORY_PROJECTS' in sql
                 ) if stage == 'read' else (lambda sql: sql.lstrip().startswith('INSERT INTO M23_STORY_VERSIONS'))
    errors = _sql_fault(engine, sessions, predicate, IntegrityError,
                        lambda: sqlite3.IntegrityError('CHECK constraint failed: unrelated_story_check'))
    sessions.armed = True
    with pytest.raises(ValueError, match='story version allocation collided repeatedly') as failed:
        repo.add_student_version(project, ANSWER, {})
    sessions.armed = False
    assert sessions.attempts == len(errors) == 3
    assert failed.value.__cause__ is errors[-1]
    assert 'unrelated_story_check' in str(failed.value.__cause__.orig)
    assert _story_versions(sessions, project) == []


def test_characterization_interview_brand_unrelated_integrity_retried_and_collision_labeled(local, monkeypatch):
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
    with pytest.raises(ValueError, match='interview answer collided repeatedly') as failed:
        repo.answer(ident, ANSWER)
    sessions.armed = False
    assert sessions.attempts == len(errors) == 3
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
@pytest.mark.parametrize('error_kind', ['operational', 'unexpected'])
def test_characterization_committed_then_exit_error_is_failed_call_with_persisted_state(local, kind, error_kind):
    if kind == 'story':
        repo, ident, engine, sessions = _story(local)
        call = lambda: repo.add_student_version(ident, ANSWER, {})
    else:
        repo, ident, engine, sessions = _interview(local)
        call = lambda: repo.answer(ident, ANSWER, evidence_tags=['initiative'])
    error = (OperationalError('synthetic postcommit exit', {}, sqlite3.OperationalError('exit failed'))
             if error_kind == 'operational' else RuntimeError('synthetic postcommit exit failed'))
    sessions.exit_error = error
    sessions.armed = True
    with pytest.raises(type(error)) as failed:
        call()
    sessions.armed = False
    assert failed.value is error and sessions.attempts == 1
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
