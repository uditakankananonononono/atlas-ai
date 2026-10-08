"""hz18 pins: stale-answer rejection after a lost answer race.

KILL pins fail on hz17 (which re-filed the original Q0 response under Q1
after a competitor committed). Compat pins pass on hz17 and hz18."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError as SAIntegrityError
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.modules.m23_study_abroad.interview import (
    IdentityInterviewRepository, QUESTIONS)

ANSWER = 'I organized a neighborhood science club after our school lab closed.'
COMPETITOR = 'A competitor answer committed while the first was in flight.'


def _repo(tmp_path, name='hz18.db'):
    e = create_engine(f"sqlite:///{tmp_path/name}")
    Base.metadata.create_all(e)
    return IdentityInterviewRepository('tenant-hz18', sessionmaker(bind=e)), e


def test_hz18_lost_race_rejects_stale_answer_instead_of_shifting_questions(tmp_path):
    # KILL: hz17 stored the original Q0 response under Q1 after the
    # competitor committed (intent shift). hz18 rejects the stale answer.
    # The competitor commit is performed directly at the sqlite boundary at
    # the moment the collision is injected - deterministic lost-race shape,
    # not a real concurrency claim.
    import sqlite3
    from sqlalchemy import event
    e = create_engine(f"sqlite:///{tmp_path/'hz18.db'}")
    Base.metadata.create_all(e)
    db_path = str(tmp_path / 'hz18.db')
    state = {'failed_once': False, 'competitor_done': False}

    @event.listens_for(e, 'before_cursor_execute')
    def boom(conn, cursor, statement, parameters, context, executemany):
        if (not state['failed_once']
                and statement.lstrip().upper().startswith('INSERT INTO M23_IDENTITY_INTERVIEW_TURNS')):
            state['failed_once'] = True
            raise SAIntegrityError(statement, parameters, sqlite3.IntegrityError(
                'UNIQUE constraint failed: m23_identity_interview_turns.session_id, m23_identity_interview_turns.ordinal'))

    class RacingSessions(sessionmaker):
        def __call__(self, **kwargs):
            # The competitor's answer commits at the retry boundary (the
            # first attempt's transaction has fully rolled back, so the
            # database is unlocked): turn ordinal 1 plus the question_index
            # advance, exactly what answer() would write. hz29: the retry
            # boundary is the fresh-session call, no longer begin().
            if state['failed_once'] and not state['competitor_done']:
                state['competitor_done'] = True
                other = sqlite3.connect(db_path)
                other.execute(
                    "INSERT INTO m23_identity_interview_turns (session_id, ordinal, modality, question, student_response, evidence_tags, created_at)"
                    " VALUES (?, 1, 'chat', ?, ?, '[]', '2026-10-07 00:00:00+00:00')",
                    (started['id'], QUESTIONS[0], COMPETITOR))
                other.execute(
                    "UPDATE m23_identity_interviews SET question_index = 1 WHERE id = ?",
                    (started['id'],))
                other.commit(); other.close()
            return super().__call__(**kwargs)

    r = IdentityInterviewRepository('tenant-hz18', RacingSessions(bind=e))
    started = r.start('college')
    with pytest.raises(ValueError, match='interview advanced'):
        r.answer(started['id'], ANSWER)
    # The stale response was never stored; only the competitor's turn exists.
    view = r.get(started['id'])
    assert [t['student_response'] for t in view['turns']] == [COMPETITOR]
    assert view['question_index'] == 1


def test_hz18_same_question_retry_still_succeeds(tmp_path):
    # Compat (passes hz17 and hz18): a transient collision while the
    # interview is still on the SAME question retries and stores the
    # response under the question it was written for.
    import sqlite3
    from sqlalchemy import event
    r, e = _repo(tmp_path)
    started = r.start('college')
    state = {'fired': False}

    @event.listens_for(e, 'before_cursor_execute')
    def boom(conn, cursor, statement, parameters, context, executemany):
        if (not state['fired']
                and statement.lstrip().upper().startswith('INSERT INTO M23_IDENTITY_INTERVIEW_TURNS')):
            state['fired'] = True
            raise SAIntegrityError(statement, parameters, sqlite3.IntegrityError(
                'UNIQUE constraint failed: m23_identity_interview_turns.session_id, m23_identity_interview_turns.ordinal'))

    view = r.answer(started['id'], ANSWER)
    assert view['question_index'] == 1
    assert view['turns'][0]['question'] == QUESTIONS[0]
    assert view['turns'][0]['student_response'] == ANSWER
