"""Bounded deterministic analysis of supplied normalized social exports.

Plugins are trusted Python dependencies, not a security sandbox. Their output
is revalidated; no platform adapter or network transport is provided.
"""
from __future__ import annotations

import copy
import csv
import hashlib
import io
import json
import re
import threading
from collections import OrderedDict
from datetime import datetime
from typing import Callable, Iterable, Protocol


class Refusal(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def reject(code: str):
    raise Refusal(code)


def offline_policy(action: str) -> bool:
    return action == 'analyze'


class Connector(Protocol):
    def read(self, payload: bytes) -> Iterable[dict]: ...


FIELDS = frozenset({'id', 'kind', 'platform', 'author', 'text', 'visibility', 'source_ref'})
KINDS = ('liked_post', 'comment', 'followed_account', 'feed_post')
THEMES = {
    'engineering': frozenset({'robot', 'sensor', 'code', 'software', 'open', 'built', 'engineering'}),
    'design': frozenset({'design', 'fragrance', 'skincare', 'packaging', 'fashion'}),
    'education': frozenset({'learn', 'school', 'study', 'education', 'course'}),
    'entrepreneurship': frozenset({'startup', 'launch', 'business', 'founder', 'product'}),
}


def _unique_pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            reject('SOCIAL_REFUSED_SCHEMA')
        out[key] = value
    return out


class NormalizedJSON:
    """Explicit normalized envelope, not a platform-specific raw-export parser."""
    def read(self, payload: bytes) -> Iterable[dict]:
        try:
            data = json.loads(payload.decode('utf-8'), object_pairs_hook=_unique_pairs)
        except (ValueError, UnicodeError, RecursionError):
            reject('SOCIAL_REFUSED_SCHEMA')
        if type(data) is not dict or set(data) != {'schema_version', 'records'}:
            reject('SOCIAL_REFUSED_SCHEMA')
        if type(data['schema_version']) is not int or data['schema_version'] != 1 or type(data['records']) is not list:
            reject('SOCIAL_REFUSED_SCHEMA')
        return data['records']


class PastedCSV:
    def read(self, payload: bytes) -> Iterable[dict]:
        try:
            reader = csv.DictReader(io.StringIO(payload.decode('utf-8-sig')), strict=True)
            if reader.fieldnames is None or len(reader.fieldnames) != len(FIELDS) or set(reader.fieldnames) != FIELDS:
                reject('SOCIAL_REFUSED_SCHEMA')
            yield from reader
        except (csv.Error, UnicodeError):
            reject('SOCIAL_REFUSED_SCHEMA')


def _positive(value, upper):
    if type(value) is not int or not 1 <= value <= upper:
        reject('SOCIAL_REFUSED_LIMIT')
    return value


def _record(row, max_text):
    if type(row) is not dict or set(row) != FIELDS or any(type(v) is not str for v in row.values()):
        reject('SOCIAL_REFUSED_SCHEMA')
    if any(any(0xD800 <= ord(char) <= 0xDFFF for char in value) for value in row.values()):
        reject('SOCIAL_REFUSED_SCHEMA')
    if any(not row[key].strip() for key in FIELDS - {'text'}):
        reject('SOCIAL_REFUSED_SCHEMA')
    if row['kind'] not in KINDS:
        reject('SOCIAL_REFUSED_SCHEMA')
    if row['visibility'] not in {'public', 'owner'} or (row['kind'] == 'followed_account' and row['visibility'] != 'public'):
        reject('SOCIAL_REFUSED_THIRDPARTYPRIVATE')
    if len(row['text']) > max_text or any(len(row[k]) > 2000 for k in FIELDS - {'text'}):
        reject('SOCIAL_REFUSED_OVERSIZE')
    if not re.match(r'^(https?://[^\s]+|export:[^\s]+)$', row['source_ref']):
        reject('SOCIAL_REFUSED_SCHEMA')
    return dict(row)


class Scanner:
    """Local, process-memory report store; tenant scoped, bounded, not durable."""
    def __init__(self, *, connectors: dict[str, Connector] | None = None,
                 policy: Callable[[str], bool] = offline_policy,
                 max_records=5000, max_bytes=2_000_000, max_text=10_000, max_reports=100):
        self.max_records = _positive(max_records, 5000)
        self.max_bytes = _positive(max_bytes, 2_000_000)
        self.max_text = _positive(max_text, 10_000)
        self.max_reports = _positive(max_reports, 1000)
        if not callable(policy):
            reject('POLICY_REFUSED_ACTION')
        self.policy = policy
        self.connectors = dict(connectors) if connectors is not None else {'normalized_json': NormalizedJSON(), 'pasted_csv': PastedCSV()}
        self._reports = OrderedDict()
        self._lock = threading.RLock()

    def run(self, *, tenant_id: str, connector: str, payload: bytes, as_of: str, action='analyze'):
        # Enforce local effect ban as well as the injected integration guard.
        if self.policy(action) is not True or action != 'analyze':
            reject('POLICY_REFUSED_ACTION')
        if type(tenant_id) is not str or not tenant_id.strip() or len(tenant_id) > 120:
            reject('SOCIAL_REFUSED_SCHEMA')
        try:
            moment = datetime.fromisoformat(as_of)
            if moment.utcoffset() is None:
                reject('SOCIAL_REFUSED_SCHEMA')
        except (ValueError, TypeError):
            reject('SOCIAL_REFUSED_SCHEMA')
        if type(payload) is not bytes or not payload:
            reject('SOCIAL_REFUSED_NOEXPORT')
        if len(payload) > self.max_bytes:
            reject('SOCIAL_REFUSED_OVERSIZE')
        if type(connector) is not str or connector not in self.connectors:
            reject('SOCIAL_REFUSED_CONNECTOR')
        unique = {}
        supplied = 0
        for raw in self.connectors[connector].read(payload):
            supplied += 1
            if supplied > self.max_records:
                reject('SOCIAL_REFUSED_OVERSIZE')
            row = _record(raw, self.max_text)
            key = (row['platform'], row['kind'], row['id'])
            if key in unique and unique[key] != row:
                reject('SOCIAL_REFUSED_CONFLICT')
            unique[key] = row
        clusters = {}
        counts = dict(supplied=supplied, unique=len(unique), duplicates=supplied-len(unique), **{kind: 0 for kind in KINDS})
        for key in sorted(unique):
            row = unique[key]
            counts[row['kind']] += 1
            words = set(re.findall(r'[a-z]+', row['text'].lower()))
            scored = [(len(words & terms), theme) for theme, terms in THEMES.items()]
            score, theme = sorted(scored, key=lambda pair: (-pair[0], pair[1]))[0]
            if not score:
                theme = 'unclassified'
            item = clusters.setdefault(theme, {'theme': theme, 'record_count': 0, 'source_refs': [], 'authors': []})
            item['record_count'] += 1
            if row['source_ref'] not in item['source_refs']:
                item['source_refs'].append(row['source_ref'])
            if row['author'] not in item['authors']:
                item['authors'].append(row['author'])
        groups = [clusters[key] for key in sorted(clusters)]
        briefs = [{
            'theme': group['theme'], 'status': 'draft', 'source_refs': list(group['source_refs']),
            'inspiration': f"Review the supplied {group['theme']} examples before choosing a direction.",
            'product_idea': f"Prototype an original {group['theme']} tool for a chosen audience.",
            'improvement_hypothesis': 'Test whether clearer onboarding or accessibility improves the chosen example; no superiority is established.',
        } for group in groups if group['theme'] != 'unclassified']
        out = {
            'unit_id': 'c33.S2.1', 'action': 'none', 'counts': counts,
            'clusters': groups, 'briefs': briefs,
            'input_sha256': hashlib.sha256(payload).hexdigest(),
            'scope': {
                'implemented': ['normalized supplied export parsing', 'bounded dedupe', 'lexical theme clustering', 'draft inspiration briefs'],
                'not_implemented': ['live platform access', 'raw vendor export formats', 'continuous scanning', 'posting or outreach', 'human psychology', 'exhaustive coverage', 'model-generated analysis', 'durable storage'],
                'data_source': 'supplied:' + connector, 'as_of': as_of,
            },
            'as_of_meaning': 'Caller-supplied snapshot label, not verified platform freshness.',
            'method': 'Fixed keyword counts; clusters and improvement ideas are unverified heuristic drafts.',
        }
        report_id = hashlib.sha256(json.dumps(out, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        out['report_id'] = report_id
        with self._lock:
            self._reports[(tenant_id, report_id)] = copy.deepcopy(out)
            self._reports.move_to_end((tenant_id, report_id))
            while len(self._reports) > self.max_reports:
                self._reports.popitem(last=False)
        return out

    def report(self, tenant_id: str, report_id: str) -> dict:
        with self._lock:
            key = (tenant_id, report_id)
            if key not in self._reports:
                reject('SOCIAL_REFUSED_NOTFOUND')
            return copy.deepcopy(self._reports[key])
