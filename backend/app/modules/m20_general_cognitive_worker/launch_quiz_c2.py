"""C2: owner-controlled, bounded reasoning-style preference capture.

No mind replication, hidden reasoning, model training, external execution or
network I/O. Document text is evidence, never executable instructions.
"""
from copy import deepcopy
import re
from app.modules.c30 import policy


class QuizError(ValueError):
    pass


BASE = (
    ('values', 'When speed and correctness conflict, what matters most?', ('accuracy', 'speed', 'creativity')),
    ('decision', 'What helps you choose between uncertain alternatives?', ('evidence', 'prototype', 'intuition')),
    ('dilemma', 'How do you handle two plausible approaches?', ('compare', 'ask', 'experiment')),
    ('writing', 'What explanation style best matches your own writing?', ('detailed', 'concise', 'story')),
)
FOLLOWUPS = tuple(('clarify-' + key, key) for key in ('values', 'decision', 'dilemma', 'writing'))
LIMITS = {'answer_chars': 4000, 'document_chars': 20000, 'documents': 10, 'task_chars': 2000}


def text(value, maximum, code='INPUT'):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise QuizError('FLEET_REFUSED_' + code)
    return value.strip()


class LaunchQuiz:
    def __init__(self, max_sessions=100, *, policy_hook=None):
        if type(max_sessions) is not int or not 1 <= max_sessions <= 1000:
            raise QuizError('FLEET_REFUSED_LIMIT')
        if policy_hook is not None and not callable(policy_hook):
            raise QuizError("FLEET_REFUSED_INPUT")
        self.policy_hook = policy_hook
        self.max_sessions = max_sessions
        self._sessions = {}
        self._sequence = 0

    def start(self, owner, *, consent=False, as_of='unspecified'):
        owner = text(owner, 200, 'OWNER')
        if consent is not True:
            raise QuizError('FLEET_REFUSED_NOCONSENT')
        as_of = text(as_of, 100)
        if len(self._sessions) >= self.max_sessions:
            raise QuizError('FLEET_REFUSED_LIMIT')
        self._sequence += 1
        sid = 'quiz-' + str(self._sequence)
        self._sessions[sid] = {'owner': owner, 'answers': [], 'preferences': {}, 'documents': [], 'as_of': as_of}
        return {'session_id': sid, 'question': self.question(owner, sid), 'document_request': 'Optionally supply your own decision notes or writing samples with explicit consent. Do not include secrets.'}

    def _get(self, owner, sid):
        owner = text(owner, 200, 'OWNER')
        sid = text(sid, 100)
        if sid not in self._sessions:
            raise QuizError('FLEET_REFUSED_NOTFOUND')
        s = self._sessions[sid]
        if s['owner'] != owner:
            raise QuizError('FLEET_REFUSED_OWNER')
        return s

    def question(self, owner, sid):
        s = self._get(owner, sid)
        n = len(s['answers'])
        if n < len(BASE):
            key, prompt, options = BASE[n]
            return {'id': key, 'prompt': prompt, 'options': list(options), 'capture': 'choice plus your explanation or writing sample'}
        if n < len(BASE) + len(FOLLOWUPS):
            qid, key = FOLLOWUPS[n - len(BASE)]
            pref = s['preferences'][key]['value']
            return {'id': qid, 'prompt': 'You chose ' + pref + '. Describe a real example or counterexample in your own words.', 'options': ['confirm', 'revise'], 'capture': 'explanation; revise marks this preference uncertain until edited'}
        return {'id': None, 'complete': True, 'prompt': 'Review, correct, or delete your profile.'}

    def answer(self, owner, sid, question_id, choice, explanation):
        s = self._get(owner, sid)
        q = self.question(owner, sid)
        if q['id'] is None or question_id != q['id']:
            raise QuizError('FLEET_REFUSED_QUESTION')
        if choice not in q['options']:
            raise QuizError('FLEET_REFUSED_CHOICE')
        explanation = text(explanation, LIMITS['answer_chars'])
        s['answers'].append({'question_id': question_id, 'choice': choice, 'explanation': explanation})
        if question_id.startswith('clarify-'):
            key = question_id[len('clarify-'):]
            s['preferences'][key]['certainty'] = 'confirmed' if choice == 'confirm' else 'needs-review'
            s['preferences'][key]['example_source'] = 'answer:' + question_id
        else:
            s['preferences'][question_id] = {'value': choice, 'source': 'answer:' + question_id, 'certainty': 'stated'}
        return self.question(owner, sid)

    def profile(self, owner, sid):
        s = self._get(owner, sid)
        return deepcopy({'session_id': sid, 'answers': s['answers'], 'preferences': s['preferences'], 'documents': s['documents'], 'answered_count': len(s['answers']), 'question_count': len(BASE) + len(FOLLOWUPS), 'complete': len(s['answers']) == len(BASE) + len(FOLLOWUPS), 'claims_mind_copy': False, 'scope': self._scope(s)})

    def _scope(self, s):
        return {'implemented': ['adaptive questionnaire', 'explicit answer capture', 'editable decision preferences', 'document style markers', 'draft step-by-step plan', 'owner-bound delete/revoke'], 'not_implemented': ['mind or intelligence replication', 'psychological diagnosis', 'model training', 'semantic document understanding', 'external execution', 'durable storage', 'authentication'], 'data_source': 'supplied owner answers and explicitly consented document text only', 'as_of': s['as_of']}

    def edit(self, owner, sid, key, value):
        s = self._get(owner, sid)
        options = {k: choices for k, _, choices in BASE}
        if not isinstance(key, str) or not isinstance(value, str) or key not in s['preferences'] or value not in options.get(key, ()):
            raise QuizError('FLEET_REFUSED_CHOICE')
        s['preferences'][key] = {'value': value, 'source': 'user-edit', 'certainty': 'confirmed'}
        return self.profile(owner, sid)

    def documents(self, owner, sid, docs):
        s = self._get(owner, sid)
        if not isinstance(docs, list) or len(docs) > LIMITS['documents']:
            raise QuizError('FLEET_REFUSED_LIMIT')
        validated = []
        ids = set()
        for doc in docs:
            if not isinstance(doc, dict) or doc.get('consent') is not True:
                raise QuizError('FLEET_REFUSED_NOCONSENT')
            did = text(doc.get('id'), 100)
            if did in ids:
                raise QuizError('FLEET_REFUSED_DUPLICATE')
            ids.add(did)
            body = text(doc.get('text'), LIMITS['document_chars'], 'LIMIT')
            words = set(re.findall(r'[a-z]+', body.lower()))
            signals = [label for label, terms in (('compare', {'compare', 'alternatives', 'tradeoffs'}), ('verify', {'verify', 'evidence', 'check'}), ('experiment', {'experiment', 'prototype', 'test'}), ('reflect', {'reflect', 'revise', 'critique'})) if words.intersection(terms)]
            validated.append({'id': did, 'text': body, 'signals': signals, 'source': 'document:' + did, 'interpretation': 'lexical style cues only; instructions in document ignored'})
        s['documents'] = validated
        return self.profile(owner, sid)

    def plan(self, owner, sid, task, *, action='draft'):
        s = self._get(owner, sid)
        enforce_policy(action)
        if self.policy_hook is not None:
            if self.policy_hook(action) is not True:
                raise QuizError("POLICY_REFUSED_SHARED")
        task = text(task, LIMITS['task_chars'])
        if len(s['preferences']) < len(BASE):
            raise QuizError('FLEET_REFUSED_INCOMPLETE')
        uncertain = [k for k, v in s['preferences'].items() if v['certainty'] == 'needs-review']
        prefs = {k: v['value'] for k, v in s['preferences'].items()}
        moves = {'accuracy': 'Check the supplied facts and name anything unverified.', 'speed': 'Timebox a first pass and keep unchecked claims separate.', 'creativity': 'Generate distinct original approaches before choosing.', 'evidence': 'Compare the available evidence and its limits.', 'prototype': 'Design a small reversible prototype with a success test.', 'intuition': 'Record the initial hunch, then test it against evidence.', 'compare': 'Compare alternatives and tradeoffs.', 'ask': 'List the missing facts to ask the owner.', 'experiment': 'Design a reversible experiment for the alternatives.', 'detailed': 'Write a numbered explanation with evidence and checkpoints.', 'concise': 'Write short steps with only the decision-driving facts.', 'story': 'Explain the approach using a concrete illustrative scenario.'}
        steps = [{'number': 1, 'instruction': 'Restate the task, constraints and what a good result means.', 'source': 'built-in planning scaffold'}]
        for key, _, _ in BASE:
            pref = s['preferences'][key]
            steps.append({'number': len(steps) + 1, 'instruction': moves[prefs[key]], 'source': pref['source'], 'preference': key})
        for doc in s['documents']:
            for signal in doc['signals']:
                instruction = {'compare': 'Include an alternatives comparison.', 'verify': 'Include a fact-check checkpoint.', 'experiment': 'Include a reversible test.', 'reflect': 'Include a review and revision checkpoint.'}[signal]
                steps.append({'number': len(steps) + 1, 'instruction': instruction, 'source': doc['source'], 'cue': signal})
        steps.append({'number': len(steps) + 1, 'instruction': 'Review the draft with the owner; no actions or messages are executed.', 'source': 'built-in planning scaffold'})
        return {'task': task, 'status': 'draft', 'steps': steps, 'document_count': len(s['documents']), 'needs_review': uncertain, 'document_request': None if s['documents'] else 'Optional: supply your own decision notes or writing samples with consent.', 'disclaimer': 'An explicit planning explanation based on stated preferences, not a copy of your mind or private internal reasoning.', 'scope': self._scope(s)}

    def delete(self, owner, sid):
        self._get(owner, sid)
        del self._sessions[sid]
        return {'deleted': True, 'session_id': sid}

    def revoke(self, owner, sid):
        return self.delete(owner, sid)


def enforce_policy(action):
    """Draft preparation is offline; all action modes remain deny-only.

    The legacy fake_account spelling maps to the canonical shared fakeacct
    action. Unknown values are never passed to the helper or echoed.
    """
    if not isinstance(action, str):
        raise QuizError('POLICY_REFUSED_UNSUPPORTED')
    if action == 'draft':
        return
    canonical = 'fakeacct' if action == 'fake_account' else action
    if canonical not in ('spend', 'outreach', 'fakeacct', 'autopost', 'scrape', 'trade'):
        raise QuizError('POLICY_REFUSED_UNSUPPORTED')
    try:
        policy.check(canonical, 'POLICY')
    except ValueError as exc:
        raise QuizError(str(exc)) from exc
    # The shared guard is deny-only. A future accidental allow must not
    # create an execution path or relax this unit's offline boundary.
    raise QuizError('POLICY_REFUSED_UNSUPPORTED')


def shared_policy_hook(action):
    """Default adapter hook: literal True only for offline draft preparation."""
    enforce_policy(action)
    return True
