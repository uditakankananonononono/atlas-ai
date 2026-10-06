"""Measured strategy calibration for learning, not autonomous self-awareness.

Uses scored attempts and pre-attempt probability predictions. No model,
synthetic outcomes, or fixed success claims. Strategy selection minimizes
observed Brier loss; evidence is returned so callers can inspect the choice.
"""
from __future__ import annotations
from math import isfinite
from statistics import mean
from typing import Any


def calibrate_attempts(attempts: list[dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(attempts, list) or not attempts:
        raise ValueError('attempts must contain scored observations')
    groups: dict[str, list[dict[str, Any]]] = {}
    seen: set[str] = set()
    observations = []
    for attempt in attempts:
        if not isinstance(attempt, dict):
            raise ValueError('each attempt must be an object')
        ident = attempt.get('id')
        strategy = attempt.get('strategy')
        evidence = attempt.get('evidence_id')
        if not all(isinstance(v, str) and v.strip() for v in (ident, strategy, evidence)):
            raise ValueError('attempt needs id, strategy and evidence_id')
        if ident in seen:
            raise ValueError('attempt ids must be unique')
        seen.add(ident)
        probability, outcome = attempt.get('predicted_success'), attempt.get('succeeded')
        if isinstance(probability, bool) or not isinstance(probability, (float, int)):
            raise ValueError('predicted_success must be a numeric probability')
        if not isfinite(probability) or not 0 <= probability <= 1 or type(outcome) is not bool:
            raise ValueError('probability must be finite in [0,1] and succeeded must be bool')
        error = probability - int(outcome)
        row = {'id': ident, 'strategy': strategy, 'evidence_id': evidence,
               'predicted_success': probability, 'succeeded': outcome,
               'signed_error': error, 'brier_loss': error ** 2}
        observations.append(row)
        groups.setdefault(strategy, []).append(row)
    metrics = []
    for strategy, rows in sorted(groups.items()):
        metrics.append({'strategy': strategy, 'n': len(rows),
                        'brier_loss': mean(r['brier_loss'] for r in rows),
                        'overconfidence': mean(r['signed_error'] for r in rows),
                        'observed_success_rate': mean(int(r['succeeded']) for r in rows),
                        'evidence_ids': [r['evidence_id'] for r in rows]})
    loss = min(m['brier_loss'] for m in metrics)
    best = [m['strategy'] for m in metrics if m['brier_loss'] == loss]
    return {'observations': observations, 'strategies': metrics,
            'brier_loss': mean(r['brier_loss'] for r in observations),
            'overconfidence': mean(r['signed_error'] for r in observations),
            'best_observed_strategies': best,
            'recommended_strategy': best[0] if len(best) == 1 else None,
            'boundary': 'Descriptive calibration of caller-supplied scored attempts. Not causal evidence that one strategy is better, not proof of understanding or autonomous metacognition.'}
