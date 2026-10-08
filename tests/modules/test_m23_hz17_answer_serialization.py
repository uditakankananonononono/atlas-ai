"""hz17 pins: duplicate-answer/concurrency serialization contract.

KILL pins fail on the pre-hz17 backend (raw IntegrityError escapes; no
(session, ordinal) uniqueness). Compat/characterization pins pass on both.
The collision pins inject IntegrityError at the real INSERT boundary via
before_cursor_execute - deterministic handler-path evidence only, no
real-race closure is claimed.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError as SAIntegrityError
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.modules.m23_study_abroad.interview import (
    IdentityInterviewRepository, IdentityTurnRow, QUESTIONS)

ANSWER = 'I organized a neighborhood science club after our school lab closed.'


def _repo(tmp_path, name='hz17.db'):
    e = create_engine(f"sqlite:///{tmp_path/name}")
    Base.metadata.create_all(e)
    return IdentityInterviewRepository('tenant-hz17', sessionmaker(bind=e)), e


def _arm_insert_failure(e, state, table):
    import sqlite3
    from sqlalchemy import event

    @event.listens_for(e, 'before_cursor_execute')
    def boom(conn, cursor, statement, parameters, context, executemany):
        if (state['armed'] and state['failures'] < state['fail_count']
                and statement.lstrip().upper().startswith(f'INSERT INTO {table}'.upper())):
            state['failures'] += 1
            raise SAIntegrityError(statement, parameters, sqlite3.IntegrityError(
                f'UNIQUE constraint failed: {table}.session_id, {table}.ordinal'))


def test_hz17_answer_collision_retries_with_reread(tmp_path):
    # KILL: pre-hz17 the injected IntegrityError escapes raw.
    r, e = _repo(tmp_path)
    state = {'armed': False, 'failures': 0, 'fail_count': 1}
    _arm_insert_failure(e, state, 'm23_identity_interview_turns')
    started = r.start('college')
    state['armed'] = True
    view = r.answer(started['id'], ANSWER, modality='voice', evidence_tags=['initiative'])
    assert view['question_index'] == 1 and view['turns'][0]['ordinal'] == 1
    assert state['failures'] == 1  # proves the collision handler ran


def test_hz17_answer_collision_exhaustion_is_domain_error(tmp_path):
    # KILL: pre-hz17 raw IntegrityError; hz17 raises the domain ValueError.
    r, e = _repo(tmp_path)
    state = {'armed': False, 'failures': 0, 'fail_count': 99}
    _arm_insert_failure(e, state, 'm23_identity_interview_turns')
    started = r.start('college')
    state['armed'] = True
    with pytest.raises(ValueError, match='collided repeatedly'):
        r.answer(started['id'], ANSWER)


def test_hz17_turn_ordinals_are_unique_at_the_schema(tmp_path):
    # KILL: pre-hz17 no (session_id, ordinal) constraint exists, so the
    # duplicate insert commits; hz17 rejects it.
    from datetime import datetime, timezone
    r, e = _repo(tmp_path)
    started = r.start('college')
    with sessionmaker(bind=e).begin() as db:
        row = dict(session_id=started['id'], ordinal=1, modality='chat',
                   question=QUESTIONS[0], student_response=ANSWER,
                   evidence_tags=[], created_at=datetime.now(timezone.utc))
        db.add(IdentityTurnRow(**row))
        db.add(IdentityTurnRow(**row))
        with pytest.raises(SAIntegrityError):
            db.flush()


def test_hz17_full_interview_still_completes(tmp_path):
    # Compat: sequential answers complete the interview on old and new.
    r, _ = _repo(tmp_path)
    started = r.start('college')
    view = None
    for i in range(len(QUESTIONS)):
        view = r.answer(started['id'], ANSWER + f' Turn {i}.')
    assert view['status'] == 'complete' and view['next_question'] is None
    assert [t['ordinal'] for t in view['turns']] == [1, 2, 3, 4, 5]
    with pytest.raises(ValueError, match='already complete'):
        r.answer(started['id'], ANSWER)


def test_hz17_identical_text_resubmission_is_a_new_answer(tmp_path):
    # Characterization (passes old and new): identical text submitted twice
    # is NOT deduplicated - the second submission answers the next question.
    # Documents the residual; client idempotency semantics are not invented.
    r, _ = _repo(tmp_path)
    started = r.start('college')
    r.answer(started['id'], ANSWER)
    view = r.answer(started['id'], ANSWER)
    assert view['question_index'] == 2
    assert [t['student_response'] for t in view['turns']] == [ANSWER, ANSWER]
