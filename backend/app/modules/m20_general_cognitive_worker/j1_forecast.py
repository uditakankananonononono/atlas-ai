"""J1 single forecast ledger/scorer. Offline, stdlib-only, supplied outcomes.

Ledger integrity is an unkeyed hash chain, not authorship authentication.
POSIX flock makes cooperating cross-process appends serial. Timestamps describe
caller data; the caller's truthful outcomes and dates are not independently proven.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import stat

from app.modules.c30 import policy

MAX_PREDICTIONS = 10000
MAX_EVENTS = 20001
MAX_BYTES = 16000000
MAX_TEXT = 4096
MIN_CALIBRATION_SAMPLE = 20
PRED_KEYS = {'prediction_id', 'claim', 'probability', 'horizon', 'source', 'made_at'}
RES_KEYS = {'prediction_id', 'outcome', 'resolved_at'}


class ForecastRefusal(ValueError):
    def __init__(self, code, detail=''):
        self.code = code
        super().__init__(code + (': ' + detail if detail else ''))


def refuse(reason, detail):
    raise ForecastRefusal('INTEL_REFUSED_' + reason, detail)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def guard(action, tenant_id, payload=None, policy_guard=None):
    classifier = policy_guard or policy.classify
    descriptor = {'class': 'offline', 'module_id': 20, 'tenant_id': tenant_id,
                  'action_type': action, 'payload': payload or {}}
    try:
        decision = classifier(descriptor)
    except ValueError as exc:
        raise ForecastRefusal(str(exc).split(':')[0], str(exc)) from exc
    if not isinstance(decision, dict) or decision.get('decision') != 'allow':
        code = decision.get('code') if isinstance(decision, dict) else None
        raise ForecastRefusal(code or 'POLICY_REFUSED_UNKNOWN', 'J1 policy did not allow offline action')


def text(value, name):
    try:
        return policy.clean_text(value, 'INTEL', name, MAX_TEXT)
    except ValueError as exc:
        refuse('SCHEMA', str(exc))


def timestamp(value, name):
    if not isinstance(value, str) or len(value) > 64:
        refuse('TIME', name + ' must be timezone-aware ISO text')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            refuse('TIME', name + ' must have a timezone')
        return parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError) as exc:
        if isinstance(exc, ForecastRefusal):
            raise
        refuse('TIME', name + ' must be valid ISO text')


def iso(value):
    return value.isoformat().replace('+00:00', 'Z')


def validate_prediction(row):
    if not isinstance(row, dict):
        refuse('SCHEMA', 'prediction must be an object')
    if row.get('horizon') is None or (isinstance(row.get('horizon'), str) and not row['horizon'].strip()):
        refuse('NOHORIZON', 'prediction requires an explicit horizon deadline')
    if set(row) != PRED_KEYS:
        refuse('SCHEMA', 'prediction fields mismatch')
    probability = row['probability']
    if type(probability) not in (int, float) or not 0 <= probability <= 1 or not math.isfinite(probability):
        refuse('SCHEMA', 'probability must be finite numeric [0,1], not bool')
    made_at = timestamp(row['made_at'], 'made_at'); horizon = timestamp(row['horizon'], 'horizon')
    if horizon <= made_at:
        refuse('TIME', 'horizon must be strictly after made_at')
    return {'prediction_id': text(row['prediction_id'], 'prediction_id'), 'claim': text(row['claim'], 'claim'),
            'probability': float(probability), 'horizon': iso(horizon), 'source': text(row['source'], 'source'),
            'made_at': iso(made_at)}


def validate_resolution(row, predictions):
    if not isinstance(row, dict) or set(row) != RES_KEYS:
        refuse('SCHEMA', 'resolution fields mismatch')
    ident = text(row['prediction_id'], 'prediction_id')
    if ident not in predictions:
        refuse('REFERENCE', 'resolution references unknown prediction')
    if type(row['outcome']) is not bool:
        refuse('SCHEMA', 'outcome must be exactly bool')
    resolved_at = timestamp(row['resolved_at'], 'resolved_at')
    if resolved_at < timestamp(predictions[ident]['horizon'], 'horizon'):
        refuse('TIME', 'resolution must be at or after horizon')
    return {'prediction_id': ident, 'outcome': row['outcome'], 'resolved_at': iso(resolved_at)}


def banks(predictions, resolutions):
    if not isinstance(predictions, list) or not isinstance(resolutions, list):
        refuse('SCHEMA', 'prediction and resolution collections must be lists')
    if len(predictions) > MAX_PREDICTIONS or len(resolutions) > MAX_PREDICTIONS:
        refuse('LIMIT', 'prediction/resolution cap exceeded')
    ps = {}; ys = {}
    for raw in predictions:
        row = validate_prediction(raw); ident = row['prediction_id']
        if ident in ps:
            refuse('DUPLICATE', 'duplicate prediction_id')
        ps[ident] = row
    for raw in resolutions:
        row = validate_resolution(raw, ps); ident = row['prediction_id']
        if ident in ys:
            refuse('DUPLICATE', 'duplicate outcome for prediction')
        ys[ident] = row
    return ps, ys


def score_predictions(predictions, resolutions, *, bins=10, calibrated=True):
    """ONE scorer S2.3 imports. Supplied dated binary predictions/outcomes only."""
    guard('analyze', 'j1-offline-scorer')
    if type(bins) is not int or not 1 <= bins <= 100 or type(calibrated) is not bool:
        refuse('SCHEMA', 'bins must be int 1..100 and calibrated exactly bool')
    ps, ys = banks(predictions, resolutions)
    if calibrated and (not ps or len(ys) != len(ps)):
        refuse('UNSCORED', 'calibrated report requires every prediction resolved and a nonempty cohort')
    scored = [(ps[ident]['probability'], float(ys[ident]['outcome'])) for ident in sorted(ys)]
    reliability = []
    for i in range(bins):
        values = [(p, y) for p, y in scored if min(int(p * bins), bins - 1) == i]
        reliability.append({'index': i, 'lower': i / bins, 'upper': (i + 1) / bins, 'count': len(values),
                            'mean_probability': math.fsum(p for p, y in values) / len(values) if values else None,
                            'observed_rate': math.fsum(y for p, y in values) / len(values) if values else None})
    scope = policy.scope(['binary Brier scoring', 'equal-width reliability bins', 'sharpness', 'computed coverage'],
                         ['future predictive skill', 'verified outcomes', 'market feeds', 'trading'],
                         'supplied predictions and outcomes', max((r['resolved_at'] for r in ys.values()), default='unresolved'))
    scope['future_skill_proven'] = False
    return {'unit': 'J1', 'status': 'scored_supplied_cohort' if calibrated else 'descriptive_partial',
            'calibrated_requested': calibrated, 'scored_n': len(scored),
            'calibration_label': 'insufficient_sample' if len(scored) < MIN_CALIBRATION_SAMPLE else 'descriptive_reliability_only',
            'small_sample_caveat': 'fewer than20 scored predictions; no calibration claim' if len(scored) < MIN_CALIBRATION_SAMPLE else None,
            'brier_score': math.fsum((p - y) ** 2 for p, y in scored) / len(scored) if scored else None,
            'sharpness': math.fsum((p - .5) ** 2 for p, y in scored) / len(scored) if scored else None,
            'reliability_bins': reliability, 'coverage': {'predictions': len(ps), 'resolved': len(ys), 'unresolved': len(ps) - len(ys)},
            'unresolved_ids': sorted(set(ps) - set(ys)), 'scope': scope,
            'honesty': 'Scored supplied cohort, not proof the forecaster is calibrated or will predict well.'}


class ForecastLedger:
    """Tenant-bound append-only POSIX JSONL ledger; reload under lock each call."""
    def __init__(self, path, *, tenant_id, policy_guard=None):
        self.path = Path(path)
        self.tenant_id = text(tenant_id, 'tenant_id')
        self.policy_guard = policy_guard
        guard('record', self.tenant_id, policy_guard=self.policy_guard)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._locked() as f:
            events = self._load(f)
            if not events:
                self._append(f, [], 'header', {'version': 1, 'tenant_id': self.tenant_id})
            else:
                self._check(events)

    @contextmanager
    def _locked(self):
        # O_NOFOLLOW rejects the final-component symlink. Parent directories
        # must be trusted host configuration, not caller-controlled paths.
        try:
            fd = os.open(self.path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        except OSError as exc:
            refuse('PATH', str(exc))
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                refuse('PATH', 'ledger must be a regular file')
            with os.fdopen(fd, 'r+b', closefd=False) as f:
                fcntl.flock(fd, fcntl.LOCK_EX)
                try:
                    yield f
                finally:
                    fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)

    def _load(self, f):
        f.seek(0); raw = f.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            refuse('LIMIT', 'ledger byte cap exceeded')
        if raw and not raw.endswith(b'\n'):
            refuse('INTEGRITY', 'incomplete trailing ledger event')
        try:
            events = [json.loads(line) for line in raw.splitlines()]
        except (ValueError, UnicodeDecodeError):
            refuse('INTEGRITY', 'invalid ledger JSON')
        if len(events) > MAX_EVENTS:
            refuse('LIMIT', 'ledger event cap exceeded')
        return events

    def _check(self, events):
        if not events:
            refuse('INTEGRITY', 'missing header')
        prev = '0' * 64; predictions = {}; resolutions = {}
        for index, event in enumerate(events):
            if not isinstance(event, dict) or set(event) != {'seq', 'prev', 'kind', 'data', 'sha256'}:
                refuse('INTEGRITY', 'event fields mismatch')
            body = {k: event[k] for k in ('seq', 'prev', 'kind', 'data')}
            try:
                actual = digest(body)
            except (ValueError, TypeError, RecursionError):
                refuse('INTEGRITY', 'event is not finite JSON')
            if type(event['seq']) is not int or event['seq'] != index or event['prev'] != prev or event['sha256'] != actual:
                refuse('INTEGRITY', 'hash chain or sequence mismatch')
            prev = actual
            if index == 0:
                if event['kind'] != 'header' or not isinstance(event['data'], dict) or set(event['data']) != {'version', 'tenant_id'} or type(event['data']['version']) is not int or event['data']['version'] != 1:
                    refuse('INTEGRITY', 'invalid header')
                if event['data']['tenant_id'] != self.tenant_id:
                    refuse('TENANT', 'ledger belongs to another tenant')
            elif event['kind'] == 'prediction':
                row = validate_prediction(event['data']); ident = row['prediction_id']
                if ident in predictions or ident != digest({k: v for k, v in row.items() if k != 'prediction_id'}):
                    refuse('INTEGRITY', 'duplicate or invalid content-bound prediction ID')
                predictions[ident] = row
            elif event['kind'] == 'resolution':
                row = validate_resolution(event['data'], predictions); ident = row['prediction_id']
                if ident in resolutions:
                    refuse('INTEGRITY', 'duplicate resolution')
                resolutions[ident] = row
            else:
                refuse('INTEGRITY', 'unknown event kind')
        if len(predictions) > MAX_PREDICTIONS:
            refuse('LIMIT', 'prediction cap exceeded')
        return predictions, resolutions

    def _append(self, f, events, kind, data):
        if len(events) >= MAX_EVENTS:
            refuse('LIMIT', 'ledger event cap reached')
        body = {'seq': len(events), 'prev': events[-1]['sha256'] if events else '0' * 64, 'kind': kind, 'data': data}
        event = dict(body, sha256=digest(body)); line = (canonical(event) + '\n').encode()
        f.seek(0, os.SEEK_END)
        if f.tell() + len(line) > MAX_BYTES:
            refuse('LIMIT', 'ledger byte cap reached')
        f.write(line); f.flush(); os.fsync(f.fileno())

    def append_prediction(self, *, claim, probability, horizon, source, made_at):
        guard('record', self.tenant_id, policy_guard=self.policy_guard)
        row = validate_prediction({'prediction_id': 'pending', 'claim': claim, 'probability': probability,
                                   'horizon': horizon, 'source': source, 'made_at': made_at})
        row['prediction_id'] = digest({k: v for k, v in row.items() if k != 'prediction_id'})
        with self._locked() as f:
            events = self._load(f); ps, ys = self._check(events)
            if row['prediction_id'] in ps:
                return dict(ps[row['prediction_id']])
            if len(ps) >= MAX_PREDICTIONS:
                refuse('LIMIT', 'prediction cap reached')
            self._append(f, events, 'prediction', row)
        return dict(row)

    def resolve(self, prediction_id, *, outcome, resolved_at):
        guard('record', self.tenant_id, policy_guard=self.policy_guard)
        with self._locked() as f:
            events = self._load(f); ps, ys = self._check(events)
            row = validate_resolution({'prediction_id': prediction_id, 'outcome': outcome, 'resolved_at': resolved_at}, ps)
            if prediction_id in ys:
                if row != ys[prediction_id]:
                    refuse('CONFLICT', 'resolution is immutable')
                return dict(row)
            self._append(f, events, 'resolution', row)
        return dict(row)

    def report(self, *, calibrated=True, bins=10):
        guard('read', self.tenant_id, policy_guard=self.policy_guard)
        with self._locked() as f:
            events = self._load(f); ps, ys = self._check(events)
        return score_predictions(list(ps.values()), list(ys.values()), calibrated=calibrated, bins=bins)
