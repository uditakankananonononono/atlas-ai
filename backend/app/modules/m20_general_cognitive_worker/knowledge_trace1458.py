"""Conditional BKT arithmetic from scored attempts and declared parameters.

No fitting, hidden-trait inference, persistence, I/O, or verified learner mastery.
Observations precede learning; predictions refer to the next attempt. The caller
must bind tenant_id and actor_id from its authenticated principal.
"""
from __future__ import annotations

from copy import deepcopy
import unicodedata
from datetime import datetime, timezone
import math
import re
from typing import Any

MAX_ATTEMPTS = 512
MAX_SKILLS = 64
MAX_SOURCES = 128
MAX_ID_LENGTH = 256
_TIMESTAMP = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$')


class KnowledgeTraceError(ValueError):
    """Unsupported, malformed, ambiguous, or cross-tenant supplied evidence."""


def _text(value: Any, field: str, limit: int = MAX_ID_LENGTH) -> str:
    if type(value) is not str or len(value) > limit or not value.strip():
        raise KnowledgeTraceError(f'{field} requires non-empty text <= {limit} characters')
    if value != value.strip() or any(unicodedata.category(c) in ('Cc', 'Zl', 'Zp') or 0x200B <= ord(c) <= 0x200F or 0x202A <= ord(c) <= 0x202E or 0x2066 <= ord(c) <= 0x2069 or ord(c) == 0xFEFF for c in value):
        raise KnowledgeTraceError(f'{field} has whitespace or control characters')
    return value


def _shape(value: Any, keys: set[str], field: str) -> dict:
    if type(value) is not dict or set(value) != keys:
        raise KnowledgeTraceError(f'{field} requires exactly {sorted(keys)}')
    return value


def _probability(value: Any, field: str) -> float:
    if type(value) not in (int, float):
        raise KnowledgeTraceError(f'{field} requires a finite numeric probability')
    try:
        number = float(value)
    except (ValueError, OverflowError):
        raise KnowledgeTraceError(f'{field} requires a finite probability in [0,1]') from None
    if not math.isfinite(number) or not 0 <= number <= 1:
        raise KnowledgeTraceError(f'{field} requires a finite probability in [0,1]')
    return number


def _instant(value: Any) -> datetime:
    if type(value) is not str or not _TIMESTAMP.fullmatch(value):
        raise KnowledgeTraceError('occurred_at requires an aware ISO timestamp with seconds')
    try:
        instant = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return instant.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        raise KnowledgeTraceError('occurred_at is not a supported timestamp') from None


def trace(payload: dict[str, Any], *, tenant_id: str, actor_id: str) -> dict[str, Any]:
    """Validate the whole request before calculating independent histories.

    Fail closed on shape/source/identity/order errors. Empty evidence or an
    impossible scored sequence abstains rather than manufacturing a posterior.
    A single scored observation permits conditional arithmetic only, not an
    estimate of fitted parameters, efficacy, confidence, or actual ability.
    """
    tenant_id = _text(tenant_id, 'tenant_id')
    actor_id = _text(actor_id, 'actor_id')
    p = _shape(payload, {'source', 'sources', 'parameters', 'attempts'}, 'payload')
    source = _shape(p['source'], {'title', 'url'}, 'source')
    _text(source['title'], 'source.title', 2048)
    url = _text(source['url'], 'source.url', 2048)
    if not url.startswith(('https://', 'http://')):
        raise KnowledgeTraceError('source.url requires an http(s) reference; it is not fetched')
    sources = p['sources']
    if type(sources) is not dict or not 1 <= len(sources) <= MAX_SOURCES:
        raise KnowledgeTraceError(f'sources requires 1..{MAX_SOURCES} declared references')
    for name, citation in sources.items():
        _text(name, 'source_id')
        _text(citation, 'source citation', 2048)

    declared = p['parameters']
    if type(declared) is not dict or not 1 <= len(declared) <= MAX_SKILLS:
        raise KnowledgeTraceError(f'parameters requires 1..{MAX_SKILLS} per-skill declarations')
    parameters = {}
    for skill, raw in declared.items():
        _text(skill, 'skill')
        raw = _shape(raw, {'prior', 'learn', 'guess', 'slip', 'source_id'}, 'parameters')
        ref = _text(raw['source_id'], 'parameters.source_id')
        if ref not in sources:
            raise KnowledgeTraceError('parameters reference unknown source_id')
        parameters[skill] = {key: _probability(raw[key], key) for key in ('prior', 'learn', 'guess', 'slip')}
        parameters[skill]['source_id'] = ref

    attempts = p['attempts']
    if type(attempts) is not list or len(attempts) > MAX_ATTEMPTS:
        raise KnowledgeTraceError(f'attempts requires a list of at most {MAX_ATTEMPTS}')
    groups: dict[tuple[str, str], list[tuple[dict, datetime]]] = {}
    seen, last = set(), {}
    for raw in attempts:
        e = _shape(raw, {'attempt_id', 'tenant_id', 'learner_id', 'skill', 'correct', 'occurred_at', 'source_id'}, 'attempt')
        for field in ('attempt_id', 'tenant_id', 'learner_id', 'skill', 'source_id'):
            _text(e[field], field)
        if e['tenant_id'] != tenant_id:
            raise KnowledgeTraceError('attempt tenant mismatches authenticated tenant')
        if e['attempt_id'] in seen:
            raise KnowledgeTraceError('duplicate attempt_id (including contradictory repeats)')
        seen.add(e['attempt_id'])
        if type(e['correct']) is not bool:
            raise KnowledgeTraceError('correct requires an explicitly supplied boolean score')
        if e['skill'] not in parameters:
            raise KnowledgeTraceError('attempt skill has no declared parameters')
        if e['source_id'] not in sources:
            raise KnowledgeTraceError('attempt references unknown source_id')
        instant = _instant(e['occurred_at'])
        key = (e['learner_id'], e['skill'])
        if key in last and instant <= last[key]:
            raise KnowledgeTraceError('history requires strictly increasing chronology, without ties')
        last[key] = instant
        groups.setdefault(key, []).append((e, instant))

    result = {
        'row_id': 1458, 'scope': {'tenant_id': tenant_id, 'actor_id': actor_id},
        'source': deepcopy(source), 'sources': deepcopy(sources),
        'parameters': deepcopy(declared), 'parameter_source': 'declared_caller',
        'update_order': 'observation_then_learning', 'fitted_to_data': False,
        'learner_mastery_verified': False, 'histories': [],
        'limitations': ['Conditional model arithmetic only, not actual learner mastery or psychometrics.',
                        'No parameter fitting, confidence estimate, forgetting, or unscored-event inference.',
                        'Binary scores and source declarations are caller supplied and not independently verified.',
                        'One observation supports arithmetic only; sparse evidence does not establish validity.',
                        'Educator review required; no grades, credentials, or high-stakes decisions.'],
    }
    if not attempts:
        return {**result, 'status': 'abstained', 'reason': 'no_scored_attempts'}

    for (learner, skill), events in sorted(groups.items()):
        par = parameters[skill]
        state = par['prior']
        h = {'learner_id': learner, 'skill': skill, 'parameter_source_id': par['source_id'],
             'steps': [], 'observation_count': 0, 'supplied_attempt_count': len(events),
             'status': 'conditional_calculation'}
        for e, instant in events:
            known_likelihood = 1 - par['slip'] if e['correct'] else par['slip']
            unknown_likelihood = par['guess'] if e['correct'] else 1 - par['guess']
            known_weight = state * known_likelihood
            likelihood = known_weight + (1 - state) * unknown_likelihood
            if likelihood == 0:
                h.update(status='abstained', reason='zero_likelihood_observation',
                         failed_attempt_id=e['attempt_id'], failed_source_id=e['source_id'],
                         failed_occurred_at=e['occurred_at'], posterior=None,
                         after_learning=None, predicted_success_next=None)
                break
            posterior = known_weight / likelihood
            after = posterior + (1 - posterior) * par['learn']
            predicted = after * (1 - par['slip']) + (1 - after) * par['guess']
            h['steps'].append({
                'attempt_id': e['attempt_id'], 'source_id': e['source_id'],
                'occurred_at': e['occurred_at'], 'occurred_at_utc': instant.isoformat(),
                'correct': e['correct'], 'prior': state, 'likelihood': likelihood,
                'posterior': posterior, 'after_learning': after, 'predicted_success_next': predicted,
            })
            h.update(posterior=posterior, after_learning=after, predicted_success_next=predicted)
            h['observation_count'] += 1
            state = after
        result['histories'].append(h)
    count = sum(h['status'] == 'abstained' for h in result['histories'])
    result['status'] = ('abstained' if count == len(groups) else 'partial_abstention' if count else 'conditional_calculation')
    return result
