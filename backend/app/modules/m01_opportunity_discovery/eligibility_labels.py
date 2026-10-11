"""Reviewed-label recorder, gate counter, grouped split and held-out evaluation for the M1 eligibility classifier.

Bookkeeping over caller-supplied, human-reviewed labels only. It never trains a model, never loads one, never
generates or infers a label, and never claims an accuracy it did not compute from supplied labels and predictions.
The readiness contract of record is classifier.fine_tune_ready (500 labels in total, 100 per class).
"""
from __future__ import annotations

import datetime
import hashlib
import re
import unicodedata
from typing import Any

from .classifier import MIN_FINE_TUNE_LABELS, MIN_PER_CLASS, fine_tune_ready

ALGORITHM = "eligibility_label_harness_v1"
PREFIX = "ELIGLAB"
LABELS = ("eligible", "ineligible", "unclear")
SOURCES = ("human_reviewed", "synthetic", "model_generated", "rule_derived")
HUMAN = "human_reviewed"
SPLITS = ("train", "dev", "test")
MAX_RECORDS = 20000
MAX_KEYS = 8
MAX_KEY_CHARS = 64
MAX_RAW_STR = 10000
MAX_ID = 128
MAX_TEXT = 8000
MAX_PROFILE = 4000
MAX_LABEL = 16
MAX_SOURCE = 16
MAX_REVIEWER = 64
MAX_DATE = 10
MAX_SEED = 64
TRAIN_BUCKETS = 8000          # of 10000: 80% train, 10% dev, 10% test by group hash
DEV_BUCKETS = 9000
KEYS = ("record_id", "group_id", "text", "profile", "label", "label_source", "reviewer", "reviewed_at")
_CAPS = (("record_id", MAX_ID), ("group_id", MAX_ID), ("text", MAX_TEXT), ("profile", MAX_PROFILE),
         ("label", MAX_LABEL), ("label_source", MAX_SOURCE), ("reviewer", MAX_REVIEWER), ("reviewed_at", MAX_DATE))
_ID = re.compile(r"[A-Za-z0-9_.:-]{1,128}")
_REVIEWER = re.compile(r"[A-Za-z0-9_.@-]{1,64}")
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_FORBIDDEN = frozenset({"Cc", "Cf", "Zl", "Zp"})
_PROSE_OK = frozenset({"\n", "\r", "\t"})
LIMITS = [
    "labels are caller-supplied: this unit does not verify that a reviewer exists or that a review took place",
    "no model is trained, loaded or evaluated here: held-out metrics are computed only from supplied gold labels and supplied predictions",
    "readiness is classifier.fine_tune_ready over human-reviewed labels only; synthetic, model-generated and rule-derived labels never count and are refused",
    "metrics describe the supplied held-out records only and say nothing about other opportunity types, sources or applicants",
]


def _refuse(reason: str, field: str) -> None:
    raise ValueError("%s_REFUSED_%s:%s" % (PREFIX, reason, field))


def _preflight(records: Any, field: str) -> None:
    """Cardinality and raw sizes only: no per-character work, subclasses refused unmeasured."""
    if type(records) is not list:
        _refuse("BAD_TYPE", field)
    if len(records) > MAX_RECORDS:
        _refuse("OVERSIZE", field)
    for rec in records:
        if type(rec) is not dict:
            _refuse("BAD_TYPE", field)
        if len(rec) > MAX_KEYS:
            _refuse("OVERSIZE", field)
        for k, v in rec.items():
            if type(k) is not str:
                _refuse("BAD_TYPE", "key")
            if len(k) > MAX_KEY_CHARS:
                _refuse("OVERSIZE", field)
            if type(v) is str and len(v) > MAX_RAW_STR:
                _refuse("OVERSIZE", field)


def _check_keys(records: list) -> None:
    for rec in records:
        if any(k not in KEYS for k in rec):
            _refuse("UNKNOWN", "record")
    for rec in records:
        for k in KEYS:
            if k not in rec:
                _refuse("MISSING", k)


def _caps_pass(records: list) -> None:
    """Each field's own raw cap across every record before any content is looked at."""
    for rec in records:
        for f, cap in _CAPS:
            v = rec[f]
            if type(v) is str and len(v) > cap:
                _refuse("OVERSIZE", f)


def _text(v: Any, f: str, prose: bool) -> str:
    if type(v) is not str:
        _refuse("BAD_TYPE", f)
    for c in v:
        if unicodedata.category(c) in _FORBIDDEN and not (prose and c in _PROSE_OK):
            _refuse("CONTROL_CHARS", f)
    return v


def _record(rec: dict) -> dict:
    out = {}
    for f in ("record_id", "group_id"):
        v = _text(rec[f], f, False)
        if not _ID.fullmatch(v):
            _refuse("BAD_FORMAT", f)
        out[f] = v
    for f in ("text", "profile"):
        v = _text(rec[f], f, True)
        if not v.strip():
            _refuse("BAD_VALUE", f)
        out[f] = v
    label = _text(rec["label"], "label", False)
    if label not in LABELS:
        _refuse("BAD_VALUE", "label")
    out["label"] = label
    src = _text(rec["label_source"], "label_source", False)
    if src not in SOURCES:
        _refuse("BAD_VALUE", "label_source")
    if src != HUMAN:
        _refuse("SYNTHETIC", "label_source")
    out["label_source"] = src
    rev = _text(rec["reviewer"], "reviewer", False)
    if not _REVIEWER.fullmatch(rev):
        _refuse("BAD_FORMAT", "reviewer")
    out["reviewer"] = rev
    date = _text(rec["reviewed_at"], "reviewed_at", False)
    if not _DATE.fullmatch(date) or not _real_day(date):
        _refuse("BAD_FORMAT", "reviewed_at")
    out["reviewed_at"] = date
    return out


def _real_day(s: str) -> bool:
    try:
        datetime.date.fromisoformat(s)
    except ValueError:
        return False
    return True


def _validated(records: Any, field: str = "records") -> list:
    _preflight(records, field)
    _check_keys(records)
    _caps_pass(records)
    out, seen = [], set()
    for rec in records:
        r = _record(rec)
        if r["record_id"] in seen:
            _refuse("DUPLICATE", "record_id")
        seen.add(r["record_id"])
        out.append(r)
    return out


def add_label(records: Any, record: Any) -> list:
    """Return a new list holding the validated records plus one more reviewed label. The input is not modified."""
    current = _validated(records)
    if type(record) is not dict:
        _refuse("BAD_TYPE", "record")
    _preflight([record], "record")
    _check_keys([record])
    _caps_pass([record])
    new = _record(record)
    if any(r["record_id"] == new["record_id"] for r in current):
        _refuse("DUPLICATE", "record_id")
    if len(current) + 1 > MAX_RECORDS:
        _refuse("OVERSIZE", "records")
    return current + [new]


def _counts(records: list) -> dict:
    counts = dict.fromkeys(LABELS, 0)
    for r in records:
        counts[r["label"]] += 1
    return counts


def gate_status(records: Any) -> dict:
    """Class counts against classifier.fine_tune_ready, which is the contract of record."""
    recs = _validated(records)
    counts = _counts(recs)
    return {"algorithm": ALGORITHM, "total": len(recs), "counts": counts,
            "ready": fine_tune_ready(dict(counts)),
            "required_total": MIN_FINE_TUNE_LABELS, "required_per_class": MIN_PER_CLASS,
            "total_shortfall": max(0, MIN_FINE_TUNE_LABELS - len(recs)),
            "class_shortfalls": {k: max(0, MIN_PER_CLASS - counts[k]) for k in LABELS},
            "label_source_counted": HUMAN, "model_trained": False, "labels_generated": False,
            "limits": list(LIMITS)}


def _seed(seed: Any) -> str:
    if type(seed) is not str:
        _refuse("BAD_TYPE", "seed")
    if len(seed) > MAX_SEED:
        _refuse("OVERSIZE", "seed")
    if not _ID.fullmatch(seed):
        _refuse("BAD_FORMAT", "seed")
    return seed


def _bucket(seed: str, group: str) -> int:
    return int(hashlib.sha256(("%s|%s" % (seed, group)).encode("utf-8")).hexdigest(), 16) % 10000


def _split_of(seed: str, group: str) -> str:
    b = _bucket(seed, group)
    return "train" if b < TRAIN_BUCKETS else "dev" if b < DEV_BUCKETS else "test"


def split_records(records: Any, seed: Any) -> dict:
    """Deterministic split by group: every record of a group lands in the same split. Refuses below the gate."""
    sd = _seed(seed)
    recs = _validated(records)
    if not fine_tune_ready(dict(_counts(recs))):
        _refuse("BELOW_GATE", "records")
    ids = {s: [] for s in SPLITS}
    counts = {s: dict.fromkeys(LABELS, 0) for s in SPLITS}
    for r in recs:
        s = _split_of(sd, r["group_id"])
        ids[s].append(r["record_id"])
        counts[s][r["label"]] += 1
    return {"algorithm": ALGORITHM, "seed": sd, "splits": {s: sorted(ids[s]) for s in SPLITS}, "counts": counts,
            "group_disjoint": True, "model_trained": False, "labels_generated": False}


def evaluate(records: Any, predictions: Any, seed: Any) -> dict:
    """Held-out metrics from supplied gold labels and supplied predictions for the test split only."""
    sd = _seed(seed)
    recs = _validated(records)
    counts = _counts(recs)
    if not fine_tune_ready(dict(counts)):
        _refuse("BELOW_GATE", "records")
    test = sorted((r for r in recs if _split_of(sd, r["group_id"]) == "test"), key=lambda r: r["record_id"])
    gold = {r["record_id"]: r["label"] for r in test}
    if type(predictions) is not dict:
        _refuse("BAD_TYPE", "predictions")
    if len(predictions) > MAX_RECORDS:
        _refuse("OVERSIZE", "predictions")
    for k, v in predictions.items():
        if type(k) is not str or type(v) is not str:
            _refuse("BAD_TYPE", "predictions")
        if len(k) > MAX_ID or len(v) > MAX_LABEL:
            _refuse("OVERSIZE", "predictions")
    for k, v in predictions.items():
        if v not in LABELS:
            _refuse("BAD_VALUE", "predictions")
    if any(k not in gold for k in predictions):
        _refuse("UNKNOWN", "predictions")
    if any(k not in predictions for k in gold):
        _refuse("MISSING", "predictions")
    support = _counts(test)
    if any(support[k] == 0 for k in LABELS):
        _refuse("EMPTY_CLASS", "test")
    matrix = {g: dict.fromkeys(LABELS, 0) for g in LABELS}
    for rid, g in gold.items():
        matrix[g][predictions[rid]] += 1
    n = len(test)
    per = {}
    f_sum = 0.0
    for c in LABELS:
        tp = matrix[c][c]
        pred_c = sum(matrix[g][c] for g in LABELS)
        p = tp / pred_c if pred_c else 0.0
        r = tp / support[c]
        f = 2 * p * r / (p + r) if p + r else 0.0
        f_sum += f
        per[c] = {"support": support[c], "precision": round(p, 6), "recall": round(r, 6), "f1": round(f, 6)}
    correct = sum(matrix[c][c] for c in LABELS)
    majority = max(support.values())
    return {"algorithm": ALGORITHM, "seed": sd, "test_records": n, "accuracy": round(correct / n, 6),
            "macro_f1": round(f_sum / len(LABELS), 6), "per_class": per,
            "confusion": matrix, "majority_baseline_accuracy": round(majority / n, 6),
            "model_trained": False, "labels_generated": False, "limits": list(LIMITS)}
