"""Measured, small local classification experiment, not sector breakthroughs.

Train a nearest-centroid classifier on labeled numeric vectors, evaluate on
ID-disjoint heldout cases and compare with a training-majority baseline.
Model files contain learned centroids, not caller-supplied victory labels.
Scope is a dataset experiment, not universal tool superiority.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
from pathlib import Path


def _rows(rows, *, dimension=None):
    if type(rows) is not list or not 1 <= len(rows) <= 10000:
        raise ValueError('one to 10000 labeled rows required')
    out, ids = [], set()
    for row in rows:
        if type(row) is not dict or set(row) != {'id', 'features', 'label'}:
            raise ValueError('row requires id, features and label')
        if any(type(row[k]) is not str or not row[k].strip() or len(row[k]) > 128 for k in ('id', 'label')):
            raise ValueError('bounded string id and label required')
        if row['id'] in ids:
            raise ValueError('duplicate row id')
        ids.add(row['id'])
        vector = row['features']
        if type(vector) is not list or not 1 <= len(vector) <= 256:
            raise ValueError('bounded feature vector required')
        if dimension is None:
            dimension = len(vector)
        if len(vector) != dimension or any(type(x) not in (int, float) or not math.isfinite(x) or abs(x) > 1e12 for x in vector):
            raise ValueError('finite equal-length numeric feature vectors required')
        out.append({'id': row['id'], 'features': list(vector), 'label': row['label']})
    return out, dimension


def experiment(training: list, heldout: list, *, model_output: Path | None = None) -> dict:
    train, dimension = _rows(training)
    test, _ = _rows(heldout, dimension=dimension)
    if {r['id'] for r in train} & {r['id'] for r in test}:
        raise ValueError('training and heldout ids overlap')
    labels = sorted({r['label'] for r in train})
    if not 2 <= len(labels) <= 256 or any(r['label'] not in labels for r in test):
        raise ValueError('two to 256 training classes and known heldout labels required')
    # Also refuse exact duplicate labeled observations leaking across splits.
    train_vectors = {(tuple(r['features']), r['label']) for r in train}
    if any((tuple(r['features']), r['label']) in train_vectors for r in test):
        raise ValueError('exact observation leaked across split')
    centers = {}
    for label in labels:
        vectors = [r['features'] for r in train if r['label'] == label]
        centers[label] = [math.fsum(v[i] for v in vectors) / len(vectors) for i in range(dimension)]
    raw_train = json.dumps(train, sort_keys=True, allow_nan=False, separators=(',', ':'))
    raw_test = json.dumps(test, sort_keys=True, allow_nan=False, separators=(',', ':'))
    model = {'algorithm': 'nearest-centroid-euclidean-v1', 'dimension': dimension,
             'centroids': centers, 'training_sha256': hashlib.sha256(raw_train.encode()).hexdigest()}
    majority = sorted(Counter(r['label'] for r in train).items(), key=lambda pair: (-pair[1], pair[0]))[0][0]
    predictions, correct, baseline_correct = [], 0, 0
    for row in test:
        prediction = min(labels, key=lambda label: (math.fsum((x-c)**2 for x,c in zip(row['features'], centers[label])), label))
        correct += prediction == row['label']
        baseline_correct += majority == row['label']
        predictions.append({'id': row['id'], 'expected': row['label'], 'predicted': prediction})
    receipt = None
    if model_output is not None:
        if not isinstance(model_output, Path) or not model_output.is_absolute() or any(p.is_symlink() for p in (model_output, *model_output.parents)):
            raise ValueError('absolute non-symlink model output required')
        raw = json.dumps(model, sort_keys=True, allow_nan=False)
        with model_output.open('x') as stream:
            stream.write(raw)
        receipt = {'path': str(model_output), 'sha256': hashlib.sha256(raw.encode()).hexdigest()}
    return {'model': model, 'model_file': receipt, 'heldout_sha256': hashlib.sha256(raw_test.encode()).hexdigest(),
            'training_count': len(train), 'heldout_count': len(test), 'predictions': predictions,
            'accuracy': correct / len(test), 'majority_baseline_accuracy': baseline_correct / len(test),
            'beats_training_majority_on_this_split': correct > baseline_correct,
            'breakthrough_claim': False,
            'limits': 'Unscaled Euclidean centroid classifier on supplied numeric data only. '
                      'Split independence beyond IDs/exact duplicates, generalization and domain validity are unverified.'}
