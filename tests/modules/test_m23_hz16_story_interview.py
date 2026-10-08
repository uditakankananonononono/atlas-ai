"""hz16 pins: story-version collision/error contract + interview read-outcome honesty.

KILL pins fail on the pre-hz16 backend (raw IntegrityError escapes the
allocator; answer()/start() perform a post-commit re-read). Compat pins pass
on both. No real-race closure is claimed: the collision pins drive a
deterministic injected IntegrityError, proving the handler path only.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError as SAIntegrityError
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.modules.m23_study_abroad.story import StoryRepository
from app.modules.m23_study_abroad.interview import IdentityInterviewRepository


def _engine(tmp_path, name='hz16.db'):
    e = create_engine(f"sqlite:///{tmp_path/name}")
    Base.metadata.create_all(e)
    return e


def _collide_sessions(e, state):
    """Armed INSERTs into m23_story_versions raise a UNIQUE-constraint
    IntegrityError at the real execution boundary - the deterministic
    lost-allocation shape (a committed competitor is not visible to the
    recomputed read, the INSERT is rejected)."""
    import sqlite3
    from sqlalchemy import event

    @event.listens_for(e, 'before_cursor_execute')
    def boom(conn, cursor, statement, parameters, context, executemany):
        if (state['armed'] and state['failures'] < state['fail_count']
                and statement.lstrip().upper().startswith('INSERT INTO M23_STORY_VERSIONS')):
            state['failures'] += 1
            raise SAIntegrityError(statement, parameters, sqlite3.IntegrityError(
                'UNIQUE constraint failed: m23_story_versions.project_id, m23_story_versions.version'))

    return sessionmaker(bind=e)


def test_hz16_story_version_collision_retries_with_recomputed_number(tmp_path):
    # KILL: on the old backend the first-commit IntegrityError escapes raw.
    e = _engine(tmp_path)
    state = {'armed': False, 'failures': 0, 'fail_count': 1}
    r = StoryRepository('a', _collide_sessions(e, state))
    p = r.project('My story', 'college', {'school': 'U'})
    state['armed'] = True
    assert r.add_student_version(p, 'I built a community lab.', {'tone': 'clear'}) == 1
    assert state['failures'] == 1  # proves the collision handler ran
    # The next allocation continues from the committed maximum.
    assert r.add_student_version(p, 'I built a community lab and learned to listen.', {}) == 2


def test_hz16_story_version_collision_exhaustion_is_domain_error(tmp_path):
    # KILL: on the old backend the raw IntegrityError escapes on the first
    # failure; on hz16 repeated collisions surface as ValueError, never
    # IntegrityError.
    e = _engine(tmp_path)
    state = {'armed': False, 'failures': 0, 'fail_count': 99}
    r = StoryRepository('a', _collide_sessions(e, state))
    p = r.project('My story', 'college', {'school': 'U'})
    state['armed'] = True
    with pytest.raises(ValueError, match='collided repeatedly'):
        r.add_student_version(p, 'I built a community lab.', {})


def test_hz16_story_versions_still_sequential(tmp_path):
    # Compat: passes on old and new - the visible allocation sequence is
    # unchanged for uncontended writes.
    e = _engine(tmp_path)
    r = StoryRepository('a', sessionmaker(bind=e))
    p = r.project('My story', 'college', {'school': 'U'})
    assert r.add_student_version(p, 'First version of my story.', {}) == 1
    assert r.add_student_version(p, 'Second version of my story.', {}) == 2


def _interview_repo(tmp_path, name='hz16i.db'):
    e = _engine(tmp_path, name)
    return IdentityInterviewRepository('tenant-hz16', sessionmaker(bind=e))


def test_hz16_interview_answer_returns_committed_view_without_reread(tmp_path, monkeypatch):
    # KILL: on the old backend answer() ends with self.get(session_id) - a
    # post-commit re-read. Making the re-read unusable kills old code; hz16
    # builds the view inside the committing transaction. This pin proves the
    # absence of the post-commit re-read; it does not prove cross-session
    # isolation.
    r = _interview_repo(tmp_path)
    started = r.start('college')
    def _no_reread(session_id):
        raise AssertionError('post-commit re-read performed')
    monkeypatch.setattr(IdentityInterviewRepository, 'get', staticmethod(_no_reread)
                        if False else lambda self, session_id: (_ for _ in ()).throw(AssertionError('post-commit re-read performed')))
    view = r.answer(started['id'], 'I organized a neighborhood science club after our lab closed.',
                    modality='voice', evidence_tags=['initiative'])
    assert view['question_index'] == 1 and view['status'] == 'active'
    assert view['turns'][0]['ordinal'] == 1 and view['turns'][0]['modality'] == 'voice'
    assert view['next_question'] is not None and view['student_owned'] is True


def test_hz16_interview_start_returns_own_transaction_view(tmp_path, monkeypatch):
    # KILL: same re-read discrimination for start().
    r = _interview_repo(tmp_path)
    monkeypatch.setattr(IdentityInterviewRepository, 'get',
                        lambda self, session_id: (_ for _ in ()).throw(AssertionError('post-commit re-read performed')))
    view = r.start('college')
    assert view['question_index'] == 0 and view['status'] == 'active'
    assert view['turns'] == [] and view['next_question'] is not None


def test_hz16_interview_get_still_serves_committed_state(tmp_path):
    # Compat: the public read path is unchanged and still reflects committed
    # state written by answer().
    r = _interview_repo(tmp_path)
    started = r.start('college')
    r.answer(started['id'], 'I organized a neighborhood science club after our lab closed.')
    resumed = r.get(started['id'])
    assert resumed['question_index'] == 1 and len(resumed['turns']) == 1
