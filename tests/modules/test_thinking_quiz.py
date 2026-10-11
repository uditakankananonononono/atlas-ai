"""m20.thinking_quiz - advanced thinking-layer quiz and profile."""
import json
import pytest
from app.modules.m20_general_cognitive_worker import thinking_quiz as tq


def make():
    return tq.ThinkingQuiz()


def started(quiz, owner='udita'):
    return quiz.start(owner, consent=True, as_of='2026-10-11')


def first_choice(quiz, owner, sid):
    q = quiz.current_question(owner, sid)
    return q['id'], q['choices'][0]['id']


def answer_all(quiz, owner, sid, pick=0):
    while True:
        q = quiz.current_question(owner, sid)
        if q is None:
            return
        quiz.answer(owner, sid, q['id'], q['choices'][pick]['id'])


def test_bank_shape_and_integrity():
    bank = tq.QUESTION_BANK
    assert len(bank) == 20
    seen = set()
    for q in bank:
        assert q['id'] not in seen
        seen.add(q['id'])
        assert q['stage'] in tq.STAGES
        assert q['dimension'] in tq.DIMENSIONS
        assert len(q['choices']) == 3
        cids = [c['id'] for c in q['choices']]
        assert len(set(cids)) == 3
        for c in q['choices']:
            assert c['text'].strip()
            assert c['traits']
            for trait, weight in c['traits'].items():
                assert trait in tq.TRAITS
                assert 0 < weight <= 1.0
    grid = {(q['stage'], q['dimension']) for q in bank}
    assert len(grid) == len(tq.STAGES) * len(tq.DIMENSIONS)


def test_bank_ordered_stage_then_dimension():
    order = [(q['stage'], q['dimension']) for q in tq.QUESTION_BANK]
    assert order == sorted(order, key=lambda p: (tq.STAGES.index(p[0]),
                                                 tq.DIMENSIONS.index(p[1])))


def test_start_requires_consent():
    quiz = make()
    with pytest.raises(tq.ThinkingQuizError) as ei:
        quiz.start('udita', consent=False)
    assert str(ei.value) == 'FLEET_REFUSED_NOCONSENT'
    with pytest.raises(tq.ThinkingQuizError) as ei:
        quiz.start('udita')
    assert str(ei.value) == 'FLEET_REFUSED_NOCONSENT'


def test_start_validates_owner_and_caps_sessions():
    quiz = tq.ThinkingQuiz(max_sessions=2)
    with pytest.raises(tq.ThinkingQuizError):
        quiz.start('', consent=True)
    s1 = started(quiz)
    started(quiz, 'other')
    with pytest.raises(tq.ThinkingQuizError) as ei:
        started(quiz, 'third')
    assert str(ei.value) == 'FLEET_REFUSED_LIMIT'
    assert s1 == 'tquiz-1'


def test_owner_scoping():
    quiz = make()
    sid = started(quiz)
    with pytest.raises(tq.ThinkingQuizError) as ei:
        quiz.current_question('mallory', sid)
    assert str(ei.value) == 'FLEET_REFUSED_OWNER'
    with pytest.raises(tq.ThinkingQuizError) as ei:
        quiz.current_question('udita', 'tquiz-99')
    assert str(ei.value) == 'FLEET_REFUSED_UNKNOWN'


def test_current_question_progression_and_completion():
    quiz = make()
    sid = started(quiz)
    q1 = quiz.current_question('udita', sid)
    assert q1['id'] == tq.QUESTION_BANK[0]['id']
    quiz.answer('udita', sid, q1['id'], q1['choices'][1]['id'])
    assert quiz.current_question('udita', sid)['id'] == tq.QUESTION_BANK[1]['id']
    answer_all(quiz, 'udita', sid)
    assert quiz.current_question('udita', sid) is None


def test_answer_validation():
    quiz = make()
    sid = started(quiz)
    q = quiz.current_question('udita', sid)
    with pytest.raises(tq.ThinkingQuizError) as ei:
        quiz.answer('udita', sid, 'nope', 'a')
    assert str(ei.value) == 'FLEET_REFUSED_UNKNOWN:question_id'
    with pytest.raises(tq.ThinkingQuizError) as ei:
        quiz.answer('udita', sid, q['id'], 'zzz')
    assert str(ei.value) == 'FLEET_REFUSED_UNKNOWN:choice_id'
    quiz.answer('udita', sid, q['id'], 'a')
    with pytest.raises(tq.ThinkingQuizError) as ei:
        quiz.answer('udita', sid, q['id'], 'b')
    assert str(ei.value) == 'FLEET_REFUSED_DUPLICATE:question_id'
    q2 = quiz.current_question('udita', sid)
    with pytest.raises(tq.ThinkingQuizError) as ei:
        quiz.answer('udita', sid, q2['id'], 'a', explanation='x' * 4001)
    assert str(ei.value) == 'FLEET_REFUSED_INPUT'


def test_profile_math_exact():
    quiz = make()
    sid = started(quiz)
    answer_all(quiz, 'udita', sid, pick=0)
    profile = quiz.profile('udita', sid)
    assert profile['answered'] == 20
    assert profile['total'] == 20
    assert profile['completeness'] == 1.0
    expected_totals = {}
    for q in tq.QUESTION_BANK:
        for trait, w in q['choices'][0]['traits'].items():
            expected_totals[trait] = round(
                expected_totals.get(trait, 0.0) + w, 6)
    assert profile['trait_totals'] == dict(sorted(expected_totals.items()))
    top3 = sorted(expected_totals.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
    assert profile['thinking_signature'] == [t for t, _ in top3]
    for stage in tq.STAGES:
        assert profile['stages'][stage] == {'answered': 5, 'total': 5}
    for dim in tq.DIMENSIONS:
        shares = profile['dimensions'][dim]
        assert abs(sum(shares.values()) - 1.0) < 2e-6 or not shares


def test_profile_partial_completion():
    quiz = make()
    sid = started(quiz)
    q = quiz.current_question('udita', sid)
    quiz.answer('udita', sid, q['id'], 'a')
    profile = quiz.profile('udita', sid)
    assert profile['answered'] == 1
    assert profile['completeness'] == 0.05
    assert profile['stages'][q['stage']]['answered'] == 1


def test_suggest_consumes_profile():
    quiz_a, quiz_b = make(), make()
    sid_a, sid_b = started(quiz_a), started(quiz_b)
    answer_all(quiz_a, 'udita', sid_a, pick=0)
    answer_all(quiz_b, 'udita', sid_b, pick=2)
    sug_a = quiz_a.suggest('udita', sid_a)
    sug_b = quiz_b.suggest('udita', sid_b)
    assert sug_a[0]['id'] != sug_b[0]['id']
    assert [s['score'] for s in sug_a] == sorted(
        [s['score'] for s in sug_a], reverse=True)
    assert len(sug_a) == 3
    for s in sug_a:
        assert s['text'].strip() and s['stage'] in tq.STAGES


def test_suggest_stage_filter_and_limit():
    quiz = make()
    sid = started(quiz)
    answer_all(quiz, 'udita', sid, pick=1)
    idea = quiz.suggest('udita', sid, stage='idea', limit=2)
    assert len(idea) == 2
    assert all(s['stage'] == 'idea' for s in idea)
    with pytest.raises(tq.ThinkingQuizError) as ei:
        quiz.suggest('udita', sid, stage='nope')
    assert str(ei.value) == 'FLEET_REFUSED_INPUT'


def test_suggest_exact_scores():
    quiz = make()
    sid = started(quiz)
    answer_all(quiz, 'udita', sid, pick=0)
    profile = quiz.profile('udita', sid)
    total = sum(profile['trait_totals'].values())
    norm = {t: v / total for t, v in profile['trait_totals'].items()}
    expected = []
    for rule in tq.SUGGESTION_RULES:
        score = round(sum(norm.get(t, 0.0) * w
                          for t, w in rule['traits'].items()), 6)
        expected.append((rule['id'], score))
    expected.sort(key=lambda kv: (-kv[1], kv[0]))
    got = [(s['id'], s['score']) for s in quiz.suggest('udita', sid, limit=20)]
    assert got == expected


def test_edit_answer():
    quiz = make()
    sid = started(quiz)
    q = quiz.current_question('udita', sid)
    quiz.answer('udita', sid, q['id'], 'a')
    before = quiz.profile('udita', sid)['trait_totals']
    quiz.edit('udita', sid, q['id'], 'b')
    after = quiz.profile('udita', sid)['trait_totals']
    assert before != after
    with pytest.raises(tq.ThinkingQuizError) as ei:
        quiz.edit('udita', sid, 'nope', 'a')
    assert str(ei.value) == 'FLEET_REFUSED_UNKNOWN:question_id'
    q2 = quiz.current_question('udita', sid)
    with pytest.raises(tq.ThinkingQuizError) as ei:
        quiz.edit('udita', sid, q2['id'], 'a')
    assert str(ei.value) == 'FLEET_REFUSED_UNKNOWN:question_id'


def test_delete_session():
    quiz = make()
    sid = started(quiz)
    quiz.answer('udita', sid, *first_choice(quiz, 'udita', sid))
    quiz.delete('udita', sid)
    with pytest.raises(tq.ThinkingQuizError) as ei:
        quiz.current_question('udita', sid)
    assert str(ei.value) == 'FLEET_REFUSED_UNKNOWN'


def test_revoke_wipes_and_blocks():
    quiz = make()
    sid = started(quiz)
    quiz.answer('udita', sid, *first_choice(quiz, 'udita', sid))
    quiz.revoke('udita', sid)
    for fn in (lambda: quiz.current_question('udita', sid),
               lambda: quiz.profile('udita', sid),
               lambda: quiz.suggest('udita', sid)):
        with pytest.raises(tq.ThinkingQuizError) as ei:
            fn()
        assert str(ei.value) == 'FLEET_REFUSED_REVOKED'
    assert quiz.answers_snapshot('udita', sid, allow_revoked=True) == []


def test_determinism_byte_identical():
    def build():
        quiz = make()
        sid = started(quiz)
        answer_all(quiz, 'udita', sid, pick=1)
        return quiz.profile('udita', sid), quiz.suggest('udita', sid)
    a, b = build(), build()
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_profile_has_no_free_text_leak():
    quiz = make()
    sid = started(quiz)
    q = quiz.current_question('udita', sid)
    quiz.answer('udita', sid, q['id'], 'a', explanation='secret thoughts')
    profile = quiz.profile('udita', sid)
    assert 'secret thoughts' not in json.dumps(profile)


def test_public_surface():
    public = {n for n in dir(tq) if not n.startswith('_')
              and callable(getattr(tq, n))
              and getattr(getattr(tq, n), '__module__', '') == tq.__name__}
    assert public == {'ThinkingQuiz', 'ThinkingQuizError'}
