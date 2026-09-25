import pytest

from app.self_improve.detector import GapDetector
from app.self_improve.events import GapEvent, GapEventStore


def test_event_validation():
    with pytest.raises(ValueError):
        GapEvent(module_slug="m1", signature="x", kind="bogus")
    with pytest.raises(ValueError):
        GapEvent(module_slug="m1", signature="  ")


def test_store_roundtrip(tmp_path):
    store = GapEventStore(tmp_path)
    store.append(GapEvent(module_slug="m1", signature="sig-a", exemplar="sample"))
    store.append(GapEvent(module_slug="m1", signature="sig-a"))
    store.append(GapEvent(module_slug="m2", signature="sig-b"))
    assert len(store.all("m1")) == 2
    assert len(store.all("m2")) == 1
    assert store.all("m1")[0].exemplar == "sample"


def test_store_rejects_unsafe_slug(tmp_path):
    store = GapEventStore(tmp_path)
    with pytest.raises(ValueError):
        store.append(GapEvent(module_slug="../escape", signature="x"))


def test_detector_threshold(tmp_path):
    store = GapEventStore(tmp_path)
    detector = GapDetector(store, min_occurrences=2)
    store.append(GapEvent(module_slug="m1", signature="once-only"))
    assert detector.detect("m1") == []
    store.append(GapEvent(module_slug="m1", signature="once-only"))
    gaps = detector.detect("m1")
    assert len(gaps) == 1
    assert gaps[0].occurrences == 2
    assert 0 < gaps[0].severity <= 1


def test_detector_orders_by_severity(tmp_path):
    store = GapEventStore(tmp_path)
    for _ in range(6):
        store.append(GapEvent(module_slug="m1", signature="hot"))
    for _ in range(2):
        store.append(GapEvent(module_slug="m1", signature="cold"))
    gaps = GapDetector(store, min_occurrences=2).detect("m1")
    assert [g.signature for g in gaps] == ["hot", "cold"]
    assert gaps[0].severity >= gaps[1].severity
