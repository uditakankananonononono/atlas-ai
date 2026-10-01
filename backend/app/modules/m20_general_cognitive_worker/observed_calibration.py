"""Measured calibration over supplied binary outcomes, reusing the core engine.

This endpoint is a batch analysis, not proof that caller outcomes are genuine.
It does not persist owner state or silently alter a live execution strategy.
"""
from __future__ import annotations
import math
from .metacognition import CalibrationEngine


def analyze(payload):
    predictions, outcomes = payload.get('predictions'), payload.get('outcomes')
    if not isinstance(predictions, list) or not isinstance(outcomes, list) or not predictions or len(predictions) != len(outcomes):
        raise ValueError('aligned nonempty predictions and outcomes are required')
    if len(predictions) > 10000:
        raise ValueError('at most 10000 observations per batch')
    if any(isinstance(p, bool) or not isinstance(p, (int, float)) or not math.isfinite(p) or not 0 <= p <= 1 for p in predictions):
        raise ValueError('predictions must be finite probabilities in [0,1]')
    if any(type(o) not in (bool, int) or o not in (0,1) for o in outcomes):
        raise ValueError('outcomes must be binary observed results, not inferred labels')
    engine = CalibrationEngine()
    for i, (probability, observed) in enumerate(zip(predictions, outcomes)):
        claim = engine.assess_claim(f'caller observation {i}', float(probability), evidence_count=1)
        engine.resolve(claim.id, bool(observed))
    accuracy = sum(outcomes)/len(outcomes)
    brier = sum((p-o)**2 for p,o in zip(predictions,outcomes))/len(outcomes)
    mean_prediction = sum(predictions)/len(predictions)
    adjustments = []
    if len(predictions) >= 5:
        adjustments = [{'observation_index': i, 'original': p,
                        'suggested_confidence': engine.adjusted_confidence(p)} for i,p in enumerate(predictions)]
    return {'execution_status': 'batch_calibration_executed', 'sample_count': len(predictions),
            'observed_accuracy': accuracy, 'mean_prediction': mean_prediction,
            'brier_score': brier, 'expected_calibration_error': engine.calibration_error(),
            'calibration_curve': engine.calibration_curve(),
            'overconfidence_gap': mean_prediction-accuracy,
            'adjustments': adjustments,
            'surprises': [{'observation_index':i,'prediction':p,'observed':o,'absolute_error':abs(p-o)}
                          for i,(p,o) in enumerate(zip(predictions,outcomes)) if abs(p-o)>=.5],
            'strategy_review': 'review evidence and reduce unsupported confidence' if mean_prediction-accuracy>.1 else 'retain strategy pending more outcome evidence',
            'calibration_required': True,
            'limits': ['Caller-supplied outcomes are not independently verified.',
                       'Small-sample results may be unstable; adjustments need at least five observations.',
                       'Batch analysis does not persist state or change a live action plan.',
                       'Core GCWRuntime supplies the separate durable prediction/outcome control loop.']}
