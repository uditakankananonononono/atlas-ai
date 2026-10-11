"""B1: lossless owner-channel snapshot and fail-closed request ledger.

This module is offline. Raw owner history remains in caller-controlled private storage.
No heuristic is allowed to erase a span or certify a feature as implemented.
"""
import copy
import hashlib
import json
import re
from collections import Counter
from datetime import datetime

STATES = {'IMPLEMENTED', 'PARKED_BY_USER', 'STOPPED_BY_USER', 'SUPERSEDED',
          'REFUSED_WITH_SUBSTITUTE', 'UNMAPPED'}
OWNER_CHANNELS = {'WhatsApp', 'iMessage', 'SMS', 'RCS'}
ROW_KEYS = {'message_id', 'body', 'ts', 'author', 'service', 'conversation_id'}

class Refused(ValueError):
    pass

def policy(action):
    """B1 has no effect paths: only private ingestion/review/report."""
    if action != 'read':
        raise Refused('POLICY_REFUSED_OUTREACH_OR_EFFECT')

def _time(value):
    try:
        t = datetime.fromisoformat(value)
        if t.tzinfo is None:
            raise ValueError('timezone required')
        return t
    except (ValueError, TypeError):
        raise Refused('PLAN_REFUSED_TIMESTAMP') from None

def _digest(rows):
    return hashlib.sha256(json.dumps(rows, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode()).hexdigest()

def _rows(rows, as_of):
    cutoff = _time(as_of)
    clean = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != ROW_KEYS:
            raise Refused('PLAN_REFUSED_SCHEMA')
        if row['author'] != 'user' or row['service'] not in OWNER_CHANNELS:
            raise Refused('PLAN_REFUSED_SOURCE')
        if not all(isinstance(v, str) for v in row.values()) or not row['message_id'] or not row['conversation_id']:
            raise Refused('PLAN_REFUSED_SCHEMA')
        if _time(row['ts']) > cutoff:
            raise Refused('PLAN_REFUSED_FUTURE')
        if row['message_id'] in seen:
            raise Refused('PLAN_REFUSED_DUPLICATE')
        seen.add(row['message_id'])
        clean.append(copy.deepcopy(row))
    return sorted(clean, key=lambda r: (_time(r['ts']), r['message_id']))

def make_snapshot(rows, *, as_of, observed_total, history_complete=False):
    clean = _rows(rows, as_of)
    if type(observed_total) is not int or observed_total != len(clean):
        raise Refused('PLAN_REFUSED_DB_COUNT')
    # The record never proves pre-join completeness, even when callers claim it.
    return dict(rows=clean, as_of=as_of, observed_total=observed_total,
                digest=_digest(clean), history_complete=False,
                history_gap='DB begins at enrollment; omissions and pre-enrollment history are not proven absent')

def split_spans(text):
    """Partition every character. Dotted identifiers/URLs are not sentence splits.

    Newlines or punctuation followed by whitespace/end delimit review candidates.
    All candidates start UNMAPPED, including greetings, fragments and quotes.
    """
    spans = []
    start = 0
    for match in re.finditer(r'\n|[.!?](?=\s|$)', text):
        end = match.end()
        spans.append(dict(start=start, end=end, text=text[start:end]))
        start = end
    if start < len(text):
        spans.append(dict(start=start, end=len(text), text=text[start:]))
    if not spans:
        spans.append(dict(start=0, end=0, text=''))
    return spans

class ChatBinder:
    def __init__(self, snapshot, action='read'):
        policy(action)
        self.snapshot = make_snapshot(snapshot['rows'], as_of=snapshot['as_of'],
                                      observed_total=snapshot['observed_total'])
        if self.snapshot['digest'] != snapshot['digest']:
            raise Refused('PLAN_REFUSED_DIGEST')
        self.spans = []
        for row in self.snapshot['rows']:
            for i, span in enumerate(split_spans(row['body'])):
                self.spans.append(dict(span, span_id=f"{row['message_id']}:{i}",
                                       message_id=row['message_id'], ts=row['ts']))
        self._index = {s['span_id']: s for s in self.spans}
        self.bindings = {}
        self.exclusions = {}
        self.audit = []

    def _span(self, sid):
        if sid not in self._index:
            raise Refused('PLAN_REFUSED_SPAN')
        return self._index[sid]

    def _pin(self, sid, evidence):
        pin = self._span(evidence.get('pin'))
        target = self._span(sid)
        if _time(pin['ts']) < _time(target['ts']) or pin['span_id'] == sid:
            raise Refused('PLAN_REFUSED_PIN_ORDER')
        return pin

    def _validate(self, sid, state, evidence):
        self._span(sid)
        if state not in STATES or not isinstance(evidence, dict):
            raise Refused('PLAN_REFUSED_STATE')
        if state == 'IMPLEMENTED':
            if not all(evidence.get(k) for k in ('unit', 'tests', 'mutation', 'commit')) or not re.fullmatch(r'[0-9a-f]{40}', evidence['commit']):
                raise Refused('PLAN_REFUSED_EVIDENCE')
        if state in {'STOPPED_BY_USER', 'PARKED_BY_USER', 'SUPERSEDED'}:
            pin = self._pin(sid, evidence)
            if state in {'STOPPED_BY_USER', 'PARKED_BY_USER'} and not re.search(r'\b(stop|stopped|pause|paused|park|skip|leave|except)\b|no need', pin['text'], re.I):
                raise Refused('PLAN_REFUSED_STOP_PIN')
            if not evidence.get('topic'):
                raise Refused('PLAN_REFUSED_EVIDENCE')
        if state == 'REFUSED_WITH_SUBSTITUTE':
            if evidence.get('substitute') not in {f'X{i}' for i in range(1,31)} or not evidence.get('unit') or not evidence.get('reason'):
                raise Refused('PLAN_REFUSED_SUBSTITUTE')

    def bind(self, sid, state, evidence):
        self._validate(sid, state, evidence)
        if sid in self.bindings or sid in self.exclusions:
            raise Refused('PLAN_REFUSED_USE_REVISION')
        self.bindings[sid] = dict(state=state, evidence=copy.deepcopy(evidence))
        self.audit.append(dict(span_id=sid, state=state, evidence=copy.deepcopy(evidence)))

    def revise(self, sid, state, evidence):
        self._validate(sid, state, evidence)
        pin = self._pin(sid, evidence)
        previous = self.bindings.get(sid)
        if previous is None:
            raise Refused('PLAN_REFUSED_NO_PREVIOUS')
        previous_pin = previous['evidence'].get('pin')
        if previous_pin and _time(pin['ts']) <= _time(self._span(previous_pin)['ts']):
            raise Refused('PLAN_REFUSED_PIN_ORDER')
        if not evidence.get('reason'):
            raise Refused('PLAN_REFUSED_EVIDENCE')
        self.bindings[sid] = dict(state=state, evidence=copy.deepcopy(evidence))
        self.audit.append(dict(span_id=sid, state=state, evidence=copy.deepcopy(evidence)))

    def exclude(self, sid, reason):
        self._span(sid)
        if not isinstance(reason, str) or not reason.strip():
            raise Refused('PLAN_REFUSED_REVIEW')
        if sid in self.bindings or sid in self.exclusions:
            raise Refused('PLAN_REFUSED_USE_REVISION')
        self.exclusions[sid] = reason
        self.audit.append(dict(span_id=sid, reviewed_nonrequest=True, reason=reason))

    def reconcile(self, database_rows):
        clean = _rows(database_rows, self.snapshot['as_of'])
        if len(clean) != self.snapshot['observed_total'] or _digest(clean) != self.snapshot['digest']:
            raise Refused('PLAN_REFUSED_DB_MISMATCH')
        return True

    def execution_gate(self, sid):
        self._span(sid)
        state = self.bindings.get(sid, {}).get('state', 'UNMAPPED')
        if state in {'STOPPED_BY_USER', 'PARKED_BY_USER', 'SUPERSEDED'}:
            return 'PLAN_REFUSED_STOPPED'
        if state == 'UNMAPPED':
            return 'PLAN_REFUSED_UNMAPPED'
        return 'B1_CLASSIFIED_NOT_EXECUTION_AUTHORITY'

    def report(self):
        counts = Counter({state: 0 for state in STATES})
        for span in self.spans:
            sid = span['span_id']
            if sid not in self.exclusions:
                counts[self.bindings.get(sid, {}).get('state', 'UNMAPPED')] += 1
        passed = bool(self.snapshot['rows']) and counts['UNMAPPED'] == 0
        return dict(unit='B1', passed=passed, refusal=None if passed else 'PLAN_REFUSED_UNMAPPED',
                    counts=dict(sorted(counts.items())), source_messages=len(self.snapshot['rows']),
                    candidate_spans=len(self.spans), reviewed_nonrequests=len(self.exclusions),
                    source_digest=self.snapshot['digest'],
                    scope=dict(implemented='lossless owner snapshot and reviewed classifications; zero-unmapped gate',
                               not_implemented='semantic completeness or feature execution proof; pre-join or missing history',
                               data_source='supplied owner-only DB snapshot', as_of=self.snapshot['as_of'],
                               history_complete=False, history_gap=self.snapshot['history_gap']))

    def private_ledger(self):
        return dict(snapshot=copy.deepcopy(self.snapshot), spans=copy.deepcopy(self.spans),
                    bindings=copy.deepcopy(self.bindings), exclusions=copy.deepcopy(self.exclusions),
                    audit=copy.deepcopy(self.audit), report=self.report())
