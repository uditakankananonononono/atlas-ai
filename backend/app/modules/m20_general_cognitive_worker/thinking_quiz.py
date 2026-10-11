"""Advanced thinking-layer quiz - launch-stage x thinking-dimension
question bank, deterministic trait scoring, and a profile that drives
suggestions.

Goes beyond C2 (launch_quiz_c2, untouched) and shares nothing with the landed c3_layers packet pipeline: a layered bank (4 launch stages
x 5 thinking dimensions), explicit trait weights per choice, a computed
thinking profile, and suggest() which ranks suggestion rules by dot product
with that profile. Consent-gated, owner-scoped, no network, no I/O, no
model training, no mind replication: answers are the owner's own supplied
words; the profile is arithmetic over them.
"""


class ThinkingQuizError(ValueError):
    pass


STAGES = ('idea', 'audience', 'positioning', 'launch')
DIMENSIONS = ('values', 'evidence', 'taste', 'risk', 'voice')
TRAITS = ('accuracy', 'bold', 'caution', 'creativity', 'data', 'experiment',
          'intuition', 'minimal', 'precision', 'speed', 'story', 'warmth')

LIMITS = {'owner_chars': 200, 'explanation_chars': 4000, 'as_of_chars': 100,
          'max_sessions': 1000, 'suggest_limit': 20}


def _q(stage, dimension, prompt, choices):
    return {'id': stage + '-' + dimension, 'stage': stage,
            'dimension': dimension, 'prompt': prompt,
            'choices': tuple({'id': cid, 'text': text, 'traits': traits}
                             for cid, text, traits in choices)}


QUESTION_BANK = (
    _q('idea', 'values',
       'When you judge a new idea, what makes it worth pursuing?',
       (('a', 'It solves a real, measurable problem', {'data': 1.0, 'accuracy': 0.5}),
        ('b', 'It is fresh and unlike anything out there', {'creativity': 1.0, 'bold': 0.5}),
        ('c', 'It can be tested small before committing', {'experiment': 1.0, 'caution': 0.5}))),
    _q('idea', 'evidence',
       'What convinces you that an idea is real?',
       (('a', 'Numbers from a small test', {'data': 1.0, 'experiment': 0.5}),
        ('b', 'A strong gut sense from experience', {'intuition': 1.0, 'speed': 0.5}),
        ('c', 'Careful comparison against alternatives', {'accuracy': 1.0, 'precision': 0.5}))),
    _q('idea', 'taste',
       'Which kind of idea excites you most?',
       (('a', 'Elegant and simple', {'minimal': 1.0, 'precision': 0.5}),
        ('b', 'Big and ambitious', {'bold': 1.0, 'creativity': 0.5}),
        ('c', 'Warm and human', {'warmth': 1.0, 'story': 0.5}))),
    _q('idea', 'risk',
       'An idea might fail publicly. What do you do?',
       (('a', 'Ship only when the downside is capped', {'caution': 1.0, 'accuracy': 0.5}),
        ('b', 'Ship early and learn in the open', {'bold': 1.0, 'speed': 0.5}),
        ('c', 'Run a quiet pilot first', {'experiment': 1.0, 'minimal': 0.5}))),
    _q('idea', 'voice',
       'How do you first describe a new idea to a friend?',
       (('a', 'A one-line sharp claim', {'precision': 1.0, 'minimal': 0.5}),
        ('b', 'A story about someone who needs it', {'story': 1.0, 'warmth': 0.5}),
        ('c', 'A quick sketch of how it works', {'data': 1.0, 'accuracy': 0.5}))),
    _q('audience', 'values',
       'Who should a launch serve first?',
       (('a', 'The few who feel the problem most', {'warmth': 1.0, 'precision': 0.5}),
        ('b', 'The biggest reachable market', {'bold': 1.0, 'speed': 0.5}),
        ('c', 'Whoever the early data points to', {'data': 1.0, 'experiment': 0.5}))),
    _q('audience', 'evidence',
       'How do you learn what your audience actually wants?',
       (('a', 'Watch what they do, not what they say', {'data': 1.0, 'accuracy': 0.5}),
        ('b', 'Ask them directly and listen hard', {'warmth': 1.0, 'intuition': 0.5}),
        ('c', 'Try small offers and measure', {'experiment': 1.0, 'data': 0.5}))),
    _q('audience', 'taste',
       'What is your favorite kind of user feedback?',
       (('a', 'Specific, blunt, numbers attached', {'precision': 1.0, 'data': 0.5}),
        ('b', 'A story about how it changed their day', {'story': 1.0, 'warmth': 0.5}),
        ('c', 'A clever use you never imagined', {'creativity': 1.0, 'intuition': 0.5}))),
    _q('audience', 'risk',
       'Early users misunderstand the product. What do you do?',
       (('a', 'Narrow the audience until it clicks', {'minimal': 1.0, 'precision': 0.5}),
        ('b', 'Keep it broad and let usage settle it', {'bold': 1.0, 'data': 0.5}),
        ('c', 'Pause and rework the message first', {'caution': 1.0, 'story': 0.5}))),
    _q('audience', 'voice',
       'How do you talk about your users in public?',
       (('a', 'Respectfully, with their words quoted exactly', {'accuracy': 1.0, 'warmth': 0.5}),
        ('b', 'Energetically, as a movement', {'bold': 1.0, 'story': 0.5}),
        ('c', 'Plainly, as numbers and segments', {'data': 1.0, 'precision': 0.5}))),
    _q('positioning', 'values',
       'A rival launches something similar first. What do you do?',
       (('a', 'Differentiate on measurable quality', {'accuracy': 1.0, 'data': 0.5}),
        ('b', 'Differentiate on story and brand', {'story': 1.0, 'creativity': 0.5}),
        ('c', 'Move faster to the next thing', {'speed': 1.0, 'bold': 0.5}))),
    _q('positioning', 'evidence',
       'What proof belongs on the landing page?',
       (('a', 'Benchmarks and comparisons', {'data': 1.0, 'precision': 0.5}),
        ('b', 'Real user stories', {'story': 1.0, 'warmth': 0.5}),
        ('c', 'A live demo people can poke', {'experiment': 1.0, 'creativity': 0.5}))),
    _q('positioning', 'taste',
       'How should the landing page feel?',
       (('a', 'Clean, one message, no clutter', {'minimal': 1.0, 'precision': 0.5}),
        ('b', 'Bold, unusual, memorable', {'bold': 1.0, 'creativity': 0.5}),
        ('c', 'Friendly and personal', {'warmth': 1.0, 'story': 0.5}))),
    _q('positioning', 'risk',
       'Do you name competitors publicly?',
       (('a', 'Never; keep the focus on us', {'caution': 1.0, 'minimal': 0.5}),
        ('b', 'Yes, with verifiable numbers only', {'accuracy': 1.0, 'data': 0.5}),
        ('c', 'Only if the story clearly favors us', {'bold': 1.0, 'story': 0.5}))),
    _q('positioning', 'voice',
       'What is your headline style?',
       (('a', 'A precise claim a skeptic can check', {'precision': 1.0, 'accuracy': 0.5}),
        ('b', 'An emotional promise', {'warmth': 1.0, 'story': 0.5}),
        ('c', 'A surprising question', {'creativity': 1.0, 'intuition': 0.5}))),
    _q('launch', 'values',
       'What does launch-day success mean to you?',
       (('a', 'Hitting the numbers you set in advance', {'data': 1.0, 'accuracy': 0.5}),
        ('b', 'People talking and sharing', {'bold': 1.0, 'story': 0.5}),
        ('c', 'Learning something that changes the plan', {'experiment': 1.0, 'intuition': 0.5}))),
    _q('launch', 'evidence',
       'In launch week, what do you watch mostly?',
       (('a', 'The dashboard metrics', {'data': 1.0, 'precision': 0.5}),
        ('b', 'What people say in their own words', {'warmth': 1.0, 'story': 0.5}),
        ('c', 'Your own read of momentum', {'intuition': 1.0, 'speed': 0.5}))),
    _q('launch', 'taste',
       'What launch shape do you prefer?',
       (('a', 'Small, controlled, then wider', {'caution': 1.0, 'minimal': 0.5}),
        ('b', 'One big moment', {'bold': 1.0, 'creativity': 0.5}),
        ('c', 'Rolling experiments', {'experiment': 1.0, 'speed': 0.5}))),
    _q('launch', 'risk',
       'Something breaks publicly on launch day. What do you do?',
       (('a', 'Acknowledge fast, fix, post the numbers after', {'accuracy': 1.0, 'bold': 0.5}),
        ('b', 'Quietly fix it before anyone notices', {'caution': 1.0, 'speed': 0.5}),
        ('c', 'Turn it into a story about how you build', {'story': 1.0, 'creativity': 0.5}))),
    _q('launch', 'voice',
       'What does your launch post sound like?',
       (('a', 'Direct and personal, first person', {'warmth': 1.0, 'story': 0.5}),
        ('b', 'Crisp and factual', {'precision': 1.0, 'minimal': 0.5}),
        ('c', 'Playful and surprising', {'creativity': 1.0, 'bold': 0.5}))),
)

SUGGESTION_RULES = (
    {'id': 's01', 'stage': 'idea', 'traits': {'warmth': 0.6, 'data': 0.4},
     'text': 'Run a 20-person problem-interview batch before writing any copy'},
    {'id': 's02', 'stage': 'idea', 'traits': {'experiment': 0.7, 'data': 0.3},
     'text': 'Build the smallest testable version and measure one metric'},
    {'id': 's03', 'stage': 'audience', 'traits': {'minimal': 0.6, 'precision': 0.4},
     'text': 'Define one narrow first-user profile and write to them only'},
    {'id': 's04', 'stage': 'audience', 'traits': {'warmth': 0.5, 'accuracy': 0.5},
     'text': 'Collect three blunt user quotes and put them on the page verbatim'},
    {'id': 's05', 'stage': 'positioning', 'traits': {'precision': 0.6, 'minimal': 0.4},
     'text': 'State one checkable headline claim and drop the rest'},
    {'id': 's06', 'stage': 'positioning', 'traits': {'story': 0.7, 'warmth': 0.3},
     'text': 'Lead with a before-and-after user story'},
    {'id': 's07', 'stage': 'launch', 'traits': {'data': 0.6, 'accuracy': 0.4},
     'text': 'Pre-commit three launch-day metrics and review them at +48h'},
    {'id': 's08', 'stage': 'launch', 'traits': {'caution': 0.5, 'accuracy': 0.5},
     'text': 'Prepare a public incident-note template before launch day'},
    {'id': 's09', 'stage': 'launch', 'traits': {'bold': 0.6, 'creativity': 0.4},
     'text': 'Ship a bold single-moment announcement with a surprise demo'},
    {'id': 's10', 'stage': 'positioning', 'traits': {'experiment': 0.5, 'creativity': 0.5},
     'text': 'Prototype three headline styles and read them with five people'},
)

_QUESTION_BY_ID = {q['id']: q for q in QUESTION_BANK}


def _refuse(code, field=''):
    return 'FLEET_REFUSED_' + code + (':' + field if field else '')


def _text(value, maximum, code='INPUT'):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ThinkingQuizError(_refuse(code))
    return value.strip()


class ThinkingQuiz:
    """Consent-gated, owner-scoped thinking-layer quiz sessions."""

    def __init__(self, max_sessions=100):
        if type(max_sessions) is not int or not 1 <= max_sessions <= LIMITS['max_sessions']:
            raise ThinkingQuizError(_refuse('LIMIT'))
        self.max_sessions = max_sessions
        self._sessions = {}
        self._sequence = 0

    def start(self, owner, *, consent=False, as_of='unspecified'):
        owner = _text(owner, LIMITS['owner_chars'], 'OWNER')
        if consent is not True:
            raise ThinkingQuizError(_refuse('NOCONSENT'))
        as_of = _text(as_of, LIMITS['as_of_chars'])
        if len(self._sessions) >= self.max_sessions:
            raise ThinkingQuizError(_refuse('LIMIT'))
        self._sequence += 1
        sid = 'tquiz-' + str(self._sequence)
        self._sessions[sid] = {'owner': owner, 'as_of': as_of,
                               'answers': {}, 'revoked': False}
        return sid

    def _get(self, owner, sid, allow_revoked=False):
        owner = _text(owner, LIMITS['owner_chars'], 'OWNER')
        s = self._sessions.get(sid)
        if s is None:
            raise ThinkingQuizError(_refuse('UNKNOWN'))
        if s['owner'] != owner:
            raise ThinkingQuizError(_refuse('OWNER'))
        if s['revoked'] and not allow_revoked:
            raise ThinkingQuizError(_refuse('REVOKED'))
        return s

    def current_question(self, owner, sid):
        s = self._get(owner, sid)
        for q in QUESTION_BANK:
            if q['id'] not in s['answers']:
                return q
        return None

    def answer(self, owner, sid, question_id, choice_id, explanation=''):
        s = self._get(owner, sid)
        q = _QUESTION_BY_ID.get(question_id)
        if q is None:
            raise ThinkingQuizError(_refuse('UNKNOWN', 'question_id'))
        if question_id in s['answers']:
            raise ThinkingQuizError(_refuse('DUPLICATE', 'question_id'))
        choice = self._choice(q, choice_id)
        if explanation:
            _text(explanation, LIMITS['explanation_chars'])
        s['answers'][question_id] = {
            'question_id': question_id, 'choice_id': choice['id'],
            'explanation': explanation, 'stage': q['stage'],
            'dimension': q['dimension'], 'traits': dict(choice['traits'])}
        return s['answers'][question_id]

    def _choice(self, q, choice_id):
        for c in q['choices']:
            if c['id'] == choice_id:
                return c
        raise ThinkingQuizError(_refuse('UNKNOWN', 'choice_id'))

    def edit(self, owner, sid, question_id, choice_id, explanation=None):
        s = self._get(owner, sid)
        if question_id not in s['answers']:
            raise ThinkingQuizError(_refuse('UNKNOWN', 'question_id'))
        q = _QUESTION_BY_ID[question_id]
        choice = self._choice(q, choice_id)
        answer = s['answers'][question_id]
        answer['choice_id'] = choice['id']
        answer['traits'] = dict(choice['traits'])
        if explanation is not None:
            if explanation:
                _text(explanation, LIMITS['explanation_chars'])
            answer['explanation'] = explanation
        return answer

    def answers_snapshot(self, owner, sid, allow_revoked=False):
        s = self._get(owner, sid, allow_revoked=allow_revoked)
        return [dict(a) for a in s['answers'].values()]

    def profile(self, owner, sid):
        s = self._get(owner, sid)
        answers = s['answers']
        totals = {}
        for q in QUESTION_BANK:
            a = answers.get(q['id'])
            if a is None:
                continue
            for trait, w in a['traits'].items():
                totals[trait] = round(totals.get(trait, 0.0) + w, 6)
        stages = {}
        for stage in STAGES:
            bank_n = sum(1 for q in QUESTION_BANK if q['stage'] == stage)
            got = sum(1 for q in QUESTION_BANK
                      if q['stage'] == stage and q['id'] in answers)
            stages[stage] = {'answered': got, 'total': bank_n}
        dimensions = {}
        for dim in DIMENSIONS:
            dim_totals = {}
            for q in QUESTION_BANK:
                if q['dimension'] != dim or q['id'] not in answers:
                    continue
                for trait, w in answers[q['id']]['traits'].items():
                    dim_totals[trait] = dim_totals.get(trait, 0.0) + w
            dim_sum = sum(dim_totals.values())
            dimensions[dim] = (dict(sorted(
                (t, round(v / dim_sum, 6))
                for t, v in dim_totals.items())) if dim_sum else {})
        answered = len(answers)
        signature = [t for t, _ in sorted(totals.items(),
                                          key=lambda kv: (-kv[1], kv[0]))[:3]]
        return {'owner': s['owner'], 'as_of': s['as_of'],
                'answered': answered, 'total': len(QUESTION_BANK),
                'completeness': round(answered / len(QUESTION_BANK), 6),
                'stages': stages, 'dimensions': dimensions,
                'trait_totals': dict(sorted(totals.items())),
                'thinking_signature': signature}

    def suggest(self, owner, sid, *, stage=None, limit=3):
        s = self._get(owner, sid)
        if stage is not None and stage not in STAGES:
            raise ThinkingQuizError(_refuse('INPUT'))
        if type(limit) is not int or not 1 <= limit <= LIMITS['suggest_limit']:
            raise ThinkingQuizError(_refuse('INPUT'))
        totals = self.profile(owner, sid)['trait_totals']
        grand = sum(totals.values())
        norm = {t: v / grand for t, v in totals.items()} if grand else {}
        scored = []
        for rule in SUGGESTION_RULES:
            if stage is not None and rule['stage'] != stage:
                continue
            score = round(sum(norm.get(t, 0.0) * w
                              for t, w in rule['traits'].items()), 6)
            scored.append({'id': rule['id'], 'stage': rule['stage'],
                           'text': rule['text'], 'score': score})
        scored.sort(key=lambda r: (-r['score'], r['id']))
        return scored[:limit]

    def delete(self, owner, sid):
        self._get(owner, sid)
        del self._sessions[sid]

    def revoke(self, owner, sid):
        s = self._get(owner, sid)
        s['answers'] = {}
        s['revoked'] = True
