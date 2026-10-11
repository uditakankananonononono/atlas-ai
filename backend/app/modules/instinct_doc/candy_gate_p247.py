"""Declared-input release gate for doc line [P247|L195] (offline, stdlib only).

Decides whether a release is blocked, from gate conditions the caller declares
in advance and observations the caller supplies. The module computes each
gate's state itself (GREEN, RED, MISSING or INVALID). A caller-supplied label
such as status, green or done is not an input: in a gate declaration it is
refused, in an observation it makes that gate INVALID.

release is true only when at least one gate is declared and every declared
gate is computed GREEN. GREEN means only that the supplied observation
satisfied the declared condition. It is not proof that any work is actually
complete, correct or honest, and it cannot detect a gate nobody declared. The
module takes no action: it returns a decision and nothing else.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

FEATURE = 'candy_gate_p247'
SOURCE_LINES = ['P247|L195']
MAX_GATES = 50
MAX_REQUIRED = 200
MAX_PRESENT = 1000
MAX_AGE_DAYS_CEILING = 3650
MAX_DATE_TEXT = 40
_HEX64 = re.compile(r'[0-9a-f]{64}')

_KIND_FIELDS = {
    'all_present': {'required'},
    'count_equals': {'expected'},
    'digest_equals': {'expected_sha256'},
    'fresh_within': {'max_age_days'},
}
_OBS_FIELDS = {
    'all_present': {'present'},
    'count_equals': {'count'},
    'digest_equals': {'sha256'},
    'fresh_within': {'checked_at'},
}
METHOD_LIMITS = (
    'Computes each gate from the declared condition and the supplied observation only. GREEN is '
    'not proof that the underlying work is complete, correct or honest, and a missing or '
    'dishonest declared gate cannot be detected. No live policy or legal enforcement. The '
    'module returns a decision and performs no action.'
)


def _check_gate(i: int, gate: Any) -> dict:
    if not isinstance(gate, dict):
        raise ValueError(f'gate {i} must be an object')
    gid = gate.get('id')
    if not isinstance(gid, str) or not gid.strip():
        raise ValueError('gate id must be a non-empty string')
    kind = gate.get('kind')
    if kind not in _KIND_FIELDS:
        raise ValueError(f'gate {gid} has unknown kind {kind}')
    allowed = {'id', 'kind'} | _KIND_FIELDS[kind]
    for k in sorted(gate, key=str):
        if k not in allowed:
            raise ValueError(f'gate {gid} has unsupported field {k}')
    for k in sorted(_KIND_FIELDS[kind]):
        if k not in gate:
            raise ValueError(f'gate {gid} needs {k}')
    if kind == 'count_equals':
        e = gate['expected']
        if isinstance(e, bool) or not isinstance(e, int) or e < 0:
            raise ValueError(f'gate {gid} expected must be a non-negative integer')
    elif kind == 'all_present':
        r = gate['required']
        if (not isinstance(r, list) or not 1 <= len(r) <= MAX_REQUIRED
                or any(not isinstance(x, str) or not x.strip() for x in r) or len(set(r)) != len(r)):
            raise ValueError(f'gate {gid} required must be a list of 1 to {MAX_REQUIRED} unique non-empty strings')
    elif kind == 'digest_equals':
        h = gate['expected_sha256']
        if not isinstance(h, str) or not _HEX64.fullmatch(h):
            raise ValueError(f'gate {gid} expected_sha256 must be 64 lowercase hex characters')
    else:
        m = gate['max_age_days']
        if isinstance(m, bool) or not isinstance(m, int) or not 1 <= m <= MAX_AGE_DAYS_CEILING:
            raise ValueError(f'gate {gid} max_age_days must be an integer from 1 to {MAX_AGE_DAYS_CEILING}')
    return gate


def _parse_checked_at(raw: Any) -> datetime | None:
    if not isinstance(raw, str):
        return None
    s = raw.strip()
    if not s or len(s) > MAX_DATE_TEXT:
        return None
    if s[-1] in 'zZ':
        s = s[:-1] + '+00:00'
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None or dt.utcoffset() is None:
        return None
    return dt.astimezone(timezone.utc)


def _state(gate: dict, obs: Any, now: datetime | None) -> tuple[str, str]:
    kind = gate['kind']
    if obs is None:
        return 'MISSING', 'missing_observation'
    if not isinstance(obs, dict):
        return 'INVALID', 'invalid_observation:observation'
    allowed_obs = _OBS_FIELDS[kind]
    for k in sorted(obs, key=str):
        if k not in allowed_obs:
            return 'INVALID', f'unsupported_observation_field:{k}'
    if kind == 'count_equals':
        c = obs.get('count')
        if isinstance(c, bool) or not isinstance(c, int) or c < 0:
            return 'INVALID', 'invalid_observation:count'
        if obs['count'] == gate['expected']:
            return 'GREEN', 'declared_condition_met'
        return 'RED', 'count_mismatch'
    if kind == 'all_present':
        present = obs.get('present')
        if (not isinstance(present, list) or len(present) > MAX_PRESENT
                or any(not isinstance(p, str) for p in present)):
            return 'INVALID', 'invalid_observation:present'
        missing = sorted(set(gate['required']) - set(present))
        if missing:
            return 'RED', 'missing_items:' + ','.join(missing)
        return 'GREEN', 'declared_condition_met'
    if kind == 'digest_equals':
        obs_sha = obs.get('sha256')
        if not isinstance(obs_sha, str) or not _HEX64.fullmatch(obs_sha):
            return 'INVALID', 'invalid_observation:sha256'
        if obs_sha != gate['expected_sha256']:
            return 'RED', 'digest_mismatch'
        return 'GREEN', 'declared_condition_met'
    checked = _parse_checked_at(obs.get('checked_at'))
    if checked is None:
        return 'INVALID', 'invalid_observation:checked_at'
    if checked > now:
        return 'RED', 'checked_at_future'
    age = now - checked
    if age > timedelta(days=gate['max_age_days']):
        return 'RED', 'stale'
    return 'GREEN', 'declared_condition_met'


def evaluate(spec: dict, observations: dict, now: datetime | None = None) -> dict:
    if not isinstance(spec, dict):
        raise ValueError('spec must be an object')
    for k in sorted(spec, key=str):
        if k != 'gates':
            raise ValueError(f'spec has unsupported field {k}')
    if not isinstance(spec.get('gates'), list):
        raise ValueError('spec needs gates as a list')
    if not isinstance(observations, dict):
        raise ValueError('observations must be an object')
    if now is not None and (not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None):
        raise ValueError('now must be a timezone-aware datetime')
    gates = spec['gates']
    if len(gates) > MAX_GATES:
        raise ValueError(f'at most {MAX_GATES} gates are allowed, got {len(gates)}')
    ids: set[str] = set()
    checked_gates = []
    for i, raw in enumerate(gates):
        gate = _check_gate(i, raw)
        gid = gate['id']
        if gid in ids:
            raise ValueError(f'duplicate gate id {gid}')
        ids.add(gid)
        checked_gates.append(gate)
    needs_now = any(g['kind'] == 'fresh_within' for g in checked_gates)
    if needs_now and now is None:
        raise ValueError('now is required for fresh_within gates')
    for oid in sorted(observations, key=str):
        if oid not in ids:
            raise ValueError(f'observation for unknown gate {oid}')
    if now is not None:
        now = now.astimezone(timezone.utc)

    results = []
    for gate in checked_gates:
        st, reason = _state(gate, observations.get(gate['id']), now)
        results.append({'id': gate['id'], 'kind': gate['kind'], 'state': st, 'reason': reason})
    results.sort(key=lambda x: x['id'])
    release = bool(results) and all(x['state'] == 'GREEN' for x in results)
    counts = {'gates': len(results)}
    for name in ('GREEN', 'RED', 'MISSING', 'INVALID'):
        counts[name] = sum(1 for x in results if x['state'] == name)
    if not results:
        reason = 'no_gates_declared'
    else:
        reason = 'all_declared_gates_green' if release else 'blocked'
    return {
        'feature': FEATURE, 'source_lines': list(SOURCE_LINES), 'release': release, 'reason': reason,
        'blocked_by': [x['id'] for x in results if x['state'] != 'GREEN'],
        'gates': results, 'counts': counts, 'action': 'none', 'method_limits': METHOD_LIMITS,
    }
